"""Comprehensive tests for Milestone T017: Sustainability Timeline + Impact Story.

Validates:
1. Timeline event creation and typing
2. Chronological ordering across multi-site assets and visits
3. Project-to-event and site relationships
4. Media-to-event relationship (images and videos)
5. Evidence-to-event relationship
6. Human verification state propagation (approved, pending, rejected)
7. Before/after card generation with Cloudinary URLs and review status
8. Uncertainty preservation and warning flags
9. Grounded narrative summary generation
10. Gemini unavailable handling and deterministic fallback
11. Story persistence in SQLite
12. Story retrieval by story ID and project ID
13. Story update endpoint
14. Timeline API endpoint
15. Impact story generate API endpoint
16. Project with no evidence (clean graceful handling)
17. Project with uncertain evidence
18. Project with approved evidence
19. Provenance completeness (traceability to assets and reviewers)
20. Cloudinary media references (image and video URLs preserved)
21. Existing evidence engine compatibility
22. Existing WorkflowEngine compatibility
23. Existing Media Intelligence compatibility
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.schemas.api import (
    BeforeAfterCard,
    ImpactStoryResponse,
    TimelineEvent,
    TimelineEventType,
    VerificationStatus,
)
from app.services import evidence_store as store
from app.services.impact_story import (
    build_before_after_cards,
    build_project_timeline_events,
    generate_grounded_impact_narrative,
    generate_impact_story,
    get_impact_story_by_id,
    get_project_impact_story,
    update_impact_story_fields,
)
from app.workflows.engine import WorkflowEngine
from app.workflows.models import (
    NodeExecutionStatus,
    WorkflowDefinition,
    WorkflowExecutionRequest,
    WorkflowExecutionStatus,
    WorkflowNode,
)
from app.skills import get_default_registry, get_default_runtime


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Isolated SQLite database and auth fixture."""
    db_file = tmp_path / "test_impact_story.sqlite3"
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(db_file))
    monkeypatch.setattr(settings, "MEDIA_UPLOAD_TOKEN", SecretStr("test-upload-token"))
    monkeypatch.setattr(settings, "REVIEWER_TOKENS", SecretStr('{"Tester":"test-reviewer-token"}'))

    with store.connection() as conn:
        now = store.timestamp()
        # Seed test project
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            ("proj_t017", "Yamuna Basin Restoration", "Rehabilitating riparian zones and removing plastic waste", now),
        )
        # Seed test sites
        conn.execute(
            "INSERT INTO sites (id, name, location, description, project_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("site_north", "North Ghat", "Delhi Sector 4", "High debris accumulation zone", "proj_t017", now),
        )
        conn.execute(
            "INSERT INTO sites (id, name, location, description, project_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("site_south", "South Shore", "Delhi Sector 7", "Wetlands buffer zone", "proj_t017", now),
        )
        # Seed visits
        conn.execute(
            "INSERT INTO visits (id, site_id, visited_on, label) VALUES (?, ?, ?, ?)",
            ("visit_b1", "site_north", "2026-08-10", "Initial Baseline Visit"),
        )
        conn.execute(
            "INSERT INTO visits (id, site_id, visited_on, label) VALUES (?, ?, ?, ?)",
            ("visit_a1", "site_north", "2026-08-25", "Post-Cleanup Inspection"),
        )
        conn.execute(
            "INSERT INTO visits (id, site_id, visited_on, label) VALUES (?, ?, ?, ?)",
            ("visit_b2", "site_south", "2026-08-12", "South Baseline Visit"),
        )
        # Seed assets
        store.save_asset(conn, {
            "asset_id": "img_north_before",
            "visit_id": "visit_b1",
            "public_id": "setowa/north_before",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/test-cloud/image/upload/north_before.jpg",
            "source": "Ranger A",
            "width": 1280,
            "height": 720,
            "format": "jpg",
            "permission_status": "granted",
            "site_id": "site_north",
            "project_id": "proj_t017",
            "media_type": "image",
            "created_at": "2026-08-10T09:00:00Z",
        })
        store.save_asset(conn, {
            "asset_id": "img_north_after",
            "visit_id": "visit_a1",
            "public_id": "setowa/north_after",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/test-cloud/image/upload/north_after.jpg",
            "source": "Ranger A",
            "width": 1280,
            "height": 720,
            "format": "jpg",
            "permission_status": "granted",
            "site_id": "site_north",
            "project_id": "proj_t017",
            "media_type": "image",
            "created_at": "2026-08-25T11:00:00Z",
        })
        store.save_asset(conn, {
            "asset_id": "vid_cleanup_action",
            "visit_id": "visit_a1",
            "public_id": "setowa/cleanup_action",
            "version": 1,
            "secure_url": "https://res.cloudinary.com/test-cloud/video/upload/cleanup_action.mp4",
            "thumbnail_url": "https://res.cloudinary.com/test-cloud/video/upload/so_0/cleanup_action.jpg",
            "source": "Team Drone",
            "width": 1920,
            "height": 1080,
            "duration": 42.5,
            "format": "mp4",
            "permission_status": "granted",
            "site_id": "site_north",
            "project_id": "proj_t017",
            "media_type": "video",
            "created_at": "2026-08-20T14:00:00Z",
        })
        # Seed observations: one approved, one pending
        conn.execute(
            """
            INSERT INTO observations (
                id, site_id, before_asset_id, after_asset_id,
                ai_draft, working_text, approved_text,
                review_status, reliability_reason, reviewed_by, reviewed_at,
                created_at, updated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "obs_north_01",
                "site_north",
                "img_north_before",
                "img_north_after",
                "AI Draft: Plastic litter removed from riverbank.",
                "Plastic litter removed from riverbank.",
                "Verified clear gravel shoreline. All solid waste removed across 50m riparian buffer.",
                "approved",
                None,
                "Auditor Aryan",
                "2026-08-26T10:00:00Z",
                "2026-08-25T12:00:00Z",
                "2026-08-26T10:00:00Z",
                2,
            ),
        )
        # Seed measurements
        conn.execute(
            """
            INSERT INTO measurements (
                id, site_id, visit_id, label, quantity, unit, source, recorded_by, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "meas_01",
                "site_north",
                "visit_a1",
                "plastic debris collected",
                145.0,
                "kg",
                "Weigh Station Digital Scale",
                "Supervisor Ananya",
                "2026-08-25T16:00:00Z",
            ),
        )
        # Seed media intelligence for before asset
        store.save_media_intelligence(conn, {
            "id": "intel_b1",
            "asset_id": "img_north_before",
            "status": "analyzed",
            "description": "Riverbank with dense plastic accumulation along shoreline.",
            "observations": json.dumps(["OBSERVED: Plastic bottles", "OBSERVED: Sediment bank"]),
            "tags_json": json.dumps(["debris", "plastic", "water"]),
            "signals_json": json.dumps(["visible_waste", "debris_accumulation"]),
            "activity": "unmanaged waste",
            "warnings_json": json.dumps([]),
        })
        # Seed media intelligence for video asset
        store.save_media_intelligence(conn, {
            "id": "intel_v1",
            "asset_id": "vid_cleanup_action",
            "status": "analyzed",
            "description": "Field workers actively bagging floating plastics into collection sacks.",
            "observations": json.dumps(["OBSERVED: Crew collecting plastics"]),
            "tags_json": json.dumps(["cleanup", "people", "plastic"]),
            "signals_json": json.dumps(["active_cleanup", "human_presence"]),
            "activity": "cleanup operations",
            "warnings_json": json.dumps([]),
        })
    return str(db_file)


