"""Comprehensive tests for Milestone T016: AI Media Intelligence + Discovery Foundation.

Validates:
1. Intelligence schema validation
2. Valid Gemini result parsing
3. Malformed Gemini response handling
4. Tag normalization and controlled taxonomy
5. Signal validation
6. Grounding and uncertainty handling
7. Warning extraction
8. Asset provenance
9. Frame provenance
10. Persistence in SQLite
11. Analysis status transitions
12. Unavailable Gemini credentials handling
13. Failed analysis resilience
14. Re-analysis and history preservation
15. API analyze endpoint
16. API intelligence retrieval endpoint
17. API history endpoint
18. Batch analysis with per-asset failure isolation and limit bounds
19. Media query filtering by tag, signal, and ai_status
20. SkillRuntime integration
21. WorkflowEngine compatibility
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.config import settings
from app.main import app
from app.schemas.api import (
    BatchMediaAnalysisRequest,
    IntelligenceStatus,
    MediaAnalysisRequest,
    MediaIntelligenceRecord,
)
from app.services import evidence_store as store
from app.services.media_intelligence import (
    analyze_asset,
    analyze_batch,
    get_asset_intelligence,
    get_asset_intelligence_history,
    normalize_signals,
    normalize_tag,
    normalize_tags,
    row_to_intelligence_record,
)
from app.skills import (
    SkillExecutionRequest,
    SkillExecutionStatus,
    get_default_registry,
    get_default_runtime,
)
from app.skills.builtins.media_intelligence import (
    CONTROLLED_SIGNALS,
    CONTROLLED_TAGS,
    MediaIntelligenceSkill,
)
from app.skills.builtins.field_frame_observation import FieldFrameObservationSkill
from app.workflows.engine import WorkflowEngine
from app.workflows.models import (
    NodeExecutionStatus,
    WorkflowDefinition,
    WorkflowExecutionRequest,
    WorkflowExecutionStatus,
    WorkflowNode,
)


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Isolated SQLite database and auth fixture."""
    db_file = tmp_path / "test_media_intel.sqlite3"
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(db_file))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("test-upload-token"))
    monkeypatch.setattr(settings, "REVIEWER_TOKENS", SecretStr('{"Tester":"test-reviewer-token"}'))

    with store.connection() as conn:
        now = store.timestamp()
        # Seed test project and site directly via SQL
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            ("proj_t016", "T016 Environmental Project", "Testing AI Media Intelligence", now),
        )
        conn.execute(
            "INSERT INTO sites (id, name, location, description, project_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("site_t016", "River Clean Zone", "North Basin", "Clean zone description", "proj_t016", now),
        )
        conn.execute(
            "INSERT INTO visits (id, site_id, visited_on, label) VALUES (?, ?, ?, ?)",
            ("visit_t016", "site_t016", "2026-09-27", "T016 Survey Visit"),
        )
        # Seed test asset 1
        store.save_asset(conn, {
            "asset_id": "asset_intel_001",
            "visit_id": "visit_t016",
            "public_id": "setowa/asset_intel_001",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
            "source": "Ranger Cam A",
            "width": 1280,
            "height": 720,
            "format": "jpg",
            "permission_status": "granted",
            "site_id": "site_t016",
            "project_id": "proj_t016",
            "media_type": "image",
            "created_at": "2026-09-27T10:00:00Z",
        })
        # Seed second test asset for batching
        store.save_asset(conn, {
            "asset_id": "asset_intel_002",
            "visit_id": "visit_t016",
            "public_id": "setowa/asset_intel_002",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/demo/image/upload/sample2.jpg",
            "source": "Ranger Cam B",
            "width": 1920,
            "height": 1080,
            "format": "jpg",
            "permission_status": "granted",
            "site_id": "site_t016",
            "project_id": "proj_t016",
            "media_type": "image",
            "created_at": "2026-09-27T10:05:00Z",
        })
        # Seed video frame for frame provenance
        store.save_video_frame(conn, {
            "frame_id": "frame_t016_01",
            "asset_id": "asset_intel_001",
            "frame_index": 0,
            "timestamp_seconds": 2.5,
            "frame_url": "https://res.cloudinary.com/demo/video/upload/so_2.5/sample.jpg",
            "source_video_url": "https://res.cloudinary.com/demo/video/upload/sample.mp4",
            "width": 640,
            "height": 360,
        })
    return str(db_file)


