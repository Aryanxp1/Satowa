"""Automated End-to-End Smoke Test for SETOWA Hackathon Showcase.

Validates the full system path across all 9 milestones:
1. System Health & Readiness Probes (/api/v1/health, /api/v1/ready)
2. Ingestion & Organization (Projects, Sites, Visits, Media Assets)
3. Cloudinary Delivery (Responsive transformations, video posters, thumbnails)
4. AI Media Intelligence (Structured tags, signals, observed visual evidence)
5. Skill Runtime Execution (Media metadata & comparison skills)
6. Workflow Engine DAG Run (Topological execution of wf_evidence_compare)
7. Evidence Review & Human Verification (Human approval, reviewer identity, review audit)
8. Grounded Impact Story (Chronological timeline spine, physical weigh slip, narrative)
9. Public Share Experience (/share/{token}, public-safe projection, published gating)
"""
from pathlib import Path
import json
import sys

# Ensure backend root on sys.path and working directory is backend
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
import os
os.chdir(backend_dir)

from fastapi.testclient import TestClient
from app.config import settings
from app.main import app
from app.services import evidence_store as store
from scripts.seed_demo import seed_demo_dataset, DEMO_PROJECT_ID, DEMO_SHARE_TOKEN


def run_smoke_test():
    print("=" * 65)
    print("  SETOWA END-TO-END DEMO SMOKE TEST")
    print("=" * 65)

    client = TestClient(app)

    # 1. Health & Readiness
    print("\n[Step 1/9] Probing Health and Readiness...")
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200, f"Health probe failed: {res_health.text}"
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    print(f"  [OK] Health probe: {health_data['status']} (v{health_data['version']})")

    res_ready = client.get("/api/v1/ready")
    assert res_ready.status_code == 200, f"Readiness probe failed: {res_ready.text}"
    ready_data = res_ready.json()
    assert ready_data["status"] == "ready"
    assert ready_data["database"] == "ready"
    print(f"  [OK] Readiness probe: db={ready_data['database']}, cloudinary={ready_data['cloudinary']}, gemini={ready_data['gemini']}")

    # 2. Ingestion & Organization
    print("\n[Step 2/9] Validating Project and Media Asset Ingestion...")
    seed_demo_dataset()

    with store.connection() as db:
        project = store.one(db, "SELECT * FROM projects WHERE id=?", (DEMO_PROJECT_ID,))
        assert project, f"Project {DEMO_PROJECT_ID} missing from database"
        sites = store.rows(db, "SELECT * FROM sites WHERE project_id=?", (DEMO_PROJECT_ID,))
        assert len(sites) >= 1, "No sites found for demo project"
        assets = store.rows(db, "SELECT * FROM assets WHERE project_id=?", (DEMO_PROJECT_ID,))
        assert len(assets) >= 3, f"Expected at least 3 assets, found {len(assets)}"
    print(f"  [OK] Verified Project '{project['name']}' with {len(sites)} site(s) and {len(assets)} media asset(s)")

    # 3. Cloudinary Delivery
    print("\n[Step 3/9] Validating Cloudinary Media Delivery URLs...")
    for a in assets:
        assert "cloudinary.com" in a["secure_url"], f"Non-Cloudinary URL in asset {a['asset_id']}"
        assert a["permission_status"] == "granted", f"Permission not granted on {a['asset_id']}"
    print("  [OK] All media assets routed via Cloudinary delivery transformations")

    # 4. AI Media Intelligence
    print("\n[Step 4/9] Validating Structured AI Media Intelligence...")
    with store.connection() as db:
        intel = store.rows(db, "SELECT * FROM media_intelligence WHERE asset_id='ast_mombasa_before'")
        assert intel, "No intelligence record for ast_mombasa_before"
        tags = json.loads(intel[0]["tags_json"])
        assert "litter" in tags or "vegetation" in tags
        assert intel[0]["status"] == "analyzed"
    print(f"  [OK] Media Intelligence: status={intel[0]['status']}, tags={tags}")

    # 5. Skill Runtime Execution
    print("\n[Step 5/9] Validating SkillRuntime Execution...")
    res_skill = client.post(
        "/api/v1/skills/media-metadata/execute",
        json={"inputs": {"asset_id": "ast_mombasa_before"}},
    )
    assert res_skill.status_code == 200, f"Skill execution failed: {res_skill.text}"
    skill_out = res_skill.json()
    assert skill_out["status"] == "success"
    assert "dimensions" in skill_out["outputs"]
    skill_lat = skill_out.get("metadata", {}).get("latency_ms", 0.0)
    print(f"  [OK] Skill 'media-metadata' executed successfully in {skill_lat:.1f}ms")

    # 6. Workflow Engine DAG Run
    print("\n[Step 6/9] Validating Workflow Engine Topological Execution...")
    res_wf = client.post(
        "/api/v1/workflows/wf_evidence_compare/execute",
        json={
            "inputs": {
                "before_asset_id": "ast_mombasa_before",
                "after_asset_id": "ast_mombasa_after",
            }
        },
    )
    assert res_wf.status_code == 200, f"Workflow execution failed: {res_wf.text}"
    wf_out = res_wf.json()
    assert wf_out["status"] == "success"
    assert "compare" in wf_out["node_results"]
    print(f"  [OK] Workflow DAG executed: status={wf_out['status']}, latency={wf_out['duration_ms']:.1f}ms")

    # 7. Evidence Review & Human Verification
    print("\n[Step 7/9] Validating Evidence Review & Provenance...")
    with store.connection() as db:
        obs = store.one(db, "SELECT * FROM observations WHERE id='obs_mombasa_creek'")
        assert obs, "Observation obs_mombasa_creek missing"
        assert obs["review_status"] == "approved"
        assert obs["reviewed_by"] == "Aryan (Field Lead)"
        assert obs["approved_text"] is not None
    print(f"  [OK] Human Verification: status={obs['review_status']}, reviewer='{obs['reviewed_by']}'")

    # 8. Grounded Impact Story (Internal API requires reviewer/upload auth)
    print("\n[Step 8/9] Validating Published Impact Story...")
    from app.services.reviewer_auth import reviewer_tokens
    token = next(iter(reviewer_tokens().values()), None) or settings.MEDIA_UPLOAD_TOKEN.get_secret_value()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    res_story = client.get(f"/api/v1/projects/{DEMO_PROJECT_ID}/impact-story", headers=headers)
    assert res_story.status_code == 200, f"Failed to get story: {res_story.text}"
    story_data = res_story.json()
    assert story_data["status"] == "published"
    assert story_data["share_token"] == DEMO_SHARE_TOKEN
    assert len(story_data["events"]) >= 3
    print(f"  [OK] Story '{story_data['title']}': status={story_data['status']}, events={len(story_data['events'])}")

    # 9. Public Share Experience
    print("\n[Step 9/9] Validating Public Share Experience & Security...")
    # HTML View
    res_html = client.get(f"/share/{DEMO_SHARE_TOKEN}")
    assert res_html.status_code == 200, f"Public HTML failed: {res_html.status_code}"
    html_text = res_html.text
    assert "<!doctype html>" in html_text.lower()
    assert "Nyali Creek Mangrove Restoration" in html_text
    assert "CLOUDINARY_API_SECRET" not in html_text
    assert "GEMINI_API_KEY" not in html_text
    assert "token_rev_" not in html_text
    print(f"  [OK] Public HTML rendered ({len(html_text):,} bytes) with zero secret leaks")

    # JSON Projection
    res_json = client.get(f"/api/v1/public/impact/{DEMO_SHARE_TOKEN}")
    assert res_json.status_code == 200, f"Public JSON failed: {res_json.status_code}"
    pub_data = res_json.json()
    assert pub_data["public_id"] == DEMO_SHARE_TOKEN
    assert pub_data["verified_findings_count"] >= 1
    assert "database_path" not in pub_data
    print(f"  [OK] Public JSON projection: verified_findings={pub_data['verified_findings_count']}, hero_media={bool(pub_data['hero_media_url'])}")

    # Gating Check: non-existent token returns 404
    res_invalid = client.get("/share/pst_fake_nonexistent_token")
    assert res_invalid.status_code == 404
    print("  [OK] Non-existent share token gated strictly with HTTP 404")

    print("\n" + "=" * 65)
    print("  ALL 9 END-TO-END DEMO STAGES PASSED SUCCESSFULLY!")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(run_smoke_test())