AUTH_HEADERS = {"Authorization": "Bearer test-upload-token"}


# ==============================================================================
# 1. Timeline Event Creation and Typing
# ==============================================================================
def test_timeline_event_creation(test_db):
    with store.connection() as conn:
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        assert len(events) >= 4
        types = {e["event_type"] for e in events}
        assert TimelineEventType.BEFORE.value in types
        assert TimelineEventType.AFTER.value in types
        assert TimelineEventType.ACTIVITY.value in types
        assert TimelineEventType.VERIFIED_FINDING.value in types
        assert TimelineEventType.MEASUREMENT.value in types


# ==============================================================================
# 2. Chronological Ordering
# ==============================================================================
def test_chronological_ordering(test_db):
    with store.connection() as conn:
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        dates = [e["timestamp_date"] for e in events]
        assert dates == sorted(dates)
        # Verify event_order is sequential 0, 1, 2, ...
        orders = [e["event_order"] for e in events]
        assert orders == list(range(len(events)))


# ==============================================================================
# 3. Project and Site Relationships
# ==============================================================================
def test_project_and_site_relationships(test_db):
    with store.connection() as conn:
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        for e in events:
            assert e["story_id"] == "story_proj_t017"
            if e["site_id"]:
                assert e["site_id"] in ("site_north", "site_south")
                assert e["site_name"] in ("North Ghat", "South Shore")


