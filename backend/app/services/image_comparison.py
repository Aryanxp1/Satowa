"""Structured two-image Gemini comparison with explicit uncertainty handling.

Invariants:
- AI is a proposal engine, never an authoritative decider.
- Human review is strictly mandatory before an observation is approved.
- Status is 4-state: changed, unchanged, uncertain, insufficient_evidence.
- Model confidence is bounded [0.0, 1.0] and represents model certainty, NOT factual accuracy.
- Unverified quantitative impact claims (weights, counts, percentages) are rejected.
- Provider errors, invalid schemas, or malformed JSON return safe uncertain/insufficient_evidence results.
"""
import base64
import json
import re
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.config import settings
from app.schemas.api import (
    ComparisonStatus,
    StructuredComparison,
    UncertaintyReason,
    VisualChange,
)
from app.services.media import MAX_BYTES


QUANTITATIVE_CLAIM_PATTERN = re.compile(
    r'(?:\b\d+(?:\.\d+)?\s*(?:kg|kilograms?|tonnes?|tons?|percent|bags?|items?|lbs?|pounds?)\b|\b\d+(?:\.\d+)?\s*%)',
    re.I
)


class Comparison(StructuredComparison):
    """Structured AI comparison proposal result."""
    pass


def unavailable(
    reason: str,
    status: ComparisonStatus = ComparisonStatus.INSUFFICIENT_EVIDENCE,
    uncertainty_reason: str | None = None,
    confidence: float | None = 0.0,
) -> Comparison:
    """Safe fallback factory when comparison cannot be reliably performed."""
    return Comparison(
        status=status,
        summary=None,
        changes=[],
        confidence=confidence,
        uncertainty_reason=uncertainty_reason or reason,
        evidence_notes=reason,
        reliable=False,
        observation=None,
        reason=reason,
    )


