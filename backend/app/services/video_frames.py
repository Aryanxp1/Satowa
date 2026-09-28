"""Video frame extraction, provenance tracking, and frame analytics service."""
import json
import logging
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from cloudinary.utils import cloudinary_url
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services.evidence_store import (
    connection,
    delete_video_frames_by_asset,
    get_frame_analyses_by_asset,
    get_frame_analysis_by_frame,
    get_media_item,
    get_video_frame,
    get_video_frames_by_asset,
    save_frame_analysis,
    save_video_frame,
    timestamp as now_iso,
)

logger = logging.getLogger(__name__)

MAX_ALLOWED_FRAMES = 60
DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_MAX_FRAMES = 20


class VideoFrameModel(BaseModel):
    """Structured representation of a single extracted video frame."""
    frame_id: str
    asset_id: str
    frame_index: int
    timestamp_seconds: float
    frame_url: str
    thumbnail_url: Optional[str] = None
    source_video_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    extraction_method: str = "cloudinary_offset_transform"
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FrameExtractionRequest(BaseModel):
    """Parameters for sampling and extracting frames from a field video."""
    interval_seconds: float = Field(
        default=DEFAULT_INTERVAL_SECONDS,
        ge=0.5,
        le=60.0,
        description="Sampling interval in seconds between consecutive frames",
    )
    max_frames: int = Field(
        default=DEFAULT_MAX_FRAMES,
        ge=1,
        le=MAX_ALLOWED_FRAMES,
        description="Maximum frame count safety limit",
    )
    strategy: Literal["interval", "uniform", "timestamps"] = Field(
        default="interval",
        description="Sampling strategy: 'interval' (every N s), 'uniform' (evenly spaced), 'timestamps' (explicit list)",
    )
    custom_timestamps: Optional[List[float]] = Field(
        default=None,
        description="Explicit list of timestamps in seconds when strategy='timestamps'",
    )


class FrameExtractionResponse(BaseModel):
    """Result of a video frame extraction operation."""
    asset_id: str
    total_frames: int
    sampling_strategy: str
    video_duration: float
    frames: List[VideoFrameModel]


class FrameAnalysisRequest(BaseModel):
    """Request to execute frame observation analysis on selected or all video frames."""
    frame_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific frame IDs to analyze. If None, analyzes all extracted frames for the asset.",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Optional custom focus prompt for the observation model",
    )
    skill_version: Optional[str] = Field(
        default="1.0.0",
        description="Version of field-frame-observation skill to execute",
    )


class SingleFrameAnalysisResponse(BaseModel):
    """Analysis result for a single video frame."""
    analysis_id: str
    frame_id: str
    timestamp_seconds: float
    frame_url: str
    status: str
    observations: List[str] = []
    detected_signals: List[str] = []
    confidence: Optional[float] = None
    warnings: List[str] = []
    latency_ms: float = 0.0


class VideoFrameAnalysisReport(BaseModel):
    """Aggregated observation report across analyzed video frames."""
    asset_id: str
    total_analyzed: int
    analyzed_at: str
    aggregated_signals: List[str] = []
    summary: str
    frames: List[SingleFrameAnalysisResponse]
    warnings: List[str] = []


def calculate_sample_timestamps(
    duration: float,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    strategy: str = "interval",
    custom_timestamps: Optional[List[float]] = None,
) -> List[float]:
    """Calculate deterministic sampling timestamps within video duration boundaries."""
    if max_frames < 1:
        raise ValueError("max_frames must be at least 1")
    if max_frames > MAX_ALLOWED_FRAMES:
        raise ValueError(f"max_frames cannot exceed {MAX_ALLOWED_FRAMES}")

    dur = max(0.0, float(duration))
    # If video duration is unknown or zero, provide a safe 10.0s window for sampling
    effective_duration = dur if dur > 0.0 else 10.0

    if strategy == "timestamps" and custom_timestamps is not None:
        valid_ts = []
        for ts in custom_timestamps:
            if ts is not None and ts >= 0.0:
                val = round(min(float(ts), effective_duration), 2)
                if val not in valid_ts:
                    valid_ts.append(val)
        valid_ts.sort()
        return valid_ts[:max_frames] if valid_ts else [0.0]

    if strategy == "uniform":
        if max_frames == 1 or effective_duration <= 0.0:
            return [0.0]
        step = effective_duration / float(max_frames - 1)
        return [round(i * step, 2) for i in range(max_frames)]

    # Default 'interval' strategy
    if interval_seconds <= 0.0:
        raise ValueError("interval_seconds must be positive")

    timestamps = []
    current = 0.0
    while current <= effective_duration and len(timestamps) < max_frames:
        timestamps.append(round(current, 2))
        current += interval_seconds

    # Always ensure at least timestamp 0.0
    if not timestamps:
        timestamps = [0.0]

    return timestamps


