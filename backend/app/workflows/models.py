"""Pydantic models for SETOWA Workflows, DAG nodes, edges, and execution contracts."""
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class WorkflowExecutionStatus(str, Enum):
    """Lifecycle status for a full workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeExecutionStatus(str, Enum):
    """Lifecycle status for a single node execution within a workflow."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


class WorkflowInputDefinition(BaseModel):
    """Declaration of a workflow-level input parameter."""
    name: str = Field(..., description="Unique parameter name, e.g. 'before_asset_id'")
    type: str = Field(..., description="Type of input: string, integer, float, boolean, object, array, image, video, asset_id")
    description: str = Field(default="", description="Human-readable description")
    required: bool = Field(default=True, description="Whether this input is mandatory")
    default: Optional[Any] = Field(default=None, description="Default value if not provided")


class WorkflowNode(BaseModel):
    """A single skill execution step in a workflow DAG."""
    id: str = Field(..., description="Unique node identifier within the workflow, e.g. 'before_meta'")
    skill: str = Field(..., description="Referenced SETOWA skill name, e.g. 'media-metadata'")
    skill_version: str = Field(default="1.0.0", description="Target skill semver, e.g. '1.0.0'")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input mapping: literal or expression ($input.x, $node.n.y)")
    position: Optional[Dict[str, float]] = Field(default=None, description="Visual canvas coordinates {'x': float, 'y': float}")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary node metadata or labels")


class WorkflowEdge(BaseModel):
    """A directed dependency connecting a source node output to a target node input."""
    source_node: str = Field(..., description="Source node ID")
    source_output: str = Field(..., description="Output property name on source node")
    target_node: str = Field(..., description="Target node ID")
    target_input: str = Field(..., description="Input property name on target node")


class WorkflowDefinition(BaseModel):
    """Declarative definition of an executable SETOWA workflow."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12], description="Unique workflow identifier")
    name: str = Field(..., description="Workflow name, e.g. 'before-after-evidence-comparison'")
    version: str = Field(default="1.0.0", description="Workflow semver")
    description: str = Field(default="", description="Workflow purpose and behavior")
    inputs: List[WorkflowInputDefinition] = Field(default_factory=list, description="Workflow-level input parameters")
    nodes: List[WorkflowNode] = Field(default_factory=list, description="Workflow nodes (skill steps)")
    edges: List[WorkflowEdge] = Field(default_factory=list, description="Explicit DAG edges connecting node outputs to inputs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Workflow tags, author, and UI layout metadata")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of creation")
    updated_at: Optional[str] = Field(default=None, description="ISO timestamp of last modification")


class WorkflowSummary(BaseModel):
    """Compact summary of a workflow for listing and overview UI."""
    id: str
    name: str
    version: str
    description: str = ""
    node_count: int = 0
    edge_count: int = 0
    updated_at: Optional[str] = None


class WorkflowValidationResult(BaseModel):
    """Result of validating a workflow's schema, skills, connections, and DAG topology."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    execution_order: List[str] = Field(default_factory=list)


class NodeExecutionResult(BaseModel):
    """Detailed record of a single node's execution in a workflow."""
    node_id: str
    skill: str
    skill_version: str
    status: NodeExecutionStatus
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    evidence: Optional[Any] = Field(default=None)
    latency_ms: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class WorkflowExecutionRequest(BaseModel):
    """Payload to trigger execution of a workflow."""
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Values for declared workflow inputs")
    execution_context: Dict[str, Any] = Field(default_factory=dict, description="Optional permissions, user tokens, etc.")


class WorkflowExecutionResult(BaseModel):
    """Comprehensive, unforgeable audit report of a workflow run."""
    execution_id: str = Field(default_factory=lambda: uuid4().hex)
    workflow_id: str
    workflow_version: str
    status: WorkflowExecutionStatus
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    node_results: Dict[str, NodeExecutionResult] = Field(default_factory=dict)
    execution_order: List[str] = Field(default_factory=list)
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
