"""Bounded, authenticated media ingestion and library pipeline for Setowa."""
import hmac
import json
from datetime import date
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.schemas.api import (
    BatchMediaAnalysisRequest,
    BatchMediaAnalysisResponse,
    BulkMediaItemResult,
    BulkMediaUploadResponse,
    MediaAnalysisRequest,
    MediaIntelligenceRecord,
    MediaItemResponse,
)
from app.services import evidence_store as store
from app.services.media import (
    MAX_BYTES,
    MAX_VIDEO_BYTES,
    ingest_image,
    ingest_media,
    ingest_video,
)
from app.services.media_intelligence import (
    analyze_asset,
    analyze_batch,
    get_asset_intelligence,
    get_asset_intelligence_history,
)
from app.services.reviewer_auth import authorization_or_local_cookie, reviewer_tokens
from app.services.video_frames import (
    FrameAnalysisRequest,
    FrameExtractionRequest,
    FrameExtractionResponse,
    SingleFrameAnalysisResponse,
    VideoFrameAnalysisReport,
    VideoFrameModel,
    analyze_video_frames,
    extract_frames_for_asset,
    get_single_frame,
    get_video_frame_analysis_report,
    list_frames_for_asset,
)

router = APIRouter(prefix="/api/v1", tags=["Media"])



def require_upload_token(request: Request, authorization: str | None = Header(default=None)):
    token = settings.MEDIA_UPLOAD_TOKEN.get_secret_value()
    reviewers = reviewer_tokens()
    allowed = [candidate for candidate in [token, *reviewers.values()] if candidate]
    if not allowed:
        raise HTTPException(503, "Media uploads are not configured")
    provided = (authorization_or_local_cookie(authorization, request) or "").encode()
    if not any(hmac.compare_digest(provided, f"Bearer {candidate}".encode()) for candidate in allowed):
        raise HTTPException(401, "Invalid upload credentials")


VALID_PERMISSION_STATUSES = {"granted", "pending_verification", "revoked"}


def row_to_media_item(row: dict) -> MediaItemResponse:
    meta = None
    if row.get("metadata_json"):
        try:
            meta = json.loads(row["metadata_json"])
        except Exception:
            pass
    return MediaItemResponse(
        asset_id=row["asset_id"],
        public_id=row["public_id"],
        version=row["version"],
        secure_url=row["secure_url"],
        thumbnail_url=row.get("thumbnail_url"),
        preview_url=row.get("preview_url"),
        source=row["source"],
        media_type=row.get("media_type") or "image",
        width=row.get("width"),
        height=row.get("height"),
        duration=row.get("duration"),
        format=row["format"],
        permission_status=row.get("permission_status") or "granted",
        processing_status=row.get("processing_status") or "ready",
        site_id=row.get("site_id"),
        visit_id=row.get("visit_id"),
        original_filename=row.get("original_filename"),
        created_at=row.get("created_at"),
        metadata=meta,
    )


