"""Comprehensive test suite for Milestone T019: Hackathon Demo + Production Hardening.

Covers all 18 required milestone verification areas:
1. Startup configuration validation (validate_environment)
2. Required environment detection and reporting
3. Health endpoint liveness (GET /api/v1/health)
4. Readiness behavior (GET /api/v1/ready)
5. Deterministic demo seed (seed_demo_dataset)
6. CLI happy path (skills, workflows, execution, run status, story show)
7. CLI failure handling (invalid inputs, missing resources)
8. Complete end-to-end demo flow
9. Public story smoke test (HTML and JSON)
10. Public secret-leak checks (zero secrets/tokens in public payloads)
11. CORS behavior and header validation
12. Production configuration safety (validate_production_readiness)
13. Error response sanitization (no raw internal tracebacks)
14. Existing Cloudinary compatibility
15. Existing Gemini compatibility
16. Existing SkillRuntime compatibility
17. Existing WorkflowEngine compatibility
18. Existing evidence verification compatibility
"""
import argparse
import asyncio
import io
import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.services import evidence_store as store
from app.services.env_validator import (
    validate_environment,
    validate_production_readiness,
)
from app.cli import (
    cmd_ingest,
    cmd_run_status,
    cmd_skill_list,
    cmd_story_show,
    cmd_workflow_list,
    cmd_workflow_run,
)
from app.services.impact_story import (
    generate_impact_story,
    get_impact_story_by_id,
    update_impact_story_fields,
)
from app.services.public_story import get_public_impact_story
from app.skills import get_default_registry, get_default_runtime
from app.workflows.engine import WorkflowEngine
from app.workflows.models import (
    NodeExecutionStatus,
    WorkflowDefinition,
    WorkflowExecutionRequest,
    WorkflowExecutionStatus,
    WorkflowNode,
)
from scripts.seed_demo import seed_demo_dataset

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-upload-token"}
REVIEW_HEADERS = {"Authorization": "Bearer test-reviewer-token"}


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Isolated SQLite database and auth fixture for each test."""
    db_file = tmp_path / "test_demo_hardening.sqlite3"
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(db_file))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("test-upload-token"))
    monkeypatch.setattr(settings, "REVIEWER_TOKENS", SecretStr('{"Auditor":"test-reviewer-token"}'))
    monkeypatch.setattr(settings, "CLOUDINARY_CLOUD_NAME", "demo-cloud")
    monkeypatch.setattr(settings, "CLOUDINARY_API_KEY", "demo-key-12345")
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", SecretStr("super-secret-cloudinary-key"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr("super-secret-gemini-key"))
    monkeypatch.setattr(settings, "USE_MOCK", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")


# -------------------------------------------------------------------------
# 1. Startup configuration validation
# -------------------------------------------------------------------------
def test_startup_env_validation():
    """Verify validate_environment reports configuration without leaking values."""
    env_report = validate_environment(settings)
    assert "status" in env_report
    assert "is_complete" in env_report
    assert "missing_variables" in env_report

    # Ensure required keys exist
    for key in ["CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET", "GEMINI_API_KEY"]:
        assert key in env_report["status"]
        assert env_report["status"][key] == "configured"

    # Crucial security check: Ensure no secret value appears in report
    report_str = json.dumps(env_report)
    assert "super-secret" not in report_str
    assert "demo-key-12345" not in report_str


# -------------------------------------------------------------------------
# 2. Required environment detection and reporting
# -------------------------------------------------------------------------
def test_required_env_detection(monkeypatch):
    """Verify missing environment variables are accurately detected."""
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", None)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    env_report = validate_environment(settings)
    assert env_report["is_complete"] is False
    assert "CLOUDINARY_API_SECRET" in env_report["missing_variables"]
    assert "GEMINI_API_KEY" not in env_report["missing_variables"]
    assert env_report["status"]["CLOUDINARY_API_SECRET"] == "missing"
    assert env_report["status"]["GEMINI_API_KEY"] == "missing"


# -------------------------------------------------------------------------
# 3. Health endpoint liveness
# -------------------------------------------------------------------------
def test_health_endpoint():
    """Verify GET /api/v1/health returns healthy liveness probe."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data
    assert data["mock_mode"] is True


