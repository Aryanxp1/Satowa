"""Local campaign drafts grounded in current reviewer-approved evidence.

Drafts are editable copy, not proof of impact and never published by this service.
"""

import hashlib
import json

from fastapi import HTTPException

from app.services import evidence_store as store

CHANNELS = {"social", "newsletter", "volunteer_update"}


def source_records(db, project_id: str) -> list[dict]:
    if not store.get_project(db, project_id):
        raise HTTPException(404, "Project not found")
    sources = []
    observations = store.rows(db, """
        SELECT o.*, b.secure_url AS before_url, a.secure_url AS after_url,
          b.source AS before_source, a.source AS after_source,
          b.permission_status AS before_permission, a.permission_status AS after_permission
        FROM observations o JOIN sites s ON s.id=o.site_id
        JOIN assets b ON b.asset_id=o.before_asset_id
        JOIN assets a ON a.asset_id=o.after_asset_id
        WHERE s.project_id=? AND o.review_status='approved' AND o.approved_text IS NOT NULL
        ORDER BY o.reviewed_at DESC, o.id LIMIT 20
    """, (project_id,))
    for o in observations:
        if o["before_permission"] != "granted" or o["after_permission"] != "granted":
            continue
        sources.append({"type": "approved_observation", "id": o["id"],
                        "text": o["approved_text"], "site_id": o["site_id"],
                        "reviewed_by": o.get("reviewed_by"),
                        "before_url": o["before_url"], "after_url": o["after_url"],
                        "before_source": o["before_source"],
                        "after_source": o["after_source"]})
    measurements = store.rows(db, """
        SELECT m.* FROM measurements m JOIN sites s ON s.id=m.site_id
        WHERE s.project_id=? ORDER BY m.recorded_at DESC, m.id LIMIT 20
    """, (project_id,))
    for m in measurements:
        sources.append({"type": "recorded_measurement", "id": m["id"],
                        "text": f"{m['quantity']} {m['unit']} {m['label']}",
                        "site_id": m["site_id"], "source": m["source"],
                        "recorded_by": m["recorded_by"],
                        "recorded_at": m["recorded_at"]})
    return sources


def _fingerprint(project: dict, sources: list[dict]) -> str:
    content = {"project_name": project["name"],
               "project_description": project.get("description"), "sources": sources}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def _is_demo(project: dict, sources: list[dict]) -> bool:
    values = [project.get("name") or "", project.get("description") or ""]
    for source in sources:
        values.extend(str(value) for value in source.values() if isinstance(value, str))
    return any(word in " ".join(values).lower() for word in ("synthetic", "demo/", "sample-media"))


def generate_draft(db, project_id: str, channel: str) -> dict:
    if channel not in CHANNELS:
        raise HTTPException(422, "Unsupported campaign channel")
    project = store.get_project(db, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    sources = source_records(db, project_id)
    if not sources:
        raise HTTPException(422, "Approve a photo observation or record a sourced measurement first")
    demo_only = _is_demo(project, sources)
    title = f"{project['name']} — field update"
    observations = [(i + 1, item) for i, item in enumerate(sources)
                    if item["type"] == "approved_observation"]
    measurements = [(i + 1, item) for i, item in enumerate(sources)
                    if item["type"] == "recorded_measurement"]
    lines = []
    if demo_only:
        lines.append("SYNTHETIC DEMO DRAFT — illustrative content, not real field impact.\n")
    if channel == "social":
        lines.append(f"Field update from {project['name']}.")
    elif channel == "newsletter":
        lines.append(f"Subject: Field evidence update — {project['name']}\n")
        lines.append("Here is what our saved field records currently support:")
    else:
        lines.append(f"Volunteer update: {project['name']}\n")
        lines.append("Thank you for helping document this site. Our current record shows:")
    for index, item in observations:
        lines.append(f"• Reviewer-approved photo observation [{index}]: {item['text']}")
    for index, item in measurements:
        lines.append(f"• Recorded measurement [{index}]: {item['text']} "
                     f"(supplied source: {item['source']}; not independently verified).")
    lines.append("\nEvidence references:")
    for index, item in enumerate(sources, 1):
        if item["type"] == "approved_observation":
            lines.append(f"[{index}] Before: {item['before_url']} | After: {item['after_url']}")
        else:
            lines.append(f"[{index}] Measurement record {item['id']}; supplied source: {item['source']}")
    lines.append("\nDraft only. Check media permissions and field records before sharing. "
                 "Reviewer approval is not an independent audit.")
    draft = {"id": store.new_id(), "project_id": project_id, "channel": channel,
             "title": title, "body": "\n".join(lines), "sources": sources,
             "source_fingerprint": _fingerprint(project, sources), "demo_only": demo_only,
             "created_at": store.timestamp(), "status": "draft", "stale": False}
    db.execute("""INSERT INTO campaign_drafts
        (id,project_id,channel,title,body,sources_json,source_fingerprint,demo_only,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (draft["id"], project_id, channel, title, draft["body"], json.dumps(sources),
         draft["source_fingerprint"], int(demo_only), draft["created_at"]))
    return draft


def list_drafts(db, project_id: str) -> list[dict]:
    project = store.get_project(db, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    fingerprint = _fingerprint(project, source_records(db, project_id))
    records = store.rows(db, "SELECT * FROM campaign_drafts WHERE project_id=? "
                         "ORDER BY created_at DESC LIMIT 30", (project_id,))
    return [{"id": row["id"], "project_id": project_id,
             "channel": row["channel"], "title": row["title"], "body": row["body"],
             "sources": json.loads(row["sources_json"]), "demo_only": bool(row["demo_only"]),
             "created_at": row["created_at"], "edited_at": row["edited_at"],
             "status": "draft",
             "stale": row["source_fingerprint"] != fingerprint}
            for row in records]


def edit_draft(db, project_id: str, draft_id: str, body: str) -> dict:
    """Save human copy edits while retaining the original evidence snapshot."""
    if not body.strip():
        raise HTTPException(422, "Draft body must not be blank")
    draft = store.one(db, "SELECT * FROM campaign_drafts WHERE id=? AND project_id=?",
                      (draft_id, project_id))
    if not draft:
        raise HTTPException(404, "Campaign draft not found")
    project = store.get_project(db, project_id)
    if draft["source_fingerprint"] != _fingerprint(project, source_records(db, project_id)):
        raise HTTPException(409, "Source records changed; generate a new draft before editing")
    db.execute("UPDATE campaign_drafts SET body=?, edited_at=? WHERE id=? AND project_id=?",
               (body.strip(), store.timestamp(), draft_id, project_id))
    return next(item for item in list_drafts(db, project_id) if item["id"] == draft_id)
