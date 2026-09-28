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


class ReadinessResponse(BaseModel):
    """Readiness probe endpoint response."""
    status: str = Field("ready", description="Overall readiness status ('ready' or 'degraded')")
    application: str = Field("ready", description="Application service status")
    database: str = Field("ready", description="Database operational status")
    cloudinary: str = Field(..., description="Cloudinary configuration status ('configured' or 'missing')")
    gemini: str = Field(..., description="Gemini configuration status ('configured' or 'missing')")
    environment: str = Field(..., description="Deployment environment")
    mode: str = Field(..., description="Operating mode ('live' or 'mock/fallback')")


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
MediaType = Literal['image', 'video']
ProcessingStatus = Literal['ready', 'processing', 'failed']


class AssetResponse(BaseModel):
    """Uploaded or stored evidence asset metadata."""
    asset_id: str
    public_id: str
    version: int
    secure_url: str
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    source: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    format: str
    media_type: str = "image"
    processing_status: str = "ready"
    site_id: Optional[str] = None
    visit_id: Optional[str] = None
    original_filename: Optional[str] = None
    created_at: Optional[str] = None
    permission_status: str = Field(
        default="granted",
        description="Explicit evidence permission status: 'granted', 'pending_verification', 'revoked'"
    )


class MediaItemResponse(BaseModel):
    """Full media library asset item representation."""
    asset_id: str
    public_id: str
    version: int
    secure_url: str
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    source: str
    media_type: str = "image"
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    format: str
    permission_status: str = "granted"
    processing_status: str = "ready"
    site_id: Optional[str] = None
    project_id: Optional[str] = None
    captured_at: Optional[str] = None
    visit_id: Optional[str] = None
    original_filename: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProjectCreate(BaseModel):
    """Payload for creating a project."""
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=600)
    metadata: Optional[Dict[str, Any]] = None


