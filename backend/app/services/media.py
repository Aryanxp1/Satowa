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


def ingest_image(data, content_type, project_id, source, visit_date):
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
        return {**identity, "secure_url": result["secure_url"], "thumbnail_url": thumbnail,
                "tags": tags, "context": context}
    except Exception:
        # SDK exceptions may contain provider request details; never expose/log credentials.
        raise HTTPException(502, "Cloudinary upload failed; no success was recorded") from None