# ==============================================================================
# 4. Media-to-Event Relationship (Images and Videos)
# ==============================================================================
def test_media_to_event_relationship(test_db):
    with store.connection() as conn:
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        video_events = [e for e in events if e["media_type"] == "video"]
        assert len(video_events) >= 1
        v_evt = video_events[0]
        assert "cleanup_action.mp4" in v_evt["primary_media_url"]
        assert "active_cleanup" in json.loads(v_evt["signals_json"])


# ==============================================================================
# 5. Evidence-to-Event Relationship
# ==============================================================================
def test_evidence_to_event_relationship(test_db):
    with store.connection() as conn:
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        finding_events = [e for e in events if e["event_type"] == TimelineEventType.VERIFIED_FINDING.value]
        assert len(finding_events) >= 1
        fe = finding_events[0]
        assert fe["observation_id"] == "obs_north_01"
        ev_data = json.loads(fe["evidence_json"])
        assert ev_data["reviewed_by"] == "Auditor Aryan"


# ==============================================================================
# 6. Human Verification State Propagation
# ==============================================================================
def test_verification_state_propagation(test_db):
    with store.connection() as conn:
        # Add a pending observation
        conn.execute(
            """
            INSERT INTO observations (
                id, site_id, before_asset_id, after_asset_id,
                ai_draft, working_text, approved_text,
                review_status, reliability_reason, reviewed_by, reviewed_at,
                created_at, updated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "obs_pending_02",
                "site_south",
                "img_north_before",
                "img_north_after",
                "AI Draft: Unreviewed change",
                "Unreviewed change",
                None,
                "pending",
                "Camera angle mismatch",
                None,
                None,
                "2026-08-27T10:00:00Z",
                "2026-08-27T10:00:00Z",
                1,
            ),
        )
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        findings = [e for e in events if e["event_type"] == TimelineEventType.VERIFIED_FINDING.value]
        status_map = {f["observation_id"]: f["verification_status"] for f in findings}
        assert status_map["obs_north_01"] == VerificationStatus.APPROVED.value
        assert status_map["obs_pending_02"] == VerificationStatus.PENDING_REVIEW.value


# ==============================================================================
# 7. Before/After Card Generation
# ==============================================================================
def test_before_after_card_generation(test_db):
    with store.connection() as conn:
        cards = build_before_after_cards(conn, "proj_t017")
        assert len(cards) >= 1
        card = cards[0]
        assert card.observation_id == "obs_north_01"
        assert card.verification_status == "approved"
        assert "north_before.jpg" in card.before_media_url
        assert "north_after.jpg" in card.after_media_url
        assert card.reviewed_by == "Auditor Aryan"
        assert "50m riparian buffer" in card.approved_text


# ==============================================================================
# 8. Uncertainty Preservation & Warning Flags
# ==============================================================================
def test_uncertainty_preservation(test_db):
    with store.connection() as conn:
        # Seed an observation with explicit uncertainty reason
        conn.execute(
            """
            INSERT INTO observations (
                id, site_id, before_asset_id, after_asset_id,
                ai_draft, working_text, approved_text,
                review_status, reliability_reason, reviewed_by, reviewed_at,
                created_at, updated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "obs_uncertain_03",
                "site_north",
                "img_north_before",
                "img_north_after",
                "AI Draft: Uncertain observation",
                "Uncertain observation",
                None,
                "pending",
                "Severe glare and motion blur",
                None,
                None,
                "2026-08-28T10:00:00Z",
                "2026-08-28T10:00:00Z",
                1,
            ),
        )
        cards = build_before_after_cards(conn, "proj_t017")
        u_card = next(c for c in cards if c.observation_id == "obs_uncertain_03")
        assert u_card.uncertainty == "Severe glare and motion blur"
        assert u_card.verification_status == "pending"


