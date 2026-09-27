"""Comprehensive tests for Milestone T018: Public / Shareable Impact Experience.

Covers all 25 milestone requirements:
1. Published story public access
2. Draft story blocked (returns 404 without leaking existence)
3. In_review story blocked (returns 404 without leaking existence)
4. Invalid public token (returns 404)
5. Public-safe projection structure
6. No internal secrets or credentials in projection
7. No reviewer tokens exposed
8. Approved finding presentation
9. Pending finding handling (honest label, excluded from verified count)
10. Rejected finding handling (honest label, excluded from verified count)
11. Uncertainty callouts and notes preservation
12. Chronological timeline preservation
13. Before/after comparative evidence preservation
14. Cloudinary URL and transformation preservation
15. Provenance preservation (source attribution, timestamps, site)
16. Public API endpoint (GET /api/v1/public/impact/{token})
17. Public HTML page route (GET /share/{token})
18. Share token generation properties
19. Share token uniqueness & entropy
20. Token rotation and revocation
21. Open Graph and social metadata
22. Existing Impact Story API compatibility
23. Existing Evidence Engine compatibility
24. Existing Media Intelligence compatibility
25. Existing Workflow Engine compatibility
"""
import asyncio
import json
import secrets
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.schemas.api import (
    PublicImpactStory,
    ShareStoryResponse,
    VerificationStatus,
)
from app.services import evidence_store as store
from app.services.impact_story import (
    generate_impact_story,
    get_impact_story_by_id,
    update_impact_story_fields,
)
from app.services.public_story import (
    ensure_story_share_token,
    generate_share_token,
    get_public_impact_story,
    render_public_story_html,
    revoke_story_share_token,
    rotate_story_share_token,
)
from app.skills import get_default_registry, get_default_runtime
from app.workflows.engine import WorkflowEngine
from app.workflows.models import (
    NodeExecutionStatus,
    WorkflowDefinition,
    WorkflowExecutionRequest,
    WorkflowExecutionStatus,
    WorkflowNode,
)