@router.post("/media/images", status_code=201, dependencies=[Depends(require_upload_token)])
async def upload_image(
    file: Annotated[UploadFile, File()],
    project_id: Annotated[str, Form(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")],
    source: Annotated[str, Form(min_length=1, max_length=200)],
    visit_date: Annotated[date, Form()],
    visit_id: Annotated[str | None, Form()] = None,
    permission_status: Annotated[str, Form()] = "granted",
):
    """Upload one permissioned JPEG/PNG/WebP image with source attribution."""
    perm_status = permission_status.strip().lower()
    if perm_status not in VALID_PERMISSION_STATUSES:
        raise HTTPException(
            422,
            f"permission_status must be one of: {', '.join(sorted(VALID_PERMISSION_STATUSES))}",
        )
    try:
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 10 MiB")
        if not source.strip():
            raise HTTPException(422, "Source must not be blank")
        if visit_id:
            with store.connection() as db:
                visit = store.one(db, "SELECT * FROM visits WHERE id=?", (visit_id,))
                if not visit:
                    raise HTTPException(404, "Visit not found")
                if visit["site_id"] != project_id or visit["visited_on"] != visit_date.isoformat():
                    raise HTTPException(422, "Upload site and date must match the visit")
        else:
            # Auto-create or find a visit for this site + date
            with store.connection() as db:
                visit_id = store.ensure_ingestion_visit(db, project_id, visit_date.isoformat())
        result = await run_in_threadpool(
            ingest_image,
            data,
            file.content_type,
            project_id,
            source.strip(),
            visit_date.isoformat(),
            file.filename,
        )
        result["permission_status"] = perm_status
        result["site_id"] = project_id
        with store.connection() as db:
            store.save_asset(
                db,
                {
                    "asset_id": result["asset_id"],
                    "visit_id": visit_id,
                    "public_id": result["public_id"],
                    "version": result["version"],
                    "secure_url": result["secure_url"],
                    "source": source.strip(),
                    "width": result["width"],
                    "height": result["height"],
                    "format": result["format"],
                    "permission_status": perm_status,
                    "thumbnail_url": result.get("thumbnail_url"),
                    "site_id": project_id,
                    "media_type": "image",
                    "processing_status": "ready",
                    "original_filename": file.filename,
                    "duration": None,
                    "preview_url": result.get("preview_url"),
                },
            )
        return result
    finally:
        await file.close()


@router.post("/media/videos", status_code=201, dependencies=[Depends(require_upload_token)])
async def upload_video(
    file: Annotated[UploadFile, File()],
    project_id: Annotated[str, Form(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")],
    source: Annotated[str, Form(min_length=1, max_length=200)],
    visit_date: Annotated[date, Form()],
    visit_id: Annotated[str | None, Form()] = None,
    permission_status: Annotated[str, Form()] = "granted",
):
    """Upload one permissioned MP4/WebM/MOV video up to 50 MiB with derived poster and previews."""
    perm_status = permission_status.strip().lower()
    if perm_status not in VALID_PERMISSION_STATUSES:
        raise HTTPException(
            422,
            f"permission_status must be one of: {', '.join(sorted(VALID_PERMISSION_STATUSES))}",
        )
    try:
        data = await file.read(MAX_VIDEO_BYTES + 1)
        if len(data) > MAX_VIDEO_BYTES:
            raise HTTPException(413, "Video exceeds 50 MiB")
        if not source.strip():
            raise HTTPException(422, "Source must not be blank")

        resolved_visit_id = visit_id
        with store.connection() as db:
            if visit_id:
                visit = store.one(db, "SELECT * FROM visits WHERE id=?", (visit_id,))
                if not visit:
                    raise HTTPException(404, "Visit not found")
                if visit["site_id"] != project_id or visit["visited_on"] != visit_date.isoformat():
                    raise HTTPException(422, "Upload site and date must match the visit")
            else:
                resolved_visit_id = store.ensure_ingestion_visit(db, project_id, visit_date.isoformat())

        result = await run_in_threadpool(
            ingest_video,
            data,
            file.content_type,
            project_id,
            source.strip(),
            visit_date.isoformat(),
            file.filename,
        )
        result["permission_status"] = perm_status
        result["site_id"] = project_id
        result["visit_id"] = resolved_visit_id

        with store.connection() as db:
            store.save_asset(
                db,
                {
                    "asset_id": result["asset_id"],
                    "visit_id": resolved_visit_id,
                    "public_id": result["public_id"],
                    "version": result["version"],
                    "secure_url": result["secure_url"],
                    "source": source.strip(),
                    "width": result.get("width") or 1280,
                    "height": result.get("height") or 720,
                    "format": result.get("format") or "mp4",
                    "permission_status": perm_status,
                    "thumbnail_url": result.get("thumbnail_url"),
                    "site_id": project_id,
                    "media_type": "video",
                    "processing_status": "ready",
                    "original_filename": file.filename,
                    "duration": result.get("duration"),
                    "preview_url": result.get("preview_url"),
                },
            )
        return result
    finally:
        await file.close()


@router.post(
    "/media/bulk",
    response_model=BulkMediaUploadResponse,
    status_code=201,
    dependencies=[Depends(require_upload_token)],
)
async def upload_bulk_media(
    files: List[UploadFile] = File(...),
    project_id: str = Form(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    source: str = Form(min_length=1, max_length=200),
    visit_date: date = Form(...),
    visit_id: Optional[str] = Form(None),
    permission_status: str = Form("granted"),
):
    """Bulk ingestion endpoint for multi-file image and video collections.

    Guarantees safe per-file error handling so individual failures do not corrupt
    the entire batch.
    """
    perm_status = permission_status.strip().lower()
    if perm_status not in VALID_PERMISSION_STATUSES:
        raise HTTPException(
            422,
            f"permission_status must be one of: {', '.join(sorted(VALID_PERMISSION_STATUSES))}",
        )
    if not source.strip():
        raise HTTPException(422, "Source must not be blank")

    # Resolve or create the associated visit
    with store.connection() as db:
        if visit_id:
            visit = store.one(db, "SELECT * FROM visits WHERE id=?", (visit_id,))
            if not visit:
                raise HTTPException(404, "Visit not found")
            if visit["site_id"] != project_id or visit["visited_on"] != visit_date.isoformat():
                raise HTTPException(422, "Upload site and date must match the visit")
            resolved_visit_id = visit_id
        else:
            resolved_visit_id = store.ensure_ingestion_visit(db, project_id, visit_date.isoformat())

    results: List[BulkMediaItemResult] = []
    successful_count = 0
    failed_count = 0

    for file in files:
        filename = file.filename or "unnamed_media"
        try:
            # Check maximum allowed size (videos up to 50 MiB, images up to 10 MiB)
            max_limit = MAX_VIDEO_BYTES if (
                (file.content_type and "video" in file.content_type)
                or filename.lower().endswith((".mp4", ".webm", ".mov"))
            ) else MAX_BYTES

            data = await file.read(max_limit + 1)
            if len(data) > max_limit:
                limit_mb = max_limit // (1024 * 1024)
                results.append(
                    BulkMediaItemResult(
                        filename=filename,
                        status="failed",
                        error=f"File exceeds maximum size limit of {limit_mb} MiB",
                    )
                )
                failed_count += 1
                continue

            result = await run_in_threadpool(
                ingest_media,
                data,
                file.content_type,
                project_id,
                source.strip(),
                visit_date.isoformat(),
                filename,
            )

            asset_record = {
                "asset_id": result["asset_id"],
                "visit_id": resolved_visit_id,
                "public_id": result["public_id"],
                "version": result["version"],
                "secure_url": result["secure_url"],
                "source": source.strip(),
                "width": result.get("width") or 800,
                "height": result.get("height") or 600,
                "format": result.get("format") or "jpg",
                "permission_status": perm_status,
                "thumbnail_url": result.get("thumbnail_url"),
                "site_id": project_id,
                "media_type": result.get("media_type") or "image",
                "processing_status": "ready",
                "original_filename": filename,
                "duration": result.get("duration"),
                "preview_url": result.get("preview_url"),
            }

            with store.connection() as db:
                store.save_asset(db, asset_record)

            item = MediaItemResponse(
                asset_id=asset_record["asset_id"],
                public_id=asset_record["public_id"],
                version=asset_record["version"],
                secure_url=asset_record["secure_url"],
                thumbnail_url=asset_record["thumbnail_url"],
                preview_url=asset_record["preview_url"],
                source=asset_record["source"],
                media_type=asset_record["media_type"],
                width=asset_record["width"],
                height=asset_record["height"],
                duration=asset_record["duration"],
                format=asset_record["format"],
                permission_status=asset_record["permission_status"],
                processing_status=asset_record["processing_status"],
                site_id=asset_record["site_id"],
                visit_id=asset_record["visit_id"],
                original_filename=asset_record["original_filename"],
                created_at=asset_record.get("created_at"),
            )
            results.append(
                BulkMediaItemResult(
                    filename=filename,
                    status="success",
                    asset=item,
                )
            )
            successful_count += 1
        except HTTPException as exc:
            results.append(
                BulkMediaItemResult(
                    filename=filename,
                    status="failed",
                    error=str(exc.detail),
                )
            )
            failed_count += 1
        except Exception as exc:
            results.append(
                BulkMediaItemResult(
                    filename=filename,
                    status="failed",
                    error="Ingestion failed; please verify file format",
                )
            )
            failed_count += 1
        finally:
            await file.close()

    return BulkMediaUploadResponse(
        total_files=len(files),
        successful=successful_count,
        failed=failed_count,
        results=results,
    )


@router.get("/media/query", dependencies=[Depends(require_upload_token)])
def query_media(
    project_id: Optional[str] = None,
    site_id: Optional[str] = None,
    media_type: Optional[str] = None,
    permission_status: Optional[str] = None,
    source: Optional[str] = None,
    filename: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    date_basis: str = Query(default="created_at", pattern="^(created_at|captured_at|effective)$"),
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lng: Optional[float] = None,
    max_lng: Optional[float] = None,
    tag: Optional[str] = None,
    signal: Optional[str] = None,
    ai_status: Optional[str] = None,
    sort: str = Query(default="desc", pattern="^(desc|asc|chronological|reverse_chronological)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Multi-dimensional media query with date range, source filtering, pagination and sorting."""
    from app.services.media_query import MediaQueryFilters, query_media_assets, validate_date_string
    validated_from = validate_date_string(date_from, "date_from")
    validated_to = validate_date_string(date_to, "date_to")

    # Validate enum-like params
    valid_media_types = {"image", "video", None}
    if media_type and media_type.lower() not in valid_media_types:
        raise HTTPException(422, f"media_type must be 'image' or 'video'")
    valid_permission_statuses = {"granted", "pending_verification", "revoked", None}
    if permission_status and permission_status.lower() not in valid_permission_statuses:
        raise HTTPException(422, f"permission_status must be one of: granted, pending_verification, revoked")

    filters = MediaQueryFilters(
        project_id=project_id,
        site_id=site_id,
        media_type=media_type.lower() if media_type else None,
        permission_status=permission_status.lower() if permission_status else None,
        source=source,
        filename=filename,
        date_from=validated_from,
        date_to=validated_to,
        date_basis=date_basis,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lng=min_lng,
        max_lng=max_lng,
        tag=tag,
        signal=signal,
        ai_status=ai_status,
        sort=sort,
        page=page,
        limit=limit,
    )
    with store.connection() as db:
        return query_media_assets(db, filters)



@router.get("/media/timeline", dependencies=[Depends(require_upload_token)])
def media_timeline(
    project_id: Optional[str] = None,
    site_id: Optional[str] = None,
    media_type: Optional[str] = None,
    permission_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    date_basis: str = Query(default="created_at", pattern="^(created_at|captured_at|effective)$"),
    sort: str = Query(default="desc", pattern="^(desc|asc|chronological|reverse_chronological)$"),
):
    """Retrieve media assets grouped by date into timeline buckets."""
    from app.services.media_query import MediaQueryFilters, query_media_timeline, validate_date_string
    validated_from = validate_date_string(date_from, "date_from")
    validated_to = validate_date_string(date_to, "date_to")

    filters = MediaQueryFilters(
        project_id=project_id,
        site_id=site_id,
        media_type=media_type.lower() if media_type else None,
        permission_status=permission_status.lower() if permission_status else None,
        date_from=validated_from,
        date_to=validated_to,
        date_basis=date_basis,
        sort=sort,
    )
    with store.connection() as db:
        return query_media_timeline(db, filters)


@router.get("/media", response_model=List[MediaItemResponse], dependencies=[Depends(require_upload_token)])
def list_media_assets(
    project_id: Optional[str] = None,
    media_type: Optional[str] = None,
    permission_status: Optional[str] = None,
    tag: Optional[str] = None,
    signal: Optional[str] = None,
    ai_status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retrieve and filter media library assets."""
    with store.connection() as db:
        rows = store.list_media(
            db,
            project_id=project_id,
            media_type=media_type,
            permission_status=permission_status,
            tag=tag,
            signal=signal,
            ai_status=ai_status,
            limit=limit,
            offset=offset,
        )
        return [row_to_media_item(r) for r in rows]



@router.get("/media/{asset_id}", response_model=MediaItemResponse, dependencies=[Depends(require_upload_token)])
def get_media_asset(asset_id: str):
    """Retrieve a single media asset by its asset ID."""
    with store.connection() as db:
        asset = store.get_media_item(db, asset_id)
        if not asset:
            raise HTTPException(404, f"Media asset '{asset_id}' not found")
        return row_to_media_item(asset)


@router.post("/media/{asset_id}/frames/extract", response_model=FrameExtractionResponse, dependencies=[Depends(require_upload_token)])
def extract_video_frames_endpoint(asset_id: str, request: FrameExtractionRequest = FrameExtractionRequest()):
    """Extract sampled frames from a video asset using Cloudinary offset transformations."""
    with store.connection() as db:
        return extract_frames_for_asset(db, asset_id, request)


@router.get("/media/{asset_id}/frames", response_model=List[VideoFrameModel], dependencies=[Depends(require_upload_token)])
def list_video_frames_endpoint(asset_id: str):
    """Retrieve all extracted frames for a video asset."""
    with store.connection() as db:
        return list_frames_for_asset(db, asset_id)


@router.get("/media/{asset_id}/frames/{frame_id}", response_model=VideoFrameModel, dependencies=[Depends(require_upload_token)])
def get_video_frame_endpoint(asset_id: str, frame_id: str):
    """Retrieve a single extracted video frame."""
    with store.connection() as db:
        frame = get_single_frame(db, frame_id)
        if frame.asset_id != asset_id:
            raise HTTPException(404, f"Frame '{frame_id}' does not belong to asset '{asset_id}'")
        return frame


@router.post("/media/{asset_id}/frames/analyze", response_model=VideoFrameAnalysisReport, dependencies=[Depends(require_upload_token)])
async def analyze_video_frames_endpoint(asset_id: str, request: FrameAnalysisRequest = FrameAnalysisRequest()):
    """Analyze video frames through the SETOWA SkillRuntime using field-frame-observation skill."""
    with store.connection() as db:
        return await analyze_video_frames(db, asset_id, request)


@router.get("/media/{asset_id}/frame-analysis", response_model=VideoFrameAnalysisReport, dependencies=[Depends(require_upload_token)])
def get_video_frame_analysis_endpoint(asset_id: str):
    """Retrieve recorded frame observation report for a video asset."""
    with store.connection() as db:
        return get_video_frame_analysis_report(db, asset_id)


# ==============================================================================
# T016 — AI Media Intelligence Endpoints
# ==============================================================================

@router.post("/media/analyze-batch", response_model=BatchMediaAnalysisResponse, dependencies=[Depends(require_upload_token)])
async def analyze_media_batch_endpoint(request: BatchMediaAnalysisRequest):
    """Perform bounded, safe batch analysis across multiple media assets with per-asset failure isolation."""
    with store.connection() as db:
        return await analyze_batch(db, request.asset_ids, context=request.context)


@router.post("/media/{asset_id}/analyze", response_model=MediaIntelligenceRecord, dependencies=[Depends(require_upload_token)])
async def analyze_media_asset_endpoint(asset_id: str, request: MediaAnalysisRequest = MediaAnalysisRequest()):
    """Analyze a media asset or video frame using the media-intelligence skill via SkillRuntime."""
    with store.connection() as db:
        return await analyze_asset(
            db,
            asset_id=asset_id,
            frame_id=request.frame_id,
            context=request.context,
            force_reanalyze=request.force_reanalyze,
        )


@router.get("/media/{asset_id}/intelligence", response_model=MediaIntelligenceRecord, dependencies=[Depends(require_upload_token)])
def get_media_intelligence_endpoint(asset_id: str, frame_id: Optional[str] = None):
    """Retrieve the latest structured AI media intelligence record for an asset or frame."""
    with store.connection() as db:
        intel = get_asset_intelligence(db, asset_id, frame_id=frame_id)
        if not intel:
            raise HTTPException(
                status_code=404,
                detail=f"No intelligence record found for media asset '{asset_id}'" + (f" frame '{frame_id}'" if frame_id else "")
            )
        return intel


@router.get("/media/{asset_id}/intelligence/history", response_model=List[MediaIntelligenceRecord], dependencies=[Depends(require_upload_token)])
def get_media_intelligence_history_endpoint(asset_id: str, frame_id: Optional[str] = None):
    """Retrieve full audit/revision history of intelligence records for an asset or frame."""
    with store.connection() as db:
        return get_asset_intelligence_history(db, asset_id, frame_id=frame_id)


@router.post("/media/{asset_id}/reanalyze", response_model=MediaIntelligenceRecord, dependencies=[Depends(require_upload_token)])
async def reanalyze_media_asset_endpoint(asset_id: str, request: MediaAnalysisRequest = MediaAnalysisRequest()):
    """Re-run AI analysis on an asset or frame, creating a new timestamped revision preserving provenance."""
    with store.connection() as db:
        return await analyze_asset(
            db,
            asset_id=asset_id,
            frame_id=request.frame_id,
            context=request.context,
            force_reanalyze=True,
        )


@router.post("/media/{asset_id}/frames/{frame_id}/analyze", response_model=MediaIntelligenceRecord, dependencies=[Depends(require_upload_token)])
async def analyze_specific_frame_endpoint(asset_id: str, frame_id: str, request: MediaAnalysisRequest = MediaAnalysisRequest()):
    """Analyze a specific extracted video frame using the media-intelligence skill."""
    with store.connection() as db:
        return await analyze_asset(
            db,
            asset_id=asset_id,
            frame_id=frame_id,
            context=request.context,
            force_reanalyze=request.force_reanalyze,
        )

