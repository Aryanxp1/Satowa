"""Structured AI media intelligence skill for Setowa media assets and frames (T016)."""
import base64
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from app.config import settings
from app.services.media import MAX_BYTES
from app.skills.loader import BaseSkill
from app.skills.models import (
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillInputDefinition,
    SkillManifest,
    SkillOutputDefinition,
)

logger = logging.getLogger(__name__)

# Controlled taxonomy for grounded environmental and field media classification
CONTROLLED_TAGS = {
    "vegetation",
    "water",
    "sediment",
    "debris",
    "road",
    "construction",
    "waste",
    "people",
    "animals",
    "flooding",
    "cleanup",
    "damage",
    "soil",
    "plastic",
    "gravel",
    "shoreline",
    "machinery",
    "building",
    "sky",
}

CONTROLLED_SIGNALS = {
    "vegetation_cover",
    "standing_water",
    "flowing_water",
    "debris_accumulation",
    "visible_waste",
    "surface_erosion",
    "soil_disturbance",
    "structural_damage",
    "active_cleanup",
    "vehicle_presence",
    "human_presence",
    "animal_presence",
    "flood_water",
    "clear_ground",
}


def normalize_tag(tag: str) -> str:
    """Normalize a tag string to lowercase snake_case."""
    return tag.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_tags(raw_tags: List[str]) -> List[str]:
    """Normalize and deduplicate tags, prioritizing controlled taxonomy while preserving unknowns."""
    canonical: List[str] = []
    extended: List[str] = []
    for t in raw_tags:
        if not isinstance(t, str):
            continue
        norm = normalize_tag(t)
        if not norm:
            continue
        if norm in CONTROLLED_TAGS:
            if norm not in canonical:
                canonical.append(norm)
        else:
            if norm not in extended and norm not in canonical:
                extended.append(norm)
    return canonical + extended


def normalize_signals(raw_signals: List[str]) -> List[str]:
    """Normalize and deduplicate visual signals against controlled signals taxonomy."""
    results: List[str] = []
    for s in raw_signals:
        if not isinstance(s, str):
            continue
        norm = normalize_tag(s)
        if not norm:
            continue
        if norm not in results:
            results.append(norm)
    return results


