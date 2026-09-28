"""Cloudinary adapter: validate originals and retain their delivery identity."""
import hashlib
import io
import warnings
from uuid import uuid4

import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.config import settings

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000
FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

MAX_VIDEO_BYTES = 50 * 1024 * 1024
VIDEO_FORMATS = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
}


def ingest_image(data, content_type, project_id, source, visit_date, original_filename=None):
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413 if data else 422, "Image must contain 1 byte to 10 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in FORMATS or content_type != FORMATS[image.format]:
                    raise HTTPException(415, "Use a JPEG, PNG or WebP with matching MIME type")
                if image.width * image.height > MAX_PIXELS or getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(422, "Use a single-frame image of at most 25 megapixels")
                image.verify()
            # Force decoding too; headers alone are insufficient validation.
            with Image.open(io.BytesIO(data)) as image:
                image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise HTTPException(422, "Invalid or oversized image") from None

    secret = settings.CLOUDINARY_API_SECRET.get_secret_value()
    if not all((settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_API_KEY, secret)):
        raise HTTPException(503, "Cloudinary is not configured")
    digest = hashlib.sha256(data).hexdigest()
    context = {"project_id": project_id, "source": source, "visit_date": visit_date,
               "sha256": digest}
    if original_filename:
        context["original_filename"] = original_filename
    tags = ["lex", f"project_{project_id}"]
    try:
        result = cloudinary.uploader.upload(
            io.BytesIO(data), cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY, api_secret=secret,
            resource_type="image", type="upload", overwrite=False,
            public_id=f"lex/{project_id}/{uuid4().hex}",
            tags=tags, context=context, timeout=30,
        )
        identity = {key: result[key] for key in (
            "asset_id", "public_id", "version", "resource_type", "format", "width", "height"
        )}
        thumbnail, _ = cloudinary_url(
            result["public_id"], cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            secure=True, version=result["version"], format=result["format"],
            width=640, height=480, crop="limit", quality="auto", fetch_format="auto",
        )
        preview, _ = cloudinary_url(
            result["public_id"], cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            secure=True, version=result["version"], format=result["format"],
            width=1200, height=900, crop="limit", quality="auto", fetch_format="auto",
        )
        return {
            **identity,
            "media_type": "image",
            "secure_url": result["secure_url"],
            "thumbnail_url": thumbnail,
            "preview_url": preview,
            "tags": tags,
            "context": context,
            "original_filename": original_filename,
            "processing_status": "ready",
        }
    except Exception:
        # SDK exceptions may contain provider request details; never expose/log credentials.
        raise HTTPException(502, "Cloudinary upload failed; no success was recorded") from None


def validate_video_header(data: bytes, content_type: str) -> str:
    """Validate video binary signature and return canonical format."""
    if not data or len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(413 if data else 422, "Video must contain 1 byte to 50 MiB")

    canonical_mime = content_type.lower().split(';')[0].strip() if content_type else ""
    if canonical_mime not in VIDEO_FORMATS:
        if len(data) >= 4 and data[:4] == b'\x1a\x45\xdf\xa3':
            canonical_mime = "video/webm"
        elif len(data) >= 8 and data[4:8] == b'ftyp':
            canonical_mime = "video/mp4"
        else:
            raise HTTPException(415, "Unsupported video format. Use MP4, WebM, or QuickTime MOV")

    if canonical_mime in ("video/mp4", "video/quicktime"):
        if len(data) < 8 or (data[4:8] != b'ftyp' and data[4:8] not in (b'moov', b'mdat', b'wide', b'skip')):
            raise HTTPException(422, "Invalid MP4/MOV container structure")
    elif canonical_mime == "video/webm":
        if len(data) < 4 or data[:4] != b'\x1a\x45\xdf\xa3':
            raise HTTPException(422, "Invalid WebM container structure")

    return VIDEO_FORMATS[canonical_mime]


def ingest_video(data, content_type, project_id, source, visit_date, original_filename=None):
    """Upload one permissioned video to Cloudinary with derived poster and previews."""
    fmt = validate_video_header(data, content_type)
    secret = settings.CLOUDINARY_API_SECRET.get_secret_value()
    if not all((settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_API_KEY, secret)):
        raise HTTPException(503, "Cloudinary is not configured")
    digest = hashlib.sha256(data).hexdigest()
    context = {"project_id": project_id, "source": source, "visit_date": visit_date,
               "sha256": digest}
    if original_filename:
        context["original_filename"] = original_filename
    tags = ["lex", "setowa", f"project_{project_id}", "video"]
    try:
        result = cloudinary.uploader.upload(
            io.BytesIO(data), cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY, api_secret=secret,
            resource_type="video", type="upload", overwrite=False,
            public_id=f"setowa/{project_id}/video_{uuid4().hex}",
            tags=tags, context=context, timeout=60,
        )
        identity = {
            "asset_id": result.get("asset_id") or uuid4().hex,
            "public_id": result["public_id"],
            "version": result.get("version", 1),
            "resource_type": "video",
            "media_type": "video",
            "format": result.get("format", fmt),
            "width": result.get("width") or 1280,
            "height": result.get("height") or 720,
            "duration": float(result.get("duration") or 0.0),
        }
        # Video poster frame thumbnail (image from video at offset 0)
        thumbnail, _ = cloudinary_url(
            result["public_id"], cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            resource_type="video", secure=True, version=result.get("version"),
            format="jpg", start_offset="0", width=400, height=400, crop="fill",
            quality="auto",
        )
        # Video high-res poster preview
        preview, _ = cloudinary_url(
            result["public_id"], cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            resource_type="video", secure=True, version=result.get("version"),
            format="jpg", start_offset="0", width=1200, height=900, crop="limit",
            quality="auto",
        )
        return {
            **identity,
            "secure_url": result["secure_url"],
            "thumbnail_url": thumbnail,
            "preview_url": preview,
            "tags": tags,
            "context": context,
            "original_filename": original_filename,
            "processing_status": "ready",
        }
    except Exception:
        raise HTTPException(502, "Cloudinary video upload failed; no success was recorded") from None


def ingest_media(data, content_type, project_id, source, visit_date, original_filename=None):
    """Unified dispatcher for ingesting either an image or a video asset."""
    mime = (content_type or "").lower().split(';')[0].strip()
    is_video = (
        mime in VIDEO_FORMATS or
        (original_filename and original_filename.lower().endswith(('.mp4', '.webm', '.mov')))
    )
    if is_video:
        return ingest_video(data, mime or "video/mp4", project_id, source, visit_date, original_filename)
    return ingest_image(data, mime or "image/png", project_id, source, visit_date, original_filename)