# -------------------------------------------------------------------------
# 4. Readiness behavior
# -------------------------------------------------------------------------
def test_readiness_endpoint():
    """Verify GET /api/v1/ready returns operational readiness probe."""
    res = client.get("/api/v1/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("ready", "degraded")
    assert data["database"] == "ready"
    assert data["cloudinary"] in ("configured", "missing")
    assert data["gemini"] in ("configured", "missing")
    # Ensure no secrets leaked in ready response
    content_str = res.text
    assert "super-secret" not in content_str


# -------------------------------------------------------------------------
# 5. Deterministic demo seed
# -------------------------------------------------------------------------
def test_deterministic_demo_seed():
    """Verify seed_demo_dataset populates all lifecycle tables idempotently."""
    summary = seed_demo_dataset()
    assert summary["project_id"] == "proj_mombasa_marine"
    assert summary["site_id"] == "site_nyali_creek"
    assert summary["share_token"] is None
    assert summary["asset_count"] >= 3
    assert summary["frame_count"] >= 3

    # Direct DB verification
    with store.connection() as conn:
        proj = conn.execute("SELECT id, name FROM projects WHERE id = ?", ("proj_mombasa_marine",)).fetchone()
        assert proj is not None
        assert "Mombasa" in proj["name"]

        assets = conn.execute("SELECT asset_id FROM assets WHERE project_id = ?", ("proj_mombasa_marine",)).fetchall()
        assert len(assets) >= 3
        assert conn.execute("SELECT COUNT(*) FROM assets WHERE project_id=? AND permission_status='granted'", ("proj_mombasa_marine",)).fetchone()[0] == 0

        derivations = conn.execute("SELECT frame_id FROM video_frames WHERE asset_id = 'ast_mombasa_video'").fetchall()
        assert len(derivations) >= 3

        obs = conn.execute("SELECT id, review_status FROM observations WHERE id = 'obs_mombasa_creek'").fetchone()
        assert obs is not None
        assert obs["review_status"] == "pending"

        story = conn.execute("SELECT id, status, share_token FROM impact_stories WHERE project_id = ?", ("proj_mombasa_marine",)).fetchone()
        assert story is not None
        assert story["status"] == "draft"
        assert story["share_token"] is None
        assert conn.execute("SELECT COUNT(*) FROM measurements WHERE id='msr_mombasa_weigh'").fetchone()[0] == 0

    # Re-running seed must be idempotent and succeed
    summary2 = seed_demo_dataset()
    assert summary2["share_token"] is None


# -------------------------------------------------------------------------
# 6. CLI happy path
# -------------------------------------------------------------------------
def test_cli_happy_path(capsys):
    """Verify all primary SETOWA CLI commands execute successfully."""
    seed_demo_dataset()

    # 1. Skill list
    args_skill = argparse.Namespace()
    assert cmd_skill_list(args_skill) == 0
    captured = capsys.readouterr()
    assert "Total Skills Available:" in captured.out
    assert "evidence-comparison" in captured.out

    # 2. Workflow list
    args_wf = argparse.Namespace()
    assert cmd_workflow_list(args_wf) == 0
    captured = capsys.readouterr()
    assert "Total Workflows Available:" in captured.out
    assert "wf_evidence_compare" in captured.out

    # 3. Workflow run
    args_run = argparse.Namespace(workflow_id="wf_evidence_compare")
    assert cmd_workflow_run(args_run) == 0
    captured = capsys.readouterr()
    assert "Running Workflow:" in captured.out
    assert "SUCCESS" in captured.out

    # 4. Run status
    import re
    match = re.search(r"Execution ID:\s+(\S+)", captured.out)
    assert match is not None
    exec_id = match.group(1)

    args_status = argparse.Namespace(execution_id=exec_id)
    assert cmd_run_status(args_status) == 0
    captured = capsys.readouterr()
    assert "Workflow Execution Detail" in captured.out
    assert exec_id in captured.out

    # 5. Story show
    args_story = argparse.Namespace(project_id="proj_mombasa_marine")
    assert cmd_story_show(args_story) == 0
    captured = capsys.readouterr()
    assert "IMPACT STORY" in captured.out
    assert "illustrative demo" in captured.out


# -------------------------------------------------------------------------
# 7. CLI failure handling
# -------------------------------------------------------------------------
def test_cli_failure_handling(capsys):
    """Verify CLI commands gracefully handle invalid inputs without uncaught exceptions."""
    seed_demo_dataset()

    # Invalid workflow
    args_bad_wf = argparse.Namespace(workflow_id="nonexistent_wf_id", input="{}")
    assert cmd_workflow_run(args_bad_wf) == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err

    # Invalid run id
    args_bad_run = argparse.Namespace(execution_id="nonexistent_run_id")
    assert cmd_run_status(args_bad_run) == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err

    # Invalid project id for story show
    args_bad_story = argparse.Namespace(project_id="nonexistent_proj")
    assert cmd_story_show(args_bad_story) == 1
    captured = capsys.readouterr()
    assert "no impact story found" in captured.err.lower()

    # Invalid directory for ingest
    args_bad_dir = argparse.Namespace(directory="nonexistent_dir_xyz_123")
    assert cmd_ingest(args_bad_dir) == 1
    captured = capsys.readouterr()
    assert "does not exist" in captured.err


# -------------------------------------------------------------------------
# 8. Complete end-to-end demo flow
# -------------------------------------------------------------------------
def test_complete_end_to_end_flow():
    """Verify the entire programmatic SETOWA lifecycle chain end-to-end."""
    # 1. Seed demo dataset
    seed_demo_dataset()

    # 2. Verify media availability & Cloudinary derived frame
    with store.connection() as conn:
        asset = store.get_asset(conn, "ast_mombasa_video")
        assert asset is not None
        assert asset["duration"] == 13.4
        derivs = store.get_video_frames_by_asset(conn, "ast_mombasa_video")
        assert len(derivs) == 3

    # 3. Verify AI intelligence records
    with store.connection() as conn:
        intel = store.get_media_intelligence(conn, "ast_mombasa_video")
        assert intel is not None
        assert intel["status"] == "insufficient_evidence"
        assert intel["model_provider"] == "demo-fixture"

    # 4. Verify skill runtime capability
    registry = get_default_registry()
    skill = registry.get("media-metadata")
    assert skill is not None

    # 5. The fixture must not impersonate a human review.
    with store.connection() as conn:
        obs = store.one(conn, "SELECT * FROM observations WHERE id=?", ("obs_mombasa_creek",))
        assert obs["review_status"] == "pending"
        assert obs["reviewed_by"] is None

    # 6. The unverified draft must not be publicly available.
    with store.connection() as conn:
        public_story = get_public_impact_story(conn, "pst_demo_mombasa_coastal_2026")
        assert public_story is None


# -------------------------------------------------------------------------
# 9. Public story smoke test
# -------------------------------------------------------------------------
def test_unverified_scenario_is_private():
    """A demonstration seed must not publish unsubstantiated field claims."""
    seed_demo_dataset()

    # Public JSON endpoint
    json_res = client.get("/api/v1/public/impact/pst_demo_mombasa_coastal_2026")
    assert json_res.status_code == 404

    # Public HTML page endpoint
    html_res = client.get("/share/pst_demo_mombasa_coastal_2026")
    assert html_res.status_code == 404


# -------------------------------------------------------------------------
# 10. Public secret-leak checks
# -------------------------------------------------------------------------
def test_public_secret_leak_checks():
    """Verify public HTML and JSON endpoints strictly never leak internal secrets or tokens."""
    seed_demo_dataset()

    json_res = client.get("/api/v1/public/impact/pst_demo_mombasa_coastal_2026")
    html_res = client.get("/share/pst_demo_mombasa_coastal_2026")

    for response_text in [json_res.text, html_res.text]:
        assert "super-secret" not in response_text
        assert "test-upload-token" not in response_text
        assert "test-reviewer-token" not in response_text
        assert "demo-key-12345" not in response_text
        assert "LEX_DB_PATH" not in response_text
        assert "sqlite3" not in response_text.lower()
        # Internal observation rejection text should not appear
        assert "Rejected due to poor lighting" not in response_text


# -------------------------------------------------------------------------
# 11. CORS behavior
# -------------------------------------------------------------------------
def test_cors_behavior():
    """Verify CORS headers respond correctly to allowed origins."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    }
    res = client.options("/api/v1/health", headers=headers)
    assert res.status_code in (200, 204)
    # The app should include allow origin header
    assert "access-control-allow-origin" in res.headers


# -------------------------------------------------------------------------
# 12. Production configuration safety
# -------------------------------------------------------------------------
def test_production_configuration_safety(monkeypatch):
    """Verify validate_production_readiness catches dangerous configurations."""
    # 1. Unsafe: Mock mode in production
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "USE_MOCK", True)
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://app.setowa.org")
    monkeypatch.setattr(settings, "CLOUDINARY_CLOUD_NAME", "prod-cloud")
    monkeypatch.setattr(settings, "CLOUDINARY_API_KEY", "prod-key")
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", SecretStr("real-secret"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr("real-gemini"))

    is_ready, violations = validate_production_readiness(settings)
    assert is_ready is False
    assert any("USE_MOCK" in v for v in violations)

    # 2. Unsafe: Wildcard CORS origin in production
    monkeypatch.setattr(settings, "USE_MOCK", False)
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "*")
    is_ready, violations = validate_production_readiness(settings)
    assert is_ready is False
    assert any("allowed_origins" in v.lower() for v in violations)

    # 3. Safe production config
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://app.setowa.org")
    is_ready, violations = validate_production_readiness(settings)
    assert is_ready is False
    assert any("DATABASE_URL" in v for v in violations)


# -------------------------------------------------------------------------
# 13. Error response sanitization
# -------------------------------------------------------------------------
def test_error_response_sanitization():
    """Verify errors return clean JSON without exposing Python stack traces or file paths."""
    res = client.get("/api/v1/impact-stories/nonexistent_story_12345", headers=AUTH_HEADERS)
    assert res.status_code == 404
    data = res.json()
    assert "detail" in data
    res_str = json.dumps(data)
    assert "Traceback" not in res_str
    assert "File \"" not in res_str
    assert ".py" not in res_str


# -------------------------------------------------------------------------
# 14. Existing Cloudinary compatibility
# -------------------------------------------------------------------------
def test_existing_cloudinary_compatibility():
    """Verify Cloudinary URL transformation utilities work as expected."""
    from cloudinary.utils import cloudinary_url
    from app.services.media import FORMATS, VIDEO_FORMATS

    url, _ = cloudinary_url("setowa/demo_image", cloud_name="demo", width=800, height=600, crop="fill", format="webp")
    assert "res.cloudinary.com" in url
    assert "w_800" in url
    assert "image/jpeg" in FORMATS.values()
    assert "video/mp4" in VIDEO_FORMATS


# -------------------------------------------------------------------------
# 15. Existing Gemini compatibility
# -------------------------------------------------------------------------
def test_existing_gemini_compatibility():
    """Verify Gemini intelligence service initializes and executes with valid schemas."""
    from app.services.ai_engine import AIEngineService
    from app.schemas.api import AnalyzeRequest

    engine = AIEngineService()
    req = AnalyzeRequest(prompt="Assess vegetation density in coastal quadrant", task_type="reasoning")
    res = asyncio.run(engine.execute_reasoning(req))
    assert res.status == "success"
    assert res.task_type == "reasoning"


# -------------------------------------------------------------------------
# 16. Existing SkillRuntime compatibility
# -------------------------------------------------------------------------
def test_existing_skill_runtime_compatibility():
    """Verify SkillRuntime registers and executes default analytical skills."""
    from app.skills import SkillExecutionRequest, SkillExecutionStatus

    runtime = get_default_runtime()
    req = SkillExecutionRequest(
        skill_name="media-metadata",
        inputs={"url": "https://res.cloudinary.com/demo/image/upload/sample.jpg"}
    )
    result = asyncio.run(runtime.execute(req))
    assert result.status == SkillExecutionStatus.SUCCESS
    assert result.outputs is not None


# -------------------------------------------------------------------------
# 17. Existing WorkflowEngine compatibility
# -------------------------------------------------------------------------
def test_existing_workflow_engine_compatibility():
    """Verify WorkflowEngine executes topological multi-node DAG workflows."""
    wf_node1 = WorkflowNode(
        id="n1",
        skill="media-metadata",
        inputs={"url": "https://res.cloudinary.com/demo/image/upload/sample.jpg"},
    )
    wf_node2 = WorkflowNode(
        id="n2",
        skill="media-metadata",
        inputs={"url": "https://res.cloudinary.com/demo/image/upload/sample2.jpg"},
    )
    wf_def = WorkflowDefinition(
        id="wf_test_dag",
        name="Test DAG Workflow",
        description="Verifies DAG sequencing",
        nodes=[wf_node1, wf_node2],
    )

    from app.workflows import get_default_workflow_engine
    engine = get_default_workflow_engine()
    req = WorkflowExecutionRequest(workflow_id="wf_test_dag", inputs={})
    res = asyncio.run(engine.execute(wf_def, req))

    assert res.status == WorkflowExecutionStatus.SUCCESS
    assert "n1" in res.node_results
    assert "n2" in res.node_results
    assert res.node_results["n1"].status == NodeExecutionStatus.SUCCESS
    assert res.node_results["n2"].status == NodeExecutionStatus.SUCCESS


# -------------------------------------------------------------------------
# 18. Existing evidence verification compatibility
# -------------------------------------------------------------------------
def test_existing_evidence_verification_compatibility():
    """Verify human review certification transitions observations and records reviewer attribution."""
    with store.connection() as conn:
        now = store.timestamp()
        conn.execute(
            "INSERT INTO projects (id, name, created_at) VALUES ('p_rev', 'Review Test', ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO sites (id, name, project_id, created_at) VALUES ('s_rev', 'Review Site', 'p_rev', ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO visits (id, site_id, visited_on, label) VALUES ('v_b', 's_rev', '2026-09-01', 'Before Visit')",
        )
        conn.execute(
            "INSERT INTO visits (id, site_id, visited_on, label) VALUES ('v_a', 's_rev', '2026-09-02', 'After Visit')",
        )
        store.save_asset(conn, {
            "asset_id": "ast_b",
            "visit_id": "v_b",
            "public_id": "setowa/b",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/demo/image/upload/b.jpg",
            "source": "field_camera",
            "width": 1920,
            "height": 1080,
            "format": "jpg",
            "created_at": now,
        })
        store.save_asset(conn, {
            "asset_id": "ast_a",
            "visit_id": "v_a",
            "public_id": "setowa/a",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/demo/image/upload/a.jpg",
            "source": "field_camera",
            "width": 1920,
            "height": 1080,
            "format": "jpg",
            "created_at": now,
        })
        conn.execute(
            """INSERT INTO observations
               (id, site_id, before_asset_id, after_asset_id, ai_draft, working_text,
                review_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "obs_pending_rev",
                "s_rev",
                "ast_b",
                "ast_a",
                "Draft observation text",
                "Working observation text",
                "pending",
                now,
                now,
            )
        )

    # Submit review through API
    payload = {
        "decision": "approve",
        "expected_version": 1,
        "text": "Certified 100% waste cleared by manual verification",
    }
    review_res = client.post(
        "/api/v1/observations/obs_pending_rev/review",
        json=payload,
        headers=REVIEW_HEADERS,
    )
    assert review_res.status_code == 200
    rev_data = review_res.json()
    assert rev_data["review_status"] == "approved"
    assert rev_data["reviewed_by"] == "Auditor"
    assert "Certified" in rev_data["approved_text"]
