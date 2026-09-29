"""Comprehensive tests for Milestone T014 — Field Video Ingestion & Frame Analytics."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services import evidence_store as store
from app.services.video_frames import (
    calculate_sample_timestamps,
    build_frame_urls,
    extract_frames_for_asset,
    list_frames_for_asset,
    get_single_frame,
    analyze_video_frames,
    get_video_frame_analysis_report,
    FrameExtractionRequest,
    FrameAnalysisRequest,
    MAX_ALLOWED_FRAMES,
)
from app.skills import get_default_registry, get_default_runtime
from app.skills.models import SkillExecutionRequest, SkillExecutionStatus
from app.workflows import get_default_workflow_engine
from app.workflows.models import WorkflowDefinition, WorkflowNode, WorkflowEdge, WorkflowInputDefinition


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Isolated temporary SQLite database for testing."""
    db_file = tmp_path / "test_frames.sqlite3"
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(db_file))
    with store.connection() as db:
        # Create a test site and visit
        db.execute("INSERT OR REPLACE INTO sites (id, name, location) VALUES ('site_test', 'River Site', 'Valley')")
        db.execute("INSERT OR REPLACE INTO visits (id, site_id, visited_on, label) VALUES ('vis_test', 'site_test', '2026-09-20', 'Survey')")
        # Create a video asset
        store.save_asset(db, {
            "asset_id": "ast_video_123",
            "visit_id": "vis_test",
            "public_id": "setowa/site_test/video_field_walkthrough",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/tlf3lv01/video/upload/v1/setowa/site_test/video_field_walkthrough.mp4",
            "source": "Drone Survey",
            "width": 1920,
            "height": 1080,
            "duration": 12.0,
            "format": "mp4",
            "media_type": "video",
            "permission_status": "granted",
            "site_id": "site_test",
            "original_filename": "walkthrough.mp4",
        })
        # Create an image asset (for non-video rejection tests)
        store.save_asset(db, {
            "asset_id": "ast_image_456",
            "visit_id": "vis_test",
            "public_id": "setowa/site_test/photo_still",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/tlf3lv01/image/upload/v1/setowa/site_test/photo_still.jpg",
            "source": "Handheld Camera",
            "width": 1200,
            "height": 800,
            "duration": 0.0,
            "format": "jpg",
            "media_type": "image",
            "permission_status": "granted",
            "site_id": "site_test",
        })
    return db_file


@pytest.fixture
def auth_client(test_db, monkeypatch):
    """TestClient with valid local reviewer cookie/token."""
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("test-upload-token"))
    client = TestClient(app)
    client.headers.update({"Authorization": "Bearer test-upload-token"})
    return client


# -----------------------------------------------------------------------------
# 1. Valid video metadata & retrieval
# -----------------------------------------------------------------------------
def test_valid_video_metadata(test_db):
    with store.connection() as db:
        item = store.get_media_item(db, "ast_video_123")
        assert item is not None
        assert item["media_type"] == "video"
        assert item["duration"] == 12.0
        assert item["width"] == 1920
        assert item["height"] == 1080


# -----------------------------------------------------------------------------
# 2. Non-video rejection
# -----------------------------------------------------------------------------
def test_non_video_rejection(test_db):
    with store.connection() as db:
        with pytest.raises(Exception) as exc:
            extract_frames_for_asset(db, "ast_image_456", FrameExtractionRequest())
        assert "not a video" in str(exc.value)


# -----------------------------------------------------------------------------
# 3. Invalid sampling parameters
# -----------------------------------------------------------------------------
def test_invalid_sampling_parameters():
    with pytest.raises(ValueError, match="interval_seconds must be positive"):
        calculate_sample_timestamps(10.0, interval_seconds=0.0)

    with pytest.raises(ValueError, match="max_frames must be at least 1"):
        calculate_sample_timestamps(10.0, max_frames=0)


# -----------------------------------------------------------------------------
# 4. Frame limit enforcement
# -----------------------------------------------------------------------------
def test_frame_limit_enforcement():
    with pytest.raises(ValueError, match="max_frames cannot exceed"):
        calculate_sample_timestamps(100.0, max_frames=MAX_ALLOWED_FRAMES + 10)

    ts = calculate_sample_timestamps(100.0, interval_seconds=1.0, max_frames=10)
    assert len(ts) == 10


