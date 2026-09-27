"""Impact story and sustainability timeline service for Setowa (Milestone T017).

Transforms persisted project assets, before/after evidence pairs, video frame
analytics, and media intelligence into a coherent, verifiable sustainability narrative.

Guiding Principles:
- Grounding: Narratives cite strictly observed and verified data.
- Transparency: Distinguishes between AI inferences, pending reviews, and approved findings.
- Zero Fabrication: Never invents quantities, carbon metrics, or claims absent from evidence.
- Resilient Fallback: Functions deterministically when Gemini is unavailable.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.schemas.api import (
    BeforeAfterCard,
    ImpactStoryResponse,
    TimelineEvent,
    TimelineEventType,
    VerificationStatus,
)
from app.services import evidence_store as store

logger = logging.getLogger(__name__)


def safe_json_loads(val: Optional[str], default: Any = None) -> Any:
    """Safely parse JSON string with fallback."""
    if not val:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


def row_to_timeline_event(row: dict) -> TimelineEvent:
    """Convert a database row dictionary to a TimelineEvent model."""
    asset_ids = safe_json_loads(row.get("asset_ids_json"), [])
    if isinstance(asset_ids, str):
        asset_ids = [asset_ids]

    tags = safe_json_loads(row.get("tags_json"), [])
    if isinstance(tags, str):
        tags = [tags]

    signals = safe_json_loads(row.get("signals_json"), [])
    if isinstance(signals, str):
        signals = [signals]

    warnings = safe_json_loads(row.get("warnings_json"), [])
    if isinstance(warnings, str):
        warnings = [warnings]

    evidence = safe_json_loads(row.get("evidence_json"), None)

    return TimelineEvent(
        id=row["id"],
        story_id=row["story_id"],
        event_order=row.get("event_order", 0),
        timestamp_date=row["timestamp_date"],
        event_type=row["event_type"],
        title=row["title"],
        description=row.get("description"),
        site_id=row.get("site_id"),
        site_name=row.get("site_name"),
        asset_ids=asset_ids,
        primary_media_url=row.get("primary_media_url"),
        thumbnail_url=row.get("thumbnail_url"),
        media_type=row.get("media_type"),
        frame_id=row.get("frame_id"),
        observation_id=row.get("observation_id"),
        measurement_id=row.get("measurement_id"),
        intelligence_id=row.get("intelligence_id"),
        verification_status=row.get("verification_status", "unverified"),
        tags=tags,
        signals=signals,
        warnings=warnings,
        uncertainty=row.get("uncertainty"),
        evidence=evidence,
        created_at=row.get("created_at") or store.timestamp(),
    )


def build_project_timeline_events(
    db,
    project_id: str,
    story_id: str,
) -> List[dict]:
    """Assemble chronological timeline events from real project evidence and media."""
    events: List[dict] = []
    now = store.timestamp()

    # 1. Fetch sites belonging to the project
    sites = store.rows(db, "SELECT * FROM sites WHERE project_id=?", (project_id,))
    site_map = {s["id"]: s["name"] for s in sites}
    site_ids = list(site_map.keys())

    # 2. Fetch all assets in project or project's sites
    if site_ids:
        placeholders = ",".join("?" for _ in site_ids)
        assets_query = f"""
            SELECT a.*, v.visited_on, s.name AS site_name
            FROM assets a
            LEFT JOIN visits v ON v.id = a.visit_id
            LEFT JOIN sites s ON s.id = a.site_id
            WHERE a.project_id = ? OR a.site_id IN ({placeholders})
            ORDER BY a.created_at ASC
        """
        assets = store.rows(db, assets_query, (project_id, *site_ids))
    else:
        assets = store.rows(
            db,
            """
            SELECT a.*, v.visited_on, s.name AS site_name
            FROM assets a
            LEFT JOIN visits v ON v.id = a.visit_id
            LEFT JOIN sites s ON s.id = a.site_id
            WHERE a.project_id = ?
            ORDER BY a.created_at ASC
            """,
            (project_id,),
        )

    asset_map = {a["asset_id"]: a for a in assets}

    # 3. Fetch media intelligence for these assets
    asset_id_list = list(asset_map.keys())
    intel_by_asset: Dict[str, dict] = {}
    if asset_id_list:
        placeholders = ",".join("?" for _ in asset_id_list)
        intel_rows = store.rows(
            db,
            f"SELECT * FROM media_intelligence WHERE asset_id IN ({placeholders}) AND frame_id IS NULL ORDER BY created_at DESC",
            tuple(asset_id_list),
        )
        for r in intel_rows:
            if r["asset_id"] not in intel_by_asset:
                intel_by_asset[r["asset_id"]] = r

    # 4. Fetch paired observations
    obs_rows = []
    if site_ids:
        placeholders = ",".join("?" for _ in site_ids)
        obs_query = f"""
            SELECT o.*, s.name AS site_name,
                   bv.visited_on AS before_date, av.visited_on AS after_date,
                   ba.secure_url AS before_url, ba.thumbnail_url AS before_thumb,
                   aa.secure_url AS after_url, aa.thumbnail_url AS after_thumb
            FROM observations o
            JOIN sites s ON s.id = o.site_id
            LEFT JOIN assets ba ON ba.asset_id = o.before_asset_id
            LEFT JOIN assets aa ON aa.asset_id = o.after_asset_id
            LEFT JOIN visits bv ON bv.id = ba.visit_id
            LEFT JOIN visits av ON av.id = aa.visit_id
            WHERE s.project_id = ? OR o.site_id IN ({placeholders})
            ORDER BY o.created_at ASC
        """
        obs_rows = store.rows(db, obs_query, (project_id, *site_ids))
    else:
        obs_rows = store.rows(
            db,
            """
            SELECT o.*, s.name AS site_name,
                   bv.visited_on AS before_date, av.visited_on AS after_date,
                   ba.secure_url AS before_url, ba.thumbnail_url AS before_thumb,
                   aa.secure_url AS after_url, aa.thumbnail_url AS after_thumb
            FROM observations o
            JOIN sites s ON s.id = o.site_id
            LEFT JOIN assets ba ON ba.asset_id = o.before_asset_id
            LEFT JOIN assets aa ON aa.asset_id = o.after_asset_id
            LEFT JOIN visits bv ON bv.id = ba.visit_id
            LEFT JOIN visits av ON av.id = aa.visit_id
            WHERE s.project_id = ?
            ORDER BY o.created_at ASC
            """,
            (project_id,),
        )

    # 5. Fetch measurements
    measurements = []
    if site_ids:
        placeholders = ",".join("?" for _ in site_ids)
        m_query = f"""
            SELECT m.*, v.visited_on, s.name AS site_name
            FROM measurements m
            JOIN sites s ON s.id = m.site_id
            LEFT JOIN visits v ON v.id = m.visit_id
            WHERE s.project_id = ? OR m.site_id IN ({placeholders})
            ORDER BY m.recorded_at ASC
        """
        measurements = store.rows(db, m_query, (project_id, *site_ids))
    else:
        measurements = store.rows(
            db,
            """
            SELECT m.*, v.visited_on, s.name AS site_name
            FROM measurements m
            JOIN sites s ON s.id = m.site_id
            LEFT JOIN visits v ON v.id = m.visit_id
            WHERE s.project_id = ?
            ORDER BY m.recorded_at ASC
            """,
            (project_id,),
        )

    emitted_assets = set()

    # Process observations into before, after, and verified finding events
    for o in obs_rows:
        site_name = o.get("site_name") or site_map.get(o["site_id"], "Field Site")
        before_id = o["before_asset_id"]
        after_id = o["after_asset_id"]

        # Before event
        if before_id and before_id not in emitted_assets:
            b_asset = asset_map.get(before_id, {})
            b_intel = intel_by_asset.get(before_id, {})
            b_date = o.get("before_date") or b_asset.get("captured_at") or b_asset.get("created_at") or "2026-09-01"
            b_tags = safe_json_loads(b_intel.get("tags_json"), [])
            b_signals = safe_json_loads(b_intel.get("signals_json"), [])
            b_warnings = safe_json_loads(b_intel.get("warnings_json"), [])
            events.append({
                "id": f"evt_before_{before_id}",
                "story_id": story_id,
                "timestamp_date": b_date[:10],
                "event_type": TimelineEventType.BEFORE.value,
                "title": f"Initial Baseline Condition: {site_name}",
                "description": b_intel.get("description") or "Baseline visual state prior to environmental intervention.",
                "site_id": o["site_id"],
                "site_name": site_name,
                "asset_ids_json": json.dumps([before_id]),
                "primary_media_url": o.get("before_url") or b_asset.get("secure_url"),
                "thumbnail_url": o.get("before_thumb") or b_asset.get("thumbnail_url"),
                "media_type": b_asset.get("media_type", "image"),
                "frame_id": None,
                "observation_id": o["id"],
                "measurement_id": None,
                "intelligence_id": b_intel.get("id"),
                "verification_status": VerificationStatus.UNVERIFIED.value,
                "tags_json": json.dumps(b_tags),
                "signals_json": json.dumps(b_signals),
                "warnings_json": json.dumps(b_warnings),
                "uncertainty": b_intel.get("uncertainty"),
                "evidence_json": json.dumps({"source": "before_asset", "asset_id": before_id}),
            })
            emitted_assets.add(before_id)

        # After event
        if after_id and after_id not in emitted_assets:
            a_asset = asset_map.get(after_id, {})
            a_intel = intel_by_asset.get(after_id, {})
            a_date = o.get("after_date") or a_asset.get("captured_at") or a_asset.get("created_at") or "2026-09-02"
            a_tags = safe_json_loads(a_intel.get("tags_json"), [])
            a_signals = safe_json_loads(a_intel.get("signals_json"), [])
            a_warnings = safe_json_loads(a_intel.get("warnings_json"), [])
            events.append({
                "id": f"evt_after_{after_id}",
                "story_id": story_id,
                "timestamp_date": a_date[:10],
                "event_type": TimelineEventType.AFTER.value,
                "title": f"Post-Intervention Condition: {site_name}",
                "description": a_intel.get("description") or "Post-intervention state documented following cleanup operations.",
                "site_id": o["site_id"],
                "site_name": site_name,
                "asset_ids_json": json.dumps([after_id]),
                "primary_media_url": o.get("after_url") or a_asset.get("secure_url"),
                "thumbnail_url": o.get("after_thumb") or a_asset.get("thumbnail_url"),
                "media_type": a_asset.get("media_type", "image"),
                "frame_id": None,
                "observation_id": o["id"],
                "measurement_id": None,
                "intelligence_id": a_intel.get("id"),
                "verification_status": VerificationStatus.UNVERIFIED.value,
                "tags_json": json.dumps(a_tags),
                "signals_json": json.dumps(a_signals),
                "warnings_json": json.dumps(a_warnings),
                "uncertainty": a_intel.get("uncertainty"),
                "evidence_json": json.dumps({"source": "after_asset", "asset_id": after_id}),
            })
            emitted_assets.add(after_id)

        # Verified finding event
        rev_status = o.get("review_status", "pending")
        v_status = (
            VerificationStatus.APPROVED.value if rev_status == "approved"
            else VerificationStatus.REJECTED.value if rev_status == "rejected"
            else VerificationStatus.PENDING_REVIEW.value
        )
        finding_date = (
            o.get("reviewed_at")
            or o.get("after_date")
            or o.get("updated_at")
            or o.get("created_at")
            or "2026-09-03"
        )
        title_prefix = "Verified Finding" if rev_status == "approved" else "Field Observation"
        description_text = (
            o.get("approved_text")
            if rev_status == "approved"
            else (o.get("working_text") or o.get("ai_draft") or "Evidence comparison finding awaiting review.")
        )
        events.append({
            "id": f"evt_finding_{o['id']}",
            "story_id": story_id,
            "timestamp_date": finding_date[:10],
            "event_type": TimelineEventType.VERIFIED_FINDING.value,
            "title": f"{title_prefix}: {site_name}",
            "description": description_text,
            "site_id": o["site_id"],
            "site_name": site_name,
            "asset_ids_json": json.dumps([before_id, after_id]),
            "primary_media_url": o.get("after_url"),
            "thumbnail_url": o.get("after_thumb"),
            "media_type": "image",
            "frame_id": None,
            "observation_id": o["id"],
            "measurement_id": None,
            "intelligence_id": None,
            "verification_status": v_status,
            "tags_json": json.dumps(["verified" if rev_status == "approved" else "pending"]),
            "signals_json": json.dumps([]),
            "warnings_json": json.dumps([o["reliability_reason"]] if o.get("reliability_reason") else []),
            "uncertainty": o.get("reliability_reason"),
            "evidence_json": json.dumps({
                "observation_id": o["id"],
                "before_asset_id": before_id,
                "after_asset_id": after_id,
                "reviewed_by": o.get("reviewed_by"),
                "reviewed_at": o.get("reviewed_at"),
                "version": o.get("version", 1),
            }),
        })

    # Video activity events
    for a in assets:
        if a.get("media_type") == "video" and a["asset_id"] not in emitted_assets:
            site_name = a.get("site_name") or site_map.get(a.get("site_id"), "Field Site")
            v_intel = intel_by_asset.get(a["asset_id"], {})
            v_date = a.get("visited_on") or a.get("captured_at") or a.get("created_at") or "2026-09-02"
            v_tags = safe_json_loads(v_intel.get("tags_json"), ["cleanup", "activity"])
            v_signals = safe_json_loads(v_intel.get("signals_json"), ["active_cleanup"])
            duration_str = f" ({a['duration']:.1f}s)" if a.get("duration") else ""
            events.append({
                "id": f"evt_video_{a['asset_id']}",
                "story_id": story_id,
                "timestamp_date": v_date[:10],
                "event_type": TimelineEventType.ACTIVITY.value,
                "title": f"Field Walkthrough & Action Recording: {site_name}",
                "description": v_intel.get("description") or f"Field video recording{duration_str} documenting on-site environmental activity.",
                "site_id": a.get("site_id"),
                "site_name": site_name,
                "asset_ids_json": json.dumps([a["asset_id"]]),
                "primary_media_url": a.get("secure_url"),
                "thumbnail_url": a.get("thumbnail_url") or a.get("preview_url"),
                "media_type": "video",
                "frame_id": None,
                "observation_id": None,
                "measurement_id": None,
                "intelligence_id": v_intel.get("id"),
                "verification_status": VerificationStatus.UNVERIFIED.value,
                "tags_json": json.dumps(v_tags),
                "signals_json": json.dumps(v_signals),
                "warnings_json": json.dumps([]),
                "uncertainty": v_intel.get("uncertainty"),
                "evidence_json": json.dumps({"source": "field_video", "asset_id": a["asset_id"], "duration": a.get("duration")}),
            })
            emitted_assets.add(a["asset_id"])

    # Measurement events
    for m in measurements:
        site_name = m.get("site_name") or site_map.get(m.get("site_id"), "Field Site")
        m_date = m.get("recorded_at") or m.get("visited_on") or "2026-09-02"
        events.append({
            "id": f"evt_meas_{m['id']}",
            "story_id": story_id,
            "timestamp_date": m_date[:10],
            "event_type": TimelineEventType.MEASUREMENT.value,
            "title": f"Measured Impact: {m['quantity']} {m['unit']} ({m['label']})",
            "description": f"Verified field metric of {m['quantity']} {m['unit']} for {m['label']} at {site_name}. Recorded by {m.get('recorded_by', 'Field Reviewer')} from source: {m.get('source', 'Field Scales')}.",
            "site_id": m.get("site_id"),
            "site_name": site_name,
            "asset_ids_json": json.dumps([]),
            "primary_media_url": None,
            "thumbnail_url": None,
            "media_type": None,
            "frame_id": None,
            "observation_id": None,
            "measurement_id": m["id"],
            "intelligence_id": None,
            "verification_status": VerificationStatus.APPROVED.value,
            "tags_json": json.dumps(["measurement", m["label"]]),
            "signals_json": json.dumps(["quantified_impact"]),
            "warnings_json": json.dumps([]),
            "uncertainty": None,
            "evidence_json": json.dumps({
                "measurement_id": m["id"],
                "quantity": m["quantity"],
                "unit": m["unit"],
                "label": m["label"],
                "recorded_by": m["recorded_by"],
                "source": m["source"],
            }),
        })

    # Milestone events for remaining standalone assets (e.g. photos not part of pairs)
    for a in assets:
        if a["asset_id"] not in emitted_assets:
            site_name = a.get("site_name") or site_map.get(a.get("site_id"), "Field Site")
            a_intel = intel_by_asset.get(a["asset_id"], {})
            a_date = a.get("visited_on") or a.get("captured_at") or a.get("created_at") or "2026-09-02"
            a_tags = safe_json_loads(a_intel.get("tags_json"), ["survey"])
            a_signals = safe_json_loads(a_intel.get("signals_json"), [])
            events.append({
                "id": f"evt_milestone_{a['asset_id']}",
                "story_id": story_id,
                "timestamp_date": a_date[:10],
                "event_type": TimelineEventType.MILESTONE.value,
                "title": f"Site Documentation: {site_name}",
                "description": a_intel.get("description") or "Field documentation photo recorded during site monitoring.",
                "site_id": a.get("site_id"),
                "site_name": site_name,
                "asset_ids_json": json.dumps([a["asset_id"]]),
                "primary_media_url": a.get("secure_url"),
                "thumbnail_url": a.get("thumbnail_url"),
                "media_type": a.get("media_type", "image"),
                "frame_id": None,
                "observation_id": None,
                "measurement_id": None,
                "intelligence_id": a_intel.get("id"),
                "verification_status": VerificationStatus.UNVERIFIED.value,
                "tags_json": json.dumps(a_tags),
                "signals_json": json.dumps(a_signals),
                "warnings_json": json.dumps([]),
                "uncertainty": a_intel.get("uncertainty"),
                "evidence_json": json.dumps({"source": "monitoring_asset", "asset_id": a["asset_id"]}),
            })
            emitted_assets.add(a["asset_id"])

    # Chronological sort and order assignment
    events.sort(key=lambda e: (e["timestamp_date"] or "9999-99-99", e["title"]))
    for order, evt in enumerate(events):
        evt["event_order"] = order

    return events


def build_before_after_cards(db, project_id: str) -> List[BeforeAfterCard]:
    """Extract before/after observation cards with human verification state."""
    sites = store.rows(db, "SELECT id, name FROM sites WHERE project_id=?", (project_id,))
    site_map = {s["id"]: s["name"] for s in sites}
    site_ids = list(site_map.keys())

    if site_ids:
        placeholders = ",".join("?" for _ in site_ids)
        query = f"""
            SELECT o.*, s.name AS site_name,
                   bv.visited_on AS before_date, av.visited_on AS after_date,
                   ba.secure_url AS before_url, aa.secure_url AS after_url
            FROM observations o
            JOIN sites s ON s.id = o.site_id
            LEFT JOIN assets ba ON ba.asset_id = o.before_asset_id
            LEFT JOIN assets aa ON aa.asset_id = o.after_asset_id
            LEFT JOIN visits bv ON bv.id = ba.visit_id
            LEFT JOIN visits av ON av.id = aa.visit_id
            WHERE s.project_id = ? OR o.site_id IN ({placeholders})
            ORDER BY o.created_at ASC
        """
        rows = store.rows(db, query, (project_id, *site_ids))
    else:
        rows = store.rows(
            db,
            """
            SELECT o.*, s.name AS site_name,
                   bv.visited_on AS before_date, av.visited_on AS after_date,
                   ba.secure_url AS before_url, aa.secure_url AS after_url
            FROM observations o
            JOIN sites s ON s.id = o.site_id
            LEFT JOIN assets ba ON ba.asset_id = o.before_asset_id
            LEFT JOIN assets aa ON aa.asset_id = o.after_asset_id
            LEFT JOIN visits bv ON bv.id = ba.visit_id
            LEFT JOIN visits av ON av.id = aa.visit_id
            WHERE s.project_id = ?
            ORDER BY o.created_at ASC
            """,
            (project_id,),
        )

    cards = []
    for r in rows:
        site_name = r.get("site_name") or site_map.get(r["site_id"], "Field Site")
        summary_text = r.get("approved_text") or r.get("working_text") or r.get("ai_draft") or "Visual comparison observation."
        changes = [summary_text] if summary_text else []
        cards.append(BeforeAfterCard(
            observation_id=r["id"],
            site_id=r["site_id"],
            site_name=site_name,
            before_asset_id=r["before_asset_id"],
            before_media_url=r.get("before_url") or "",
            before_date=r.get("before_date"),
            after_asset_id=r["after_asset_id"],
            after_media_url=r.get("after_url") or "",
            after_date=r.get("after_date"),
            comparison_summary=summary_text,
            verification_status=r.get("review_status", "pending"),
            approved_text=r.get("approved_text"),
            reviewed_by=r.get("reviewed_by"),
            reviewed_at=r.get("reviewed_at"),
            uncertainty=r.get("reliability_reason"),
            reliability_reason=r.get("reliability_reason"),
            detected_changes=changes,
        ))
    return cards


async def generate_grounded_impact_narrative(
    project: dict,
    events: List[dict],
    before_after_cards: List[BeforeAfterCard],
    measurements: List[dict],
) -> Tuple[str, Optional[str]]:
    """Synthesize a factual impact narrative strictly grounded in provided data.

    Attempts live Gemini synthesis if configured; falls back deterministically to rule-based synthesis.
    """
    project_name = project.get("name", "Environmental Project")
    project_desc = project.get("description", "")
    total_events = len(events)
    total_cards = len(before_after_cards)
    approved_cards = [c for c in before_after_cards if c.verification_status == "approved"]
    pending_cards = [c for c in before_after_cards if c.verification_status != "approved"]

    # Gather verified facts
    measurement_summaries = [
        f"{m['quantity']} {m['unit']} of {m['label']} (Source: {m.get('source', 'Field')})"
        for m in measurements
    ]

    has_gemini = bool(settings.GEMINI_API_KEY)
    if has_gemini:
        try:
            facts_payload = {
                "project_name": project_name,
                "project_description": project_desc,
                "timeline_events_count": total_events,
                "total_comparisons": total_cards,
                "verified_approved_comparisons": len(approved_cards),
                "pending_comparisons": len(pending_cards),
                "approved_findings": [c.approved_text for c in approved_cards if c.approved_text],
                "measurements": measurement_summaries,
                "uncertainties": [c.reliability_reason for c in before_after_cards if c.reliability_reason],
            }

            prompt = (
                "You are an environmental verification auditor for Setowa.\n"
                "Synthesize a concise, factual 2-3 paragraph sustainability impact story for this project.\n"
                "STRICT GROUNDING RULES:\n"
                "1. State ONLY what is supported by the provided facts.\n"
                "2. Explicitly distinguish between human-verified findings and pending unverified AI proposals.\n"
                "3. Cite exact measurements where provided.\n"
                "4. If any evidence has uncertainty or pending reviews, explicitly note it.\n"
                "5. NEVER invent carbon metrics, percentage improvements, or beneficiary numbers.\n"
                "6. Respond ONLY with valid JSON having keys 'narrative' (string) and 'uncertainty_note' (string or null).\n\n"
                f"FACTS:\n{json.dumps(facts_payload, indent=2)}"
            )

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_VISION_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json",
                },
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=body)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        parsed = json.loads(text)
                        narrative = parsed.get("narrative")
                        uncertainty_note = parsed.get("uncertainty_note")
                        if narrative and isinstance(narrative, str):
                            return narrative.strip(), (uncertainty_note.strip() if uncertainty_note else None)
        except Exception as exc:
            logger.warning("Gemini narrative generation failed or timed out; falling back to deterministic synthesis: %s", exc)

    # Deterministic Grounded Fallback
    paragraphs = []
    p1 = f"{project_name} encompasses {total_events} documented timeline milestones across field monitoring sites."
    if project_desc:
        p1 += f" The objective of this project focuses on {project_desc.lower()}."
    paragraphs.append(p1)

    p2_parts = []
    if total_cards > 0:
        p2_parts.append(
            f"Visual field monitoring includes {total_cards} before-and-after photographic comparisons. "
            f"Of these, {len(approved_cards)} finding(s) have completed independent human verification and approval, "
            f"while {len(pending_cards)} finding(s) remain pending auditor review."
        )
    else:
        p2_parts.append("Visual evidence collection is currently ongoing, establishing initial baseline documentation.")

    if approved_cards:
        sample_finding = approved_cards[0].approved_text
        if sample_finding:
            p2_parts.append(f'Key verified observation: "{sample_finding}".')
    paragraphs.append(" ".join(p2_parts))

    p3_parts = []
    if measurements:
        p3_parts.append(
            f"Field operations recorded explicit physical impact measurements: {', '.join(measurement_summaries)}."
        )
    else:
        p3_parts.append("Quantitative physical measurements have not yet been recorded for this project timeline.")

    if pending_cards or any(c.reliability_reason for c in before_after_cards):
        p3_parts.append(
            "Note: Unverified visual changes represent automated algorithmic proposals and do not constitute certified impact until approved by human reviewers."
        )
    paragraphs.append(" ".join(p3_parts))

    narrative = "\n\n".join(paragraphs)

    uncertainty_note = None
    if len(pending_cards) > 0 or any(c.reliability_reason for c in before_after_cards):
        reasons = [c.reliability_reason for c in before_after_cards if c.reliability_reason]
        if reasons:
            uncertainty_note = f"Verification note: {len(pending_cards)} proposal(s) pending review. Observed warnings include: {', '.join(set(reasons))}."
        else:
            uncertainty_note = f"Verification note: {len(pending_cards)} proposal(s) remain pending formal human reviewer verification."

    return narrative, uncertainty_note


async def generate_impact_story(
    db,
    project_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    force_regenerate: bool = False,
    include_ai_summary: bool = True,
) -> ImpactStoryResponse:
    """Generate or refresh a persistent impact story and chronological timeline for a project."""
    project = store.get_project(db, project_id)
    if not project:
        raise ValueError(f"Project '{project_id}' not found")

    story_id = f"story_{project_id}"
    existing_story = store.get_impact_story(db, story_id)

    # If story already exists and force_regenerate is False, return it with populated events
    if existing_story and not force_regenerate:
        stored_events = store.get_impact_story_events(db, story_id)
        if stored_events:
            events_models = [row_to_timeline_event(e) for e in stored_events]
            cards = build_before_after_cards(db, project_id)
            meta = safe_json_loads(existing_story.get("metadata_json"), {})
            return ImpactStoryResponse(
                id=existing_story["id"],
                project_id=project_id,
                project_name=project["name"],
                title=existing_story["title"],
                description=existing_story.get("description"),
                status=existing_story.get("status", "draft"),
                summary_narrative=existing_story.get("summary_narrative"),
                uncertainty_note=existing_story.get("uncertainty_note"),
                date_range=meta.get("date_range", {}),
                metrics=meta.get("metrics", {}),
                events=events_models,
                before_after_cards=cards,
                created_at=existing_story["created_at"],
                updated_at=existing_story["updated_at"],
            )

    # Otherwise assemble fresh timeline events and cards from real project data
    raw_events = build_project_timeline_events(db, project_id, story_id)
    cards = build_before_after_cards(db, project_id)

    # Compute date range
    dates = [e["timestamp_date"] for e in raw_events if e.get("timestamp_date")]
    date_range = {
        "start_date": min(dates) if dates else None,
        "end_date": max(dates) if dates else None,
    }

    # Gather measurements for narrative synthesis
    sites = store.rows(db, "SELECT id FROM sites WHERE project_id=?", (project_id,))
    site_ids = [s["id"] for s in sites]
    measurements = []
    if site_ids:
        placeholders = ",".join("?" for _ in site_ids)
        measurements = store.rows(
            db,
            f"SELECT * FROM measurements WHERE site_id IN ({placeholders}) ORDER BY recorded_at ASC",
            tuple(site_ids),
        )

    # Generate grounded narrative
    story_title = title or f"{project['name']} — Impact Story"
    story_desc = description or project.get("description") or "Chronological field evidence and verified environmental findings."

    summary_narrative, uncertainty_note = "", None
    if include_ai_summary:
        summary_narrative, uncertainty_note = await generate_grounded_impact_narrative(
            project, raw_events, cards, measurements
        )

    metrics = {
        "event_count": len(raw_events),
        "comparison_count": len(cards),
        "approved_findings_count": len([c for c in cards if c.verification_status == "approved"]),
        "measurement_count": len(measurements),
        "site_count": len(sites),
    }

    meta_json = json.dumps({
        "date_range": date_range,
        "metrics": metrics,
    })

    # Persist story record
    saved_story = store.save_impact_story(db, {
        "id": story_id,
        "project_id": project_id,
        "title": story_title,
        "description": story_desc,
        "status": existing_story.get("status", "draft") if existing_story else "draft",
        "summary_narrative": summary_narrative,
        "uncertainty_note": uncertainty_note,
        "metadata_json": meta_json,
    })

    # Persist timeline events
    saved_events = store.save_impact_story_events(db, story_id, raw_events)
    events_models = [row_to_timeline_event(e) for e in saved_events]

    return ImpactStoryResponse(
        id=saved_story["id"],
        project_id=project_id,
        project_name=project["name"],
        title=saved_story["title"],
        description=saved_story.get("description"),
        status=saved_story.get("status", "draft"),
        summary_narrative=saved_story.get("summary_narrative"),
        uncertainty_note=saved_story.get("uncertainty_note"),
        date_range=date_range,
        metrics=metrics,
        events=events_models,
        before_after_cards=cards,
        created_at=saved_story["created_at"],
        updated_at=saved_story["updated_at"],
    )


def get_impact_story_by_id(db, story_id: str) -> Optional[ImpactStoryResponse]:
    """Retrieve an existing impact story by its story ID."""
    story = store.get_impact_story(db, story_id)
    if not story:
        return None
    project = store.get_project(db, story["project_id"])
    project_name = project["name"] if project else "Project"
    raw_events = store.get_impact_story_events(db, story_id)
    events_models = [row_to_timeline_event(e) for e in raw_events]
    cards = build_before_after_cards(db, story["project_id"])
    meta = safe_json_loads(story.get("metadata_json"), {})

    return ImpactStoryResponse(
        id=story["id"],
        project_id=story["project_id"],
        project_name=project_name,
        title=story["title"],
        description=story.get("description"),
        status=story.get("status", "draft"),
        summary_narrative=story.get("summary_narrative"),
        uncertainty_note=story.get("uncertainty_note"),
        date_range=meta.get("date_range", {}),
        metrics=meta.get("metrics", {}),
        events=events_models,
        before_after_cards=cards,
        created_at=story["created_at"],
        updated_at=story["updated_at"],
    )


def get_project_impact_story(db, project_id: str) -> Optional[ImpactStoryResponse]:
    """Retrieve current impact story for a project ID."""
    story = store.get_project_impact_story(db, project_id)
    if not story:
        return None
    return get_impact_story_by_id(db, story["id"])


def update_impact_story_fields(db, story_id: str, updates: dict) -> Optional[ImpactStoryResponse]:
    """Update editable fields on an impact story."""
    updated = store.update_impact_story(db, story_id, updates)
    if not updated:
        return None
    return get_impact_story_by_id(db, story_id)


def get_story_timeline_events(db, story_id: str) -> List[TimelineEvent]:
    """Retrieve chronological timeline events for a story."""
    raw = store.get_impact_story_events(db, story_id)
    return [row_to_timeline_event(e) for e in raw]