async def _image_bytes(client, asset):
    parsed = urlparse(asset['secure_url'])
    expected = f'/'+settings.CLOUDINARY_CLOUD_NAME+'/image/upload/'
    if parsed.scheme != 'https' or parsed.netloc != 'res.cloudinary.com' or not parsed.path.startswith(expected):
        raise ValueError('Evidence URL is not a trusted Cloudinary image')
    data = bytearray()
    async with client.stream('GET', asset['secure_url'], follow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError('Evidence could not be retrieved')
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ValueError('Evidence exceeds image size limit')
    if not data:
        raise ValueError('Evidence is empty')
    return base64.b64encode(data).decode('ascii')


async def compare_images(before, after) -> Comparison:
    if before['secure_url'].startswith('/demo/sample-media/') or after['secure_url'].startswith('/demo/sample-media/'):
        return unavailable(
            'Synthetic sample photos are for a local walkthrough only. Inspect them and write a manual observation; no AI comparison was run.',
            status=ComparisonStatus.INSUFFICIENT_EVIDENCE,
            uncertainty_reason='synthetic_walkthrough_evidence',
        )
    if settings.AI_PROVIDER == 'nvidia':
        # The selected vision model's two-image behavior has not been live-validated.
        # Single-image intelligence is available separately; do not synthesize a pair verdict.
        return unavailable(
            'Automatic pair comparison is not enabled for NVIDIA. Analyze each photo in Intelligence, then write and review a manual comparison.',
            uncertainty_reason='pair_model_not_validated',
        )
    if not settings.GEMINI_API_KEY:
        return unavailable(
            'AI comparison is unavailable until GEMINI_API_KEY is configured. A reviewer may write an observation manually.',
            status=ComparisonStatus.INSUFFICIENT_EVIDENCE,
            uncertainty_reason='provider_unavailable',
        )
    prompt = (
        "Compare BEFORE image first with AFTER image second for one cleanup site.\n"
        "Rules:\n"
        "1. Compare only the supplied visual evidence.\n"
        "2. Describe visible differences only in one or two concise sentences.\n"
        "3. Do not infer hidden events, elapsed time, cause, or work performed.\n"
        "4. Do not invent measurements, weights, percentages, or counts.\n"
        "5. Do not claim certainty when viewpoints, lighting, or framing differ.\n"
        "6. If evidence is inadequate or viewpoints differ, use status 'uncertain' or 'insufficient_evidence'.\n"
        "7. All output is a proposal subject to mandatory human verification.\n\n"
        "Return JSON with exactly:\n"
        "- status: 'changed' | 'unchanged' | 'uncertain' | 'insufficient_evidence'\n"
        "- summary: string or null\n"
        "- changes: list of {type: string, description: string, evidence: string or null}\n"
        "- confidence: float between 0.0 and 1.0\n"
        "- uncertainty_reason: string or null (e.g. camera_angle_mismatch, lighting_difference, partial_occlusion, insufficient_visual_overlap, poor_image_quality, relevant_area_not_visible, incompatible_framing)\n"
        "- evidence_notes: string or null"
    )
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            before_data = await _image_bytes(client, before)
            after_data = await _image_bytes(client, after)
            payload = {'contents': [{'parts': [
                {'text': prompt},
                {'inline_data': {'mime_type': 'image/'+('jpeg' if before['format']=='jpg' else before['format']), 'data': before_data}},
                {'inline_data': {'mime_type': 'image/'+('jpeg' if after['format']=='jpg' else after['format']), 'data': after_data}},
            ]}], 'generationConfig': {'responseMimeType': 'application/json'}}
            response = await client.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_VISION_MODEL}:generateContent',
                headers={'x-goog-api-key': settings.GEMINI_API_KEY}, json=payload,
            )
            response.raise_for_status()
            parts = response.json()['candidates'][0]['content']['parts']
            raw_text = ''.join(part.get('text', '') for part in parts).strip()
            if raw_text.startswith('```'):
                lines = raw_text.splitlines()
                if lines and lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                raw_text = '\n'.join(lines).strip()
            raw_json = json.loads(raw_text)
            result = Comparison.model_validate(raw_json)

            # Uncertain or insufficient evidence handling
            if result.status in (ComparisonStatus.UNCERTAIN, ComparisonStatus.INSUFFICIENT_EVIDENCE):
                return unavailable(
                    result.uncertainty_reason or result.evidence_notes or 'The images cannot be compared reliably.',
                    status=result.status,
                    uncertainty_reason=result.uncertainty_reason,
                    confidence=result.confidence,
                )

            # Observation text check
            text = (result.summary or result.observation or '').strip()
            if not text:
                return unavailable(
                    'The AI did not provide a supported observation.',
                    status=ComparisonStatus.UNCERTAIN,
                    uncertainty_reason=UncertaintyReason.POOR_IMAGE_QUALITY.value,
                    confidence=result.confidence,
                )

            # Check for unverified quantitative claims
            texts_to_check = [text]
            for change in result.changes:
                if change.type:
                    texts_to_check.append(change.type)
                if change.description:
                    texts_to_check.append(change.description)
                if change.evidence:
                    texts_to_check.append(change.evidence)

            if any(QUANTITATIVE_CLAIM_PATTERN.search(t) for t in texts_to_check):
                return unavailable(
                    'The AI proposed an unverified numerical impact claim.',
                    status=ComparisonStatus.UNCERTAIN,
                    uncertainty_reason=UncertaintyReason.UNVERIFIED_QUANTITATIVE_CLAIM.value,
                    confidence=result.confidence,
                )

            # Return validated comparison proposal
            return Comparison(
                status=result.status,
                summary=text,
                changes=result.changes,
                confidence=result.confidence if result.confidence is not None else 0.85,
                uncertainty_reason=None,
                evidence_notes=result.evidence_notes,
                reliable=True,
                observation=text,
                reason=None,
            )
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, ValidationError):
        return unavailable(
            'AI comparison failed or returned an invalid result. Review the images manually.',
            status=ComparisonStatus.UNCERTAIN,
            uncertainty_reason=UncertaintyReason.PROVIDER_ERROR.value,
        )