# -----------------------------------------------------------------------------
# 5. Deterministic sampling strategies
# -----------------------------------------------------------------------------
def test_deterministic_sampling_strategies():
    # Strategy 'interval'
    ts_int1 = calculate_sample_timestamps(10.0, interval_seconds=2.0, strategy="interval")
    ts_int2 = calculate_sample_timestamps(10.0, interval_seconds=2.0, strategy="interval")
    assert ts_int1 == ts_int2 == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]

    # Strategy 'uniform'
    ts_uni = calculate_sample_timestamps(10.0, max_frames=5, strategy="uniform")
    assert ts_uni == [0.0, 2.5, 5.0, 7.5, 10.0]

    # Strategy 'timestamps'
    ts_custom = calculate_sample_timestamps(10.0, strategy="timestamps", custom_timestamps=[4.2, 1.5, 8.9, 12.0])
    assert ts_custom == [1.5, 4.2, 8.9, 10.0]


# -----------------------------------------------------------------------------
# 6. Timestamp calculation edge cases
# -----------------------------------------------------------------------------
def test_timestamp_calculation_edge_cases():
    # Zero or negative duration provides safe window
    ts_zero = calculate_sample_timestamps(0.0, interval_seconds=5.0)
    assert 0.0 in ts_zero

    # Single frame limit
    ts_one = calculate_sample_timestamps(10.0, max_frames=1)
    assert ts_one == [0.0]


# -----------------------------------------------------------------------------
# 7. Cloudinary frame transformation generation
# -----------------------------------------------------------------------------
def test_cloudinary_frame_transformation_generation():
    frame_url, thumb_url = build_frame_urls("setowa/demo/sample_video", 3.5, version=2, cloud_name="test_cloud")
    assert "test_cloud" in frame_url
    assert "video/upload" in frame_url
    assert "so_3.50" in frame_url or "so_3.5" in frame_url
    assert frame_url.endswith(".jpg")

    assert "w_400" in thumb_url or "c_fill" in thumb_url
    assert "so_3.50" in thumb_url or "so_3.5" in thumb_url


# -----------------------------------------------------------------------------
# 8. Frame provenance
# -----------------------------------------------------------------------------
def test_frame_provenance(test_db):
    with store.connection() as db:
        res = extract_frames_for_asset(db, "ast_video_123", FrameExtractionRequest(interval_seconds=3.0, max_frames=5))
        assert len(res.frames) > 0
        first_frame = res.frames[0]
        # Frame answers "Which exact video and timestamp produced this frame?"
        assert first_frame.asset_id == "ast_video_123"
        assert first_frame.timestamp_seconds == 0.0
        assert "ast_video_123" in first_frame.frame_id
        assert first_frame.source_video_url == "https://res.cloudinary.com/tlf3lv01/video/upload/v1/setowa/site_test/video_field_walkthrough.mp4"
        assert first_frame.extraction_method == "cloudinary_offset_transform"


# -----------------------------------------------------------------------------
# 9. Frame persistence in SQLite
# -----------------------------------------------------------------------------
def test_frame_persistence(test_db):
    with store.connection() as db:
        res = extract_frames_for_asset(db, "ast_video_123", FrameExtractionRequest(interval_seconds=4.0))
        assert res.total_frames == 4  # 0.0, 4.0, 8.0, 12.0

        persisted = store.get_video_frames_by_asset(db, "ast_video_123")
        assert len(persisted) == 4
        assert persisted[1]["timestamp_seconds"] == 4.0

        single = store.get_video_frame(db, persisted[0]["frame_id"])
        assert single is not None
        assert single["asset_id"] == "ast_video_123"


