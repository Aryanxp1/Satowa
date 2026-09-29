"""On-demand, project-scoped semantic retrieval over saved evidence text.

Only descriptions and reviewed records are embedded. Original media stays in Cloudinary.
The SQLite cache is local and is refreshed when source content changes.
"""

import hashlib
import json
import math
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings
from app.services import evidence_store as store

MODEL = "gemini-embedding-2"
MAX_DOCUMENTS = 24


def _document(key: str, project_id: str, site_id: str, kind: str, entity_id: str,
              content: str, review_status: str, evidence: list[dict]) -> dict:
    return dict(doc_key=key, project_id=project_id, site_id=site_id, kind=kind,
                entity_id=entity_id, content=content[:2500], review_status=review_status,
                evidence=evidence)


def collect_documents(db, project_id: str) -> list[dict]:
    """Rebuild the searchable source set; never index revoked media or AI drafts as facts."""
    documents = []
    assets = store.rows(db, """
        SELECT a.*, v.visited_on, s.project_id,
          (SELECT description FROM media_intelligence i WHERE i.asset_id=a.asset_id
           AND i.frame_id IS NULL ORDER BY i.created_at DESC LIMIT 1) AS ai_description
        FROM assets a JOIN visits v ON v.id=a.visit_id
        JOIN sites s ON s.id=v.site_id
        WHERE s.project_id=? AND a.permission_status='granted'
        ORDER BY COALESCE(a.captured_at, v.visited_on) DESC, a.asset_id
    """, (project_id,))
    for a in assets:
        description = (a.get("ai_description") or "").strip()
        content = " | ".join(part for part in [
            "Media: " + (a.get("original_filename") or a["public_id"]),
            "Source: " + (a.get("source") or "not recorded"),
            "Visit: " + (a.get("visited_on") or "date not recorded"),
            "AI description (unreviewed): " + description if description else "",
        ] if part)
        documents.append(_document("media:" + a["asset_id"], project_id,
            a.get("site_id") or "", "media", a["asset_id"], content,
            "ai_description_unreviewed" if description else "metadata_only",
            [{"asset_id": a["asset_id"], "url": a["secure_url"],
              "source": a.get("source"), "visited_on": a.get("visited_on")}]))

    frames = store.rows(db, """
        SELECT f.frame_id, f.asset_id, f.timestamp_seconds, f.frame_url,
          f.source_video_url, a.site_id, a.source,
          (SELECT i.description FROM media_intelligence i
           WHERE i.frame_id=f.frame_id ORDER BY i.created_at DESC LIMIT 1) AS ai_description,
          (SELECT fa.observations_json FROM frame_analyses fa
           WHERE fa.frame_id=f.frame_id ORDER BY fa.created_at DESC LIMIT 1) AS observations_json
        FROM video_frames f JOIN assets a ON a.asset_id=f.asset_id
        JOIN visits v ON v.id=a.visit_id JOIN sites s ON s.id=v.site_id
        WHERE s.project_id=? AND a.permission_status='granted'
        ORDER BY f.created_at DESC, f.frame_id
    """, (project_id,))
    for frame in frames:
        description = (frame.get("ai_description") or "").strip()
        observations = frame.get("observations_json") or ""
        if not description and not observations:
            continue
        content = (f"Unreviewed AI video frame at {frame['timestamp_seconds']:.1f} seconds. "
                   f"Source: {frame['source']}. Description: {description}. "
                   f"Frame observations: {observations}")
        documents.append(_document("frame:" + frame["frame_id"], project_id,
            frame.get("site_id") or "", "video_frame", frame["frame_id"],
            content, "ai_description_unreviewed",
            [{"asset_id": frame["asset_id"], "frame_id": frame["frame_id"],
              "url": frame["frame_url"], "role": "video frame",
              "source_video_url": frame["source_video_url"],
              "timestamp_seconds": frame["timestamp_seconds"]}]))

    observations = store.rows(db, """
        SELECT o.*, s.project_id, b.secure_url AS before_url,
               a.secure_url AS after_url, b.permission_status AS before_permission,
               a.permission_status AS after_permission
        FROM observations o JOIN sites s ON s.id=o.site_id
        JOIN assets b ON b.asset_id=o.before_asset_id
        JOIN assets a ON a.asset_id=o.after_asset_id
        WHERE s.project_id=? AND o.review_status='approved' AND o.approved_text IS NOT NULL
        ORDER BY o.updated_at DESC, o.id
    """, (project_id,))
    for o in observations:
        if o["before_permission"] != "granted" or o["after_permission"] != "granted":
            continue
        documents.append(_document("observation:" + o["id"], project_id,
            o["site_id"], "approved_observation", o["id"],
            "Reviewer-approved photo comparison: " + o["approved_text"], "approved",
            [{"asset_id": o["before_asset_id"], "url": o["before_url"], "role": "before"},
             {"asset_id": o["after_asset_id"], "url": o["after_url"], "role": "after"}]))

    measurements = store.rows(db, """
        SELECT m.*, s.project_id FROM measurements m JOIN sites s ON s.id=m.site_id
        WHERE s.project_id=? ORDER BY m.recorded_at DESC, m.id
    """, (project_id,))
    for m in measurements:
        documents.append(_document("measurement:" + m["id"], project_id,
            m["site_id"], "recorded_measurement", m["id"],
            f"Recorded measurement: {m['quantity']} {m['unit']} {m['label']}. "
            f"Supplied source: {m['source']}. Recorded by {m['recorded_by']}.",
            "recorded_not_independently_verified",
            [{"measurement_id": m["id"], "source": m["source"],
              "recorded_at": m["recorded_at"]}]))
    return documents