# ==============================================================================
# 9. Grounded Narrative Summary Generation (Deterministic Fallback)
# ==============================================================================
def test_grounded_narrative_summary_deterministic(test_db):
    with store.connection() as conn:
        project = store.get_project(conn, "proj_t017")
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        cards = build_before_after_cards(conn, "proj_t017")
        measurements = store.rows(conn, "SELECT * FROM measurements WHERE site_id='site_north'")

        narrative, uncertainty = asyncio.run(
            generate_grounded_impact_narrative(project, events, cards, measurements)
        )
        assert "Yamuna Basin Restoration" in narrative
        assert "145.0 kg" in narrative
        assert "plastic debris collected" in narrative
        assert "not independently audited" in narrative


# ==============================================================================
# 10. Gemini Unavailable Handling & Graceful Fallback
# ==============================================================================
def test_gemini_unavailable_handling(test_db):
    with store.connection() as conn:
        project = store.get_project(conn, "proj_t017")
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        cards = build_before_after_cards(conn, "proj_t017")

        with patch("app.config.settings.GEMINI_API_KEY", ""):
            narrative, uncertainty = asyncio.run(
                generate_grounded_impact_narrative(project, events, cards, [])
            )
        assert narrative is not None
        assert len(narrative) > 50
        assert "Yamuna Basin Restoration" in narrative


# ==============================================================================
# 11. Story Persistence in SQLite
# ==============================================================================
def test_story_persistence(test_db):
    with store.connection() as conn:
        story_data = {
            "id": "story_proj_t017",
            "project_id": "proj_t017",
            "title": "Yamuna Basin Restoration Story",
            "description": "Chronological evidence narrative",
            "status": "published",
            "summary_narrative": "Verified impact summary text.",
            "uncertainty_note": "No remaining uncertainties.",
        }
        saved = store.save_impact_story(conn, story_data)
        assert saved["id"] == "story_proj_t017"

        retrieved = store.get_impact_story(conn, "story_proj_t017")
        assert retrieved is not None
        assert retrieved["status"] == "published"
        assert retrieved["summary_narrative"] == "Verified impact summary text."


# ==============================================================================
# 12. Story Retrieval by Project ID
# ==============================================================================
def test_story_retrieval_by_project_id(test_db):
    with store.connection() as conn:
        story = asyncio.run(generate_impact_story(conn, "proj_t017", force_regenerate=True))
        assert story.project_id == "proj_t017"
        assert story.metrics["comparison_count"] >= 1
        assert story.metrics["measurement_count"] >= 1

        retrieved = get_project_impact_story(conn, "proj_t017")
        assert retrieved is not None
        assert retrieved.id == story.id
        assert len(retrieved.events) == len(story.events)