AUTH_HEADERS = {"Authorization": "Bearer test-upload-token"}


# ==============================================================================
# 1. Intelligence Schema Validation
# ==============================================================================
def test_intelligence_schema_validation():
    valid_data = {
        "id": "rec_001",
        "asset_id": "asset_001",
        "frame_id": None,
        "status": "analyzed",
        "description": "Clear shoreline with riparian plants.",
        "observations": ["OBSERVED: Water line", "OBSERVED: Grass"],
        "tags": ["vegetation", "water"],
        "signals": ["vegetation_cover", "standing_water"],
        "activity": "debris cleanup",
        "warnings": [],
        "uncertainty": None,
        "evidence": {"source_url": "https://example.com/img.jpg"},
        "model_provider": "gemini",
        "model_name": "gemini-2.0-flash",
        "created_at": "2026-09-27T10:00:00Z",
        "updated_at": "2026-09-27T10:00:00Z",
    }
    record = MediaIntelligenceRecord(**valid_data)
    assert record.id == "rec_001"
    assert record.status == "analyzed"
    assert "vegetation" in record.tags


# ==============================================================================
# 2. Tag Normalization & Controlled Taxonomy
# ==============================================================================
def test_tag_normalization():
    assert normalize_tag("  VEGETATION  ") == "vegetation"
    assert normalize_tag("Surface-Erosion") == "surface_erosion"
    assert normalize_tag("clean up") == "clean_up"

    raw = ["VEGETATION", "debris", "Unknown-Concept", "vegetation", "Water", ""]
    norm = normalize_tags(raw)
    assert "vegetation" in norm
    assert "debris" in norm
    assert "water" in norm
    assert "unknown_concept" in norm
    assert len(norm) == len(set(norm))


# ==============================================================================
# 3. Signal Normalization
# ==============================================================================
def test_signal_normalization():
    raw_signals = ["vegetation-cover", "VISIBLE_WASTE", "vegetation_cover"]
    norm = normalize_signals(raw_signals)
    assert norm == ["vegetation_cover", "visible_waste"]


# ==============================================================================
# 4. Valid Gemini Result Parsing in Skill
# ==============================================================================
def test_valid_gemini_parsing():
    skill = MediaIntelligenceSkill()
    gemini_body = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps({
                        "description": "Gravel shoreline with accumulated plastics and driftwood.",
                        "observations": [
                            "OBSERVED: Gravel terrain bordering river water",
                            "OBSERVED: Mixed plastic litter and wooden debris",
                        ],
                        "tags": ["water", "sediment", "debris", "plastic"],
                        "detected_signals": ["debris_accumulation", "visible_waste", "standing_water"],
                        "activity": "debris cleanup",
                        "status": "analyzed",
                        "warnings": [],
                        "uncertainty": None,
                    })
                }]
            }
        }]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = gemini_body

    mock_img_resp = MagicMock()
    mock_img_resp.status_code = 200
    mock_img_resp.content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 200

    with patch("httpx.AsyncClient.get", return_value=mock_img_resp), \
         patch("httpx.AsyncClient.post", return_value=mock_resp), \
         patch("app.config.settings.GEMINI_API_KEY", "dummy-gemini-key"):
        result = asyncio.run(skill.execute(
            {"media_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg", "asset_id": "a1"},
            {},
        ))

    assert result.status == SkillExecutionStatus.SUCCESS
    assert result.outputs["status"] == "analyzed"
    assert "plastic" in result.outputs["tags"]
    assert "debris_accumulation" in result.outputs["detected_signals"]
    assert result.outputs["activity"] == "debris cleanup"


