"""Tests for T011 — Video Pipeline, Bulk Media Ingestion, and Media Library."""
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


@pytest.fixture(autouse=True)
def media_env(monkeypatch, tmp_path):
    db_file = tmp_path / "test_media.sqlite3"
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(db_file))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("test-token"))
    monkeypatch.setattr(settings, "REVIEWER_TOKENS", SecretStr('{"Tester":"test-reviewer-token"}'))
    monkeypatch.setattr(settings, "CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setattr(settings, "CLOUDINARY_API_KEY", "test-key")
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", SecretStr("test-secret"))

    def mock_upload(*args, **kwargs):
        from uuid import uuid4
        resource_type = kwargs.get("resource_type", "image")
        pub_id = kwargs.get("public_id", "test/asset_mock")
        unique_suffix = uuid4().hex[:8]
        if resource_type == "video":
            return {
                "asset_id": f"vid-asset-{unique_suffix}",
                "public_id": pub_id,
                "version": 456,
                "resource_type": "video",
                "format": "mp4",
                "width": 1920,
                "height": 1080,
                "duration": 14.5,
                "secure_url": f"https://res.cloudinary.com/test-cloud/video/upload/v456/{pub_id}.mp4",
            }
        return {
            "asset_id": f"img-asset-{unique_suffix}",
            "public_id": pub_id,
            "version": 789,
            "resource_type": "image",
            "format": "png",
            "width": 800,
            "height": 600,
            "secure_url": f"https://res.cloudinary.com/test-cloud/image/upload/v789/{pub_id}.png",
        }

    mock = Mock(side_effect=mock_upload)
    monkeypatch.setattr(media.cloudinary.uploader, "upload", mock)
    return mock


def sample_png():
    out = io.BytesIO()
    Image.new("RGB", (32, 24), color=(0, 128, 255)).save(out, format="PNG")
    return out.getvalue()


def sample_mp4():
    # Construct a minimal MP4 container header (ftyp box)
    ftyp_box = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42"
    moov_box = b"\x00\x00\x00\x08moov"
    return ftyp_box + moov_box + (b"\x00" * 32)


def test_video_upload_extracts_poster_and_duration():
    """Verify video upload derives poster frames, duration, and persists video media_type."""
    video_data = sample_mp4()
    response = client.post(
        "/api/v1/media/videos",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("field_recording.mp4", video_data, "video/mp4")},
        data={
            "project_id": "river-delta",
            "source": "Ranger aerial sweep",
            "visit_date": "2026-09-24",
            "permission_status": "granted",
        },
    )
    assert response.status_code == 201
    result = response.json()
    assert result["media_type"] == "video"
    assert result["duration"] == 14.5
    assert result["width"] == 1920
    assert result["height"] == 1080
    assert "start_offset_0" in result["thumbnail_url"] or "so_0" in result["thumbnail_url"] or "start_offset" in result["thumbnail_url"]
    assert result["permission_status"] == "granted"
    assert result["site_id"] == "river-delta"

    # Verify persisted in database
    with store.connection() as db:
        saved = store.get_media_item(db, result["asset_id"])
        assert saved is not None
        assert saved["media_type"] == "video"
        assert saved["duration"] == 14.5
        assert saved["original_filename"] == "field_recording.mp4"


def test_video_header_validation():
    """Verify unsupported or corrupted video formats are rejected."""
    # Invalid container signature
    bad_data = b"not a valid video payload"
    resp = client.post(
        "/api/v1/media/videos",
        headers={"Authorization": "Bearer test-token"},
        files={"file": ("test.mp4", bad_data, "video/mp4")},
        data={
            "project_id": "river-delta",
            "source": "Field camera",
            "visit_date": "2026-09-24",
        },
    )
    assert resp.status_code in (415, 422)