# ==============================================================================
# 13. Story Update Endpoint
# ==============================================================================
def test_story_update_fields(test_db):
    with store.connection() as conn:
        story = asyncio.run(generate_impact_story(conn, "proj_t017", force_regenerate=True))
        updated = update_impact_story_fields(conn, story.id, {
            "title": "Custom Updated Impact Title",
            "status": "published",
        })
        assert updated is not None
        assert updated.title == "Custom Updated Impact Title"
        assert updated.status == "published"


# ==============================================================================
# 14. API: GET /api/v1/impact-stories/{story_id}/timeline
# ==============================================================================
def test_api_get_story_timeline(test_db):
    client = TestClient(app)
    # Generate story first
    gen_resp = client.post("/api/v1/projects/proj_t017/impact-story/generate", headers=AUTH_HEADERS)
    assert gen_resp.status_code == 200
    story_id = gen_resp.json()["id"]

    resp = client.get(f"/api/v1/impact-stories/{story_id}/timeline", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    timeline = resp.json()
    assert isinstance(timeline, list)
    assert len(timeline) >= 4
    assert timeline[0]["event_order"] == 0


# ==============================================================================
# 15. API: GET & POST /api/v1/projects/{project_id}/impact-story
# ==============================================================================
def test_api_project_impact_story_lifecycle(test_db):
    client = TestClient(app)

    # 1. Nonexistent project -> 404
    resp_bad = client.get("/api/v1/projects/nonexistent_proj/impact-story", headers=AUTH_HEADERS)
    assert resp_bad.status_code == 404

    # 2. Project before generation -> 404
    resp_unready = client.get("/api/v1/projects/proj_t017/impact-story", headers=AUTH_HEADERS)
    assert resp_unready.status_code == 404

    # 3. Generate impact story -> 200
    resp_gen = client.post(
        "/api/v1/projects/proj_t017/impact-story/generate",
        headers=AUTH_HEADERS,
        json={"title": "Custom Restoration Story", "force_regenerate": True},
    )
    assert resp_gen.status_code == 200
    data = resp_gen.json()
    assert data["project_id"] == "proj_t017"
    assert data["title"] == "Custom Restoration Story"
    assert len(data["before_after_cards"]) >= 1

    # 4. Now GET succeeds
    resp_get = client.get("/api/v1/projects/proj_t017/impact-story", headers=AUTH_HEADERS)
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == data["id"]

    # 5. PUT updates story
    resp_put = client.put(
        f"/api/v1/impact-stories/{data['id']}",
        headers=AUTH_HEADERS,
        json={"status": "published", "description": "Audited final version"},
    )
    assert resp_put.status_code == 200
    assert resp_put.json()["status"] == "published"
    assert resp_put.json()["description"] == "Audited final version"


# ==============================================================================
# 16. Project with No Evidence
# ==============================================================================
def test_project_with_no_evidence(test_db):
    with store.connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            ("proj_empty", "Empty Project", "No sites or assets yet", store.timestamp()),
        )
        story = asyncio.run(generate_impact_story(conn, "proj_empty", force_regenerate=True))
        assert story.project_id == "proj_empty"
        assert len(story.events) == 0
        assert len(story.before_after_cards) == 0
        assert "Empty Project" in story.summary_narrative


