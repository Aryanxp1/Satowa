"""AI Media Intelligence Service for Setowa (T016).

Coordinates per-media structured visual analysis, grounding, uncertainty handling,
persistence, re-analysis provenance, and batch processing.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException
from app.config import settings

from app.schemas.api import (
    BatchMediaAnalysisItemResult,
    BatchMediaAnalysisResponse,
    IntelligenceStatus,
    MediaIntelligenceRecord,
)
from app.services import evidence_store as store
from app.skills import (
    SkillExecutionRequest,
    SkillExecutionStatus,
    get_default_runtime,
)
from app.skills.builtins.media_intelligence import (
    CONTROLLED_SIGNALS,
    CONTROLLED_TAGS,
    normalize_signals,
    normalize_tag,
    normalize_tags,
)

logger = logging.getLogger(__name__)


def safe_json_loads(val: Optional[str], default: Any = None) -> Any:
    """Safely parse JSON string with fallback."""
    if not val:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


def row_to_intelligence_record(row: dict) -> MediaIntelligenceRecord:
    """Convert a database row dictionary to a validated MediaIntelligenceRecord."""
    observations = safe_json_loads(row.get("observations"), [])
    if isinstance(observations, str):
        observations = [observations]

    tags = safe_json_loads(row.get("tags_json"), [])
    if isinstance(tags, str):
        tags = [tags]

    signals = safe_json_loads(row.get("signals_json"), [])
    if isinstance(signals, str):
        signals = [signals]

    warnings = safe_json_loads(row.get("warnings_json"), [])
    if isinstance(warnings, str):
        warnings = [warnings]

    evidence = safe_json_loads(row.get("evidence_json"), {})

    return MediaIntelligenceRecord(
        id=row["id"],
        asset_id=row["asset_id"],
        frame_id=row.get("frame_id"),
        status=row.get("status") or "pending",
        description=row.get("description"),
        observations=observations or [],
        tags=tags or [],
        signals=signals or [],
        activity=row.get("activity"),
        warnings=warnings or [],
        uncertainty=row.get("uncertainty"),
        evidence=evidence or {},
        model_provider=row.get("model_provider"),
        model_name=row.get("model_name"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def analyze_asset(
    db,
    asset_id: str,
    frame_id: Optional[str] = None,
    context: Optional[str] = None,
    force_reanalyze: bool = False,
) -> MediaIntelligenceRecord:
    """Analyze a media asset or frame using the SETOWA SkillRuntime.
    
    Guarantees:
    - Verifies asset and frame existence before execution.
    - Idempotent: returns existing analysis if already analyzed, unless force_reanalyze is True.
    - Re-analysis preserves full historical provenance without overwriting past runs.
    - Honest status handling: maps provider failures and uncertainty correctly.
    """
    asset = store.get_media_item(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Media asset '{asset_id}' not found.")

    if asset.get("permission_status") != "granted":
        raise HTTPException(403, "Media permission is not granted")

    target_url = asset["secure_url"]

    if frame_id:
        frame = store.get_video_frame(db, frame_id)
        if not frame:
            raise HTTPException(status_code=404, detail=f"Video frame '{frame_id}' not found.")
        if frame["asset_id"] != asset_id:
            raise HTTPException(
                status_code=404,
                detail=f"Frame '{frame_id}' does not belong to asset '{asset_id}'."
            )
        target_url = frame["frame_url"]

    # Check for existing intelligence if not forcing re-analysis
    if not force_reanalyze:
        existing = store.get_media_intelligence(db, asset_id, frame_id)
        cache_matches = existing and (settings.AI_PROVIDER != "nvidia" or (
            existing.get("model_provider") == "nvidia" and
            existing.get("model_name") == settings.NVIDIA_VISION_MODEL and
            safe_json_loads(existing.get("evidence_json"), {}).get("asset_version") == asset["version"] and
            safe_json_loads(existing.get("evidence_json"), {}).get("schema_version") == "nvidia-description-v1"))
        if cache_matches and existing.get("status") in ("analyzed", "uncertain", "insufficient_evidence"):
            return row_to_intelligence_record(existing)

    # Invoke built-in skill through SkillRuntime
    runtime = get_default_runtime()
    skill_request = SkillExecutionRequest(
        skill_name="media-intelligence",
        skill_version="1.0.0",
        inputs={
            "media_url": target_url,
            "asset_id": asset_id,
            "frame_id": frame_id,
            "context": context,
        },
        execution_context={
            "asset_id": asset_id,
            "frame_id": frame_id,
            "caller": "api_media_intelligence",
        },
    )

    skill_result = await runtime.execute(skill_request)
    outputs = skill_result.outputs or {}

    # Map skill status to intelligence status
    if skill_result.status == SkillExecutionStatus.UNAVAILABLE:
        status_val = IntelligenceStatus.UNAVAILABLE.value
    elif skill_result.status == SkillExecutionStatus.FAILED:
        status_val = outputs.get("status") or IntelligenceStatus.FAILED.value
    else:
        status_val = outputs.get("status") or IntelligenceStatus.ANALYZED.value

    # Extract structured fields
    description = outputs.get("description")
    observations = outputs.get("observations") or []
    tags = normalize_tags(outputs.get("tags") or [])
    signals = normalize_signals(outputs.get("detected_signals") or [])
    activity = outputs.get("activity")
    warnings = outputs.get("warnings") or []
    if skill_result.errors:
        for err in skill_result.errors:
            if err not in warnings:
                warnings.append(err)

    uncertainty = outputs.get("uncertainty")
    evidence_meta = outputs.get("evidence") or {
        "source_url": target_url,
        "asset_id": asset_id,
        "frame_id": frame_id,
    }
    model_provider = outputs.get("model_provider") or "gemini"
    model_name = outputs.get("model_name") or "unknown"

    record_data = {
        "id": uuid4().hex,
        "asset_id": asset_id,
        "frame_id": frame_id,
        "status": status_val,
        "description": description,
        "observations": json.dumps(observations),
        "tags_json": json.dumps(tags),
        "signals_json": json.dumps(signals),
        "activity": activity,
        "warnings_json": json.dumps(warnings),
        "uncertainty": uncertainty,
        "evidence_json": json.dumps(evidence_meta),
        "model_provider": model_provider,
        "model_name": model_name,
    }

    saved = store.save_media_intelligence(db, record_data)
    return row_to_intelligence_record(saved)


def get_asset_intelligence(db, asset_id: str, frame_id: Optional[str] = None) -> Optional[MediaIntelligenceRecord]:
    """Retrieve the latest intelligence record for an asset or frame."""
    asset = store.get_media_item(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Media asset '{asset_id}' not found.")

    row = store.get_media_intelligence(db, asset_id, frame_id)
    if not row:
        return None
    return row_to_intelligence_record(row)


def get_asset_intelligence_history(db, asset_id: str, frame_id: Optional[str] = None) -> List[MediaIntelligenceRecord]:
    """Retrieve full audit/revision history of intelligence records for an asset or frame."""
    asset = store.get_media_item(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Media asset '{asset_id}' not found.")

    rows = store.get_media_intelligence_history(db, asset_id, frame_id)
    return [row_to_intelligence_record(r) for r in rows]


async def analyze_batch(
    db,
    asset_ids: List[str],
    context: Optional[str] = None,
) -> BatchMediaAnalysisResponse:
    """Perform safe, bounded synchronous batch analysis with per-asset failure isolation.
    
    Guarantees:
    - Bounded to max 20 assets.
    - Failure of one asset does not abort remaining assets.
    - Explicit progress tracking and reporting.
    """
    if len(asset_ids) > 20:
        raise HTTPException(
            status_code=422,
            detail="Batch analysis exceeds maximum limit of 20 assets per batch."
        )

    results: List[BatchMediaAnalysisItemResult] = []
    successful_count = 0
    failed_count = 0

    for aid in asset_ids:
        try:
            intel = await analyze_asset(db, aid, context=context, force_reanalyze=False)
            is_success = intel.status in ("analyzed", "uncertain", "insufficient_evidence")
            if is_success:
                successful_count += 1
            else:
                failed_count += 1

            results.append(
                BatchMediaAnalysisItemResult(
                    asset_id=aid,
                    success=is_success,
                    status=intel.status,
                    error=None if is_success else "; ".join(intel.warnings),
                    intelligence=intel,
                )
            )
        except Exception as exc:
            failed_count += 1
            results.append(
                BatchMediaAnalysisItemResult(
                    asset_id=aid,
                    success=False,
                    status="failed",
                    error=str(exc),
                    intelligence=None,
                )
            )

    return BatchMediaAnalysisResponse(
        total=len(asset_ids),
        processed=len(results),
        successful=successful_count,
        failed=failed_count,
        results=results,
    )
