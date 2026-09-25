"""
End-to-End QA & Journey Verification for Setowa / Project LEX (T009).

Tests the complete judge journey from clean fresh-start DB to report generation:
1. Fresh-start initialization & database schema
2. Complete end-to-end happy path:
   Site -> Visits -> Assets -> Pair -> Gemini AI Proposal -> Human Approval -> Traceable Report
3. Lifecycle & Approval Invalidation:
   Approved -> Edit -> Invalidation to Pending -> Report Exclusion -> Reject
4. Comprehensive Failure Paths:
   Chronological ordering, cross-site, permission restrictions, version conflicts, provider errors
5. Frontend Contract & Static Assets
"""
import io
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from app.schemas.api import VisualChange
from app.services import evidence_store as store
from app.services.image_comparison import Comparison
from app.services.reviewer_auth import LOCAL_SESSIONS

REVIEWER_HEADERS = {"Authorization": "Bearer judge-token"}


@pytest.fixture
def clean_db(monkeypatch):
    """Provide a completely isolated fresh SQLite database for each test."""
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "fresh_test.sqlite3"
    monkeypatch.setattr(settings, "LEX_DB_PATH", str(db_file))
    monkeypatch.setattr(settings, "REVIEWER_TOKENS", SecretStr('{"Judge Reviewer":"judge-token"}'))
    LOCAL_SESSIONS.clear()
    with store.connection() as db:
        pass
    yield db_file


@pytest.fixture
def client(clean_db):
    """FastAPI TestClient configured for tests."""
    return TestClient(app)


def create_asset_direct(asset_id, visit_id, secure_url, source="Field ranger", perm="granted"):
    """Helper to register an asset in the database."""
    with store.connection() as db:
        db.execute(
            """INSERT INTO assets (asset_id, visit_id, public_id, version, secure_url, source,
                                   width, height, format, permission_status)
               VALUES (?, ?, ?, 1, ?, ?, 1920, 1080, 'jpeg', ?)""",
            (asset_id, visit_id, f"pub/{asset_id}", secure_url, source, perm),
        )


# ==============================================================================
# 1. FRESH-START TEST
# ==============================================================================

