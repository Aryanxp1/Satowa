"""API schemas for request and response validation."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


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
