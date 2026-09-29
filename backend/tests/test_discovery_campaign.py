"""Evidence boundaries for the local discovery and campaign workflows."""

import asyncio
import sqlite3

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.services import evidence_store as store
from app.services import semantic_search

client = TestClient(app)
HEADERS = {"Authorization": "Bearer local-test"}


def seed(db):
    now = store.timestamp()
    for project in ("p-one", "p-two"):
        db.execute("INSERT INTO projects(id,name,description,created_at) VALUES(?,?,?,?)",
                   (project, project, "Test project", now))
        db.execute("INSERT INTO sites(id,name,project_id) VALUES(?,?,?)",
                   (project + "-site", project + " site", project))
        for suffix, day in (("before", "2026-09-01"), ("after", "2026-09-02")):
            visit = project + "-" + suffix
            db.execute("INSERT INTO visits(id,site_id,visited_on,label) VALUES(?,?,?,?)",
                       (visit, project + "-site", day, suffix))
            store.save_asset(db, {"asset_id": visit, "visit_id": visit,
                "public_id": visit, "version": 1,
                "secure_url": "https://res.cloudinary.com/test/image/upload/" + visit,
                "source": "Permissioned test image", "width": 10, "height": 10,
                "format": "png", "permission_status": "granted", "site_id": project + "-site",
                "project_id": project, "original_filename": suffix + ".png"})
    for oid, status, text in (("approved", "approved", "Less visible litter near the bridge."),
                              ("pending", "pending", None)):
        db.execute("""INSERT INTO observations
            (id,site_id,before_asset_id,after_asset_id,ai_draft,approved_text,
             review_status,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?)""",
             (oid, "p-one-site", "p-one-before", "p-one-after",
              "AI invented a huge impact", text, status, now, now))
    store.save_asset(db, {"asset_id": "p-one-video", "visit_id": "p-one-after",
        "public_id": "p-one-video", "version": 1,
        "secure_url": "https://res.cloudinary.com/test/video/upload/p-one-video",
        "source": "Permissioned video", "width": 10, "height": 10, "format": "mp4",
        "permission_status": "granted", "site_id": "p-one-site", "project_id": "p-one",
        "media_type": "video", "original_filename": "cleanup.mp4"})
    db.execute("""INSERT INTO video_frames
      (frame_id,asset_id,frame_index,timestamp_seconds,frame_url,source_video_url,created_at)
      VALUES(?,?,?,?,?,?,?)""",
      ("frame-1", "p-one-video", 0, 12.5,
       "https://res.cloudinary.com/test/video/upload/so_12.5/p-one-video.jpg",
       "https://res.cloudinary.com/test/video/upload/p-one-video", now))
    db.execute("""INSERT INTO frame_analyses
      (analysis_id,asset_id,frame_id,skill_name,skill_version,status,observations_json,created_at)
      VALUES(?,?,?,?,?,?,?,?)""",
      ("frame-analysis-1", "p-one-video", "frame-1", "test", "1", "analyzed",
       '["People carrying bags"]', now))
    db.execute("""INSERT INTO measurements
      (id,site_id,visit_id,label,quantity,unit,source,recorded_by,recorded_at)
      VALUES(?,?,?,?,?,?,?,?,?)""",
      ("m-one", "p-one-site", "p-one-after", "collected litter", 2, "kg",
       "Field scale log", "Tester", now))


def test_campaign_uses_approved_and_sourced_records_only(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("local-test"))
    with store.connection() as db:
        seed(db)
        now = store.timestamp()
        db.execute("""INSERT INTO observations
            (id,site_id,before_asset_id,after_asset_id,approved_text,
             review_status,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?)""",
             ("unsourced-quantity", "p-one-site", "p-one-before", "p-one-after",
              "35 kg of waste was removed", "approved", now, now))
    result = client.post("/api/v1/projects/p-one/campaign-drafts", headers=HEADERS,
                         json={"channel": "social"})
    assert result.status_code == 201, result.text
    draft = result.json()
    assert "Less visible litter" in draft["body"]
    assert "2.0 kg" in draft["body"]
    assert "AI invented" not in draft["body"]
    assert "35 kg" not in draft["body"]
    assert len(draft["sources"]) == 2
    assert draft["status"] == "draft"
    edit = client.put(f"/api/v1/projects/p-one/campaign-drafts/{draft['id']}",
                      headers=HEADERS, json={"body": draft["body"] + "\nHuman closing note."})
    assert edit.status_code == 200, edit.text
    assert edit.json()["edited_at"]
    assert "Human closing note." in edit.json()["body"]
    assert client.put(f"/api/v1/projects/p-two/campaign-drafts/{draft['id']}",
                      headers=HEADERS, json={"body": "wrong project"}).status_code == 404
    with store.connection() as db:
        db.execute("UPDATE observations SET review_status='pending',approved_text=NULL WHERE id='approved'")
    listed = client.get("/api/v1/projects/p-one/campaign-drafts", headers=HEADERS)
    assert listed.status_code == 200
    assert listed.json()[0]["stale"] is True
    assert "Human closing note." not in listed.json()[0]["body"]
    assert listed.json()[0]["sources"] == []
    assert client.put(f"/api/v1/projects/p-one/campaign-drafts/{draft['id']}",
                      headers=HEADERS, json={"body": "Outdated"}).status_code == 409
    assert client.post("/api/v1/projects/p-two/campaign-drafts", headers=HEADERS,
                       json={"channel": "social"}).status_code == 422