async def embed_text(text: str, task_type: str) -> list[float]:
    if not settings.GEMINI_API_KEY:
        raise HTTPException(503, "Gemini API key is required for semantic search")
    # Embedding 2 uses asymmetric text prefixes for retrieval, not taskType.
    prepared = (f"task: search result | query: {text}" if task_type == "RETRIEVAL_QUERY"
                else f"title: none | text: {text}")
    payload = {"model": f"models/{MODEL}", "content": {"parts": [{"text": prepared}]}}
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:embedContent",
                headers={"x-goog-api-key": settings.GEMINI_API_KEY}, json=payload)
        response.raise_for_status()
        values = response.json()["embedding"]["values"]
        if not values or not all(math.isfinite(float(v)) for v in values):
            raise ValueError("Invalid embedding vector")
        return [float(v) for v in values]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(502, "Gemini embedding request failed; search was not changed") from exc


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


async def search_project(db, project_id: str, query: str, limit: int = 8) -> dict[str, Any]:
    if not settings.GEMINI_API_KEY:
        raise HTTPException(503, "Gemini API key is required for semantic search")
    if not store.get_project(db, project_id):
        raise HTTPException(404, "Project not found")
    documents = collect_documents(db, project_id)
    truncated = len(documents) > MAX_DOCUMENTS
    documents = documents[:MAX_DOCUMENTS]
    existing = {r["doc_key"]: r for r in store.rows(db,
        "SELECT * FROM semantic_documents WHERE project_id=?", (project_id,))}
    indexed = 0
    for doc in documents:
        digest = hashlib.sha256(json.dumps({"content": doc["content"],
            "evidence": doc["evidence"], "review_status": doc["review_status"]},
            sort_keys=True).encode()).hexdigest()
        cached = existing.get(doc["doc_key"])
        if cached and cached["content_hash"] == digest and cached["model"] == MODEL:
            continue
        vector = await embed_text(doc["content"], "RETRIEVAL_DOCUMENT")
        db.execute("""INSERT INTO semantic_documents
            (doc_key,project_id,site_id,kind,entity_id,content,content_hash,model,
             embedding_json,evidence_json,review_status,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(doc_key) DO UPDATE SET content=excluded.content,
             content_hash=excluded.content_hash,model=excluded.model,
             embedding_json=excluded.embedding_json,evidence_json=excluded.evidence_json,
             review_status=excluded.review_status,updated_at=excluded.updated_at""",
            (doc["doc_key"], project_id, doc["site_id"], doc["kind"], doc["entity_id"],
             doc["content"], digest, MODEL, json.dumps(vector), json.dumps(doc["evidence"]),
             doc["review_status"], store.timestamp()))
        indexed += 1
    active_keys = {d["doc_key"] for d in documents}
    for key in existing.keys() - active_keys:
        db.execute("DELETE FROM semantic_documents WHERE doc_key=? AND project_id=?", (key, project_id))
    if not documents:
        return {"query": query, "results": [], "indexed": indexed, "truncated": False,
                "max_documents": MAX_DOCUMENTS, "model": MODEL}
    query_vector = await embed_text(query, "RETRIEVAL_QUERY")
    rows = store.rows(db, "SELECT * FROM semantic_documents WHERE project_id=?", (project_id,))
    ranked = []
    for row in rows:
        score = _cosine(query_vector, json.loads(row["embedding_json"]))
        ranked.append({"kind": row["kind"], "entity_id": row["entity_id"],
                       "site_id": row["site_id"], "text": row["content"],
                       "score": round(score, 4), "review_status": row["review_status"],
                       "evidence": json.loads(row["evidence_json"])})
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return {"query": query, "results": ranked[:limit], "indexed": indexed,
            "truncated": truncated, "max_documents": MAX_DOCUMENTS, "model": MODEL}