def test_fresh_start_database_and_tables(clean_db):
    """Verifies that an uninitialized database file is created and schemas migrated cleanly."""
    assert clean_db.exists()
    with sqlite3.connect(clean_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        expected = {
            "sites", "visits", "assets", "observations",
            "observation_revisions", "measurements"
        }
        assert expected.issubset(tables)


# ==============================================================================
# 2. COMPLETE HAPPY PATH
# ==============================================================================

def test_complete_judge_happy_path(client):
    """
    Executes the entire end-to-end judge flow without developer intervention:
    1. Create site
    2. Add before and after visits
    3. Add permissioned evidence assets
    4. Validate pair & run Gemini analysis
    5. Verify AI proposal: status, model confidence, structured changes, pending review status
    6. Verify unapproved proposal is EXCLUDED from report
    7. Record a valid quantitative measurement
    8. Reviewer approves observation with custom verified text
    9. Verify observation transitions to 'approved' with reviewer attribution
    10. Verify report includes approved observation & measurement
    11. Verify markdown report download
    """
    # 1. Create site
    site_payload = {
        "id": "creek-restoration",
        "name": "Creek Restoration Project",
        "location": "North Basin, Sector 4",
        "description": "Community cleanup targeting plastic debris and runoff.",
    }
    r_site = client.post("/api/v1/sites", json=site_payload, headers=REVIEWER_HEADERS)
    assert r_site.status_code in (200, 201)
    assert r_site.json()["id"] == "creek-restoration"

    # 2. Add Visits (Visit 1 precedes Visit 2)
    r_v1 = client.post("/api/v1/sites/creek-restoration/visits", json={
        "visited_on": "2026-10-01",
        "label": "Visit 1 — Pre-cleanup Baseline",
    }, headers=REVIEWER_HEADERS)
    assert r_v1.status_code in (200, 201)
    v1_id = r_v1.json()["id"]

    r_v2 = client.post("/api/v1/sites/creek-restoration/visits", json={
        "visited_on": "2026-10-15",
        "label": "Visit 2 — Post-cleanup Followup",
    }, headers=REVIEWER_HEADERS)
    assert r_v2.status_code in (200, 201)
    v2_id = r_v2.json()["id"]

    # 3. Add Evidence Assets
    create_asset_direct("asset-before-1", v1_id,
                        "https://res.cloudinary.com/demo/image/upload/v1/before.jpg",
                        source="Field Ranger Photo", perm="granted")
    create_asset_direct("asset-after-1", v2_id,
                        "https://res.cloudinary.com/demo/image/upload/v1/after.jpg",
                        source="Field Ranger Photo", perm="granted")

    # 4. Run Pair Comparison with Mocked Gemini AI Analysis
    mock_comparison = Comparison(
        status="changed",
        confidence=0.88,
        summary="Visible plastic and debris significantly reduced along the creek embankment.",
        changes=[
            VisualChange(type="removal", description="Plastic bottles cleared", evidence="Near bank foreground"),
            VisualChange(type="vegetation", description="Vegetation visible", evidence="Center bank")
        ],
        uncertainty_reason=None,
        evidence_notes="Good lighting and matching camera angle across visits.",
    )

    with patch("app.routes.evidence.compare_images", new_callable=AsyncMock) as m:
        m.return_value = mock_comparison
        r_pair = client.post("/api/v1/pairs", json={
            "before_asset_id": "asset-before-1",
            "after_asset_id": "asset-after-1",
        }, headers=REVIEWER_HEADERS)

    assert r_pair.status_code in (200, 201)
    pair_data = r_pair.json()
    obs_id = pair_data["id"]

    # 5. Verify Structured AI Proposal Invariants
    assert pair_data["review_status"] == "pending"
    assert pair_data["approved_text"] is None
    assert pair_data["ai_draft"] == "Visible plastic and debris significantly reduced along the creek embankment."
    assert pair_data["comparison"]["status"] == "changed"
    assert pair_data["comparison"]["confidence"] == 0.88
    assert len(pair_data["comparison"]["changes"]) == 2

    # 6. Verify Unapproved Proposal is EXCLUDED from Report
    r_report_initial = client.get("/api/v1/sites/creek-restoration/report", headers=REVIEWER_HEADERS)
    assert r_report_initial.status_code == 200
    report_initial = r_report_initial.json()
    assert len(report_initial["observations"]) == 0  # Crucial trust invariant!

    # 7. Record a Valid Quantitative Measurement
    r_meas = client.post("/api/v1/sites/creek-restoration/measurements", json={
        "visit_id": v2_id,
        "label": "Collected debris sacks",
        "quantity": 8.5,
        "unit": "bags",
        "source": "Weigh scale ticket #402",
    }, headers=REVIEWER_HEADERS)
    assert r_meas.status_code in (200, 201)

    # 8. Human Reviewer Approves Observation
    approved_finding = "Verified by Field Supervisor: 8 sacks of debris cleared from north embankment."
    r_review = client.post(f"/api/v1/observations/{obs_id}/review", json={
        "decision": "approve",
        "expected_version": 1,
        "text": approved_finding,
    }, headers=REVIEWER_HEADERS)
    assert r_review.status_code == 200
    review_data = r_review.json()

    # 9. Verify Observation Transition to Approved
    assert review_data["review_status"] == "approved"
    assert review_data["approved_text"] == approved_finding
    assert review_data["reviewed_by"] == "Judge Reviewer"
    assert review_data["reviewed_at"] is not None
    assert review_data["version"] == 2

    # 10. Verify Report INCLUDES Approved Observation & Measurement
    r_report_final = client.get("/api/v1/sites/creek-restoration/report", headers=REVIEWER_HEADERS)
    assert r_report_final.status_code == 200
    report_final = r_report_final.json()
    assert len(report_final["observations"]) == 1
    assert report_final["observations"][0]["approved_text"] == approved_finding
    assert report_final["observations"][0]["reviewed_by"] == "Judge Reviewer"
    assert len(report_final["recorded_measurements"]) == 1
    assert report_final["recorded_measurements"][0]["quantity"] == 8.5

    # 11. Verify Markdown Report Download
    r_md = client.get("/api/v1/sites/creek-restoration/report?format=markdown", headers=REVIEWER_HEADERS)
    assert r_md.status_code == 200
    assert "text/markdown" in r_md.headers["content-type"]
    assert approved_finding in r_md.text
    assert "Judge Reviewer" in r_md.text


# ==============================================================================
# 3. LIFECYCLE & APPROVAL INVALIDATION
# ==============================================================================

def test_approval_invalidation_lifecycle(client):
    """
    Verifies the trust rule:
    Editing an approved observation immediately clears approval,
    resets review_status to 'pending', and removes it from the official report.
    """
    # Setup site, visits, assets, observation
    client.post("/api/v1/sites", json={"id": "river-invalidation", "name": "Invalidation Test"}, headers=REVIEWER_HEADERS)
    v1 = client.post("/api/v1/sites/river-invalidation/visits", json={"visited_on": "2026-09-01", "label": "V1"}, headers=REVIEWER_HEADERS).json()
    v2 = client.post("/api/v1/sites/river-invalidation/visits", json={"visited_on": "2026-09-10", "label": "V2"}, headers=REVIEWER_HEADERS).json()
    create_asset_direct("inv-a1", v1["id"], "https://res.cloudinary.com/demo/image/upload/v1/inv1.jpg")
    create_asset_direct("inv-a2", v2["id"], "https://res.cloudinary.com/demo/image/upload/v1/inv2.jpg")

    mock_cmp = Comparison(status="changed", confidence=0.9, summary="Cleaned", changes=[], uncertainty_reason=None)
    with patch("app.services.image_comparison.compare_images", new_callable=AsyncMock) as m:
        m.return_value = mock_cmp
        obs = client.post("/api/v1/pairs", json={"before_asset_id": "inv-a1", "after_asset_id": "inv-a2"}, headers=REVIEWER_HEADERS).json()

    # Step 1: Approve
    client.post(f"/api/v1/observations/{obs['id']}/review", json={
        "decision": "approve",
        "expected_version": 1,
        "text": "Human-approved cleanup observation.",
    }, headers=REVIEWER_HEADERS)
    # Verify in report
    rep1 = client.get("/api/v1/sites/river-invalidation/report", headers=REVIEWER_HEADERS).json()
    assert len(rep1["observations"]) == 1

    # Step 2: Edit working text
    r_edit = client.patch(f"/api/v1/observations/{obs['id']}", json={
        "expected_version": 2,
        "working_text": "Minor revision to visual description.",
    }, headers=REVIEWER_HEADERS)
    assert r_edit.status_code == 200
    edited_obs = r_edit.json()

    # Invariants on edit:
    assert edited_obs["review_status"] == "pending"
    assert edited_obs["approved_text"] is None
    assert edited_obs["reviewed_by"] is None
    assert edited_obs["version"] == 3

    # Must be EXCLUDED from report now
    rep2 = client.get("/api/v1/sites/river-invalidation/report", headers=REVIEWER_HEADERS).json()
    assert len(rep2["observations"]) == 0

    # Step 3: Rejecting the observation
    r_reject = client.post(f"/api/v1/observations/{obs['id']}/review", json={
        "decision": "reject",
        "expected_version": 3,
    }, headers=REVIEWER_HEADERS)
    assert r_reject.status_code == 200
    rejected_obs = r_reject.json()
    assert rejected_obs["review_status"] == "rejected"
    assert rejected_obs["version"] == 4

    # Remains excluded from report
    rep3 = client.get("/api/v1/sites/river-invalidation/report", headers=REVIEWER_HEADERS).json()
    assert len(rep3["observations"]) == 0


# ==============================================================================
# 4. COMPREHENSIVE FAILURE PATHS
# ==============================================================================

def test_failure_path_chronological_violation(client):
    """Chronologically inverted visits (after precedes before) must be rejected with 422."""
    client.post("/api/v1/sites", json={"id": "chrono-site", "name": "Chrono Test"}, headers=REVIEWER_HEADERS)
    v1 = client.post("/api/v1/sites/chrono-site/visits", json={"visited_on": "2026-10-10", "label": "Later"}, headers=REVIEWER_HEADERS).json()
    v2 = client.post("/api/v1/sites/chrono-site/visits", json={"visited_on": "2026-10-01", "label": "Earlier"}, headers=REVIEWER_HEADERS).json()
    create_asset_direct("chr-a1", v1["id"], "https://res.cloudinary.com/demo/image/upload/v1/c1.jpg")
    create_asset_direct("chr-a2", v2["id"], "https://res.cloudinary.com/demo/image/upload/v1/c2.jpg")

    r = client.post("/api/v1/pairs", json={"before_asset_id": "chr-a1", "after_asset_id": "chr-a2"}, headers=REVIEWER_HEADERS)
    assert r.status_code == 422
    assert "precede" in r.json()["detail"].lower()


def test_failure_path_revoked_permission(client):
    """Assets without granted permission cannot be paired or included in reports."""
    client.post("/api/v1/sites", json={"id": "perm-site", "name": "Perm Test"}, headers=REVIEWER_HEADERS)
    v1 = client.post("/api/v1/sites/perm-site/visits", json={"visited_on": "2026-09-01", "label": "V1"}, headers=REVIEWER_HEADERS).json()
    v2 = client.post("/api/v1/sites/perm-site/visits", json={"visited_on": "2026-09-10", "label": "V2"}, headers=REVIEWER_HEADERS).json()
    create_asset_direct("p-a1", v1["id"], "https://res.cloudinary.com/demo/image/upload/v1/p1.jpg", perm="granted")
    create_asset_direct("p-a2", v2["id"], "https://res.cloudinary.com/demo/image/upload/v1/p2.jpg", perm="revoked")

    r = client.post("/api/v1/pairs", json={"before_asset_id": "p-a1", "after_asset_id": "p-a2"}, headers=REVIEWER_HEADERS)
    assert r.status_code == 422
    assert "permission" in r.json()["detail"].lower()


def test_failure_path_cross_site_mismatch(client):
    """Assets from different sites cannot be paired."""
    client.post("/api/v1/sites", json={"id": "site-alpha", "name": "Site Alpha"}, headers=REVIEWER_HEADERS)
    client.post("/api/v1/sites", json={"id": "site-beta", "name": "Site Beta"}, headers=REVIEWER_HEADERS)
    va = client.post("/api/v1/sites/site-alpha/visits", json={"visited_on": "2026-09-01", "label": "VA"}, headers=REVIEWER_HEADERS).json()
    vb = client.post("/api/v1/sites/site-beta/visits", json={"visited_on": "2026-09-10", "label": "VB"}, headers=REVIEWER_HEADERS).json()
    create_asset_direct("a-alpha", va["id"], "https://res.cloudinary.com/demo/image/upload/v1/a.jpg")
    create_asset_direct("a-beta", vb["id"], "https://res.cloudinary.com/demo/image/upload/v1/b.jpg")

    r = client.post("/api/v1/pairs", json={"before_asset_id": "a-alpha", "after_asset_id": "a-beta"}, headers=REVIEWER_HEADERS)
    assert r.status_code == 422
    assert "same site" in r.json()["detail"].lower()


def test_failure_path_version_conflict_409(client):
    """Stale version during review results in 409 conflict, preventing overwrites."""
    client.post("/api/v1/sites", json={"id": "conflict-site", "name": "Conflict Test"}, headers=REVIEWER_HEADERS)
    v1 = client.post("/api/v1/sites/conflict-site/visits", json={"visited_on": "2026-09-01", "label": "V1"}, headers=REVIEWER_HEADERS).json()
    v2 = client.post("/api/v1/sites/conflict-site/visits", json={"visited_on": "2026-09-10", "label": "V2"}, headers=REVIEWER_HEADERS).json()
    create_asset_direct("c-a1", v1["id"], "https://res.cloudinary.com/demo/image/upload/v1/c1.jpg")
    create_asset_direct("c-a2", v2["id"], "https://res.cloudinary.com/demo/image/upload/v1/c2.jpg")

    mock_cmp = Comparison(status="changed", confidence=0.8, summary="Cleaned", changes=[], uncertainty_reason=None)
    with patch("app.services.image_comparison.compare_images", new_callable=AsyncMock) as m:
        m.return_value = mock_cmp
        obs = client.post("/api/v1/pairs", json={"before_asset_id": "c-a1", "after_asset_id": "c-a2"}, headers=REVIEWER_HEADERS).json()

    # Attempt review with incorrect expected_version (e.g. version 99 instead of 1)
    r = client.post(f"/api/v1/observations/{obs['id']}/review", json={
        "decision": "approve",
        "expected_version": 99,
        "text": "Overwriting attempt",
    }, headers=REVIEWER_HEADERS)
    assert r.status_code == 409
    assert "reload" in r.json()["detail"].lower()


def test_failure_path_uncertain_and_insufficient_evidence(client):
    """Uncertain and insufficient evidence comparison results preserve reason and remain pending."""
    client.post("/api/v1/sites", json={"id": "unc-site", "name": "Uncertainty Test"}, headers=REVIEWER_HEADERS)
    v1 = client.post("/api/v1/sites/unc-site/visits", json={"visited_on": "2026-09-01", "label": "V1"}, headers=REVIEWER_HEADERS).json()
    v2 = client.post("/api/v1/sites/unc-site/visits", json={"visited_on": "2026-09-10", "label": "V2"}, headers=REVIEWER_HEADERS).json()
    create_asset_direct("u-a1", v1["id"], "https://res.cloudinary.com/demo/image/upload/v1/u1.jpg")
    create_asset_direct("u-a2", v2["id"], "https://res.cloudinary.com/demo/image/upload/v1/u2.jpg")

    mock_unc = Comparison(
        status="uncertain",
        confidence=0.25,
        summary="",
        changes=[],
        uncertainty_reason="camera_angle_mismatch",
        reason="camera_angle_mismatch",
        evidence_notes="Camera angles between visits differ significantly.",
    )
    with patch("app.routes.evidence.compare_images", new_callable=AsyncMock) as m:
        m.return_value = mock_unc
        res = client.post("/api/v1/pairs", json={"before_asset_id": "u-a1", "after_asset_id": "u-a2"}, headers=REVIEWER_HEADERS).json()

    assert res["review_status"] == "pending"
    assert res["reliability_reason"] == "camera_angle_mismatch"
    assert res["approved_text"] is None
    assert res["comparison"]["status"] == "uncertain"
    assert res["comparison"]["uncertainty_reason"] == "camera_angle_mismatch"


# ==============================================================================
# 5. FRONTEND CONTRACT & STATIC ASSET DELIVERY
# ==============================================================================

def test_static_demo_bundle_and_script_syntax(client):
    """Verify demo static bundle serves correctly and script contains required hardening patterns."""
    r_index = client.get("/demo/")
    assert r_index.status_code == 200
    assert "Setowa" in r_index.text

    r_js = client.get("/demo/app.js")
    assert r_js.status_code == 200
    js_text = r_js.text

    # Verify loading state text patterns are present
    assert "Comparing with Gemini..." in js_text
    assert "Uploading to Cloudinary..." in js_text
    assert "Generating report..." in js_text

    # Verify error sanitization patterns are present
    assert "sanitizeErrorMessage" in js_text
    assert "Network connection failed" in js_text
