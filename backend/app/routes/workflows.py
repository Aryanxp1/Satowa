"""FastAPI endpoints for SETOWA Workflows: CRUD, validation, execution, and audit history."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.workflows import (
    WorkflowDefinition,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
    WorkflowSummary,
    WorkflowValidationResult,
    get_default_workflow_engine,
    get_default_workflow_store,
)

router = APIRouter(prefix="/api/v1", tags=["Workflows"])


@router.get("/workflows", response_model=List[WorkflowSummary])
def list_workflows() -> List[WorkflowSummary]:
    """List summary records for all registered workflows."""
    store = get_default_workflow_store()
    return store.list()


@router.post("/workflows", response_model=WorkflowDefinition, status_code=status.HTTP_201_CREATED)
def create_workflow(workflow: WorkflowDefinition) -> WorkflowDefinition:
    """Create and persist a new workflow definition."""
    store = get_default_workflow_store()
    engine = get_default_workflow_engine()

    # Pre-validate before saving
    val_res = engine.validate(workflow)
    if not val_res.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Workflow definition is invalid", "errors": val_res.errors},
        )

    # Check for duplicate ID if ID is provided
    if store.get(workflow.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow with ID '{workflow.id}' already exists.",
        )

    return store.create(workflow)


@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinition)
def get_workflow(workflow_id: str) -> WorkflowDefinition:
    """Retrieve the full definition of a workflow by ID."""
    store = get_default_workflow_store()
    wf = store.get(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found.",
        )
    return wf


@router.put("/workflows/{workflow_id}", response_model=WorkflowDefinition)
def update_workflow(workflow_id: str, workflow: WorkflowDefinition) -> WorkflowDefinition:
    """Update an existing workflow definition."""
    store = get_default_workflow_store()
    engine = get_default_workflow_engine()

    existing = store.get(workflow_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found.",
        )

    workflow.id = workflow_id
    val_res = engine.validate(workflow)
    if not val_res.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Workflow definition is invalid", "errors": val_res.errors},
        )

    updated = store.update(workflow)
    return updated


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_200_OK)
def delete_workflow(workflow_id: str) -> Dict[str, Any]:
    """Delete a workflow definition and its execution records."""
    store = get_default_workflow_store()
    deleted = store.delete(workflow_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found.",
        )
    return {"message": f"Workflow '{workflow_id}' deleted successfully."}


@router.post("/workflows/{workflow_id}/validate", response_model=WorkflowValidationResult)
def validate_stored_workflow(workflow_id: str) -> WorkflowValidationResult:
    """Validate a stored workflow against current skill manifests and DAG rules."""
    store = get_default_workflow_store()
    engine = get_default_workflow_engine()

    wf = store.get(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found.",
        )
    return engine.validate(wf)


@router.post("/workflows/validate-draft", response_model=WorkflowValidationResult)
def validate_draft_workflow(workflow: WorkflowDefinition) -> WorkflowValidationResult:
    """Validate a draft workflow definition before saving (used by the Workflow Builder UI)."""
    engine = get_default_workflow_engine()
    return engine.validate(workflow)


@router.post("/workflows/{workflow_id}/execute", response_model=WorkflowExecutionResult)
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecutionRequest,
) -> WorkflowExecutionResult:
    """Execute a workflow DAG with provided inputs through the SETOWA SkillRuntime."""
    store = get_default_workflow_store()
    engine = get_default_workflow_engine()

    wf = store.get(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found.",
        )

    result = await engine.execute(wf, request)
    # Persist execution run
    store.save_execution(result)
    return result


@router.get("/workflows/{workflow_id}/executions", response_model=List[Dict[str, Any]])
def list_workflow_executions(
    workflow_id: str,
    limit: int = Query(default=50, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """List execution history records for a specific workflow."""
    store = get_default_workflow_store()
    return store.list_executions(workflow_id=workflow_id, limit=limit)


@router.get("/workflow-executions/{execution_id}", response_model=WorkflowExecutionResult)
def get_workflow_execution(execution_id: str) -> WorkflowExecutionResult:
    """Retrieve full audit record of a past workflow execution."""
    store = get_default_workflow_store()
    res = store.get_execution(execution_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow execution '{execution_id}' not found.",
        )
    return res