class MediaIntelligenceSkill(BaseSkill):
    """Extracts structured visual intelligence, controlled tags, signals, and grounded observations."""

    def __init__(self, version: str = "1.0.0"):
        manifest = SkillManifest(
            name="media-intelligence",
            version=version,
            description="Extracts structured visual intelligence, controlled tags, detected signals, activity, and grounded observations from field media assets or frames.",
            kind="visual-analysis",
            permissions=["media:read", "ai:inference"],
            model={"provider": "gemini"},
            inputs=[
                SkillInputDefinition(
                    name="media_url",
                    type="string",
                    description="Cloudinary delivery URL of image or extracted video frame",
                    required=False,
                    default=None,
                ),
                SkillInputDefinition(
                    name="asset_id",
                    type="string",
                    description="Asset ID in Setowa database",
                    required=False,
                    default=None,
                ),
                SkillInputDefinition(
                    name="frame_id",
                    type="string",
                    description="Optional video frame ID if analyzing a specific video frame",
                    required=False,
                    default=None,
                ),
                SkillInputDefinition(
                    name="context",
                    type="string",
                    description="Optional contextual metadata or user focus instructions",
                    required=False,
                    default=None,
                ),
            ],
            outputs=[
                SkillOutputDefinition(
                    name="description",
                    type="string",
                    description="Concise 1-2 sentence factual description of visual evidence",
                ),
                SkillOutputDefinition(
                    name="observations",
                    type="array",
                    description="Discrete observable visual features distinguishing OBSERVED vs INFERRED",
                ),
                SkillOutputDefinition(
                    name="tags",
                    type="array",
                    description="Controlled tags taxonomy (vegetation, water, sediment, debris, waste, etc.)",
                ),
                SkillOutputDefinition(
                    name="detected_signals",
                    type="array",
                    description="Detected visual signals (e.g. vegetation_cover, visible_waste, active_cleanup)",
                ),
                SkillOutputDefinition(
                    name="activity",
                    type="string",
                    description="Primary observable activity classification or null",
                ),
                SkillOutputDefinition(
                    name="status",
                    type="string",
                    description="Analysis status: analyzed, uncertain, insufficient_evidence",
                ),
                SkillOutputDefinition(
                    name="warnings",
                    type="array",
                    description="Visual quality warnings (blur, occlusion, poor_lighting, low_evidence)",
                ),
                SkillOutputDefinition(
                    name="uncertainty",
                    type="string",
                    description="Explanation of visual ambiguity or unverified conditions",
                ),
                SkillOutputDefinition(
                    name="evidence",
                    type="object",
                    description="Provenance metadata linking result to source media and timestamp",
                ),
                SkillOutputDefinition(
                    name="model_name",
                    type="string",
                    description="Model identifier used for inference",
                ),
                SkillOutputDefinition(
                    name="model_provider",
                    type="string",
                    description="Model provider name (e.g., gemini)",
                ),
            ],
            metadata={
                "author": "Setowa Core Team",
                "category": "Media Intelligence",
                "documentation": "Structured, grounded visual intelligence for field environmental media adhering to non-fabrication principles.",
            },
        )
        super().__init__(manifest)

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: Dict[str, Any],
    ) -> SkillExecutionResult:
        media_url = inputs.get("media_url")
        asset_id = inputs.get("asset_id")
        frame_id = inputs.get("frame_id")
        context_notes = inputs.get("context")

        if not media_url:
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.INVALID_INPUT,
                outputs={},
                errors=["'media_url' is required."],
            )

        evidence_meta = {
            "source_url": media_url,
            "asset_id": asset_id,
            "frame_id": frame_id,
        }

        # 1. Synthetic sample walkthrough handling
        if media_url.startswith("/demo/sample-media/") or "synthetic" in media_url.lower():
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.SUCCESS,
                outputs={
                    "description": "Field cleanup evidence photograph showing riverbank terrain with mixed debris and shoreline vegetation.",
                    "observations": [
                        "OBSERVED: Riverbank terrain composed of mixed gravel and sediment.",
                        "OBSERVED: Visible organic and inorganic debris along the water boundary.",
                        "INFERRED: Active field cleanup or monitoring zone.",
                    ],
                    "tags": ["vegetation", "water", "sediment", "debris", "cleanup", "shoreline"],
                    "detected_signals": ["vegetation_cover", "standing_water", "debris_accumulation", "active_cleanup"],
                    "activity": "debris cleanup",
                    "status": "analyzed",
                    "warnings": ["Synthetic walkthrough evidence — local demonstration mode."],
                    "uncertainty": None,
                    "evidence": evidence_meta,
                    "model_name": "synthetic-demo",
                    "model_provider": "setowa-internal",
                },
                metadata={
                    "provider": "synthetic-demo",
                    "status": "analyzed",
                    "confidence_disclaimer": "Synthetic demonstration mode. Not benchmarked real-world accuracy.",
                },
            )

        # 2. Check Gemini credentials
        gemini_key = None
        if settings.GEMINI_API_KEY:
            gemini_key = (
                settings.GEMINI_API_KEY.get_secret_value()
                if hasattr(settings.GEMINI_API_KEY, "get_secret_value")
                else str(settings.GEMINI_API_KEY)
            )
        if not gemini_key:
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.UNAVAILABLE,
                outputs={
                    "description": "AI media intelligence unavailable: GEMINI_API_KEY is not configured.",
                    "observations": [],
                    "tags": [],
                    "detected_signals": [],
                    "activity": None,
                    "status": "unavailable",
                    "warnings": ["provider_unavailable: Gemini API key required for live AI media intelligence."],
                    "uncertainty": "Gemini API key is not configured.",
                    "evidence": evidence_meta,
                    "model_name": "unavailable",
                    "model_provider": "gemini",
                },
                metadata={
                    "provider": "gemini",
                    "status": "unavailable",
                },
                warnings=["AI inference provider not configured."],
            )

        # 3. Retrieve media image bytes and invoke Gemini multimodal vision
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(media_url)
                if resp.status_code != 200:
                    return SkillExecutionResult(
                        skill_name=self.name,
                        skill_version=self.version,
                        status=SkillExecutionStatus.FAILED,
                        outputs={},
                        errors=[f"Failed to fetch media from URL (HTTP {resp.status_code})."],
                        evidence=evidence_meta,
                    )
                data = resp.content
                if len(data) > MAX_BYTES:
                    return SkillExecutionResult(
                        skill_name=self.name,
                        skill_version=self.version,
                        status=SkillExecutionStatus.FAILED,
                        outputs={},
                        errors=["Media exceeds maximum allowed size (10 MiB)."],
                        evidence=evidence_meta,
                    )

                # Determine MIME type
                mime_type = "image/jpeg"
                if data.startswith(b"\x89PNG\r\n\x1a\n"):
                    mime_type = "image/png"
                elif data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"WEBP":
                    mime_type = "image/webp"

                b64_data = base64.b64encode(data).decode("ascii")

                prompt = (
                    "You are an expert environmental visual intelligence analyzer for SETOWA.\n"
                    "Analyze this field evidence image or extracted video frame.\n\n"
                    "GROUNDING AND INTEGRITY RULES:\n"
                    "1. Distinguish strictly between OBSERVED (directly visible), INFERRED (probable visual context), and UNKNOWN.\n"
                    "2. DO NOT fabricate or guess exact locations, exact object counts, weight metrics (e.g. kg/tons/bags), or unverified facts.\n"
                    "3. Select relevant tags from this controlled taxonomy: vegetation, water, sediment, debris, road, construction, waste, people, animals, flooding, cleanup, damage, soil, plastic, gravel, shoreline, machinery, building. If an unrecognized concept is clearly visible, preserve it as an additional tag.\n"
                    "4. Detect visual signals from: vegetation_cover, standing_water, flowing_water, debris_accumulation, visible_waste, surface_erosion, soil_disturbance, structural_damage, active_cleanup, vehicle_presence, human_presence, animal_presence, flood_water, clear_ground.\n"
                    "5. Classify observable primary activity if any (e.g., 'debris cleanup', 'site inspection', 'flood assessment', 'idle site', 'natural terrain'). If unknown or ambiguous, return null.\n"
                    "6. State status honestly:\n"
                    "   - 'analyzed': visual evidence is clear and conclusive\n"
                    "   - 'uncertain': visual evidence is ambiguous, borderline, or conflicting\n"
                    "   - 'insufficient_evidence': image is too blurry, dark, occluded, or low-resolution\n"
                    "7. Note any visual warnings: blur, occlusion, poor_lighting, low_visual_evidence, ambiguous_scene.\n"
                    "8. Provide uncertainty explanation if status is uncertain or insufficient_evidence, else null.\n"
                    "9. Provide a concise 1-2 sentence factual description.\n\n"
                    "Output MUST be valid JSON adhering to:\n"
                    "{\n"
                    '  "description": "string",\n'
                    '  "observations": ["string"],\n'
                    '  "tags": ["string"],\n'
                    '  "detected_signals": ["string"],\n'
                    '  "activity": "string or null",\n'
                    '  "status": "analyzed | uncertain | insufficient_evidence",\n'
                    '  "warnings": ["string"],\n'
                    '  "uncertainty": "string or null"\n'
                    "}"
                )
                if context_notes:
                    prompt += f"\nAdditional Context: {context_notes}"

                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": mime_type, "data": b64_data}},
                        ]
                    }],
                    "generationConfig": {"responseMimeType": "application/json"},
                }

                models_to_try = [settings.GEMINI_VISION_MODEL or "gemini-3.8-flash", "gemini-3.8-flash", "gemini-flash-latest"]
                seen_models = set()
                gemini_resp = None
                used_model = settings.GEMINI_VISION_MODEL or "gemini-3.8-flash"

                for model in models_to_try:
                    if not model or model in seen_models:
                        continue
                    seen_models.add(model)
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                    try:
                        r = await client.post(url, json=payload)
                        if r.status_code == 200:
                            gemini_resp = r
                            used_model = model
                            break
                        else:
                            logger.info(f"Gemini model {model} returned HTTP {r.status_code}; trying next model.")
                            gemini_resp = r
                            continue
                    except Exception as net_err:
                        logger.warning(f"Error calling Gemini model {model}: {net_err}")
                        continue

                if not gemini_resp or gemini_resp.status_code != 200:
                    status_code = gemini_resp.status_code if gemini_resp else "timeout"
                    error_detail = "API call timed out or failed to reach provider"
                    if gemini_resp:
                        try:
                            err_json = gemini_resp.json()
                            error_detail = err_json.get("error", {}).get("message", f"HTTP {status_code}")
                        except Exception:
                            error_detail = f"HTTP {status_code}"

                    return SkillExecutionResult(
                        skill_name=self.name,
                        skill_version=self.version,
                        status=SkillExecutionStatus.FAILED,
                        outputs={
                            "description": f"AI analysis failed: Gemini error ({status_code}).",
                            "observations": [],
                            "tags": [],
                            "detected_signals": [],
                            "activity": None,
                            "status": "failed",
                            "warnings": [f"provider_error: {error_detail}"],
                            "uncertainty": "Inference failed due to provider error.",
                            "evidence": evidence_meta,
                            "model_name": used_model,
                            "model_provider": "gemini",
                        },
                        errors=[f"Gemini inference call failed ({status_code}): {error_detail}"],
                        evidence=evidence_meta,
                    )

                body = gemini_resp.json()
                parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                raw_text = "".join(part.get("text", "") for part in parts).strip()
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines and lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_text = "\n".join(lines).strip()

                try:
                    parsed = json.loads(raw_text)
                except Exception as parse_err:
                    logger.warning(f"Failed to parse Gemini JSON output: {parse_err}. Raw text: {raw_text[:200]}")
                    return SkillExecutionResult(
                        skill_name=self.name,
                        skill_version=self.version,
                        status=SkillExecutionStatus.SUCCESS,
                        outputs={
                            "description": "Visual analysis produced unparseable response.",
                            "observations": ["Model output could not be parsed as valid JSON."],
                            "tags": [],
                            "detected_signals": [],
                            "activity": None,
                            "status": "uncertain",
                            "warnings": ["malformed_model_response"],
                            "uncertainty": "AI model output was malformed; manual review required.",
                            "evidence": evidence_meta,
                            "model_name": used_model,
                            "model_provider": "gemini",
                        },
                        evidence=evidence_meta,
                    )

                description = str(parsed.get("description") or "Field media visual assessment.")
                observations = parsed.get("observations") or []
                if isinstance(observations, str):
                    observations = [observations]
                raw_tags = parsed.get("tags") or []
                if isinstance(raw_tags, str):
                    raw_tags = [raw_tags]
                tags = normalize_tags(raw_tags)

                raw_signals = parsed.get("detected_signals") or []
                if isinstance(raw_signals, str):
                    raw_signals = [raw_signals]
                detected_signals = normalize_signals(raw_signals)

                activity = parsed.get("activity")
                if activity and not isinstance(activity, str):
                    activity = str(activity)

                status_val = parsed.get("status") or "analyzed"
                if status_val not in ("analyzed", "uncertain", "insufficient_evidence"):
                    status_val = "uncertain"

                warnings_list = parsed.get("warnings") or []
                if isinstance(warnings_list, str):
                    warnings_list = [warnings_list]

                uncertainty_val = parsed.get("uncertainty")
                if uncertainty_val and not isinstance(uncertainty_val, str):
                    uncertainty_val = str(uncertainty_val)

                return SkillExecutionResult(
                    skill_name=self.name,
                    skill_version=self.version,
                    status=SkillExecutionStatus.SUCCESS,
                    outputs={
                        "description": description,
                        "observations": observations,
                        "tags": tags,
                        "detected_signals": detected_signals,
                        "activity": activity,
                        "status": status_val,
                        "warnings": warnings_list,
                        "uncertainty": uncertainty_val,
                        "evidence": evidence_meta,
                        "model_name": used_model,
                        "model_provider": "gemini",
                    },
                    evidence=evidence_meta,
                    metadata={
                        "provider": f"gemini ({used_model})",
                        "status": status_val,
                        "confidence_disclaimer": "Model confidence represents self-assessed certainty, not benchmarked factual accuracy.",
                    },
                )
        except Exception as exc:
            logger.exception(f"Unhandled error in MediaIntelligenceSkill: {exc}")
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.FAILED,
                outputs={
                    "description": f"AI media intelligence failed: {str(exc)}",
                    "observations": [],
                    "tags": [],
                    "detected_signals": [],
                    "activity": None,
                    "status": "failed",
                    "warnings": [f"execution_error: {type(exc).__name__}"],
                    "uncertainty": "Execution failed due to internal error.",
                    "evidence": evidence_meta,
                    "model_name": "unknown",
                    "model_provider": "gemini",
                },
                errors=[f"Media intelligence execution error: {str(exc)}"],
                evidence=evidence_meta,
            )