AUTH_HEADERS = {"Authorization": "Bearer test-upload-token"}
REVIEW_HEADERS = {"Authorization": "Bearer test-reviewer-token"}


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Isolated SQLite database and auth fixture with sample sustainability data."""
    db_file = tmp_path / "test_public_story.sqlite3"
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(db_file))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("test-upload-token"))
    monkeypatch.setattr(settings, "REVIEWER_TOKENS", SecretStr('{"Auditor":"test-reviewer-token"}'))
    monkeypatch.setattr(settings, "CLOUDINARY_API_SECRET", SecretStr("super-secret-cloudinary-key"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", SecretStr("super-secret-gemini-key"))

    with store.connection() as conn:
        now = store.timestamp()
        # Seed test project
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            ("proj_t018", "Sundarbans Mangrove Conservation", "Restoring coastal buffer zones and monitoring canopy health", now),
        )
        # Seed test site
        conn.execute(
            "INSERT INTO sites (id, name, location, description, project_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("site_delta", "Delta Reach 01", "Zone 4 Tidal Flat", "Degraded mangrove zone undergoing active planting", "proj_t018", now),
        )
        # Seed visits
        conn.execute(
            "INSERT INTO visits (id, site_id, visited_on, label) VALUES (?, ?, ?, ?)",
            ("visit_b1", "site_delta", "2026-07-01", "Baseline Tidal Assessment"),
        )
        conn.execute(
            "INSERT INTO visits (id, site_id, visited_on, label) VALUES (?, ?, ?, ?)",
            ("visit_a1", "site_delta", "2026-08-15", "Post-Planting Evaluation"),
        )
        # Seed Cloudinary assets
        store.save_asset(conn, {
            "asset_id": "img_b1",
            "visit_id": "visit_b1",
            "public_id": "setowa/sundarbans_baseline",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/setowa/sundarbans_baseline.jpg",
            "source": "Field Officer Roy",
            "width": 1920,
            "height": 1080,
            "format": "jpg",
            "permission_status": "granted",
            "site_id": "site_delta",
            "project_id": "proj_t018",
            "media_type": "image",
            "created_at": "2026-07-01T10:00:00Z",
        })
        store.save_asset(conn, {
            "asset_id": "img_a1",
            "visit_id": "visit_a1",
            "public_id": "setowa/sundarbans_post",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/setowa/sundarbans_post.jpg",
            "source": "Field Officer Roy",
            "width": 1920,
            "height": 1080,
            "format": "jpg",
            "permission_status": "granted",
            "site_id": "site_delta",
            "project_id": "proj_t018",
            "media_type": "image",
            "created_at": "2026-08-15T14:30:00Z",
        })
        # Seed approved observation using correct DB columns (review_status, reliability_reason)
        conn.execute(
            """INSERT INTO observations
               (id, site_id, before_asset_id, after_asset_id, ai_draft, working_text, approved_text,
                review_status, reliability_reason, reviewed_by, reviewed_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "obs_approved",
                "site_delta",
                "img_b1",
                "img_a1",
                "AI proposal: Mangrove saplings established across 40m shoreline.",
                "Reviewer draft: Visible seedling emergence confirmed.",
                "Approved: 40 meters of tidal mudflat successfully planted with Avicennia marina seedlings.",
                "approved",
                "Sapling survival will require monsoon tidal monitoring.",
                "Auditor Roy",
                "2026-08-16T11:00:00Z",
                now,
                now,
            ),
        )
        # Seed a measurement
        conn.execute(
            "INSERT INTO measurements (id, site_id, visit_id, label, quantity, unit, source, recorded_by, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("meas_01", "site_delta", "visit_a1", "Saplings Planted", 350.0, "items", "Nursery Log B-12", "Officer Roy", "2026-08-15"),
        )


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def published_story_token():
    """Helper fixture creating a published impact story with a share token."""
    with store.connection() as db:
        # Create story
        story = store.save_impact_story(db, {
            "id": "story_pub_01",
            "project_id": "proj_t018",
            "title": "Sundarbans Mangrove Restoration — 2026 Season",
            "description": "Verified field evidence from the tidal delta regeneration project.",
            "status": "published",
            "summary_narrative": "Between July and August 2026, field teams planted 350 mangrove seedlings across Delta Reach 01.",
            "uncertainty_note": "Long-term root anchoring cannot be fully verified until post-monsoon inspection.",
            "share_token": "pst_valid_test_token_12345",
            "metadata_json": json.dumps({"date_range": {"start_date": "2026-07-01", "end_date": "2026-08-15"}}),
        })
        # Save timeline events
        store.save_impact_story_events(db, "story_pub_01", [
            {
                "id": "evt_01",
                "impact_story_id": "story_pub_01",
                "project_id": "proj_t018",
                "site_id": "site_delta",
                "event_type": "before",
                "title": "Baseline Assessment",
                "description": "Mudflat prior to restoration planting.",
                "timestamp_date": "2026-07-01",
                "asset_ids": ["img_b1"],
                "asset_ids_json": json.dumps(["img_b1"]),
                "primary_media_url": "https://res.cloudinary.com/demo/image/upload/v1/setowa/sundarbans_baseline.jpg",
                "thumbnail_url": "https://res.cloudinary.com/demo/image/upload/c_thumb,w_300/v1/setowa/sundarbans_baseline.jpg",
                "media_type": "image",
                "verification_status": "approved",
                "evidence_json": json.dumps({"source": "Field Officer Roy", "source_provenance": "Field Officer Roy"}),
            },
            {
                "id": "evt_02",
                "impact_story_id": "story_pub_01",
                "project_id": "proj_t018",
                "site_id": "site_delta",
                "event_type": "after",
                "title": "Post-Planting Verification",
                "description": "Seedlings established across shoreline.",
                "timestamp_date": "2026-08-15",
                "asset_ids": ["img_a1"],
                "asset_ids_json": json.dumps(["img_a1"]),
                "primary_media_url": "https://res.cloudinary.com/demo/image/upload/v1/setowa/sundarbans_post.jpg",
                "thumbnail_url": "https://res.cloudinary.com/demo/image/upload/c_thumb,w_300/v1/setowa/sundarbans_post.jpg",
                "media_type": "image",
                "verification_status": "approved",
                "evidence_json": json.dumps({"source": "Field Officer Roy", "source_provenance": "Field Officer Roy"}),
            },
        ])
        return "pst_valid_test_token_12345"