# -----------------------------------------------------------------------------
# 10. Frame extraction API (POST /media/{asset_id}/frames/extract)
# -----------------------------------------------------------------------------
def test_frame_extraction_api(auth_client):
    resp = auth_client.post(
        "/api/v1/media/ast_video_123/frames/extract",
        json={"interval_seconds": 3.0, "max_frames": 10, "strategy": "interval"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["asset_id"] == "ast_video_123"
    assert data["total_frames"] == 5  # 0, 3, 6, 9, 12
    assert len(data["frames"]) == 5
    assert data["frames"][0]["timestamp_seconds"] == 0.0
    assert data["frames"][1]["timestamp_seconds"] == 3.0


# -----------------------------------------------------------------------------
# 11. Frame listing API (GET /media/{asset_id}/frames)
# -----------------------------------------------------------------------------
def test_frame_listing_api(auth_client):
    # First extract
    auth_client.post("/api/v1/media/ast_video_123/frames/extract", json={"interval_seconds": 6.0})
    # Then list
    resp = auth_client.get("/api/v1/media/ast_video_123/frames")
    assert resp.status_code == 200
    frames = resp.json()
    assert len(frames) == 3  # 0.0, 6.0, 12.0
    assert frames[0]["frame_index"] == 0
    assert frames[1]["frame_index"] == 1


# -----------------------------------------------------------------------------
# 12. Frame inspection API (GET /media/{asset_id}/frames/{frame_id})
# -----------------------------------------------------------------------------
def test_frame_inspection_api(auth_client):
    extract_res = auth_client.post("/api/v1/media/ast_video_123/frames/extract", json={"interval_seconds": 5.0}).json()
    fid = extract_res["frames"][0]["frame_id"]

    resp = auth_client.get(f"/api/v1/media/ast_video_123/frames/{fid}")
    assert resp.status_code == 200
    frame = resp.json()
    assert frame["frame_id"] == fid
    assert frame["asset_id"] == "ast_video_123"

    # Mismatched asset_id returns 404
    resp_bad = auth_client.get(f"/api/v1/media/ast_other_999/frames/{fid}")
    assert resp_bad.status_code in (400, 404)


# -----------------------------------------------------------------------------
# 13. Frame analysis API (POST /media/{asset_id}/frames/analyze)
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_frame_analysis_api(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-only-key")
    # Extract frames
    auth_client.post("/api/v1/media/ast_video_123/frames/extract", json={"interval_seconds": 6.0})

    # Trigger analysis on extracted frames (mocking Gemini call to be deterministic)
    with patch("app.skills.builtins.field_frame_observation.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None

        mock_instance.get = AsyncMock(return_value=MagicMock(status_code=200, content=b"fake_frame_bytes"))
        mock_gemini_resp = MagicMock(status_code=200)
        mock_gemini_resp.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "observations": ["Riparian buffer with rock jetty and natural sediment deposition."],
                            "detected_signals": ["riparian_zone", "sediment", "rocks"],
                            "status": "analyzed",
                            "confidence": 0.91,
                            "warnings": [],
                        })
                    }]
                }
            }]
        }
        mock_instance.post = AsyncMock(return_value=mock_gemini_resp)
        mock_client.return_value = mock_instance

        resp = auth_client.post("/api/v1/media/ast_video_123/frames/analyze", json={})
        assert resp.status_code == 200
        report = resp.json()
        assert report["asset_id"] == "ast_video_123"
        assert report["total_analyzed"] == 3
        assert "riparian_zone" in report["aggregated_signals"]
        assert len(report["frames"]) == 3
        assert report["frames"][0]["status"] == "analyzed"
        assert report["frames"][0]["confidence"] == 0.91


# -----------------------------------------------------------------------------
# 14. field-frame-observation SkillRuntime execution
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_field_frame_observation_skill_runtime():
    runtime = get_default_runtime()

    # Synthetic demo frame execution
    req = SkillExecutionRequest(
        skill_name="field-frame-observation",
        skill_version="1.0.0",
        inputs={
            "frame_url": "/demo/sample-media/synthetic-frame.jpg",
            "timestamp_seconds": 4.5,
            "source_asset_id": "ast_video_demo",
        },
        execution_context={"user_id": "analyst", "granted_permissions": ["media:read", "ai:inference"]},
    )
    result = await runtime.execute(req)
    assert result.status == SkillExecutionStatus.SUCCESS
    assert "riverbank" in result.outputs["detected_signals"]
    assert result.outputs["confidence"] == 0.85
    assert result.evidence["timestamp_seconds"] == 4.5


