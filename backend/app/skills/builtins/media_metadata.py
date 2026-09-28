"""Deterministic media metadata extraction skill."""
from typing import Any, Dict, Optional
from app.skills.loader import BaseSkill
from app.skills.models import (
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillInputDefinition,
    SkillManifest,
    SkillOutputDefinition,
)
from app.services.evidence_store import connection, get_media_item


class MediaMetadataSkill(BaseSkill):
    """Inspects media assets and extracts Cloudinary delivery, format, dimensions, and duration metadata."""

    def __init__(self, version: str = "1.0.0"):
        manifest = SkillManifest(
            name="media-metadata",
            version=version,
            description="Inspect media assets and extract Cloudinary delivery, format, dimensions, and duration metadata.",
            kind="deterministic",
            permissions=["media:read"],
            inputs=[
                SkillInputDefinition(
                    name="asset_id",
                    type="string",
                    description="Unique asset ID stored in Setowa database",
                    required=False,
                ),
                SkillInputDefinition(
                    name="media",
                    type="object",
                    description="Raw media asset dictionary or Cloudinary response payload",
                    required=False,
                ),
                SkillInputDefinition(
                    name="url",
                    type="string",
                    description="Direct media asset URL for inspection",
                    required=False,
                ),
            ],
            outputs=[
                SkillOutputDefinition(name="media_type", type="string", description="Type of media ('image' or 'video')"),
                SkillOutputDefinition(name="format", type="string", description="Asset format (e.g. jpg, png, mp4, webm)"),
                SkillOutputDefinition(name="dimensions", type="object", description="Image or video width and height"),
                SkillOutputDefinition(name="duration", type="number", description="Video duration in seconds if applicable"),
                SkillOutputDefinition(name="secure_url", type="string", description="Cloudinary delivery URL"),
                SkillOutputDefinition(name="thumbnail_url", type="string", description="Optimized thumbnail URL"),
                SkillOutputDefinition(name="preview_url", type="string", description="Responsive preview URL"),
                SkillOutputDefinition(name="processing_status", type="string", description="Asset status: ready, processing, failed"),
                SkillOutputDefinition(name="metadata", type="object", description="Full extended asset metadata"),
            ],
            metadata={
                "author": "Setowa Core Team",
                "category": "Media Pipeline",
                "documentation": "Extracts delivery, dimensions, and duration parameters from Cloudinary assets.",
            },
        )
        super().__init__(manifest)

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: Dict[str, Any]
    ) -> SkillExecutionResult:
        asset_id = inputs.get("asset_id")
        media_dict = inputs.get("media")
        url = inputs.get("url")

        if not asset_id and not media_dict and not url:
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.INVALID_INPUT,
                outputs={},
                errors=["At least one of 'asset_id', 'media', or 'url' must be provided."],
            )

        asset: Optional[Dict[str, Any]] = None

        # 1. Database asset lookup
        if asset_id:
            try:
                db_conn = context.get("db")
                if db_conn is not None:
                    asset = get_media_item(db_conn, asset_id)
                else:
                    with connection() as db:
                        asset = get_media_item(db, asset_id)
            except Exception as e:
                return SkillExecutionResult(
                    skill_name=self.name,
                    skill_version=self.version,
                    status=SkillExecutionStatus.FAILED,
                    outputs={},
                    errors=[f"Database lookup failed for asset '{asset_id}': {str(e)}"],
                )

            if not asset and not media_dict and not url:
                return SkillExecutionResult(
                    skill_name=self.name,
                    skill_version=self.version,
                    status=SkillExecutionStatus.FAILED,
                    outputs={},
                    errors=[f"Asset with ID '{asset_id}' not found in Setowa media library."],
                )

        # 2. Direct media payload fallback
        if not asset and isinstance(media_dict, dict):
            asset = media_dict

        # 3. Direct URL fallback
        if not asset and url:
            # Infer media type and format from URL
            clean_url = url.split("?")[0].lower()
            is_video = any(clean_url.endswith(ext) for ext in (".mp4", ".webm", ".mov", ".m4v"))
            fmt = clean_url.split(".")[-1] if "." in clean_url else "unknown"
            asset = {
                "media_type": "video" if is_video else "image",
                "format": fmt,
                "secure_url": url,
                "thumbnail_url": url,
                "preview_url": url,
                "processing_status": "ready",
                "width": None,
                "height": None,
                "duration": None,
                "metadata": {"inferred_from_url": True},
            }

        # Build structured outputs
        width = asset.get("width")
        height = asset.get("height")
        dimensions = {"width": width, "height": height} if (width is not None or height is not None) else None

        outputs = {
            "media_type": asset.get("media_type", "image"),
            "format": asset.get("format", "unknown"),
            "dimensions": dimensions,
            "duration": asset.get("duration"),
            "secure_url": asset.get("secure_url", ""),
            "thumbnail_url": asset.get("thumbnail_url"),
            "preview_url": asset.get("preview_url"),
            "processing_status": asset.get("processing_status", "ready"),
            "metadata": asset.get("metadata", {}),
        }

        return SkillExecutionResult(
            skill_name=self.name,
            skill_version=self.version,
            status=SkillExecutionStatus.SUCCESS,
            outputs=outputs,
            evidence={
                "asset_id": asset.get("asset_id") or asset_id,
                "public_id": asset.get("public_id"),
                "source": asset.get("source"),
            },
            metadata={
                "provider": "setowa-deterministic",
                "media_type": outputs["media_type"],
            },
        )