class ProjectSummaryResponse(BaseModel):
    """Project record with aggregate media and site metrics."""
    project_id: str
    name: str
    description: str = ""
    created_at: str
    site_count: int = 0
    media_count: int = 0
    image_count: int = 0
    video_count: int = 0
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SiteSummaryResponse(BaseModel):
    """Site record with location metadata and aggregate media metrics."""
    site_id: str
    project_id: Optional[str] = None
    name: str
    location: str = ""
    description: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: Optional[str] = None
    media_count: int = 0
    image_count: int = 0
    video_count: int = 0
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PaginatedMediaQueryResponse(BaseModel):
    """Standard multi-dimensional media query response."""
    items: List[MediaItemResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    filters: Dict[str, Any]


class TimelineBucket(BaseModel):
    """A collection of media assets grouped by date."""
    date: str
    count: int
    items: List[MediaItemResponse]


class TimelineMediaResponse(BaseModel):
    """Media assets organized into date-based timeline buckets."""
    total_items: int
    total_dates: int
    filters: Dict[str, Any]
    buckets: List[TimelineBucket]


class BulkMediaItemResult(BaseModel):
    """Result of an individual file ingestion within a bulk batch."""
    filename: str
    status: Literal['success', 'failed']
    asset: Optional[MediaItemResponse] = None
    error: Optional[str] = None


class BulkMediaUploadResponse(BaseModel):
    """Aggregate response for bulk media collection ingestion."""
    total_files: int
    successful: int
    failed: int
    results: List[BulkMediaItemResult]



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


class IntelligenceStatus(str, Enum):
    """Lifecycle status of AI media intelligence analysis."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    UNCERTAIN = "uncertain"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class MediaIntelligenceRecord(BaseModel):
    """Structured AI intelligence record for an asset or frame."""
    id: str
    asset_id: str
    frame_id: Optional[str] = None
    status: str
    description: Optional[str] = None
    observations: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    signals: List[str] = Field(default_factory=list)
    activity: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    created_at: str
    updated_at: str


class MediaAnalysisRequest(BaseModel):
    """Request payload to analyze or re-analyze a media asset or frame."""
    frame_id: Optional[str] = None
    context: Optional[str] = None
    force_reanalyze: bool = False


class BatchMediaAnalysisRequest(BaseModel):
    """Bounded, safe batch analysis request (max 20 assets)."""
    asset_ids: List[str] = Field(..., min_length=1, max_length=20)
    context: Optional[str] = None


class BatchMediaAnalysisItemResult(BaseModel):
    """Per-asset outcome of batch analysis."""
    asset_id: str
    success: bool
    status: str
    error: Optional[str] = None
    intelligence: Optional[MediaIntelligenceRecord] = None


class BatchMediaAnalysisResponse(BaseModel):
    """Aggregated batch analysis execution summary."""
    total: int
    processed: int
    successful: int
    failed: int
    results: List[BatchMediaAnalysisItemResult]


class TimelineEventType(str, Enum):
    """Categorization of events in a project impact timeline."""
    BEFORE = "before"
    ACTIVITY = "activity"
    AFTER = "after"
    VERIFIED_FINDING = "verified_finding"
    MEASUREMENT = "measurement"
    MILESTONE = "milestone"


class VerificationStatus(str, Enum):
    """Human verification status for impact findings and events."""
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNVERIFIED = "unverified"
    UNCERTAIN = "uncertain"


class TimelineEvent(BaseModel):
    """An event on the sustainability and impact timeline."""
    id: str
    story_id: str
    event_order: int = 0
    timestamp_date: str
    event_type: str
    title: str
    description: Optional[str] = None
    site_id: Optional[str] = None
    site_name: Optional[str] = None
    asset_ids: List[str] = Field(default_factory=list)
    primary_media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_type: Optional[str] = None
    frame_id: Optional[str] = None
    observation_id: Optional[str] = None
    measurement_id: Optional[str] = None
    intelligence_id: Optional[str] = None
    verification_status: str = "unverified"
    tags: List[str] = Field(default_factory=list)
    signals: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    created_at: str


class BeforeAfterCard(BaseModel):
    """Grounded before/after comparison evidence card."""
    observation_id: str
    site_id: str
    site_name: Optional[str] = None
    before_asset_id: str
    before_media_url: str
    before_date: Optional[str] = None
    after_asset_id: str
    after_media_url: str
    after_date: Optional[str] = None
    comparison_summary: Optional[str] = None
    verification_status: str = "pending"
    approved_text: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    uncertainty: Optional[str] = None
    reliability_reason: Optional[str] = None
    detected_changes: List[str] = Field(default_factory=list)


class ImpactStoryResponse(BaseModel):
    """Complete sustainability impact story representation."""
    id: str
    project_id: str
    project_name: str
    title: str
    description: Optional[str] = None
    status: str
    summary_narrative: Optional[str] = None
    uncertainty_note: Optional[str] = None
    share_token: Optional[str] = None
    share_url: Optional[str] = None
    date_range: Dict[str, Optional[str]] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    events: List[TimelineEvent] = Field(default_factory=list)
    before_after_cards: List[BeforeAfterCard] = Field(default_factory=list)
    created_at: str
    updated_at: str


class GenerateImpactStoryRequest(BaseModel):
    """Parameters for generating or re-generating an impact story."""
    title: Optional[str] = None
    description: Optional[str] = None
    force_regenerate: bool = False
    include_ai_summary: bool = True


class UpdateImpactStoryRequest(BaseModel):
    """Editable fields for an existing impact story."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    summary_narrative: Optional[str] = None
    share_token: Optional[str] = None


class ShareStoryResponse(BaseModel):
    """Public share token information for an impact story."""
    story_id: str
    project_id: str
    status: str
    share_token: Optional[str] = None
    share_url: Optional[str] = None
    is_public: bool = False


class PublicTimelineEvent(BaseModel):
    """Public read-only projection of a timeline event."""
    event_type: str
    timestamp_date: str
    title: str
    description: Optional[str] = None
    site_name: Optional[str] = None
    primary_media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    media_type: Optional[str] = None
    verification_status: str = "unverified"
    observations: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None
    source_attribution: Optional[str] = None
    source_provenance: Optional[str] = None


class PublicBeforeAfterCard(BaseModel):
    """Public read-only projection of a before/after comparative evidence card."""
    site_name: Optional[str] = None
    before_media_url: str
    before_date: Optional[str] = None
    after_media_url: str
    after_date: Optional[str] = None
    verification_status: str = "pending"
    approved_text: Optional[str] = None
    verified_text: Optional[str] = None
    proposal_text: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_role: Optional[str] = None
    uncertainty: Optional[str] = None
    detected_changes: List[str] = Field(default_factory=list)


class PublicImpactStory(BaseModel):
    """Public-safe, read-only projection of a published impact story."""
    public_token: str
    public_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    summary_narrative: Optional[str] = None
    uncertainty_note: Optional[str] = None
    project_name: str
    project_description: Optional[str] = None
    date_range: Dict[str, Optional[str]] = Field(default_factory=dict)
    hero_media_url: Optional[str] = None
    hero_thumbnail_url: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    verified_findings_count: int = 0
    timeline: List[PublicTimelineEvent] = Field(default_factory=list)
    before_after: List[PublicBeforeAfterCard] = Field(default_factory=list)
    published_at: str
    share_url: str
    social_meta: Dict[str, str] = Field(default_factory=dict)