# ==============================================================================
# 5. Malformed Gemini Response Handling
# ==============================================================================
def test_malformed_gemini_response_handling():
    skill = MediaIntelligenceSkill()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": "This is plain unstructured text, not valid JSON."}]
            }
        }]
    }

    mock_img_resp = MagicMock()
    mock_img_resp.status_code = 200
    mock_img_resp.content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 200

    with patch("httpx.AsyncClient.get", return_value=mock_img_resp), \
         patch("httpx.AsyncClient.post", return_value=mock_resp), \
         patch("app.config.settings.GEMINI_API_KEY", "dummy-gemini-key"):
        result = asyncio.run(skill.execute(
            {"media_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg", "asset_id": "a1"},
            {},
        ))

    assert result.status == SkillExecutionStatus.SUCCESS
    assert result.outputs["status"] == "uncertain"
    assert "malformed_model_response" in result.outputs["warnings"]


# ==============================================================================
# 6. Grounding and Uncertainty Handling
# ==============================================================================
def test_uncertainty_and_warnings():
    skill = MediaIntelligenceSkill()
    gemini_body = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps({
                        "description": "Heavily motion-blurred scene near riverbank.",
                        "observations": ["OBSERVED: Blur and extreme motion glare."],
                        "tags": ["water"],
                        "detected_signals": [],
                        "activity": None,
                        "status": "insufficient_evidence",
                        "warnings": ["blur", "poor_lighting"],
                        "uncertainty": "Severe motion blur prevents visual verification.",
                    })
                }]
            }
        }]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = gemini_body

    mock_img_resp = MagicMock()
    mock_img_resp.status_code = 200
    mock_img_resp.content = b"\xFF\xD8\xFF\xE0" + b"\x00" * 200

    with patch("httpx.AsyncClient.get", return_value=mock_img_resp), \
         patch("httpx.AsyncClient.post", return_value=mock_resp), \
         patch("app.config.settings.GEMINI_API_KEY", "dummy-gemini-key"):
        result = asyncio.run(skill.execute(
            {"media_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg", "asset_id": "a1"},
            {},
        ))

    assert result.outputs["status"] == "insufficient_evidence"
    assert "blur" in result.outputs["warnings"]
    assert "Severe motion blur" in result.outputs["uncertainty"]


# ==============================================================================
# 7. Asset & Frame Provenance
# ==============================================================================
def test_asset_and_frame_provenance(test_db):
    with store.connection() as conn:
        with patch("app.services.media_intelligence.get_default_runtime") as mock_get_rt:
            mock_rt = MagicMock()
            mock_rt.execute = AsyncMock(return_value=MagicMock(
                status=SkillExecutionStatus.SUCCESS,
                errors=[],
                outputs={
                    "description": "Video frame at 2.5s showing riverbed gravel.",
                    "observations": ["OBSERVED: Gravel riverbed."],
                    "tags": ["sediment", "water"],
                    "detected_signals": ["clear_ground"],
                    "activity": "site inspection",
                    "status": "analyzed",
                    "warnings": [],
                    "uncertainty": None,
                    "evidence": {
                        "source_url": "https://res.cloudinary.com/demo/video/upload/so_2.5/sample.jpg",
                        "asset_id": "asset_intel_001",
                        "frame_id": "frame_t016_01",
                    },
                    "model_name": "gemini-2.0-flash",
                    "model_provider": "gemini",
                }
            ))
            mock_get_rt.return_value = mock_rt

            record = asyncio.run(analyze_asset(conn, "asset_intel_001", frame_id="frame_t016_01"))
            assert record.asset_id == "asset_intel_001"
            assert record.frame_id == "frame_t016_01"
            assert record.evidence["source_url"].endswith("so_2.5/sample.jpg")


