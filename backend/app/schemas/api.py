"""API schemas for request and response validation."""
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any, List, Literal


class HealthResponse(BaseModel):
    """Health check endpoint response."""
    status: str = Field("healthy", description="Current system operational status")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Deployment environment")
    mock_mode: bool = Field(..., description="Whether fallback mock mode is active")


class MetricStat(BaseModel):
    """Showcase metric statistics."""
    label: str
    value: str
    trend: str
    status: str


class ShowcaseStatsResponse(BaseModel):
    """Aggregate statistics for frontend dashboard and showcase."""
    metrics: List[MetricStat]
    timestamp: str


class AnalyzeRequest(BaseModel):
    """Analysis or reasoning request payload."""
    prompt: str = Field(..., description="The user or system prompt to evaluate")
    task_type: Optional[str] = Field("general", description="Task category: summarization, reasoning, extraction")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom hyperparameters or context flags")


class AnalyzeResponse(BaseModel):
    """AI engine analysis response."""
    status: str = Field("success", description="Status of the analysis")
    task_type: str
    source: str = Field(..., description="Source engine: 'mock-engine' or 'gemini-api'")
    result: str = Field(..., description="Output text or structured response")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    latency_ms: float = Field(..., description="Processing time in milliseconds")


PermissionStatus = Literal['granted', 'pending_verification', 'revoked']


class AssetResponse(BaseModel):
    """Uploaded or stored evidence asset metadata."""
    asset_id: str
    public_id: str
    version: int
    secure_url: str
    thumbnail_url: Optional[str] = None
    source: str
    width: int
    height: int
    format: str
    permission_status: str = Field(
        default="granted",
        description="Explicit evidence permission status: 'granted', 'pending_verification', 'revoked'"
    )


class ComparisonStatus(str, Enum):
    """4-state status for structured visual comparison."""
    CHANGED = 'changed'
    UNCHANGED = 'unchanged'
    UNCERTAIN = 'uncertain'
    INSUFFICIENT_EVIDENCE = 'insufficient_evidence'


class UncertaintyReason(str, Enum):
    """Controlled vocabulary for comparison uncertainty reasons."""
    CAMERA_ANGLE_MISMATCH = 'camera_angle_mismatch'
    LIGHTING_DIFFERENCE = 'lighting_difference'
    PARTIAL_OCCLUSION = 'partial_occlusion'
    INSUFFICIENT_VISUAL_OVERLAP = 'insufficient_visual_overlap'
    POOR_IMAGE_QUALITY = 'poor_image_quality'
    RELEVANT_AREA_NOT_VISIBLE = 'relevant_area_not_visible'
    INCOMPATIBLE_FRAMING = 'incompatible_framing'
    EVIDENCE_UNAVAILABLE = 'evidence_unavailable'
    PROVIDER_ERROR = 'provider_error'
    UNVERIFIED_QUANTITATIVE_CLAIM = 'unverified_quantitative_claim'
    OTHER = 'other'


class VisualChange(BaseModel):
    """Specific visible difference identified by visual comparison."""
    type: str = Field(default="visible_change", min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=600)
    evidence: Optional[str] = Field(default=None, max_length=600)


class StructuredComparison(BaseModel):
    """Structured AI comparison proposal result."""
    status: ComparisonStatus = Field(
        default=ComparisonStatus.UNCERTAIN,
        description="4-state comparison result enum: 'changed', 'unchanged', 'uncertain', 'insufficient_evidence'"
    )
    summary: Optional[str] = Field(
        default=None,
        max_length=600,
        description="Concise description of visible differences only"
    )
    changes: List[VisualChange] = Field(
        default_factory=list,
        description="Discrete visible changes visually supported by evidence"
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model confidence score between 0.0 and 1.0 (NOT accuracy)"
    )
    uncertainty_reason: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Machine/human-readable reason when uncertain or insufficient evidence"
    )
    evidence_notes: Optional[str] = Field(
        default=None,
        max_length=600,
        description="Additional technical notes on framing, overlap, or image quality"
    )
    reliable: bool = Field(
        default=False,
        description="Backward-compatible boolean indicating if observation is supported for drafting"
    )
    observation: Optional[str] = Field(
        default=None,
        max_length=600,
        description="Backward-compatible observation text draft"
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Backward-compatible unreliability reason explanation"
    )

    @model_validator(mode='before')
    @classmethod
    def _coerce_compatibility(cls, data: Any) -> Any:
        if isinstance(data, dict):
            status_val = data.get('status')
            if status_val is not None:
                if status_val in (ComparisonStatus.CHANGED, ComparisonStatus.CHANGED.value):
                    data.setdefault('reliable', True)
                    data.setdefault('observation', data.get('summary'))
                elif status_val in (ComparisonStatus.UNCHANGED, ComparisonStatus.UNCHANGED.value):
                    data.setdefault('reliable', True)
                    data.setdefault('observation', data.get('summary') or 'No meaningful visible change detected.')
                elif status_val in (
                    ComparisonStatus.UNCERTAIN, ComparisonStatus.UNCERTAIN.value,
                    ComparisonStatus.INSUFFICIENT_EVIDENCE, ComparisonStatus.INSUFFICIENT_EVIDENCE.value,
                ):
                    data.setdefault('reliable', False)
                    data.setdefault('observation', None)
                    data.setdefault('reason', data.get('uncertainty_reason') or data.get('evidence_notes'))
            elif 'reliable' in data:
                if data['reliable']:
                    data['status'] = ComparisonStatus.CHANGED.value
                    data['summary'] = data.get('observation')
                    data.setdefault('confidence', 0.8)
                else:
                    data['status'] = ComparisonStatus.UNCERTAIN.value
                    data['uncertainty_reason'] = data.get('reason')
                    data.setdefault('confidence', 0.0)
        return data