# -----------------------------------------------------------------------------
# 15. Gemini unavailable handling
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_gemini_unavailable_handling(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    runtime = get_default_runtime()

    req = SkillExecutionRequest(
        skill_name="field-frame-observation",
        skill_version="1.0.0",
        inputs={
            "frame_url": "https://res.cloudinary.com/tlf3lv01/video/upload/so_2.0/test.jpg",
            "timestamp_seconds": 2.0,
        },
        execution_context={"user_id": "analyst", "granted_permissions": ["media:read", "ai:inference"]},
    )
    result = await runtime.execute(req)
    assert result.status == SkillExecutionStatus.UNAVAILABLE
    assert result.outputs["status"] == "insufficient_evidence"
    assert "GEMINI_API_KEY is not configured" in result.outputs["observations"][0]


# -----------------------------------------------------------------------------
# 16. Invalid asset handling (404 and 400)
# -----------------------------------------------------------------------------
def test_invalid_asset_handling(auth_client):
    # Non-existent asset
    resp404 = auth_client.post("/api/v1/media/ast_nonexistent/frames/extract", json={})
    assert resp404.status_code == 404

    # Non-video asset
    resp400 = auth_client.post("/api/v1/media/ast_image_456/frames/extract", json={})
    assert resp400.status_code == 400
    assert "is an image, not a video" in resp400.json()["detail"]


# -----------------------------------------------------------------------------
# 17. Multi-frame analysis & selective frame IDs
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_multi_frame_selective_analysis(test_db):
    with store.connection() as db:
        extract_res = extract_frames_for_asset(db, "ast_video_123", FrameExtractionRequest(interval_seconds=3.0))
        target_fids = [extract_res.frames[0].frame_id, extract_res.frames[2].frame_id]

        with patch("app.skills.builtins.field_frame_observation.httpx.AsyncClient") as mock_client:
            mock_inst = MagicMock()
            mock_inst.__aenter__.return_value = mock_inst
            mock_inst.__aexit__.return_value = None
            mock_inst.get.return_value = MagicMock(status_code=200, content=b"frame_bytes")
            mock_inst.post.return_value = MagicMock(status_code=200, json=lambda: {
                "candidates": [{"content": {"parts": [{"text": json.dumps({
                    "observations": ["Water flow observed"],
                    "detected_signals": ["water", "stream"],
                    "status": "analyzed",
                    "confidence": 0.88,
                    "warnings": [],
                })}]}}]
            })
            mock_client.return_value = mock_inst

            report = await analyze_video_frames(db, "ast_video_123", FrameAnalysisRequest(frame_ids=target_fids))
            assert report.total_analyzed == 2
            analyzed_fids = [f.frame_id for f in report.frames]
            assert analyzed_fids == target_fids


# -----------------------------------------------------------------------------
# 18. Analysis failure behavior
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_analysis_failure_behavior(test_db, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-only-key")
    with store.connection() as db:
        extract_frames_for_asset(db, "ast_video_123", FrameExtractionRequest(interval_seconds=5.0))

        with patch("app.skills.builtins.field_frame_observation.httpx.AsyncClient") as mock_client:
            mock_inst = MagicMock()
            mock_inst.__aenter__.return_value = mock_inst
            mock_inst.__aexit__.return_value = None
            # Network error downloading frame
            mock_inst.get.side_effect = Exception("Cloudinary connection reset")
            mock_client.return_value = mock_inst

            report = await analyze_video_frames(db, "ast_video_123", FrameAnalysisRequest())
            assert report.total_analyzed == len(report.frames)
            for f in report.frames:
                assert f.status == "failed"


# -----------------------------------------------------------------------------
# 19. Existing WorkflowEngine compatibility
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_workflow_engine_frame_observation_compatibility():
    engine = get_default_workflow_engine()

    wf = WorkflowDefinition(
        id="wf_frame_obs_test",
        name="Field Video Frame Analysis Pipeline",
        version="1.0.0",
        description="Workflow orchestrating field-frame-observation skill.",
        inputs=[
            WorkflowInputDefinition(name="frame_url", type="string", required=True),
            WorkflowInputDefinition(name="timestamp", type="number", required=False, default=2.0),
        ],
        nodes=[
            WorkflowNode(
                id="frame_analyzer",
                skill="field-frame-observation",
                skill_version="1.0.0",
                inputs={
                    "frame_url": "$input.frame_url",
                    "timestamp_seconds": "$input.timestamp",
                },
            )
        ],
        edges=[],
    )

    validation = engine.validate(wf)
    assert validation.is_valid is True
    assert validation.execution_order == ["frame_analyzer"]

    # Execute workflow with synthetic frame
    from app.workflows.models import WorkflowExecutionRequest
    res = await engine.execute(
        wf,
        WorkflowExecutionRequest(
            inputs={"frame_url": "/demo/sample-media/synthetic-shoreline.jpg", "timestamp": 2.5},
            execution_context={"user_id": "analyst"},
        ),
    )
    assert res.status.value == "success"
    node_out = res.node_results["frame_analyzer"]
    assert node_out.status.value == "success"
    assert "riverbank" in node_out.outputs["detected_signals"]


@pytest.fixture(autouse=True)
def optional_gemini_contract(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
