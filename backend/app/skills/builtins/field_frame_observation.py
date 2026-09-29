"""Structured visual observation skill for field video frames."""
import base64
import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

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


class FieldFrameObservationSkill(BaseSkill):
    """Analyzes a single video frame extracted from field evidence using structured visual intelligence."""

    def __init__(self, version: str = "1.0.0"):
        manifest = SkillManifest(
            name="field-frame-observation",
            version=version,
            description="Structured visual observation and signal detection on extracted field video frames.",
            kind="visual-analysis",
            permissions=["media:read", "ai:inference"],
            model={"provider": "gemini"},
            inputs=[
                SkillInputDefinition(
                    name="frame_url",
                    type="string",
                    description="Cloudinary delivery URL of extracted video frame",
                    required=True,
                ),
                SkillInputDefinition(
                    name="timestamp_seconds",
                    type="number",
                    description="Timestamp offset within source video in seconds",
                    required=False,
                    default=0.0,
                ),
                SkillInputDefinition(
                    name="source_asset_id",
                    type="string",
                    description="Asset ID of source video in Setowa database",
                    required=False,
                    default=None,
                ),
                SkillInputDefinition(
                    name="prompt",
                    type="string",
                    description="Optional custom focus prompt for observation",
                    required=False,
                    default=None,
                ),
            ],
            outputs=[
                SkillOutputDefinition(
                    name="observations",
                    type="array",
                    description="Concise visual observations describing terrain, visible objects, and cleanup status",
                ),
                SkillOutputDefinition(
                    name="detected_signals",
                    type="array",
                    description="Detected signal tags (e.g., vegetation, debris, shoreline, litter, gravel, water)",
                ),
                SkillOutputDefinition(
                    name="status",
                    type="string",
                    description="Observation status enum: analyzed, uncertain, insufficient_evidence",
                ),
                SkillOutputDefinition(
                    name="confidence",
                    type="number",
                    description="Model certainty score between 0.0 and 1.0 (represents model certainty, NOT accuracy)",
                ),
                SkillOutputDefinition(
                    name="warnings",
                    type="array",
                    description="Visual quality warnings such as blur, glare, lighting, or occlusion",
                ),
            ],
            metadata={
                "author": "Setowa Core Team",
                "category": "Video Frame Intelligence",
                "documentation": "Analyzes extracted video frames adhering to Setowa uncertainty and non-fabrication principles.",
            },
        )
        super().__init__(manifest)

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: Dict[str, Any],
    ) -> SkillExecutionResult:
        frame_url = inputs.get("frame_url")
        timestamp_seconds = float(inputs.get("timestamp_seconds") or 0.0)
        source_asset_id = inputs.get("source_asset_id")
        user_prompt = inputs.get("prompt")

        if not frame_url:
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.INVALID_INPUT,
                outputs={},
                errors=["'frame_url' is required."],
            )

        evidence_meta = {
            "frame_url": frame_url,
            "timestamp_seconds": timestamp_seconds,
            "source_asset_id": source_asset_id,
        }

        # 1. Synthetic sample walkthrough handling
        if frame_url.startswith("/demo/sample-media/"):
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.SUCCESS,
                outputs={
                    "observations": ["Walkthrough sample frame showing riverbank gravel bar with mixed organic debris."],
                    "detected_signals": ["riverbank", "gravel", "organic_debris", "vegetation"],
                    "status": "analyzed",
                    "confidence": 0.85,
                    "warnings": ["Synthetic walkthrough evidence — local demonstration only."],
                },
                evidence=evidence_meta,
                metadata={
                    "provider": "synthetic-demo",
                    "timestamp": timestamp_seconds,
                    "confidence_disclaimer": "Model confidence represents self-assessed certainty, not benchmarked factual accuracy.",
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
                    "observations": ["Frame analysis unavailable: GEMINI_API_KEY is not configured."],
                    "detected_signals": [],
                    "status": "insufficient_evidence",
                    "confidence": 0.0,
                    "warnings": ["provider_unavailable: Gemini API key required for live AI frame observation."],
                },
                evidence=evidence_meta,
                metadata={
                    "provider": "gemini-vision",
                    "status": "unavailable",
                    "timestamp": timestamp_seconds,
                },
                warnings=["AI inference provider not configured."],
            )

        # 3. Retrieve frame image bytes and call Gemini multimodal API
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(frame_url)
                if resp.status_code != 200:
                    return SkillExecutionResult(
                        skill_name=self.name,
                        skill_version=self.version,
                        status=SkillExecutionStatus.FAILED,
                        outputs={},
                        errors=[f"Failed to fetch frame image from URL (HTTP {resp.status_code})"],
                        evidence=evidence_meta,
                    )
                data = resp.content
                if len(data) > MAX_BYTES:
                    return SkillExecutionResult(
                        skill_name=self.name,
                        skill_version=self.version,
                        status=SkillExecutionStatus.FAILED,
                        outputs={},
                        errors=["Frame image exceeds maximum allowed size (10 MiB)."],
                        evidence=evidence_meta,
                    )
                b64_data = base64.b64encode(data).decode("ascii")

                prompt = (
                    "Analyze this single video frame captured from field environmental cleanup evidence.\n"
                    "Rules:\n"
                    "1. Describe visible environmental features, terrain, and cleanup evidence in one or two concise sentences.\n"
                    "2. Identify observable signal tags (e.g., vegetation, soil, water, litter, plastic, construction, shoreline, gravel, debris).\n"
                    "3. Do not infer hidden activities, elapsed time, or quantitative weights/counts.\n"
                    "4. Note any visual quality issues (blur, glare, occlusion).\n"
                    "5. Output is a proposal for human review.\n\n"
                    "Return JSON with:\n"
                    "- observations: list of concise strings describing what is visible\n"
                    "- detected_signals: list of short signal tags\n"
                    "- status: 'analyzed' | 'uncertain' | 'insufficient_evidence'\n"
                    "- confidence: float between 0.0 and 1.0\n"
                    "- warnings: list of string warnings (or empty list)"
                )
                if user_prompt:
                    prompt += f"\nAdditional focus: {user_prompt}"

                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64_data}},
                        ]
                    }],
                    "generationConfig": {"responseMimeType": "application/json"},
                }

                # Try active vision models with automatic fallback
                models_to_try = [settings.GEMINI_VISION_MODEL or "gemini-3.8-flash", "gemini-3.8-flash", "gemini-flash-latest"]
                seen_models = set()
                gemini_resp = None
                used_model = settings.GEMINI_VISION_MODEL or "gemini-3.8-flash"

                for model in models_to_try:
                    if not model or model in seen_models:
                        continue
                    seen_models.add(model)
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    try:
                        r = await client.post(url, headers={"x-goog-api-key": gemini_key}, json=payload)
                        if r.status_code == 200:
                            gemini_resp = r
                            used_model = model
                            break
                        else:
                            logger.info(f"Gemini model {model} returned HTTP {r.status_code}; trying next model.")
                            gemini_resp = r
                            continue
                    except Exception:
                        logger.warning("Error calling Gemini model %s.", model)
                        continue

                if not gemini_resp or gemini_resp.status_code != 200:
                    status_code = gemini_resp.status_code if gemini_resp else "timeout"
                    return SkillExecutionResult(
                        skill_name=self.name,
                        skill_version=self.version,
                        status=SkillExecutionStatus.FAILED,
                        outputs={},
                        errors=[f"Gemini inference call failed (status {status_code})."],
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

                parsed = json.loads(raw_text)

                observations = parsed.get("observations") or []
                if isinstance(observations, str):
                    observations = [observations]
                detected_signals = parsed.get("detected_signals") or []
                status_val = parsed.get("status") or "analyzed"
                raw_conf = parsed.get("confidence")
                conf_val = float(raw_conf) if raw_conf is not None else 0.8
                conf_val = max(0.0, min(1.0, conf_val))
                warnings_list = parsed.get("warnings") or []

                return SkillExecutionResult(
                    skill_name=self.name,
                    skill_version=self.version,
                    status=SkillExecutionStatus.SUCCESS,
                    outputs={
                        "observations": observations,
                        "detected_signals": detected_signals,
                        "status": status_val,
                        "confidence": conf_val,
                        "warnings": warnings_list,
                    },
                    evidence=evidence_meta,
                    metadata={
                        "provider": f"gemini-multimodal ({used_model})",
                        "timestamp": timestamp_seconds,
                        "confidence_disclaimer": "Model confidence represents self-assessed certainty, not benchmarked factual accuracy.",
                    },
                )
        except Exception as exc:
            return SkillExecutionResult(
                skill_name=self.name,
                skill_version=self.version,
                status=SkillExecutionStatus.FAILED,
                outputs={},
                errors=[f"Field frame observation failed: {str(exc)}"],
                evidence=evidence_meta,
            )
