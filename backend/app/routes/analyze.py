"""Analysis and reasoning endpoints."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from app.schemas.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    ShowcaseStatsResponse,
    MetricStat,
)
from app.services.ai_engine import ai_service

router = APIRouter(prefix="/api/v1", tags=["Analysis & Intelligence"])


@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_200_OK)
async def analyze_input(payload: AnalyzeRequest):
    """
    Execute AI reasoning or algorithmic analysis on user input.
    Operates seamlessly in either live API or simulated mock mode.
    """
    if not payload.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Prompt text must not be empty.",
        )

    return await ai_service.execute_reasoning(payload)


@router.get("/mock-stats", response_model=ShowcaseStatsResponse)
async def get_mock_stats():
    """
    Returns live showcase metrics matching the hackathon landing page.
    Allows frontend to dynamically query and bind showcase widgets.
    """
    return ShowcaseStatsResponse(
        metrics=[
            MetricStat(
                label="Response Latency",
                value="~120ms",
                trend="Optimized",
                status="positive"
            ),
            MetricStat(
                label="AI Accuracy",
                value="99.4%",
                trend="High-Confidence",
                status="positive"
            ),
            MetricStat(
                label="Automation Gain",
                value="10x",
                trend="Time Saved",
                status="positive"
            ),
        ],
        timestamp=datetime.now(timezone.utc).isoformat()
    )