def test_semantic_search_scoped_cached_and_labeled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("local-test"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy-key")
    with store.connection() as db:
        seed(db)
    calls = []

    async def fake_embedding(text, task_type):
        calls.append((text, task_type))
        return [1.0, 0.0] if "litter" in text.lower() else [0.0, 1.0]

    async def fake_documents(texts):
        return [await fake_embedding(text, "RETRIEVAL_DOCUMENT") for text in texts]

    monkeypatch.setattr(semantic_search, "embed_text", fake_embedding)
    monkeypatch.setattr(semantic_search, "embed_documents", fake_documents)
    url = "/api/v1/projects/p-one/semantic-search"
    assert client.post("/api/v1/projects/p-one/search-index", headers=HEADERS).status_code == 200
    first = client.post(url, headers=HEADERS, json={"query": "litter near bridge"})
    assert first.status_code == 200, first.text
    hits = first.json()["results"]
    assert hits[0]["kind"] == "approved_observation"
    assert all(hit["entity_id"] != "p-two-before" for hit in hits)
    assert all("AI invented" not in hit["text"] for hit in hits)
    assert any(hit["review_status"] == "metadata_only" for hit in hits)
    assert any(hit["kind"] == "video_frame" and "12.5 seconds" in hit["text"] for hit in hits)
    document_calls = len([task for _, task in calls if task == "RETRIEVAL_DOCUMENT"])
    second = client.post(url, headers=HEADERS, json={"query": "litter near bridge"})
    assert second.status_code == 200
    assert second.json()["indexed"] == 0
    assert len([task for _, task in calls if task == "RETRIEVAL_DOCUMENT"]) == document_calls
    with store.connection() as db:
        db.execute("UPDATE assets SET permission_status='revoked' WHERE asset_id='p-one-before'")
    third = client.post(url, headers=HEADERS, json={"query": "litter near bridge"})
    assert third.status_code == 200
    assert all(hit["entity_id"] != "approved" for hit in third.json()["results"])
    assert all(hit["entity_id"] != "p-one-before" for hit in third.json()["results"])


def test_semantic_search_fails_honestly_without_key(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("local-test"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    response = client.post("/api/v1/projects/proj_default/semantic-search", headers=HEADERS,
                           json={"query": "find cleanup images"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_keeps_approved_records_in_large_local_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("local-test"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy-key")
    with store.connection() as db:
        seed(db)
        for index in range(35):
            store.save_asset(db, {"asset_id": f"extra-{index}",
                "visit_id": "p-one-after", "public_id": f"extra-{index}", "version": 1,
                "secure_url": f"https://res.cloudinary.com/test/image/upload/extra-{index}",
                "source": "Permissioned test image", "width": 10, "height": 10,
                "format": "png", "permission_status": "granted",
                "site_id": "p-one-site", "project_id": "p-one",
                "original_filename": f"extra-{index}.png"})

    async def fake_embedding(text, task_type):
        return [1.0, 0.0] if "litter" in text.lower() else [0.0, 1.0]

    async def fake_documents(texts):
        return [await fake_embedding(text, "RETRIEVAL_DOCUMENT") for text in texts]

    monkeypatch.setattr(semantic_search, "embed_text", fake_embedding)
    monkeypatch.setattr(semantic_search, "embed_documents", fake_documents)
    indexed = client.post("/api/v1/projects/p-one/search-index", headers=HEADERS)
    assert indexed.json()["indexed"] == 24
    result = client.post("/api/v1/projects/p-one/semantic-search", headers=HEADERS,
                         json={"query": "litter near bridge", "limit": 20})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["truncated"] is True
    assert data["indexed"] == 0
    assert data["indexed_count"] == data["batch_size"] == 24
    assert data["total_documents"] > data["indexed_count"]
    assert any(hit["kind"] == "approved_observation" for hit in data["results"])
    assert any(hit["kind"] == "video_frame" for hit in data["results"])
    assert client.post("/api/v1/projects/p-one/search-index", headers=HEADERS).status_code == 200
    followup = client.post("/api/v1/projects/p-one/semantic-search", headers=HEADERS,
                           json={"query": "litter near bridge", "limit": 20})
    assert followup.status_code == 200, followup.text
    assert followup.json()["truncated"] is False
    assert followup.json()["indexed_count"] == followup.json()["total_documents"]



def test_existing_local_campaign_database_gets_edit_column(tmp_path, monkeypatch):
    path = tmp_path / "existing.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE campaign_drafts (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, channel TEXT NOT NULL,
            title TEXT NOT NULL, body TEXT NOT NULL, sources_json TEXT NOT NULL,
            source_fingerprint TEXT NOT NULL, demo_only INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL)""")
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(path))
    with store.connection() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(campaign_drafts)")}
    assert "edited_at" in columns


def test_keyword_fallback_filters_revoked_and_never_indexes(tmp_path, monkeypatch):
    from app.providers import nvidia
    monkeypatch.setattr(settings, 'LEX_DB_PATH', str(tmp_path / 'fallback.sqlite3'))
    monkeypatch.setattr(settings, 'MEDIA_UPLOAD_TOKEN', SecretStr('local-test'))
    async def forbidden(*args, **kwargs):
        raise AssertionError('A query must not embed documents')
    monkeypatch.setattr(semantic_search, 'embed_documents', forbidden)
    with store.connection() as db:
        seed(db)
        db.execute("UPDATE assets SET permission_status='revoked' WHERE asset_id='p-one-before'")
    response = client.post('/api/v1/projects/p-one/semantic-search', headers=HEADERS,
                           json={'query': 'litter bridge cleanup'})
    assert response.status_code == 200
    result = response.json()
    assert result['mode'] == 'keyword'
    assert all(h['entity_id'] not in {'approved', 'p-one-before', 'p-two-before'} for h in result['results'])