def build_frame_urls(
    public_id: str,
    timestamp_seconds: float,
    version: Optional[int] = None,
    cloud_name: Optional[str] = None,
) -> tuple[str, str]:
    """Generate Cloudinary delivery URLs for full-res frame and thumbnail at given offset."""
    c_name = cloud_name or settings.CLOUDINARY_CLOUD_NAME
    offset_str = f"{timestamp_seconds:.2f}"

    # High-res frame image derived at start_offset
    frame_url, _ = cloudinary_url(
        public_id,
        cloud_name=c_name,
        resource_type="video",
        format="jpg",
        start_offset=offset_str,
        secure=True,
        version=version,
    )

    # Thumbnail for timeline/inspector (400x225 16:9 crop)
    thumb_url, _ = cloudinary_url(
        public_id,
        cloud_name=c_name,
        resource_type="video",
        format="jpg",
        start_offset=offset_str,
        width=400,
        height=225,
        crop="fill",
        quality="auto",
        secure=True,
        version=version,
    )

    return frame_url, thumb_url


def extract_frames_for_asset(
    db,
    asset_id: str,
    req: FrameExtractionRequest,
) -> FrameExtractionResponse:
    """Extract and persist deterministic video frames from an existing video asset."""
    asset = get_media_item(db, asset_id)
    if not asset:
        raise HTTPException(404, f"Media asset '{asset_id}' not found")

    if asset.get("media_type") != "video":
        raise HTTPException(400, f"Asset '{asset_id}' is an image, not a video. Frame extraction requires video assets.")

    duration = float(asset.get("duration") or 0.0)
    timestamps = calculate_sample_timestamps(
        duration=duration,
        interval_seconds=req.interval_seconds,
        max_frames=req.max_frames,
        strategy=req.strategy,
        custom_timestamps=req.custom_timestamps,
    )

    # Clean existing extracted frames for this asset to maintain idempotent extraction
    delete_video_frames_by_asset(db, asset_id)

    public_id = asset["public_id"]
    version = asset.get("version")
    source_url = asset["secure_url"]
    width = asset.get("width")
    height = asset.get("height")

    frames_created = []
    for idx, ts in enumerate(timestamps):
        frame_id = f"frm_{asset_id}_{idx:03d}_{uuid4().hex[:6]}"
        frame_url, thumb_url = build_frame_urls(public_id, ts, version=version)

        meta = {
            "strategy": req.strategy,
            "interval_seconds": req.interval_seconds,
            "source_public_id": public_id,
        }

        frame_data = {
            "frame_id": frame_id,
            "asset_id": asset_id,
            "frame_index": idx,
            "timestamp_seconds": ts,
            "frame_url": frame_url,
            "thumbnail_url": thumb_url,
            "source_video_url": source_url,
            "width": width,
            "height": height,
            "extraction_method": "cloudinary_offset_transform",
            "metadata_json": json.dumps(meta),
        }
        saved = save_video_frame(db, frame_data)
        frames_created.append(VideoFrameModel(
            frame_id=saved["frame_id"],
            asset_id=saved["asset_id"],
            frame_index=saved["frame_index"],
            timestamp_seconds=saved["timestamp_seconds"],
            frame_url=saved["frame_url"],
            thumbnail_url=saved.get("thumbnail_url"),
            source_video_url=saved["source_video_url"],
            width=saved.get("width"),
            height=saved.get("height"),
            extraction_method=saved.get("extraction_method", "cloudinary_offset_transform"),
            created_at=saved.get("created_at"),
            metadata=meta,
        ))

    return FrameExtractionResponse(
        asset_id=asset_id,
        total_frames=len(frames_created),
        sampling_strategy=req.strategy,
        video_duration=duration,
        frames=frames_created,
    )


