"""Evidence boundaries for the local discovery and campaign workflows."""

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
    result = client.post("/api/v1/projects/p-one/campaign-drafts", headers=HEADERS,
                         json={"channel": "social"})
    assert result.status_code == 201, result.text
    draft = result.json()
    assert "Less visible litter" in draft["body"]
    assert "2.0 kg" in draft["body"]
    assert "AI invented" not in draft["body"]
    assert len(draft["sources"]) == 2
    assert draft["status"] == "draft"
    with store.connection() as db:
        db.execute("UPDATE observations SET review_status='pending',approved_text=NULL WHERE id='approved'")
    listed = client.get("/api/v1/projects/p-one/campaign-drafts", headers=HEADERS)
    assert listed.status_code == 200
    assert listed.json()[0]["stale"] is True
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

    monkeypatch.setattr(semantic_search, "embed_text", fake_embedding)
    url = "/api/v1/projects/p-one/semantic-search"
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
    assert response.status_code == 503
    assert "Gemini API key" in response.json()["detail"]