# ==============================================================================
# 17. Project with Uncertain Evidence
# ==============================================================================
def test_project_with_uncertain_evidence(test_db):
    with store.connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            ("proj_uncertain", "Uncertain Project", "Challenging terrain", store.timestamp()),
        )
        conn.execute(
            "INSERT INTO sites (id, name, location, project_id, created_at) VALUES (?, ?, ?, ?, ?)",
            ("site_hazy", "Hazy Cove", "East Basin", "proj_uncertain", store.timestamp()),
        )
        conn.execute(
            """
            INSERT INTO observations (
                id, site_id, before_asset_id, after_asset_id,
                ai_draft, working_text, approved_text,
                review_status, reliability_reason, created_at, updated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "obs_foggy",
                "site_hazy",
                "img_north_before",
                "img_north_after",
                "AI Draft: Low visibility",
                "Low visibility",
                None,
                "pending",
                "camera_angle_mismatch",
                "2026-09-01T10:00:00Z",
                "2026-09-01T10:00:00Z",
                1,
            ),
        )
        story = asyncio.run(generate_impact_story(conn, "proj_uncertain", force_regenerate=True))
        assert story.uncertainty_note is not None
        assert "camera_angle_mismatch" in story.uncertainty_note or "pending" in story.uncertainty_note


# ==============================================================================
# 18. Project with Approved Evidence
# ==============================================================================
def test_project_with_approved_evidence(test_db):
    with store.connection() as conn:
        story = asyncio.run(generate_impact_story(conn, "proj_t017", force_regenerate=True))
        assert story.metrics["approved_findings_count"] >= 1
        approved = [c for c in story.before_after_cards if c.verification_status == "approved"]
        assert len(approved) >= 1
        assert approved[0].reviewed_by == "Auditor Aryan"


# ==============================================================================
# 19. Provenance Completeness
# ==============================================================================
def test_provenance_completeness(test_db):
    with store.connection() as conn:
        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        for e in events:
            # Every event must have a timestamp and traceable provenance
            assert e["timestamp_date"] is not None
            assert len(e["timestamp_date"]) == 10  # YYYY-MM-DD
            assert e["evidence_json"] is not None
            evidence_dict = json.loads(e["evidence_json"])
            assert isinstance(evidence_dict, dict)
            assert len(evidence_dict) > 0


# ==============================================================================
# 20. Cloudinary Media References Preserved
# ==============================================================================
def test_cloudinary_media_references(test_db):
    with store.connection() as conn:
        cards = build_before_after_cards(conn, "proj_t017")
        for c in cards:
            assert c.before_media_url.startswith("https://res.cloudinary.com")
            assert c.after_media_url.startswith("https://res.cloudinary.com")

        events = build_project_timeline_events(conn, "proj_t017", "story_proj_t017")
        media_events = [e for e in events if e.get("primary_media_url")]
        for me in media_events:
            assert me["primary_media_url"].startswith("https://res.cloudinary.com")


REVIEWER_AUTH_HEADERS = {"Authorization": "Bearer test-reviewer-token"}


# ==============================================================================
# 21. Existing Evidence Engine Compatibility
# ==============================================================================
def test_existing_evidence_engine_compatibility(test_db):
    client = TestClient(app)
    # The existing review endpoint should still function without interference
    resp = client.get("/api/v1/observations/obs_north_01", headers=REVIEWER_AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "approved"


# ==============================================================================
# 22. Existing WorkflowEngine Compatibility
# ==============================================================================
def test_existing_workflow_engine_compatibility(test_db):
    runtime = get_default_runtime()
    registry = get_default_registry()
    engine = WorkflowEngine(runtime=runtime, registry=registry)
    workflow_def = WorkflowDefinition(
        id="wf_impact_compat",
        name="Impact Compatibility Flow",
        nodes=[
            WorkflowNode(
                id="node_meta",
                skill="media-metadata",
                skill_version="1.0.0",
                inputs={"asset_id": "img_north_before"},
            ),
        ],
    )
    req = WorkflowExecutionRequest(inputs={})
    res = asyncio.run(engine.execute(workflow_def, req))
    assert res.status == WorkflowExecutionStatus.SUCCESS
    assert "node_meta" in res.node_results
    assert res.node_results["node_meta"].status == NodeExecutionStatus.SUCCESS


# ==============================================================================
# 23. Existing Media Intelligence Compatibility
# ==============================================================================
def test_existing_media_intelligence_compatibility(test_db):
    client = TestClient(app)
    resp = client.get("/api/v1/media/img_north_before/intelligence", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "analyzed"
    assert "plastic" in resp.json()["tags"]