def list_frames_for_asset(db, asset_id: str) -> List[VideoFrameModel]:
    """Retrieve all stored frames for a video asset."""
    asset = get_media_item(db, asset_id)
    if not asset:
        raise HTTPException(404, f"Media asset '{asset_id}' not found")
    if asset.get("media_type") != "video":
        raise HTTPException(400, f"Asset '{asset_id}' is not a video")

    raw_frames = get_video_frames_by_asset(db, asset_id)
    result = []
    for r in raw_frames:
        meta = json.loads(r["metadata_json"]) if r.get("metadata_json") else None
        result.append(VideoFrameModel(
            frame_id=r["frame_id"],
            asset_id=r["asset_id"],
            frame_index=r["frame_index"],
            timestamp_seconds=r["timestamp_seconds"],
            frame_url=r["frame_url"],
            thumbnail_url=r.get("thumbnail_url"),
            source_video_url=r["source_video_url"],
            width=r.get("width"),
            height=r.get("height"),
            extraction_method=r.get("extraction_method", "cloudinary_offset_transform"),
            created_at=r.get("created_at"),
            metadata=meta,
        ))
    return result


def get_single_frame(db, frame_id: str) -> VideoFrameModel:
    """Retrieve a single video frame by frame_id."""
    r = get_video_frame(db, frame_id)
    if not r:
        raise HTTPException(404, f"Frame '{frame_id}' not found")
    meta = json.loads(r["metadata_json"]) if r.get("metadata_json") else None
    return VideoFrameModel(
        frame_id=r["frame_id"],
        asset_id=r["asset_id"],
        frame_index=r["frame_index"],
        timestamp_seconds=r["timestamp_seconds"],
        frame_url=r["frame_url"],
        thumbnail_url=r.get("thumbnail_url"),
        source_video_url=r["source_video_url"],
        width=r.get("width"),
        height=r.get("height"),
        extraction_method=r.get("extraction_method", "cloudinary_offset_transform"),
        created_at=r.get("created_at"),
        metadata=meta,
    )


async def analyze_video_frames(
    db,
    asset_id: str,
    req: FrameAnalysisRequest,
    runtime: Any = None,
    context: Optional[Dict[str, Any]] = None,
) -> VideoFrameAnalysisReport:
    """Analyze video frames through the SETOWA SkillRuntime using field-frame-observation skill."""
    from app.skills import get_default_runtime
    from app.skills.models import SkillExecutionRequest

    asset = get_media_item(db, asset_id)
    if not asset:
        raise HTTPException(404, f"Media asset '{asset_id}' not found")
    if asset.get("media_type") != "video":
        raise HTTPException(400, f"Asset '{asset_id}' is not a video")

    all_frames = list_frames_for_asset(db, asset_id)
    if not all_frames:
        raise HTTPException(400, f"No extracted frames found for video asset '{asset_id}'. Extract frames first.")

    target_frames = all_frames
    if req.frame_ids:
        id_set = set(req.frame_ids)
        target_frames = [f for f in all_frames if f.frame_id in id_set]
        if not target_frames:
            raise HTTPException(400, f"None of the requested frame IDs match extracted frames for asset '{asset_id}'")

    skill_runtime = runtime or get_default_runtime()
    ctx = {
        "user_id": (context or {}).get("user_id", "analyst"),
        "granted_permissions": ["media:read", "ai:inference"],
        "db": db,
    }

    analyzed_results: List[SingleFrameAnalysisResponse] = []
    all_signals: set[str] = set()
    collected_observations: List[str] = []
    collected_warnings: List[str] = []

    for frame in target_frames:
        skill_req = SkillExecutionRequest(
            skill_name="field-frame-observation",
            skill_version=req.skill_version or "1.0.0",
            inputs={
                "frame_url": frame.frame_url,
                "timestamp_seconds": frame.timestamp_seconds,
                "source_asset_id": asset_id,
                "prompt": req.prompt,
            },
            execution_context=ctx,
        )

        res = await skill_runtime.execute(skill_req)

        analysis_id = f"anl_{frame.frame_id}_{uuid4().hex[:6]}"
        obs = res.outputs.get("observations") or []
        signals = res.outputs.get("detected_signals") or []
        status_str = res.outputs.get("status") or res.status.value
        confidence_val = res.outputs.get("confidence")
        warns = (res.outputs.get("warnings") or []) + res.warnings
        latency = res.metadata.get("latency_ms", 0.0)

        # Persist to database
        analysis_record = {
            "analysis_id": analysis_id,
            "asset_id": asset_id,
            "frame_id": frame.frame_id,
            "skill_name": "field-frame-observation",
            "skill_version": req.skill_version or "1.0.0",
            "status": status_str,
            "observations_json": json.dumps(obs),
            "detected_signals_json": json.dumps(signals),
            "confidence": confidence_val,
            "warnings_json": json.dumps(warns),
            "latency_ms": latency,
            "raw_result_json": json.dumps(res.model_dump(), default=str),
        }
        save_frame_analysis(db, analysis_record)

        for sig in signals:
            all_signals.add(sig)
        for ob in obs:
            if ob not in collected_observations:
                collected_observations.append(ob)
        for w in warns:
            if w not in collected_warnings:
                collected_warnings.append(w)

        analyzed_results.append(SingleFrameAnalysisResponse(
            analysis_id=analysis_id,
            frame_id=frame.frame_id,
            timestamp_seconds=frame.timestamp_seconds,
            frame_url=frame.frame_url,
            status=status_str,
            observations=obs,
            detected_signals=signals,
            confidence=confidence_val,
            warnings=warns,
            latency_ms=latency,
        ))

    summary_text = (
        f"Analyzed {len(analyzed_results)} field video frame(s) across duration {target_frames[0].timestamp_seconds}s to {target_frames[-1].timestamp_seconds}s. "
        + (" ".join(collected_observations[:2]) if collected_observations else "Visual assessment recorded.")
    )

    return VideoFrameAnalysisReport(
        asset_id=asset_id,
        total_analyzed=len(analyzed_results),
        analyzed_at=now_iso(),
        aggregated_signals=sorted(list(all_signals)),
        summary=summary_text,
        frames=analyzed_results,
        warnings=collected_warnings,
    )