def test_bulk_media_mixed_upload():
    """Verify bulk ingestion handles mixed images and videos cleanly."""
    files = [
        ("files", ("survey_1.png", sample_png(), "image/png")),
        ("files", ("survey_2.png", sample_png(), "image/png")),
        ("files", ("drone_sweep.mp4", sample_mp4(), "video/mp4")),
    ]
    response = client.post(
        "/api/v1/media/bulk",
        headers={"Authorization": "Bearer test-token"},
        files=files,
        data={
            "project_id": "coastal-reserve",
            "source": "Field Expedition 2026",
            "visit_date": "2026-09-25",
            "permission_status": "granted",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_files"] == 3
    assert data["successful"] == 3
    assert data["failed"] == 0
    assert len(data["results"]) == 3

    types = [r["asset"]["media_type"] for r in data["results"]]
    assert types == ["image", "image", "video"]

    # Verify preview_url is present on all assets
    for r in data["results"]:
        assert r["status"] == "success"
        assert r["asset"]["preview_url"] is not None
        assert r["asset"]["thumbnail_url"] is not None


def test_bulk_media_partial_failure_resilience():
    """Verify invalid files in a batch do not fail the valid files."""
    files = [
        ("files", ("valid_photo.png", sample_png(), "image/png")),
        ("files", ("corrupted_binary.png", b"corrupted file content", "image/png")),
        ("files", ("valid_clip.mp4", sample_mp4(), "video/mp4")),
    ]
    response = client.post(
        "/api/v1/media/bulk",
        headers={"Authorization": "Bearer test-token"},
        files=files,
        data={
            "project_id": "mangrove-wetlands",
            "source": "Volunteer Team",
            "visit_date": "2026-09-26",
            "permission_status": "granted",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_files"] == 3
    assert data["successful"] == 2
    assert data["failed"] == 1

    # Check that individual status is correctly reported
    assert data["results"][0]["status"] == "success"
    assert data["results"][1]["status"] == "failed"
    assert data["results"][1]["error"] is not None
    assert data["results"][2]["status"] == "success"


def test_media_library_filtering_and_retrieval():
    """Verify listing and filtering media by project, media_type, and permission_status."""
    # Ingest 2 images and 1 video
    client.post(
        "/api/v1/media/bulk",
        headers={"Authorization": "Bearer test-token"},
        files=[
            ("files", ("site_a_photo.png", sample_png(), "image/png")),
            ("files", ("site_a_video.mp4", sample_mp4(), "video/mp4")),
        ],
        data={
            "project_id": "site-alpha",
            "source": "Alpha team",
            "visit_date": "2026-09-20",
            "permission_status": "granted",
        },
    )
    client.post(
        "/api/v1/media/bulk",
        headers={"Authorization": "Bearer test-token"},
        files=[("files", ("site_b_photo.png", sample_png(), "image/png"))],
        data={
            "project_id": "site-beta",
            "source": "Beta team",
            "visit_date": "2026-09-21",
            "permission_status": "pending_verification",
        },
    )

    # 1. Filter by site_id; project_id names the parent project.
    resp_alpha = client.get("/api/v1/media?site_id=site-alpha", headers={"Authorization": "Bearer test-token"})
    assert resp_alpha.status_code == 200
    alpha_items = resp_alpha.json()
    assert len(alpha_items) == 2
    assert all(item["site_id"] == "site-alpha" for item in alpha_items)
    assert all(item["project_id"] == "proj_default" for item in alpha_items)

    # 2. Filter by media_type=video
    resp_video = client.get("/api/v1/media?media_type=video", headers={"Authorization": "Bearer test-token"})
    assert resp_video.status_code == 200
    video_items = resp_video.json()
    assert len(video_items) >= 1
    assert all(item["media_type"] == "video" for item in video_items)

    # 3. Filter by permission_status=pending_verification
    resp_perm = client.get("/api/v1/media?permission_status=pending_verification", headers={"Authorization": "Bearer test-token"})
    assert resp_perm.status_code == 200
    perm_items = resp_perm.json()
    assert len(perm_items) == 1
    assert perm_items[0]["site_id"] == "site-beta"

    # 4. Single item retrieval
    asset_id = alpha_items[0]["asset_id"]
    resp_single = client.get(f"/api/v1/media/{asset_id}", headers={"Authorization": "Bearer test-token"})
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["asset_id"] == asset_id
    assert single_data["secure_url"].startswith("https://res.cloudinary.com")

    # 5. Non-existent asset retrieval returns 404
    resp_404 = client.get("/api/v1/media/non-existent-id", headers={"Authorization": "Bearer test-token"})
    assert resp_404.status_code == 404
