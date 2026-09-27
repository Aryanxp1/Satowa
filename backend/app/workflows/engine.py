"""Workflow execution engine executing declarative DAGs through the SETOWA SkillRuntime."""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from app.skills.models import (
    SkillExecutionRequest,
    SkillExecutionStatus,
)
from app.skills.registry import SkillRegistry
from app.skills.runtime import SkillRuntime
from app.workflows.dag import DAGGraph
from app.workflows.models import (
    NodeExecutionResult,
    NodeExecutionStatus,
    WorkflowDefinition,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
    WorkflowExecutionStatus,
    WorkflowValidationResult,
)
from app.workflows.validation import validate_workflow

logger = logging.getLogger("setowa.workflows.engine")


class WorkflowEngine:
    """Orchestrates validation, state propagation, and topological execution of SETOWA workflows."""

    def __init__(self, runtime: SkillRuntime, registry: SkillRegistry):
        self.runtime = runtime
        self.registry = registry

    def validate(self, workflow: WorkflowDefinition) -> WorkflowValidationResult:
        """Validate a workflow definition for structural, referential, and DAG integrity."""
        return validate_workflow(workflow, self.registry)

    async def execute(
        self,
        workflow: WorkflowDefinition,
        request: WorkflowExecutionRequest,
    ) -> WorkflowExecutionResult:
        """Execute a workflow DAG with topological ordering, state propagation, and failure safety."""
        execution_id = uuid4().hex
        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.perf_counter()

        # 1. Pre-execution DAG & schema validation
        val_result = self.validate(workflow)
        if not val_result.is_valid:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            completed_at = datetime.now(timezone.utc).isoformat()
            return WorkflowExecutionResult(
                execution_id=execution_id,
                workflow_id=workflow.id,
                workflow_version=workflow.version,
                status=WorkflowExecutionStatus.FAILED,
                inputs=request.inputs,
                outputs={},
                node_results={},
                execution_order=[],
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                errors=[f"Workflow validation failed: {err}" for err in val_result.errors],
                warnings=val_result.warnings,
            )

        # 2. Check required workflow inputs
        missing_wf_inputs = []
        for inp_def in workflow.inputs:
            if inp_def.required and inp_def.default is None:
                if inp_def.name not in request.inputs or request.inputs[inp_def.name] is None:
                    missing_wf_inputs.append(inp_def.name)

        if missing_wf_inputs:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            completed_at = datetime.now(timezone.utc).isoformat()
            err_msg = f"Missing required workflow inputs: {missing_wf_inputs}"
            return WorkflowExecutionResult(
                execution_id=execution_id,
                workflow_id=workflow.id,
                workflow_version=workflow.version,
                status=WorkflowExecutionStatus.FAILED,
                inputs=request.inputs,
                outputs={},
                node_results={},
                execution_order=val_result.execution_order,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                errors=[err_msg],
                warnings=val_result.warnings,
            )

        # 3. Construct DAG and topological order
        dag = DAGGraph.from_workflow(workflow)
        execution_order = dag.topological_sort()
        node_map = {n.id: n for n in workflow.nodes}

        # Execution tracking state
        node_results: Dict[str, NodeExecutionResult] = {}
        execution_state: Dict[str, Dict[str, Any]] = {}  # node_id -> outputs dict
        failed_or_skipped_nodes: Set[str] = set()
        workflow_errors: List[str] = []
        workflow_warnings: List[str] = list(val_result.warnings)

        # 4. Execute nodes in topological order
        for node_id in execution_order:
            node = node_map[node_id]
            node_start = time.perf_counter()
            node_started_at = datetime.now(timezone.utc).isoformat()

            # Check if any upstream dependencies failed or were skipped
            upstream_deps = dag.get_upstream_dependencies(node_id)
            blocking_deps = upstream_deps.intersection(failed_or_skipped_nodes)

            if blocking_deps:
                node_latency = round((time.perf_counter() - node_start) * 1000, 2)
                node_completed_at = datetime.now(timezone.utc).isoformat()
                skip_msg = f"Skipped node '{node_id}' because upstream dependencies did not succeed: {sorted(list(blocking_deps))}."
                logger.info(skip_msg)
                node_results[node_id] = NodeExecutionResult(
                    node_id=node_id,
                    skill=node.skill,
                    skill_version=node.skill_version,
                    status=NodeExecutionStatus.SKIPPED,
                    inputs={},
                    outputs={},
                    errors=[skip_msg],
                    warnings=[],
                    evidence=[],
                    latency_ms=node_latency,
                    started_at=node_started_at,
                    completed_at=node_completed_at,
                )
                failed_or_skipped_nodes.add(node_id)
                continue

            # Resolve node inputs
            resolved_inputs: Dict[str, Any] = {}

            # Step A: From node.inputs declarations ($input.x, $node.n.y, or literals)
            for key, val in node.inputs.items():
                if isinstance(val, str) and val.startswith("$input."):
                    var_name = val[7:]
                    default_val = next((i.default for i in workflow.inputs if i.name == var_name), None)
                    resolved_inputs[key] = request.inputs.get(var_name, default_val)
                elif isinstance(val, str) and val.startswith("$node."):
                    parts = val[6:].split(".")
                    src_id, out_name = parts[0], parts[1]
                    src_outputs = execution_state.get(src_id, {})
                    resolved_inputs[key] = src_outputs.get(out_name)
                else:
                    resolved_inputs[key] = val

            # Step B: From explicit incoming WorkflowEdges
            for edge in workflow.edges:
                if edge.target_node == node_id:
                    src_outputs = execution_state.get(edge.source_node, {})
                    resolved_inputs[edge.target_input] = src_outputs.get(edge.source_output)

            # Step C: Fallback to skill manifest defaults if an input was not mapped
            skill_inst = self.registry.get(node.skill, node.skill_version)
            if skill_inst:
                for inp_def in skill_inst.manifest.inputs:
                    if inp_def.name not in resolved_inputs and inp_def.default is not None:
                        resolved_inputs[inp_def.name] = inp_def.default

            # Invoke skill via single source of truth: SkillRuntime
            skill_request = SkillExecutionRequest(
                skill_name=node.skill,
                skill_version=node.skill_version,
                inputs=resolved_inputs,
                execution_context=request.execution_context,
            )

            skill_result = await self.runtime.execute(skill_request)
            node_latency = round((time.perf_counter() - node_start) * 1000, 2)
            node_completed_at = datetime.now(timezone.utc).isoformat()

            # Map SkillExecutionStatus to NodeExecutionStatus
            if skill_result.status == SkillExecutionStatus.SUCCESS:
                node_status = NodeExecutionStatus.SUCCESS
                execution_state[node_id] = skill_result.outputs
            elif skill_result.status == SkillExecutionStatus.UNAVAILABLE:
                node_status = NodeExecutionStatus.UNAVAILABLE
                failed_or_skipped_nodes.add(node_id)
                workflow_errors.extend(skill_result.errors)
            else:
                node_status = NodeExecutionStatus.FAILED
                failed_or_skipped_nodes.add(node_id)
                workflow_errors.extend(skill_result.errors)

            workflow_warnings.extend(skill_result.warnings)

            node_results[node_id] = NodeExecutionResult(
                node_id=node_id,
                skill=node.skill,
                skill_version=skill_result.skill_version,
                status=node_status,
                inputs=resolved_inputs,
                outputs=skill_result.outputs,
                errors=skill_result.errors,
                warnings=skill_result.warnings,
                evidence=skill_result.evidence,
                latency_ms=node_latency,
                started_at=node_started_at,
                completed_at=node_completed_at,
            )

        # 5. Evaluate final workflow status and assemble outputs
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        completed_at = datetime.now(timezone.utc).isoformat()

        if failed_or_skipped_nodes:
            wf_status = WorkflowExecutionStatus.FAILED
            if not workflow_errors:
                workflow_errors.append("One or more nodes failed or were skipped during execution.")
        else:
            wf_status = WorkflowExecutionStatus.SUCCESS

        # Collect structured workflow outputs
        wf_outputs: Dict[str, Any] = {
            node_id: res.outputs
            for node_id, res in node_results.items()
            if res.status == NodeExecutionStatus.SUCCESS
        }

        # If there are leaf nodes (nodes with out-degree == 0 in DAG), copy their outputs into top-level namespace
        leaf_nodes = [n for n in execution_order if len(dag.adjacency[n]) == 0]
        for leaf in leaf_nodes:
            if leaf in execution_state:
                wf_outputs[f"{leaf}_output"] = execution_state[leaf]

        return WorkflowExecutionResult(
            execution_id=execution_id,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            status=wf_status,
            inputs=request.inputs,
            outputs=wf_outputs,
            node_results=node_results,
            execution_order=execution_order,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            errors=workflow_errors,
            warnings=workflow_warnings,
            metadata={"total_nodes": len(workflow.nodes), "successful_nodes": len(execution_state)},
        )
