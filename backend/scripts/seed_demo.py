"""Deterministic Demo Data Seed for SETOWA Hackathon Showcase.

Idempotently populates an illustrative demonstration dataset:
- Project & Site (Mombasa Marine Litter & Mangrove Restoration)
- Chronological Visits (Baseline, Cleanup Action, Post-Verification)
- Multi-Type Media (Images, Video, Poster frame)
- Cloudinary Frame Analytics (Derived video frame timeline & frame analyses)
- Structured Media Intelligence (Controlled tags, signals, observed findings, model provenance)
- Evidence Review (an unapproved proposal for a reviewer to assess)
- Draft Impact Story (never published as field evidence)
- Preserves legacy demo-riverbank fixtures for backward compatibility.
"""
from pathlib import Path
import json
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.services import evidence_store as store
from app.services.public_story import generate_share_token

DEMO_PROJECT_ID = "proj_mombasa_marine"
DEMO_SITE_ID = "site_nyali_creek"
DEMO_STORY_ID = "story_mombasa_marine"
DEMO_SHARE_TOKEN = "pst_demo_mombasa_coastal_2026"


def seed_demo_dataset():
    now = store.timestamp()
    cloud = settings.CLOUDINARY_CLOUD_NAME or "tlf3lv01"
    with store.connection() as db:
        # Repair only the known demonstration IDs from older seeds. Never leave a
        # fabricated approval, measurement or public share in an existing demo DB.
        db.execute("DELETE FROM measurements WHERE id='msr_mombasa_weigh'")
        db.execute("""UPDATE observations SET
            approved_text=NULL, review_status='pending', reviewed_by=NULL, reviewed_at=NULL,
            ai_draft=NULL,
            working_text='Illustrative proposal: the later image may show less visible debris. Media origin, date and matching viewpoint require verification.',
            reliability_reason='Demo fixture only. No field visit, comparison or independent review is substantiated.'
            WHERE id='obs_mombasa_creek'""")
        db.execute("UPDATE impact_stories SET status='draft', share_token=NULL WHERE id=?", (DEMO_STORY_ID,))
        # 1. Projects
        db.execute("""INSERT OR IGNORE INTO projects(id, name, description, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?)""",
            (
                DEMO_PROJECT_ID,
                "Mombasa coastal scenario · illustrative demo",
                "Illustrative workflow fixture. Visit dates, media provenance, locations and visual claims have not been independently verified.",
                now,
                json.dumps({"status": "demo", "synthetic_demo": True}),
            )
        )

        # 2. Sites
        db.execute("""INSERT OR IGNORE INTO sites(id, name, location, description, project_id, latitude, longitude, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                DEMO_SITE_ID,
                "Illustrative coastal site · Mombasa scenario",
                "Illustrative location; coordinates unverified",
                "Demo fixture only. No claim of a documented cleanup at this site.",
                DEMO_PROJECT_ID,
                None,
                None,
                now,
                json.dumps({"ecosystem": "mangrove", "synthetic_demo": True}),
            )
        )

        # 3. Visits
        visits = [
            ("v_mombasa_before", DEMO_SITE_ID, "2026-09-02", "Baseline Ecological Assessment"),
            ("v_mombasa_action", DEMO_SITE_ID, "2026-09-14", "Volunteer Cleanup Action & Weighing"),
            ("v_mombasa_after", DEMO_SITE_ID, "2026-09-22", "Post-Cleanup Verification Visit"),
        ]
        for v in visits:
            db.execute("INSERT OR IGNORE INTO visits(id, site_id, visited_on, label) VALUES (?, ?, ?, ?)", v)
        db.execute("UPDATE visits SET label='Illustrative date · ' || label WHERE site_id=? AND label NOT LIKE 'Illustrative date · %'", (DEMO_SITE_ID,))

        # 4. Media Assets
        assets = [
            (
                "ast_mombasa_before",
                "v_mombasa_before",
                "setowa/creek_baseline_debris",
                1,
                f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_baseline_debris.jpg",
                "Demo media · origin and date unverified",
                1200,
                800,
                "jpg",
                "granted",
                f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/setowa/creek_baseline_debris.jpg",
                DEMO_SITE_ID,
                "image",
                "ready",
                "creek_baseline_debris.jpg",
                None,
                None,
                now,
                json.dumps({"synthetic_demo": True, "provenance": "unverified"}),
                DEMO_PROJECT_ID,
                None,
            ),
            (
                "ast_mombasa_video",
                "v_mombasa_action",
                "setowa/t014_live_walkthrough",
                1,
                f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/setowa/t014_live_walkthrough.mp4",
                "Demo video · origin and date unverified",
                1280,
                720,
                "mp4",
                "granted",
                f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_0/setowa/t014_live_walkthrough.jpg",
                DEMO_SITE_ID,
                "video",
                "ready",
                "t014_live_walkthrough.mp4",
                13.4,
                f"https://res.cloudinary.com/{cloud}/video/upload/so_0/setowa/t014_live_walkthrough.jpg",
                now,
                json.dumps({"synthetic_demo": True, "provenance": "unverified"}),
                DEMO_PROJECT_ID,
                None,
            ),
            (
                "ast_mombasa_after",
                "v_mombasa_after",
                "setowa/creek_post_cleanup",
                1,
                f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_post_cleanup.jpg",
                "Demo media · origin and date unverified",
                1200,
                800,
                "jpg",
                "granted",
                f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/setowa/creek_post_cleanup.jpg",
                DEMO_SITE_ID,
                "image",
                "ready",
                "creek_post_cleanup.jpg",
                None,
                None,
                now,
                json.dumps({"synthetic_demo": True, "provenance": "unverified"}),
                DEMO_PROJECT_ID,
                None,
            ),
        ]
        for a in assets:
            db.execute("""INSERT OR REPLACE INTO assets(
                asset_id, visit_id, public_id, version, secure_url, source, width, height, format,
                permission_status, thumbnail_url, site_id, media_type, processing_status,
                original_filename, duration, preview_url, created_at, metadata_json, project_id, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", a)
        db.execute("""UPDATE assets SET
            source='Demo media · origin and date unverified',
            permission_status='pending_verification',
            captured_at=NULL,
            metadata_json='{"synthetic_demo": true, "provenance": "unverified"}'
            WHERE site_id=?""", (DEMO_SITE_ID,))

        # 5. Video Frames (Cloudinary offset derivations)
        frames = [
            ("frm_mombasa_1", "ast_mombasa_video", 0, 1.5,
             f"https://res.cloudinary.com/{cloud}/video/upload/so_1.5/setowa/t014_live_walkthrough.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_1.5/setowa/t014_live_walkthrough.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/setowa/t014_live_walkthrough.mp4",
             854, 480, "cloudinary_offset"),
            ("frm_mombasa_2", "ast_mombasa_video", 1, 4.0,
             f"https://res.cloudinary.com/{cloud}/video/upload/so_4.0/setowa/t014_live_walkthrough.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_4.0/setowa/t014_live_walkthrough.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/setowa/t014_live_walkthrough.mp4",
             854, 480, "cloudinary_offset"),
            ("frm_mombasa_3", "ast_mombasa_video", 2, 8.0,
             f"https://res.cloudinary.com/{cloud}/video/upload/so_8.0/setowa/t014_live_walkthrough.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_8.0/setowa/t014_live_walkthrough.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/setowa/t014_live_walkthrough.mp4",
             854, 480, "cloudinary_offset"),
        ]
        for f in frames:
            db.execute("""INSERT OR REPLACE INTO video_frames(
                frame_id, asset_id, frame_index, timestamp_seconds, frame_url, thumbnail_url,
                source_video_url, width, height, extraction_method, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (*f, now))

        # 6. Frame Analyses
        frame_analyses = [
            ("fa_mombasa_1", "ast_mombasa_video", "frm_mombasa_1", "field-frame-observation", "1.0.0",
             "analyzed", json.dumps(["Volunteer crew clearing tidal mangrove root area"]),
             json.dumps(["human_activity", "vegetation_cover"]), 0.92,
             json.dumps(["Illustrative fixture, not a recorded model output"]), 420.5, now, json.dumps({"model": "demo-fixture"})),
            ("fa_mombasa_2", "ast_mombasa_video", "frm_mombasa_2", "field-frame-observation", "1.0.0",
             "analyzed", json.dumps(["Gathering discarded plastic containers into reusable burlap sacks"]),
             json.dumps(["human_activity", "marine_debris"]), 0.88,
             json.dumps(["Illustrative fixture, not a recorded model output"]), 395.2, now, json.dumps({"model": "demo-fixture"})),
            ("fa_mombasa_3", "ast_mombasa_video", "frm_mombasa_3", "field-frame-observation", "1.0.0",
             "analyzed", json.dumps(["Staging weighed cleanup bags at high-tide access path"]),
             json.dumps(["cleanup_activity", "human_activity"]), 0.94,
             json.dumps(["Illustrative fixture, not a recorded model output"]), 410.0, now, json.dumps({"model": "demo-fixture"})),
        ]
        for fa in frame_analyses:
            db.execute("""INSERT OR IGNORE INTO frame_analyses(
                analysis_id, asset_id, frame_id, skill_name, skill_version,
                status, observations_json, detected_signals_json, confidence,
                warnings_json, latency_ms, created_at, raw_result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", fa)
        db.execute("""UPDATE frame_analyses SET
            status='insufficient_evidence',
            confidence=NULL,
            observations_json='["Illustrative frame fixture; media provenance unverified"]',
            detected_signals_json='[]',
            warnings_json='["Illustrative fixture, not a recorded model output"]',
            raw_result_json='{"model":"demo-fixture"}'
            WHERE asset_id='ast_mombasa_video'""")

        # 7. Media Intelligence
        intel_records = [
            ("mi_mombasa_before", "ast_mombasa_before", None, "analyzed",
             "Baseline inspection of Nyali Creek mangrove shoreline showing visible surface marine debris and plastic bottles entangled in prop roots.",
             json.dumps(["Visible plastic bags, bottles, and foam fragments trapped along high-tide mangrove fringe"]),
             json.dumps(["coastal", "vegetation", "litter"]),
             json.dumps(["marine_debris", "vegetation_cover"]),
             "none", json.dumps([]), "Visual observation of shoreline surface litter",
             json.dumps({"synthetic_demo": True, "provenance": "unverified"}), "demo-fixture", "none", now, now),
            ("mi_mombasa_video", "ast_mombasa_video", None, "analyzed",
             "Walkthrough video documenting community volunteer team actively recovering marine debris from the mangrove root zone.",
             json.dumps(["Volunteer team actively clearing and bagging tidal flotsam"]),
             json.dumps(["coastal", "vegetation", "litter", "cleanup_activity"]),
             json.dumps(["human_activity", "marine_debris"]),
             "volunteer_cleanup", json.dumps([]), "Documented field activity",
             json.dumps({"synthetic_demo": True, "provenance": "unverified"}), "demo-fixture", "none", now, now),
            ("mi_mombasa_after", "ast_mombasa_after", None, "analyzed",
             "Post-intervention audit of the identical Nyali Creek coordinates showing clear water flow and cleared mangrove prop roots.",
             json.dumps(["Marked absence of macro-debris along shoreline waterline; cleared prop roots"]),
             json.dumps(["coastal", "vegetation"]),
             json.dumps(["vegetation_cover"]),
             "none", json.dumps([]), "Verification audit photograph",
             json.dumps({"synthetic_demo": True, "provenance": "unverified"}), "demo-fixture", "none", now, now),
        ]
        for mi in intel_records:
            db.execute("""INSERT OR IGNORE INTO media_intelligence(
                id, asset_id, frame_id, status, description, observations, tags_json, signals_json,
                activity, warnings_json, uncertainty, evidence_json, model_provider, model_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", mi)
        db.execute("""UPDATE media_intelligence SET
            status='insufficient_evidence',
            description='Illustrative scenario media; provenance and field claims unverified.',
            observations='No verified field observation available.',
            tags_json='[]', signals_json='[]',
            model_provider='demo-fixture', model_name='none',
            warnings_json='["Illustrative fixture, not a recorded model output"]',
            evidence_json='{"synthetic_demo": true, "provenance": "unverified"}'
            WHERE asset_id IN ('ast_mombasa_before','ast_mombasa_video','ast_mombasa_after')""")

        # 8. An unapproved example proposal. A human must make any review decision.
        obs_id = "obs_mombasa_creek"
        if not store.one(db, "SELECT id FROM observations WHERE id=?", (obs_id,)):
            obs_record = {
                "id": obs_id,
                "site_id": DEMO_SITE_ID,
                "before_asset_id": "ast_mombasa_before",
                "after_asset_id": "ast_mombasa_after",
                "ai_draft": None,
                "working_text": "Illustrative proposal: the later image may show less visible debris. Media origin, date and matching viewpoint require verification.",
                "approved_text": None,
                "review_status": "pending",
                "reliability_reason": "Demo fixture only. No field visit, comparison or independent review is substantiated.",
                "reviewed_by": None,
                "reviewed_at": None,
                "created_at": now,
                "updated_at": now,
                "version": 1,
            }
            db.execute("""INSERT INTO observations VALUES
                (:id, :site_id, :before_asset_id, :after_asset_id, :ai_draft, :working_text,
                 :approved_text, :review_status, :reliability_reason, :reviewed_by,
                 :reviewed_at, :created_at, :updated_at, :version)""", obs_record)
            store.revision(db, obs_record, "demo_proposal_created", "demo setup", obs_record["working_text"])

        # 9. The story stays private and contains no invented impact quantities.
        # A reviewer can generate a new story after collecting real, permissioned evidence.
        story_data = {
            "id": DEMO_STORY_ID,
            "project_id": DEMO_PROJECT_ID,
            "title": "Mombasa coastal scenario · illustrative demo",
            "description": "Unverified demonstration fixture. No real-world cleanup or impact is asserted.",
            "status": "draft",
            "summary_narrative": "This is a simulated workspace walkthrough. Dates and media provenance are unverified; the proposed comparison is awaiting human review.",
            "uncertainty_note": "Do not publish as evidence of a real Mombasa cleanup.",
            "share_token": None,
            "metadata_json": json.dumps({"synthetic_demo": True, "metrics": {"approved_findings_count": 0, "measurement_count": 0}}),
        }
        store.save_impact_story(db, story_data)
        store.save_impact_story_events(db, DEMO_STORY_ID, [])

    # Also seed legacy riverbank sample so previous unit tests retain their expected rows
    try:
        from scripts.seed_local_demo import seed as seed_legacy
    except ImportError:
        from seed_local_demo import seed as seed_legacy
    seed_legacy()

    print(f"[OK] SETOWA Demo Dataset seeded successfully:")
    print(f"  Project: {DEMO_PROJECT_ID} (illustrative Mombasa scenario)")
    print(f"  Site: {DEMO_SITE_ID} (unverified location and dates)")
    print(f"  Assets: 3 (Baseline Image, Cleanup Action Video, Post-Verification Image)")
    print(f"  Video Frames: 3 with Cloudinary offset derivations")
    print(f"  Impact Story: {DEMO_STORY_ID} (private draft; unverified scenario)")

    return {
        "project_id": DEMO_PROJECT_ID,
        "site_id": DEMO_SITE_ID,
        "story_id": DEMO_STORY_ID,
        "share_token": None,
        "asset_count": 3,
        "frame_count": 3,
    }


if __name__ == "__main__":
    seed_demo_dataset()