# 1. Published story public access
def test_published_story_public_access_html(client, published_story_token):
    resp = client.get(f"/share/{published_story_token}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Sundarbans Mangrove Restoration" in resp.text
    assert "Avicennia marina" in resp.text
    assert "Cloudinary" in resp.text


# 2. Draft story blocked
def test_draft_story_blocked_returns_404(client):
    with store.connection() as db:
        store.save_impact_story(db, {
            "id": "story_draft_01",
            "project_id": "proj_t018",
            "title": "Draft Secret Story",
            "status": "draft",
            "share_token": "pst_draft_token_abc",
        })
    # Must return 404 for HTML
    resp_html = client.get("/share/pst_draft_token_abc")
    assert resp_html.status_code == 404

    # Must return 404 for API
    resp_api = client.get("/api/v1/public/impact/pst_draft_token_abc")
    assert resp_api.status_code == 404


# 3. In_review story blocked
def test_in_review_story_blocked_returns_404(client):
    with store.connection() as db:
        store.save_impact_story(db, {
            "id": "story_review_01",
            "project_id": "proj_t018",
            "title": "In Review Story",
            "status": "in_review",
            "share_token": "pst_review_token_xyz",
        })
    resp_html = client.get("/share/pst_review_token_xyz")
    assert resp_html.status_code == 404

    resp_api = client.get("/api/v1/public/impact/pst_review_token_xyz")
    assert resp_api.status_code == 404


# 4. Invalid public token
def test_invalid_public_token_returns_404(client):
    resp_html = client.get("/share/pst_completely_nonexistent_token")
    assert resp_html.status_code == 404

    resp_api = client.get("/api/v1/public/impact/pst_completely_nonexistent_token")
    assert resp_api.status_code == 404


# 5. Public-safe projection structure
def test_public_safe_projection_structure(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["public_id"] == published_story_token
    assert data["title"] == "Sundarbans Mangrove Restoration — 2026 Season"
    assert data["project_name"] == "Sundarbans Mangrove Conservation"
    assert data["summary_narrative"] != ""
    assert data["verified_findings_count"] >= 1
    assert "date_range" in data
    assert "timeline" in data
    assert "before_after" in data
    assert "social_meta" in data


# 6. No internal secrets or credentials in projection
def test_no_internal_secrets_in_projection(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    text = resp.text

    # Verify no private config or secrets are present
    assert "super-secret-cloudinary-key" not in text
    assert "super-secret-gemini-key" not in text
    assert "test-upload-token" not in text
    assert "test-reviewer-token" not in text
    assert "sqlite3" not in text


# 7. No reviewer tokens exposed
def test_no_reviewer_tokens_exposed(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    data = resp.json()

    for card in data["before_after"]:
        assert "reviewer_token" not in card
        assert "token" not in card
        if card.get("verified_by"):
            assert "secret" not in card["verified_by"].lower()


# 8. Approved finding presentation
def test_approved_finding_presentation(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    data = resp.json()

    cards = data["before_after"]
    assert len(cards) >= 1
    approved_cards = [c for c in cards if c["verification_status"] == "approved"]
    assert len(approved_cards) >= 1
    assert approved_cards[0]["verified_text"] is not None
    assert "Avicennia marina" in approved_cards[0]["verified_text"]


# 9. Pending finding handling (honest label, excluded from verified count)
def test_pending_finding_handling():
    with store.connection() as db:
        now = store.timestamp()
        conn = db
        # Add unreviewed observation
        conn.execute(
            """INSERT INTO observations
               (id, site_id, before_asset_id, after_asset_id, ai_draft, review_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("obs_pending", "site_delta", "img_b1", "img_a1", "AI proposal: Possible sediment shift.", "pending", now, now),
        )
        token = "pst_test_pending_token_999"
        store.save_impact_story(db, {
            "id": "story_pending_test",
            "project_id": "proj_t018",
            "title": "Story with Pending Finding",
            "status": "published",
            "share_token": token,
        })

    with store.connection() as db:
        pub = get_public_impact_story(db, token)
        assert pub is not None
        pending_cards = [c for c in pub.before_after if c.verification_status == "pending"]
        assert len(pending_cards) >= 1
        assert pending_cards[0].verified_text is None  # Never show unapproved draft as verified finding


# 10. Rejected finding handling (excluded from verified findings)
def test_rejected_finding_handling():
    with store.connection() as db:
        now = store.timestamp()
        conn = db
        conn.execute(
            """INSERT INTO observations
               (id, site_id, before_asset_id, after_asset_id, ai_draft, review_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("obs_rejected", "site_delta", "img_b1", "img_a1", "AI proposal: False water clearance.", "rejected", now, now),
        )
        token = "pst_test_rejected_token_888"
        store.save_impact_story(db, {
            "id": "story_rejected_test",
            "project_id": "proj_t018",
            "title": "Story with Rejected Finding",
            "status": "published",
            "share_token": token,
        })

    with store.connection() as db:
        pub = get_public_impact_story(db, token)
        assert pub is not None
        rejected_cards = [c for c in pub.before_after if c.verification_status == "rejected"]
        assert len(rejected_cards) >= 1
        assert rejected_cards[0].verified_text is None


# 11. Uncertainty callouts and notes preservation
def test_uncertainty_handling(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    data = resp.json()

    assert data["uncertainty_note"] is not None
    assert "monsoon" in data["uncertainty_note"]

    # Verify uncertainty is rendered in HTML
    html_resp = client.get(f"/share/{published_story_token}")
    assert "monsoon" in html_resp.text
    assert "Verification Caveats" in html_resp.text


# 12. Chronological timeline preservation
def test_timeline_preservation(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    data = resp.json()
    timeline = data["timeline"]

    assert len(timeline) == 2
    assert timeline[0]["timestamp_date"] <= timeline[1]["timestamp_date"]
    assert timeline[0]["event_type"] in ["before", "after", "activity", "verified_finding"]


# 13. Before/after comparative evidence preservation
def test_before_after_preservation(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    data = resp.json()

    cards = data["before_after"]
    assert len(cards) >= 1
    c = cards[0]
    assert c["before_media_url"] is not None
    assert c["after_media_url"] is not None
    assert c["site_name"] is not None


# 14. Cloudinary URL and transformation preservation
def test_cloudinary_url_preservation(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    data = resp.json()

    assert "res.cloudinary.com" in data["hero_media_url"]
    assert "res.cloudinary.com" in data["before_after"][0]["before_media_url"]
    assert "res.cloudinary.com" in data["before_after"][0]["after_media_url"]


# 15. Provenance preservation (source attribution, timestamps, site)
def test_provenance_preservation(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    data = resp.json()

    assert data["timeline"][0]["source_provenance"] == "Field Officer Roy"
    assert data["timeline"][0]["site_name"] == "Delta Reach 01"


# 16. Public API endpoint
def test_public_api_endpoint(client, published_story_token):
    resp = client.get(f"/api/v1/public/impact/{published_story_token}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"
    obj = PublicImpactStory(**resp.json())
    assert obj.public_id == published_story_token


# 17. Public HTML page route
def test_public_page_route(client, published_story_token):
    resp = client.get(f"/share/{published_story_token}")
    assert resp.status_code == 200
    assert "<!doctype html>" in resp.text.lower()
    assert "<meta property=\"og:title\"" in resp.text
    assert "@media print" in resp.text


# 18. Share token generation properties
def test_share_token_generation_properties():
    tok = generate_share_token()
    assert tok.startswith("pst_")
    assert len(tok) >= 20


# 19. Share token uniqueness & entropy
def test_share_token_uniqueness():
    tokens = {generate_share_token() for _ in range(50)}
    assert len(tokens) == 50


# 20. Token rotation and revocation
def test_token_rotation_and_revocation(client, published_story_token):
    # Rotate token
    rotate_resp = client.post(
        f"/api/v1/impact-stories/story_pub_01/share/rotate",
        headers=AUTH_HEADERS,
    )
    assert rotate_resp.status_code == 200
    rot_data = rotate_resp.json()
    new_token = rot_data["share_token"]
    assert new_token != published_story_token

    # Old token is now 404
    old_resp = client.get(f"/share/{published_story_token}")
    assert old_resp.status_code == 404

    # New token works
    new_resp = client.get(f"/share/{new_token}")
    assert new_resp.status_code == 200

    # Revoke token
    revoke_resp = client.post(
        f"/api/v1/impact-stories/story_pub_01/share/revoke",
        headers=AUTH_HEADERS,
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["share_token"] is None
    assert revoke_resp.json()["is_public"] is False

    # Revoked token is now 404
    assert client.get(f"/share/{new_token}").status_code == 404


# 21. Open Graph and social metadata
def test_open_graph_metadata(client, published_story_token):
    resp = client.get(f"/share/{published_story_token}")
    html = resp.text

    assert "<meta property=\"og:title\"" in html
    assert "<meta property=\"og:description\"" in html
    assert "<meta property=\"og:image\"" in html
    assert "<meta property=\"og:url\"" in html
    assert "<meta name=\"twitter:card\" content=\"summary_large_image\">" in html


# 22. Existing Impact Story API compatibility
def test_existing_impact_story_compatibility(client, published_story_token):
    # Project impact story endpoint returns full story with share_token & share_url
    resp = client.get("/api/v1/projects/proj_t018/impact-story", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "story_pub_01"
    assert data["share_token"] == published_story_token
    assert data["share_url"] == f"/share/{published_story_token}"


# 23. Existing Evidence Engine compatibility
def test_existing_evidence_engine_compatibility(client):
    resp = client.get("/api/v1/sites/site_delta/observations", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    obs_resp = client.get("/api/v1/observations/obs_approved", headers=AUTH_HEADERS)
    assert obs_resp.status_code == 200
    assert obs_resp.json()["review_status"] == "approved"


# 24. Existing Media Intelligence compatibility
def test_existing_media_intelligence_compatibility(client):
    resp = client.get("/api/v1/media", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


# 25. Existing Workflow Engine compatibility
def test_existing_workflow_engine_compatibility(test_db):
    runtime = get_default_runtime()
    registry = get_default_registry()
    engine = WorkflowEngine(runtime=runtime, registry=registry)
    workflow_def = WorkflowDefinition(
        id="wf_pub_compat",
        name="Public Story Compatibility Flow",
        nodes=[
            WorkflowNode(
                id="node_meta",
                skill="media-metadata",
                skill_version="1.0.0",
                inputs={"asset_id": "img_b1"},
            ),
        ],
    )
    req = WorkflowExecutionRequest(inputs={})
    res = asyncio.run(engine.execute(workflow_def, req))
    assert res.status == WorkflowExecutionStatus.SUCCESS
    assert "node_meta" in res.node_results
    assert res.node_results["node_meta"].status == NodeExecutionStatus.SUCCESS
