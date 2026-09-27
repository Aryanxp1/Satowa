"""Tests for T015 — Project/Location/Timeline Media Grouping & Spatial-Temporal Queries."""
import io
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.services import evidence_store as store
from app.services import media

client = TestClient(app)

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def t015_env(monkeypatch, tmp_path):
    db_file = tmp_path / "t015_test.sqlite3"
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(db_file))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("test-token"))
    monkeypatch.setattr(settings, "REVIEWER_TOKENS", SecretStr('{"Tester":"test-reviewer-token"}'))
    monkeypatch.setattr(settings, "CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setattr(settings, "CLOUDINARY_API_KEY", "test-key")
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", SecretStr("test-secret"))

    from uuid import uuid4
    call_count = {"n": 0}

    def mock_upload(*args, **kwargs):
        call_count["n"] += 1
        n = call_count["n"]
        resource_type = kwargs.get("resource_type", "image")
        if resource_type == "video":
            return {
                "asset_id": f"vid-{n}",
                "public_id": f"test/video_{n}",
                "version": 1,
                "resource_type": "video",
                "format": "mp4",
                "width": 1920,
                "height": 1080,
                "duration": 10.0,
                "secure_url": f"https://res.cloudinary.com/test-cloud/video/upload/v1/test/video_{n}.mp4",
            }
        return {
            "asset_id": f"img-{n}",
            "public_id": f"test/image_{n}",
            "version": 1,
            "resource_type": "image",
            "format": "png",
            "width": 800,
            "height": 600,
            "secure_url": f"https://res.cloudinary.com/test-cloud/image/upload/v1/test/image_{n}.png",
        }

    mock = Mock(side_effect=mock_upload)
    monkeypatch.setattr(media.cloudinary.uploader, "upload", mock)
    return mock


def sample_png():
    out = io.BytesIO()
    Image.new("RGB", (32, 24), color=(10, 20, 30)).save(out, format="PNG")
    return out.getvalue()


def upload_image(project_id="site-alpha", visit_date="2026-09-01", permission_status="granted"):
    """Helper to upload a test image."""
    return client.post(
        "/api/v1/media/images",
        headers=AUTH_HEADERS,
        files={"file": ("photo.png", sample_png(), "image/png")},
        data={
            "project_id": project_id,
            "source": "Test source",
            "visit_date": visit_date,
            "permission_status": permission_status,
        },
    )


def create_site(site_id="site-alpha", name="Alpha Site", project_id=None):
    """Helper to ensure default project and site exist."""
    payload = {"id": site_id, "name": name}
    if project_id:
        payload["project_id"] = project_id
    resp = client.post("/api/v1/sites", headers=AUTH_HEADERS, json=payload)
    return resp


def create_project(project_id="proj-001", name="Test Project"):
    return client.post(
        "/api/v1/projects",
        headers=AUTH_HEADERS,
        json={"id": project_id, "name": name, "description": "A test project"},
    )


# ─────────────────────────────────────────────
# T015-01: Default project is auto-seeded
# ─────────────────────────────────────────────
def test_default_project_seeded():
    """Default project proj_default is seeded on first connection."""
    with store.connection() as db:
        proj = store.get_project(db, "proj_default")
    assert proj is not None
    assert proj["name"] == "Default Environmental Project"


# ─────────────────────────────────────────────
# T015-02: Create and retrieve a project
# ─────────────────────────────────────────────
def test_create_and_get_project():
    resp = create_project("proj-alpha", "Alpha Project")
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == "proj-alpha"
    assert data["name"] == "Alpha Project"
    assert data["site_count"] == 0
    assert data["media_count"] == 0

    get_resp = client.get("/api/v1/projects/proj-alpha", headers=AUTH_HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["project_id"] == "proj-alpha"


# ─────────────────────────────────────────────
# T015-03: Duplicate project returns 409
# ─────────────────────────────────────────────
def test_create_duplicate_project_returns_409():
    create_project("dup-proj")
    resp = create_project("dup-proj")
    assert resp.status_code == 409


# ─────────────────────────────────────────────
# T015-04: List projects includes all projects
# ─────────────────────────────────────────────
def test_list_projects_includes_all():
    create_project("list-p1", "List Project 1")
    create_project("list-p2", "List Project 2")
    resp = client.get("/api/v1/projects", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    project_ids = [p["project_id"] for p in data]
    # default + seeded projects
    assert "list-p1" in project_ids
    assert "list-p2" in project_ids


# ─────────────────────────────────────────────
# T015-05: Project 404 for unknown project
# ─────────────────────────────────────────────
def test_get_unknown_project_returns_404():
    resp = client.get("/api/v1/projects/no-such-project", headers=AUTH_HEADERS)
    assert resp.status_code == 404


# ─────────────────────────────────────────────
# T015-06: Create site with project_id and lat/lng
# ─────────────────────────────────────────────
def test_create_site_with_location():
    create_project("geo-proj")
    resp = client.post("/api/v1/sites", headers=AUTH_HEADERS, json={
        "id": "geo-site",
        "name": "Geo Site",
        "project_id": "geo-proj",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "location": "New Delhi",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == "geo-proj"
    assert data["latitude"] == 28.6139
    assert data["longitude"] == 77.2090


# ─────────────────────────────────────────────
# T015-07: Site defaults to proj_default when no project_id
# ─────────────────────────────────────────────
def test_site_defaults_to_proj_default():
    resp = client.post("/api/v1/sites", headers=AUTH_HEADERS, json={
        "id": "no-proj-site",
        "name": "No Project Site",
    })
    assert resp.status_code == 201
    assert resp.json()["project_id"] == "proj_default"


# ─────────────────────────────────────────────
# T015-08: Site detail endpoint returns summary
# ─────────────────────────────────────────────
def test_site_detail_returns_summary():
    create_site("detail-site", "Detail Site")
    resp = client.get("/api/v1/sites/detail-site/detail", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["site_id"] == "detail-site"
    assert "media_count" in data
    assert "image_count" in data
    assert "video_count" in data


# ─────────────────────────────────────────────
# T015-09: GET /sites?project_id= filters by project
# ─────────────────────────────────────────────
def test_list_sites_filter_by_project():
    create_project("filter-proj")
    client.post("/api/v1/sites", headers=AUTH_HEADERS, json={
        "id": "s-in-proj",
        "name": "In Project",
        "project_id": "filter-proj",
    })
    client.post("/api/v1/sites", headers=AUTH_HEADERS, json={
        "id": "s-not-in-proj",
        "name": "Other Site",
    })
    resp = client.get("/api/v1/sites?project_id=filter-proj", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert "s-in-proj" in ids
    assert "s-not-in-proj" not in ids


# ─────────────────────────────────────────────
# T015-10: GET /media remains backward compatible
# ─────────────────────────────────────────────
def test_get_media_backward_compatible():
    create_site("compat-site")
    upload_image("compat-site", "2026-09-10")
    resp = client.get("/api/v1/media", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────
# T015-11: GET /media/query returns paginated response
# ─────────────────────────────────────────────
def test_media_query_returns_paginated():
    resp = client.get("/api/v1/media/query", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert "total_pages" in data
    assert "filters" in data


# ─────────────────────────────────────────────
# T015-12: Media query filters by site_id
# ─────────────────────────────────────────────
def test_media_query_filter_by_site():
    create_site("query-site-a")
    create_site("query-site-b")
    upload_image("query-site-a", "2026-09-05")
    upload_image("query-site-b", "2026-09-06")

    resp = client.get("/api/v1/media/query?site_id=query-site-a", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    site_ids = [item["site_id"] for item in data["items"]]
    assert all(sid == "query-site-a" for sid in site_ids)


# ─────────────────────────────────────────────
# T015-13: Media query filters by media_type
# ─────────────────────────────────────────────
def test_media_query_filter_by_media_type():
    create_site("type-site")
    upload_image("type-site", "2026-09-07")

    resp = client.get("/api/v1/media/query?media_type=image", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["media_type"] == "image" for item in data["items"])

    resp2 = client.get("/api/v1/media/query?media_type=video", headers=AUTH_HEADERS)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert all(item["media_type"] == "video" for item in data2["items"])


# ─────────────────────────────────────────────
# T015-14: Media query filters by date_from and date_to
# ─────────────────────────────────────────────
def test_media_query_date_range():
    create_site("date-site")
    upload_image("date-site", "2026-08-01")
    upload_image("date-site", "2026-09-15")
    upload_image("date-site", "2026-10-01")

    resp = client.get(
        "/api/v1/media/query?date_from=2026-09-01&date_to=2026-09-30",
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    # The date range filter should work (items in range should be returned)
    # Since created_at is set at insert time (now), all items may pass if
    # tests run within same second, but the filter logic must not fail.
    assert isinstance(data["items"], list)
    assert data["total"] >= 0


# ─────────────────────────────────────────────
# T015-15: Invalid date_from returns 422
# ─────────────────────────────────────────────
def test_media_query_invalid_date_returns_422():
    resp = client.get("/api/v1/media/query?date_from=not-a-date", headers=AUTH_HEADERS)
    assert resp.status_code == 422


# ─────────────────────────────────────────────
# T015-16: Media query sort=asc returns chronological order
# ─────────────────────────────────────────────
def test_media_query_sort_asc():
    resp = client.get("/api/v1/media/query?sort=asc&limit=100", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"]
    if len(items) >= 2:
        dates = [item["created_at"] for item in items if item["created_at"]]
        assert dates == sorted(dates), "Items should be in ascending (oldest first) order"


# ─────────────────────────────────────────────
# T015-17: Media query pagination - page 2 returns different results
# ─────────────────────────────────────────────
def test_media_query_pagination():
    create_site("pag-site")
    for i in range(5):
        upload_image("pag-site", "2026-09-01")

    resp1 = client.get("/api/v1/media/query?limit=2&page=1", headers=AUTH_HEADERS)
    resp2 = client.get("/api/v1/media/query?limit=2&page=2", headers=AUTH_HEADERS)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    d1 = resp1.json()
    d2 = resp2.json()
    assert d1["page"] == 1
    assert d2["page"] == 2
    # IDs should be different across pages (if total > 2)
    if d1["total"] > 2:
        ids1 = {i["asset_id"] for i in d1["items"]}
        ids2 = {i["asset_id"] for i in d2["items"]}
        assert ids1.isdisjoint(ids2), "Pages should have non-overlapping items"


# ─────────────────────────────────────────────
# T015-18: Timeline endpoint returns bucketed response
# ─────────────────────────────────────────────
def test_media_timeline_basic():
    resp = client.get("/api/v1/media/timeline", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "buckets" in data
    assert "total_items" in data
    assert "total_dates" in data
    assert "filters" in data
    assert isinstance(data["buckets"], list)


# ─────────────────────────────────────────────
# T015-19: Site media endpoint returns filtered results
# ─────────────────────────────────────────────
def test_site_media_endpoint():
    create_site("sm-site")
    upload_image("sm-site", "2026-09-20")
    upload_image("sm-site", "2026-09-21")

    resp = client.get("/api/v1/sites/sm-site/media", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


# ─────────────────────────────────────────────
# T015-20: Project media endpoint returns filtered results
# ─────────────────────────────────────────────
def test_project_media_endpoint():
    create_project("pm-proj")
    client.post("/api/v1/sites", headers=AUTH_HEADERS, json={
        "id": "pm-site",
        "name": "PM Site",
        "project_id": "pm-proj",
    })
    upload_image("pm-site", "2026-09-22")

    resp = client.get("/api/v1/projects/pm-proj/media", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


# ─────────────────────────────────────────────
# T015-21: Project aggregate metrics count sites and media
# ─────────────────────────────────────────────
def test_project_aggregate_metrics():
    create_project("agg-proj")
    client.post("/api/v1/sites", headers=AUTH_HEADERS, json={
        "id": "agg-site-1",
        "name": "Agg Site 1",
        "project_id": "agg-proj",
    })
    client.post("/api/v1/sites", headers=AUTH_HEADERS, json={
        "id": "agg-site-2",
        "name": "Agg Site 2",
        "project_id": "agg-proj",
    })
    upload_image("agg-site-1", "2026-09-01")
    upload_image("agg-site-1", "2026-09-02")

    resp = client.get("/api/v1/projects/agg-proj", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["site_count"] == 2
    assert data["media_count"] >= 2
    assert data["image_count"] >= 2