def get_video_frame_analysis_report(db, asset_id: str) -> VideoFrameAnalysisReport:
    """Retrieve existing frame analysis history for a video asset."""
    asset = get_media_item(db, asset_id)
    if not asset:
        raise HTTPException(404, f"Media asset '{asset_id}' not found")
    if asset.get("media_type") != "video":
        raise HTTPException(400, f"Asset '{asset_id}' is not a video")

    raw_analyses = get_frame_analyses_by_asset(db, asset_id)
    if not raw_analyses:
        return VideoFrameAnalysisReport(
            asset_id=asset_id,
            total_analyzed=0,
            analyzed_at=now_iso(),
            aggregated_signals=[],
            summary="No frame analyses recorded yet for this video asset.",
            frames=[],
            warnings=[],
        )

    # Map frames for timestamp and URL lookup
    frames_map = {f["frame_id"]: f for f in get_video_frames_by_asset(db, asset_id)}

    frames_resp: List[SingleFrameAnalysisResponse] = []
    all_signals: set[str] = set()
    collected_observations: List[str] = []
    collected_warnings: List[str] = []

    # Keep latest analysis per frame
    seen_frames = set()
    for row in raw_analyses:
        fid = row["frame_id"]
        if fid in seen_frames:
            continue
        seen_frames.add(fid)

        f_item = frames_map.get(fid)
        f_url = f_item["frame_url"] if f_item else ""
        ts = f_item["timestamp_seconds"] if f_item else 0.0

        obs = json.loads(row["observations_json"]) if row.get("observations_json") else []
        sigs = json.loads(row["detected_signals_json"]) if row.get("detected_signals_json") else []
        warns = json.loads(row["warnings_json"]) if row.get("warnings_json") else []

        for sig in sigs:
            all_signals.add(sig)
        for ob in obs:
            if ob not in collected_observations:
                collected_observations.append(ob)
        for w in warns:
            if w not in collected_warnings:
                collected_warnings.append(w)

        frames_resp.append(SingleFrameAnalysisResponse(
            analysis_id=row["analysis_id"],
            frame_id=fid,
            timestamp_seconds=ts,
            frame_url=f_url,
            status=row["status"],
            observations=obs,
            detected_signals=sigs,
            confidence=row.get("confidence"),
            warnings=warns,
            latency_ms=row.get("latency_ms", 0.0),
        ))

    frames_resp.sort(key=lambda x: x.timestamp_seconds)

    summary_text = (
        f"Recorded visual evidence across {len(frames_resp)} sampled frame(s). "
        + (" ".join(collected_observations[:2]) if collected_observations else "Visual assessment recorded.")
    )

    return VideoFrameAnalysisReport(
        asset_id=asset_id,
        total_analyzed=len(frames_resp),
        analyzed_at=raw_analyses[0].get("created_at") or now_iso(),
        aggregated_signals=sorted(list(all_signals)),
        summary=summary_text,
        frames=frames_resp,
        warnings=collected_warnings,
    )