# ==============================================================================
# 8. SQLite Persistence and Retrieval
# ==============================================================================
def test_persistence_and_retrieval(test_db):
    with store.connection() as conn:
        data = {
            "id": "persist_001",
            "asset_id": "asset_intel_001",
            "frame_id": None,
            "status": "analyzed",
            "description": "Field test description",
            "observations": json.dumps(["OBSERVED: Test rock"]),
            "tags_json": json.dumps(["sediment"]),
            "signals_json": json.dumps(["clear_ground"]),
            "activity": "idle site",
            "warnings_json": json.dumps([]),
            "uncertainty": None,
            "evidence_json": json.dumps({"source": "manual_test"}),
            "model_provider": "gemini",
            "model_name": "gemini-flash-latest",
        }
        saved = store.save_media_intelligence(conn, data)
        assert saved["id"] == "persist_001"

        retrieved = store.get_media_intelligence(conn, "asset_intel_001")
        assert retrieved is not None
        assert retrieved["id"] == "persist_001"
        assert retrieved["description"] == "Field test description"


# ==============================================================================
# 9. Unavailable Gemini Handling
# ==============================================================================
def test_unavailable_gemini_handling():
    skill = MediaIntelligenceSkill()
    with patch("app.config.settings.GEMINI_API_KEY", ""):
        result = asyncio.run(skill.execute(
            {"media_url": "https://example.com/test.jpg", "asset_id": "asset_01"},
            {},
        ))
    assert result.status == SkillExecutionStatus.UNAVAILABLE
    assert result.outputs["status"] == "unavailable"
    assert "provider_unavailable" in result.outputs["warnings"][0]


# ==============================================================================
# 10. Failed Analysis Handling (Network Error)
# ==============================================================================
def test_failed_analysis_resilience():
    skill = MediaIntelligenceSkill()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.json.return_value = {"error": {"message": "Internal quota exceeded"}}

    mock_img_resp = MagicMock()
    mock_img_resp.status_code = 200
    mock_img_resp.content = b"\xFF\xD8\xFF\xE0" + b"\x00" * 100

    with patch("httpx.AsyncClient.get", return_value=mock_img_resp), \
         patch("httpx.AsyncClient.post", return_value=mock_resp), \
         patch("app.config.settings.GEMINI_API_KEY", "dummy-gemini-key"):
        result = asyncio.run(skill.execute(
            {"media_url": "https://example.com/test.jpg", "asset_id": "asset_01"},
            {},
        ))

    assert result.status == SkillExecutionStatus.FAILED
    assert result.outputs["status"] == "failed"


# ==============================================================================
# 11. Re-analysis and History Preservation
# ==============================================================================
def test_reanalysis_and_history(test_db):
    with store.connection() as conn:
        with patch("app.services.media_intelligence.get_default_runtime") as mock_get_rt:
            mock_rt = MagicMock()
            # First run: uncertain
            mock_rt.execute = AsyncMock(return_value=MagicMock(
                status=SkillExecutionStatus.SUCCESS,
                errors=[],
                outputs={
                    "description": "Initial uncertain run.",
                    "observations": ["Ambiguous terrain"],
                    "tags": ["water"],
                    "detected_signals": [],
                    "activity": None,
                    "status": "uncertain",
                    "warnings": ["low_visual_evidence"],
                    "uncertainty": "Scene ambiguous",
                    "model_name": "gemini-flash-v1",
                    "model_provider": "gemini",
                }
            ))
            mock_get_rt.return_value = mock_rt

            r1 = asyncio.run(analyze_asset(conn, "asset_intel_001", force_reanalyze=True))
            assert r1.status == "uncertain"

            # Second run: re-analyzed with clear evidence
            mock_rt.execute = AsyncMock(return_value=MagicMock(
                status=SkillExecutionStatus.SUCCESS,
                errors=[],
                outputs={
                    "description": "Re-analyzed clear riverbank terrain.",
                    "observations": ["OBSERVED: Clear gravel bar"],
                    "tags": ["water", "sediment"],
                    "detected_signals": ["clear_ground"],
                    "activity": "site inspection",
                    "status": "analyzed",
                    "warnings": [],
                    "uncertainty": None,
                    "model_name": "gemini-2.0-flash",
                    "model_provider": "gemini",
                }
            ))

            r2 = asyncio.run(analyze_asset(conn, "asset_intel_001", force_reanalyze=True))
            assert r2.status == "analyzed"
            assert r2.id != r1.id

            # Check history contains both records
            history = get_asset_intelligence_history(conn, "asset_intel_001")
            assert len(history) == 2
            assert history[0].status == "analyzed"
            assert history[1].status == "uncertain"


