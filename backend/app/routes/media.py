"""Bounded, authenticated image ingestion for the private hackathon demo."""
import hmac
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.services.media import MAX_BYTES, ingest_image
from app.services import evidence_store as store
from app.services.reviewer_auth import authorization_or_local_cookie, reviewer_tokens

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
            f"permission_status must be one of: {', '.join(sorted(VALID_PERMISSION_STATUSES))}"
        )
    try:
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 10 MiB")
        if not source.strip():
            raise HTTPException(422, "Source must not be blank")
        if visit_id:
            with store.connection() as db:
                visit = store.one(db, 'SELECT * FROM visits WHERE id=?', (visit_id,))
                if not visit:
                    raise HTTPException(404, 'Visit not found')
                if visit['site_id'] != project_id or visit['visited_on'] != visit_date.isoformat():
                    raise HTTPException(422, 'Upload site and date must match the visit')
        result = await run_in_threadpool(
            ingest_image, data, file.content_type, project_id, source.strip(), visit_date.isoformat()
        )
        result["permission_status"] = perm_status
        if visit_id:
            with store.connection() as db:
                db.execute("""INSERT INTO assets
                    (asset_id,visit_id,public_id,version,secure_url,source,width,height,format,permission_status,thumbnail_url)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (result['asset_id'], visit_id, result['public_id'], result['version'],
                     result['secure_url'], source.strip(), result['width'], result['height'],
                     result['format'], perm_status, result.get('thumbnail_url')))
        return result
    finally:
        await file.close()
