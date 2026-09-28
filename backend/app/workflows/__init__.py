"""SETOWA Workflow Engine package exporting models, DAG, validation, engine, and store."""
from app.skills import get_default_registry, get_default_runtime
from app.workflows.dag import CycleError, DAGGraph
from app.workflows.engine import WorkflowEngine
from app.workflows.models import (
    NodeExecutionResult,
    NodeExecutionStatus,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
    WorkflowExecutionStatus,
    WorkflowInputDefinition,
    WorkflowNode,
    WorkflowSummary,
    WorkflowValidationResult,
)
from app.workflows.store import WorkflowStore
from app.workflows.validation import validate_workflow

_default_store: WorkflowStore = None
_default_engine: WorkflowEngine = None


def get_default_workflow_store() -> WorkflowStore:
    """Return the global singleton WorkflowStore instance."""
    global _default_store
    if _default_store is None:
        _default_store = WorkflowStore()
    return _default_store


def get_default_workflow_engine() -> WorkflowEngine:
    """Return the global singleton WorkflowEngine instance connected to SkillRuntime."""
    global _default_engine
    if _default_engine is None:
        runtime = get_default_runtime()
        registry = get_default_registry()
        _default_engine = WorkflowEngine(runtime=runtime, registry=registry)
    return _default_engine


__all__ = [
    "WorkflowDefinition",
    "WorkflowNode",
    "WorkflowEdge",
    "WorkflowInputDefinition",
    "WorkflowSummary",
    "WorkflowValidationResult",
    "WorkflowExecutionRequest",
    "WorkflowExecutionResult",
    "WorkflowExecutionStatus",
    "NodeExecutionStatus",
    "NodeExecutionResult",
    "DAGGraph",
    "CycleError",
    "WorkflowEngine",
    "WorkflowStore",
    "validate_workflow",
    "get_default_workflow_store",
    "get_default_workflow_engine",
]