# ==============================================================================
# 12. API: POST /api/v1/media/{asset_id}/analyze
# ==============================================================================
def test_api_analyze(test_db):
    client = TestClient(app)
    with patch("app.services.media_intelligence.get_default_runtime") as mock_get_rt:
        mock_rt = MagicMock()
        mock_rt.execute = AsyncMock(return_value=MagicMock(
            status=SkillExecutionStatus.SUCCESS,
            errors=[],
            outputs={
                "description": "API analyzed riverbank evidence.",
                "observations": ["OBSERVED: Water and vegetation"],
                "tags": ["water", "vegetation"],
                "detected_signals": ["vegetation_cover"],
                "activity": "site inspection",
                "status": "analyzed",
                "warnings": [],
                "uncertainty": None,
                "model_name": "gemini-2.0-flash",
                "model_provider": "gemini",
            }
        ))
        mock_get_rt.return_value = mock_rt

        resp = client.post(
            "/api/v1/media/asset_intel_001/analyze",
            headers=AUTH_HEADERS,
            json={"context": "Verify riparian buffer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_id"] == "asset_intel_001"
        assert data["status"] == "analyzed"
        assert "vegetation" in data["tags"]


# ==============================================================================
# 13. API: GET /api/v1/media/{asset_id}/intelligence
# ==============================================================================
def test_api_get_intelligence(test_db):
    client = TestClient(app)
    # First query non-analyzed asset -> 404
    resp_empty = client.get("/api/v1/media/asset_intel_002/intelligence", headers=AUTH_HEADERS)
    assert resp_empty.status_code == 404

    # Seed intelligence for asset_intel_002
    with store.connection() as conn:
        store.save_media_intelligence(conn, {
            "id": "rec_002",
            "asset_id": "asset_intel_002",
            "status": "analyzed",
            "description": "Seeded intelligence record",
            "observations": json.dumps(["OBSERVED: Shoreline"]),
            "tags_json": json.dumps(["shoreline"]),
            "signals_json": json.dumps(["standing_water"]),
            "warnings_json": json.dumps([]),
        })

    resp = client.get("/api/v1/media/asset_intel_002/intelligence", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "analyzed"
    assert resp.json()["description"] == "Seeded intelligence record"


# ==============================================================================
# 14. API: GET /api/v1/media/{asset_id}/intelligence/history
# ==============================================================================
def test_api_get_history(test_db):
    client = TestClient(app)
    with store.connection() as conn:
        store.save_media_intelligence(conn, {
            "id": "hist_1",
            "asset_id": "asset_intel_001",
            "status": "uncertain",
            "description": "Run 1",
            "created_at": "2026-09-27T09:00:00Z",
            "updated_at": "2026-09-27T09:00:00Z",
        })
        store.save_media_intelligence(conn, {
            "id": "hist_2",
            "asset_id": "asset_intel_001",
            "status": "analyzed",
            "description": "Run 2",
            "created_at": "2026-09-27T10:00:00Z",
            "updated_at": "2026-09-27T10:00:00Z",
        })

    resp = client.get("/api/v1/media/asset_intel_001/intelligence/history", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 2
    assert items[0]["description"] == "Run 2"
    assert items[1]["description"] == "Run 1"


# ==============================================================================
# 15. API: POST /api/v1/media/{asset_id}/reanalyze
# ==============================================================================
def test_api_reanalyze(test_db):
    client = TestClient(app)
    with patch("app.services.media_intelligence.get_default_runtime") as mock_get_rt:
        mock_rt = MagicMock()
        mock_rt.execute = AsyncMock(return_value=MagicMock(
            status=SkillExecutionStatus.SUCCESS,
            errors=[],
            outputs={
                "description": "Forced re-analysis output.",
                "observations": ["OBSERVED: Clear terrain"],
                "tags": ["cleanup"],
                "detected_signals": ["active_cleanup"],
                "activity": "cleanup",
                "status": "analyzed",
                "warnings": [],
                "uncertainty": None,
                "model_name": "gemini-2.0-flash",
                "model_provider": "gemini",
            }
        ))
        mock_get_rt.return_value = mock_rt

        resp = client.post("/api/v1/media/asset_intel_001/reanalyze", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["description"] == "Forced re-analysis output."


# ==============================================================================
# 16. Batch Analysis & Failure Isolation
# ==============================================================================
def test_batch_analysis_isolation(test_db):
    with store.connection() as conn:
        with patch("app.services.media_intelligence.get_default_runtime") as mock_get_rt:
            mock_rt = MagicMock()
            # asset_intel_001 succeeds, asset_intel_002 fails
            async def mock_execute(req):
                if req.inputs.get("asset_id") == "asset_intel_001":
                    return MagicMock(
                        status=SkillExecutionStatus.SUCCESS,
                        errors=[],
                        outputs={
                            "description": "Batch item 1 analyzed.",
                            "observations": ["Obs 1"],
                            "tags": ["water"],
                            "detected_signals": ["standing_water"],
                            "activity": None,
                            "status": "analyzed",
                            "warnings": [],
                            "uncertainty": None,
                        }
                    )
                else:
                    return MagicMock(
                        status=SkillExecutionStatus.FAILED,
                        errors=["Simulated network timeout"],
                        outputs={"status": "failed", "warnings": ["timeout"]},
                    )

            mock_rt.execute = AsyncMock(side_effect=mock_execute)
            mock_get_rt.return_value = mock_rt

            batch_resp = asyncio.run(analyze_batch(conn, ["asset_intel_001", "asset_intel_002", "nonexistent_asset"]))
            assert batch_resp.total == 3
            assert batch_resp.processed == 3
            assert batch_resp.successful == 1
            assert batch_resp.failed == 2
            # Per-asset isolation verified: item 1 succeeded even though others failed
            assert batch_resp.results[0].success is True
            assert batch_resp.results[1].success is False
            assert batch_resp.results[2].success is False


# ==============================================================================
# 17. Batch Analysis Bounds Limit Enforcement (> 20 assets)
# ==============================================================================
def test_batch_limit_bounds(test_db):
    client = TestClient(app)
    too_many = [f"asset_{i}" for i in range(25)]
    resp = client.post("/api/v1/media/analyze-batch", headers=AUTH_HEADERS, json={"asset_ids": too_many})
    assert resp.status_code == 422


# ==============================================================================
# 18. Structured Discovery Filtering by Tag, Signal, AI Status
# ==============================================================================
def test_media_query_discovery_filtering(test_db):
    client = TestClient(app)
    # Seed intelligence records
    with store.connection() as conn:
        store.save_media_intelligence(conn, {
            "id": "intel_filt_1",
            "asset_id": "asset_intel_001",
            "status": "analyzed",
            "description": "Wetlands survey",
            "tags_json": json.dumps(["wetlands", "water", "vegetation"]),
            "signals_json": json.dumps(["standing_water", "vegetation_cover"]),
        })
        store.save_media_intelligence(conn, {
            "id": "intel_filt_2",
            "asset_id": "asset_intel_002",
            "status": "uncertain",
            "description": "Dry dirt lot",
            "tags_json": json.dumps(["road", "sediment"]),
            "signals_json": json.dumps(["surface_erosion"]),
        })

    # Filter by tag
    resp_tag = client.get("/api/v1/media/query?tag=vegetation", headers=AUTH_HEADERS)
    assert resp_tag.status_code == 200
    tag_items = resp_tag.json()["items"]
    assert len(tag_items) == 1
    assert tag_items[0]["asset_id"] == "asset_intel_001"

    # Filter by signal
    resp_sig = client.get("/api/v1/media/query?signal=surface_erosion", headers=AUTH_HEADERS)
    assert resp_sig.status_code == 200
    sig_items = resp_sig.json()["items"]
    assert len(sig_items) == 1
    assert sig_items[0]["asset_id"] == "asset_intel_002"

    # Filter by ai_status
    resp_stat = client.get("/api/v1/media/query?ai_status=analyzed", headers=AUTH_HEADERS)
    assert resp_stat.status_code == 200
    assert len(resp_stat.json()["items"]) == 1

    # Filter via /api/v1/media
    resp_list = client.get("/api/v1/media?tag=water", headers=AUTH_HEADERS)
    assert resp_list.status_code == 200
    assert len(resp_list.json()) == 1


# ==============================================================================
# 19. SkillRuntime Integration
# ==============================================================================
def test_skill_runtime_resolves_and_executes_media_intelligence():
    runtime = get_default_runtime()
    req = SkillExecutionRequest(
        skill_name="media-intelligence",
        skill_version="1.0.0",
        inputs={
            "media_url": "/demo/sample-media/synthetic_river_cleanup.jpg",
            "asset_id": "synth_01",
        },
        execution_context={"caller": "test"},
    )
    result = asyncio.run(runtime.execute(req))
    assert result.status == SkillExecutionStatus.SUCCESS
    assert result.outputs["status"] == "analyzed"
    assert "debris" in result.outputs["tags"]
    assert "media-intelligence@1.0.0" in result.metadata["skill_id"]


def test_cloudinary_synthetic_filename_does_not_trigger_demo_output(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    result = asyncio.run(MediaIntelligenceSkill().execute({
        "media_url": "https://res.cloudinary.com/example/image/upload/pilot/synthetic-before.png",
        "asset_id": "pilot-image",
    }, {}))
    assert result.status == SkillExecutionStatus.UNAVAILABLE
    assert result.outputs["model_provider"] == "gemini"
    assert result.outputs["model_name"] != "synthetic-demo"

    frame = asyncio.run(FieldFrameObservationSkill().execute({
        "frame_url": "https://res.cloudinary.com/example/video/upload/pilot/synthetic-frame.jpg",
        "source_asset_id": "pilot-video",
    }, {}))
    assert frame.status == SkillExecutionStatus.UNAVAILABLE
    assert frame.metadata["provider"] != "synthetic-demo"


# ==============================================================================
# 20. WorkflowEngine Compatibility
# ==============================================================================
def test_workflow_engine_compatibility_with_media_intelligence():
    runtime = get_default_runtime()
    registry = get_default_registry()
    engine = WorkflowEngine(runtime=runtime, registry=registry)
    workflow_def = WorkflowDefinition(
        id="wf_media_intel_test",
        name="Media Intelligence Workflow",
        description="Extracts metadata then intelligence",
        nodes=[
            WorkflowNode(
                id="node_intel",
                skill="media-intelligence",
                skill_version="1.0.0",
                inputs={
                    "media_url": "/demo/sample-media/synthetic_river_cleanup.jpg",
                    "asset_id": "synth_wf_01",
                },
            ),
        ],
    )

    req = WorkflowExecutionRequest(inputs={})
    res = asyncio.run(engine.execute(workflow_def, req))
    assert res.status == WorkflowExecutionStatus.SUCCESS
    assert "node_intel" in res.node_results
    node_res = res.node_results["node_intel"]
    assert node_res.status == NodeExecutionStatus.SUCCESS
    assert node_res.outputs["status"] == "analyzed"
