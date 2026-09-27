"""Visual intelligence evidence comparison skill."""
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
from app.services.image_comparison import compare_images


class EvidenceComparisonSkill(BaseSkill):
    """Compares before and after environmental cleanup media using structured visual intelligence."""

    def __init__(self, version: str = "1.0.0"):
        manifest = SkillManifest(
            name="evidence-comparison",
            version=version,
            description="Compare before and after environmental cleanup media using structured visual intelligence.",
            kind="visual-analysis",
            permissions=["media:read", "ai:inference"],
            model={"provider": "gemini"},
            inputs=[
                SkillInputDefinition(
                    name="before_url",
                    type="string",
                    description="Cloudinary URL for before-cleanup evidence photo",
                    required=False,
                ),
                SkillInputDefinition(
                    name="after_url",
                    type="string",
                    description="Cloudinary URL for after-cleanup evidence photo",
                    required=False,
                ),
                SkillInputDefinition(
                    name="before_asset_id",
                    type="string",
                    description="Asset ID of before-cleanup photo in Setowa database",
                    required=False,
                ),
                SkillInputDefinition(
                    name="after_asset_id",
                    type="string",
                    description="Asset ID of after-cleanup photo in Setowa database",
                    required=False,
                ),
                SkillInputDefinition(
                    name="prompt",
                    type="string",
                    description="Optional custom comparison prompt",
                    required=False,
                    default=None,
                ),
            ],
            outputs=[
                SkillOutputDefinition(name="status", type="string", description="Result enum: changed, unchanged, uncertain, insufficient_evidence"),
                SkillOutputDefinition(name="summary", type="string", description="Concise description of visible differences"),
                SkillOutputDefinition(name="changes", type="array", description="Structured visual changes supported by evidence"),
                SkillOutputDefinition(name="confidence", type="number", description="Model certainty score between 0.0 and 1.0 (NOT accuracy)"),
                SkillOutputDefinition(name="uncertainty_reason", type="string", description="Reason when uncertain or insufficient evidence"),
                SkillOutputDefinition(name="evidence_notes", type="string", description="Technical framing or overlap notes"),
            ],
            metadata={
                "author": "Setowa Core Team",
                "category": "Evidence Verification",
                "documentation": "Structured before/after comparison adhering to Setowa trust and uncertainty rules.",
            },
        )
        super().__init__(manifest)

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: Dict[str, Any]
    ) -> SkillExecutionResult:
        before_url = inputs.get("before_url")
        after_url = inputs.get("after_url")
        before_asset_id = inputs.get("before_asset_id")
        after_asset_id = inputs.get("after_asset_id")
        prompt = inputs.get("prompt")

        # Resolve asset IDs from database if provided
        if not before_url and before_asset_id:
            try:
                db_conn = context.get("db")
                if db_conn is not None:
                    asset = get_media_item(db_conn, before_asset_id)
                else:
                    with connection() as db:
                        asset = get_media_item(db, before_asset_id)
                if asset:
                    before_url = asset.get("secure_url")
            except Exception as e:
                return SkillExecutionResult(
                    skill_name=self.name,
                    skill_version=self.version,
                    status=SkillExecutionStatus.FAILED,
                    outputs={},
                    errors=[f"Failed to resolve before_asset_id '{before_asset_id}': {str(e)}"],
                )

        if not after_url and after_asset_id:
            try:
                db_conn = context.get("db")
                if db_conn is not None:
                    asset = get_media_item(db_conn, after_asset_id)
                else:
                    with connection() as db:
                        asset = get_media_item(db, after_asset_id)
                if asset:
                    after_url = asset.get("secure_url")
            except Exception as e:
                return SkillExecutionResult(
                    skill_name=self.name,
                    skill_version=self.version,
                    status=SkillExecutionStatus.FAILED,
                    outputs={},
                    errors=[f"Failed to resolve after_asset_id '{after_asset_id}': {str(e)}"],
                )

        if not before_url or not after_url:
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.INVALID_INPUT,
                outputs={},
                errors=["Both 'before' and 'after' media URLs or asset IDs must be provided."],
            )

        # Execute structured comparison using the core image_comparison service
        try:
            before_fmt = before_url.split(".")[-1].split("?")[0].lower() if "." in before_url else "jpg"
            after_fmt = after_url.split(".")[-1].split("?")[0].lower() if "." in after_url else "jpg"
            before_asset = {"secure_url": before_url, "format": before_fmt}
            after_asset = {"secure_url": after_url, "format": after_fmt}

            comparison = await compare_images(before_asset, after_asset)
            outputs = {
                "status": comparison.status.value if hasattr(comparison.status, "value") else str(comparison.status),
                "summary": comparison.summary,
                "changes": [c.model_dump() if hasattr(c, "model_dump") else c for c in comparison.changes],
                "confidence": comparison.confidence,
                "uncertainty_reason": comparison.uncertainty_reason,
                "evidence_notes": comparison.evidence_notes,
            }

            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.SUCCESS,
                outputs=outputs,
                evidence={
                    "before_url": before_url,
                    "after_url": after_url,
                    "before_asset_id": before_asset_id,
                    "after_asset_id": after_asset_id,
                },
                metadata={
                    "provider": "gemini-multimodal",
                    "comparison_status": outputs["status"],
                    "confidence_disclaimer": "Model confidence represents self-assessed certainty, not benchmarked factual accuracy.",
                },
            )
        except Exception as exc:
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.FAILED,
                outputs={},
                errors=[f"Visual evidence comparison failed: {str(exc)}"],
            )
