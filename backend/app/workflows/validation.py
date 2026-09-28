"""Validation logic for SETOWA workflows, schemas, DAG topology, and skill compatibility."""
from typing import Dict, List, Set, Tuple
from app.skills.registry import SkillRegistry
from app.workflows.dag import CycleError, DAGGraph
from app.workflows.models import (
    WorkflowDefinition,
    WorkflowValidationResult,
)


def validate_workflow(
    workflow: WorkflowDefinition,
    registry: SkillRegistry,
) -> WorkflowValidationResult:
    """Perform comprehensive structural, referential, and topological validation on a workflow."""
    errors: List[str] = []
    warnings: List[str] = []
    execution_order: List[str] = []

    # 1. Basic definition checks
    if not workflow.name or not workflow.name.strip():
        errors.append("Workflow 'name' is required.")

    if not workflow.nodes:
        errors.append("Workflow must contain at least one node.")
        return WorkflowValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # 2. Unique Node IDs
    node_ids: Set[str] = set()
    node_map: Dict[str, any] = {}
    for node in workflow.nodes:
        if not node.id or not node.id.strip():
            errors.append("All nodes must have a non-empty 'id'.")
            continue
        if node.id in node_ids:
            errors.append(f"Duplicate node ID detected: '{node.id}'. Node IDs must be unique.")
        node_ids.add(node.id)
        node_map[node.id] = node

    # 3. Workflow Input Declarations
    wf_input_names: Set[str] = set()
    for inp in workflow.inputs:
        if not inp.name or not inp.name.strip():
            errors.append("Workflow inputs must have a valid non-empty 'name'.")
            continue
        if inp.name in wf_input_names:
            errors.append(f"Duplicate workflow input name: '{inp.name}'.")
        wf_input_names.add(inp.name)

    # 4. Skill Existence and Version Resolution
    node_skills: Dict[str, any] = {}  # node_id -> BaseSkill instance
    for node in workflow.nodes:
        skill = registry.get(node.skill, node.skill_version)
        if not skill:
            errors.append(
                f"Node '{node.id}' references unregistered or unavailable skill '{node.skill}@{node.skill_version}'."
            )
            continue
        node_skills[node.id] = skill

    # 5. Edge Source and Target Node Existence
    for edge in workflow.edges:
        if edge.source_node not in node_map:
            errors.append(f"Edge references nonexistent source_node: '{edge.source_node}'.")
            continue
        if edge.target_node not in node_map:
            errors.append(f"Edge references nonexistent target_node: '{edge.target_node}'.")
            continue
        if edge.source_node == edge.target_node:
            errors.append(f"Self-loop detected on edge: node '{edge.source_node}' cannot connect to itself.")

    # 6. Edge Port / Schema Validation (if skills exist)
    for edge in workflow.edges:
        source_skill = node_skills.get(edge.source_node)
        target_skill = node_skills.get(edge.target_node)
        if source_skill:
            valid_outputs = {out.name for out in source_skill.manifest.outputs}
            if edge.source_output not in valid_outputs:
                errors.append(
                    f"Edge source output '{edge.source_output}' does not exist on skill "
                    f"'{source_skill.full_id}' of node '{edge.source_node}'. Valid outputs: {sorted(list(valid_outputs))}"
                )
        if target_skill:
            valid_inputs = {inp.name for inp in target_skill.manifest.inputs}
            if edge.target_input not in valid_inputs:
                errors.append(
                    f"Edge target input '{edge.target_input}' does not exist on skill "
                    f"'{target_skill.full_id}' of node '{edge.target_node}'. Valid inputs: {sorted(list(valid_inputs))}"
                )

    # 7. Input Expression Validation ($input.<var>, $node.<node_id>.<output>)
    for node in workflow.nodes:
        skill = node_skills.get(node.id)
        valid_node_inputs = {inp.name for inp in skill.manifest.inputs} if skill else set()

        for input_key, val in node.inputs.items():
            if skill and input_key not in valid_node_inputs:
                warnings.append(
                    f"Node '{node.id}' defines input '{input_key}' which is not in skill manifest '{skill.full_id}'."
                )

            if isinstance(val, str):
                if val.startswith("$input."):
                    wf_var = val[7:]
                    if wf_var not in wf_input_names:
                        errors.append(
                            f"Node '{node.id}' references undeclared workflow input '{wf_var}' (via '{val}')."
                        )
                elif val.startswith("$node."):
                    parts = val[6:].split(".")
                    if len(parts) < 2:
                        errors.append(
                            f"Node '{node.id}' has malformed node reference '{val}'. Format must be '$node.<node_id>.<output>'."
                        )
                    else:
                        src_id, out_name = parts[0], parts[1]
                        if src_id not in node_map:
                            errors.append(
                                f"Node '{node.id}' references nonexistent upstream node '{src_id}' in '{val}'."
                            )
                        elif src_id == node.id:
                            errors.append(f"Node '{node.id}' cannot reference its own output in '{val}'.")
                        else:
                            src_skill = node_skills.get(src_id)
                            if src_skill:
                                valid_src_outputs = {out.name for out in src_skill.manifest.outputs}
                                if out_name not in valid_src_outputs:
                                    errors.append(
                                        f"Node '{node.id}' references output '{out_name}' on upstream node '{src_id}', "
                                        f"which is not declared in '{src_skill.full_id}' outputs."
                                    )

    # 8. Required Skill Inputs Satisfiability Check
    # Build map of incoming inputs for each node:
    # A node input is satisfied if:
    #   - Provided in node.inputs (literal, $input, or $node)
    #   - Provided via an incoming WorkflowEdge target_input
    #   - Defined with a default in the skill manifest
    incoming_edges_map: Dict[str, Set[str]] = {node.id: set() for node in workflow.nodes}
    for edge in workflow.edges:
        if edge.target_node in incoming_edges_map:
            incoming_edges_map[edge.target_node].add(edge.target_input)

    for node in workflow.nodes:
        skill = node_skills.get(node.id)
        if not skill:
            continue
        provided_inputs = set(node.inputs.keys()) | incoming_edges_map[node.id]
        for skill_inp in skill.manifest.inputs:
            if skill_inp.required and skill_inp.default is None:
                if skill_inp.name not in provided_inputs:
                    errors.append(
                        f"Node '{node.id}' ({skill.full_id}) is missing required input '{skill_inp.name}'."
                    )

    # 9. Topological DAG Validation (Self-loops & Cycles)
    try:
        dag = DAGGraph.from_workflow(workflow)
        has_loop, loop_node = dag.has_self_loop()
        if has_loop:
            errors.append(f"Self-loop detected: node '{loop_node}' depends on itself.")
        else:
            execution_order = dag.topological_sort()
    except CycleError as ce:
        errors.append(str(ce))
    except Exception as exc:
        errors.append(f"DAG graph validation failed: {str(exc)}")

    is_valid = len(errors) == 0
    return WorkflowValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        execution_order=execution_order,
    )
