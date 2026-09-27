"""Deterministic Demo Data Seed for SETOWA Hackathon Showcase.

Idempotently populates a complete, realistic, verified demonstration dataset:
- Project & Site (Mombasa Marine Litter & Mangrove Restoration)
- Chronological Visits (Baseline, Cleanup Action, Post-Verification)
- Multi-Type Media (Images, Video, Poster frame)
- Cloudinary Frame Analytics (Derived video frame timeline & frame analyses)
- Structured Media Intelligence (Controlled tags, signals, observed findings, model provenance)
- Evidence Review (Paired before/after comparison with human approval)
- Physical Measurement (Certified weigh slip with exact attribution)
- Published Impact Story with Public Share Token (Immediate shareable URL)
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
        # 1. Projects
        db.execute("""INSERT OR IGNORE INTO projects(id, name, description, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?)""",
            (
                DEMO_PROJECT_ID,
                "Mombasa Marine Litter & Mangrove Restoration",
                "Community-led coastal cleanup, mangrove bank debris extraction, and physical weighing verification along the Nyali Creek corridor.",
                now,
                json.dumps({"status": "active", "target_date": "2026-10-15"}),
            )
        )

        # 2. Sites
        db.execute("""INSERT OR IGNORE INTO sites(id, name, location, description, project_id, latitude, longitude, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                DEMO_SITE_ID,
                "Nyali Creek Mangrove Shoreline",
                "Mombasa, Kenya (-4.0435, 39.6682)",
                "Tidal mangrove basin impacted by marine plastic flotsam and shoreline debris.",
                DEMO_PROJECT_ID,
                -4.0435,
                39.6682,
                now,
                json.dumps({"ecosystem": "mangrove"}),
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

        # 4. Media Assets
        assets = [
            (
                "ast_mombasa_before",
                "v_mombasa_before",
                "setowa/creek_baseline_debris",
                1,
                f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_baseline_debris.jpg",
                "Field Camera · Nyali Baseline GPS Tagged",
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
                json.dumps({"latitude": -4.0435, "longitude": 39.6682}),
                DEMO_PROJECT_ID,
                "2026-09-02T09:15:00Z",
            ),
            (
                "ast_mombasa_video",
                "v_mombasa_action",
                "setowa/t014_live_walkthrough",
                1,
                f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/setowa/t014_live_walkthrough.mp4",
                "Action Cam · Volunteer Cleanup Walkthrough",
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
                json.dumps({"latitude": -4.0436, "longitude": 39.6683}),
                DEMO_PROJECT_ID,
                "2026-09-14T11:00:00Z",
            ),
            (
                "ast_mombasa_after",
                "v_mombasa_after",
                "setowa/creek_post_cleanup",
                1,
                f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_post_cleanup.jpg",
                "Field Camera · Post-Intervention Verification",
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
                json.dumps({"latitude": -4.0435, "longitude": 39.6682}),
                DEMO_PROJECT_ID,
                "2026-09-22T15:30:00Z",
            ),
        ]
        for a in assets:
            db.execute("""INSERT OR REPLACE INTO assets(
                asset_id, visit_id, public_id, version, secure_url, source, width, height, format,
                permission_status, thumbnail_url, site_id, media_type, processing_status,
                original_filename, duration, preview_url, created_at, metadata_json, project_id, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", a)

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
             json.dumps([]), 420.5, now, json.dumps({"model": "gemini-3.8-flash"})),
            ("fa_mombasa_2", "ast_mombasa_video", "frm_mombasa_2", "field-frame-observation", "1.0.0",
             "analyzed", json.dumps(["Gathering discarded plastic containers into reusable burlap sacks"]),
             json.dumps(["human_activity", "marine_debris"]), 0.88,
             json.dumps([]), 395.2, now, json.dumps({"model": "gemini-3.8-flash"})),
            ("fa_mombasa_3", "ast_mombasa_video", "frm_mombasa_3", "field-frame-observation", "1.0.0",
             "analyzed", json.dumps(["Staging weighed cleanup bags at high-tide access path"]),
             json.dumps(["cleanup_activity", "human_activity"]), 0.94,
             json.dumps([]), 410.0, now, json.dumps({"model": "gemini-3.8-flash"})),
        ]
        for fa in frame_analyses:
            db.execute("""INSERT OR IGNORE INTO frame_analyses(
                analysis_id, asset_id, frame_id, skill_name, skill_version,
                status, observations_json, detected_signals_json, confidence,
                warnings_json, latency_ms, created_at, raw_result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", fa)

        # 7. Media Intelligence
        intel_records = [
            ("mi_mombasa_before", "ast_mombasa_before", None, "analyzed",
             "Baseline inspection of Nyali Creek mangrove shoreline showing visible surface marine debris and plastic bottles entangled in prop roots.",
             json.dumps(["Visible plastic bags, bottles, and foam fragments trapped along high-tide mangrove fringe"]),
             json.dumps(["coastal", "vegetation", "litter"]),
             json.dumps(["marine_debris", "vegetation_cover"]),
             "none", json.dumps([]), "Visual observation of shoreline surface litter",
             json.dumps({"camera": "Field Cam", "gps": "-4.0435, 39.6682"}), "gemini", "gemini-3.8-flash", now, now),
            ("mi_mombasa_video", "ast_mombasa_video", None, "analyzed",
             "Walkthrough video documenting community volunteer team actively recovering marine debris from the mangrove root zone.",
             json.dumps(["Volunteer team actively clearing and bagging tidal flotsam"]),
             json.dumps(["coastal", "vegetation", "litter", "cleanup_activity"]),
             json.dumps(["human_activity", "marine_debris"]),
             "volunteer_cleanup", json.dumps([]), "Documented field activity",
             json.dumps({"camera": "Action Cam", "fps": 30}), "gemini", "gemini-3.8-flash", now, now),
            ("mi_mombasa_after", "ast_mombasa_after", None, "analyzed",
             "Post-intervention audit of the identical Nyali Creek coordinates showing clear water flow and cleared mangrove prop roots.",
             json.dumps(["Marked absence of macro-debris along shoreline waterline; cleared prop roots"]),
             json.dumps(["coastal", "vegetation"]),
             json.dumps(["vegetation_cover"]),
             "none", json.dumps([]), "Verification audit photograph",
             json.dumps({"camera": "Field Cam", "gps": "-4.0435, 39.6682"}), "gemini", "gemini-3.8-flash", now, now),
        ]
        for mi in intel_records:
            db.execute("""INSERT OR IGNORE INTO media_intelligence(
                id, asset_id, frame_id, status, description, observations, tags_json, signals_json,
                activity, warnings_json, uncertainty, evidence_json, model_provider, model_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", mi)

        # 8. Observations (Human Reviewed & Approved Pair)
        obs_id = "obs_mombasa_creek"
        if not store.one(db, "SELECT id FROM observations WHERE id=?", (obs_id,)):
            obs_record = {
                "id": obs_id,
                "site_id": DEMO_SITE_ID,
                "before_asset_id": "ast_mombasa_before",
                "after_asset_id": "ast_mombasa_after",
                "ai_draft": "Visual comparison demonstrates substantial removal of plastic bottles and bags across the mangrove waterline.",
                "working_text": "Significant reduction of macro-plastic debris along the high-tide mangrove root zone. Natural mangrove prop roots cleared of plastic bags and bottles.",
                "approved_text": "Significant reduction of macro-plastic debris along the high-tide mangrove root zone. Natural mangrove prop roots cleared of plastic bags and bottles.",
                "review_status": "approved",
                "reliability_reason": "Verified on-site during post-cleanup audit with matching GPS coordinates and tidal benchmark.",
                "reviewed_by": "Farhan (Field Lead)",
                "reviewed_at": "2026-09-23T14:30:00Z",
                "created_at": now,
                "updated_at": now,
                "version": 1,
            }
            db.execute("""INSERT INTO observations VALUES
                (:id, :site_id, :before_asset_id, :after_asset_id, :ai_draft, :working_text,
                 :approved_text, :review_status, :reliability_reason, :reviewed_by,
                 :reviewed_at, :created_at, :updated_at, :version)""", obs_record)
            store.revision(db, obs_record, "human_approved", "Farhan (Field Lead)", obs_record["approved_text"])

        # 9. Measurements
        msr_id = "msr_mombasa_weigh"
        if not store.one(db, "SELECT id FROM measurements WHERE id=?", (msr_id,)):
            db.execute("""INSERT INTO measurements(id, site_id, visit_id, label, quantity, unit, source, recorded_by, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msr_id,
                    DEMO_SITE_ID,
                    "v_mombasa_action",
                    "Net Shoreline Waste Collected",
                    320.0,
                    "kg",
                    "Nyali Municipal Disposal & Weigh Station Slip #4892",
                    "Farhan (Field Lead)",
                    "2026-09-14T12:00:00Z",
                )
            )

        # 10. Impact Story
        story_data = {
            "id": DEMO_STORY_ID,
            "project_id": DEMO_PROJECT_ID,
            "title": "Nyali Creek Mangrove Restoration & Litter Interception",
            "description": "A verified coastal intervention documenting baseline mangrove pollution, community volunteer collection, certified municipal weighing, and post-cleanup habitat recovery.",
            "status": "published",
            "summary_narrative": "During September 2026, the community cleanup initiative cleared macro-plastic debris from the Nyali Creek mangrove shoreline. Field evidence corroborates a substantial reduction in surface plastic flotsam across the high-tide root zone, substantiated by 320.0 kg of certified waste delivered to the Nyali Municipal Station. Human-in-the-loop review approved the visual comparison and verified spatial consistency across all visits.",
            "uncertainty_note": "Visual inspection confirms surface litter removal; subsurface soil microplastics were not tested under this visual scope. Lighting variations between morning and afternoon visits were accounted for.",
            "share_token": DEMO_SHARE_TOKEN,
            "metadata_json": json.dumps({
                "date_range": {"start": "2026-09-02", "end": "2026-09-22", "start_date": "2026-09-02", "end_date": "2026-09-22"},
                "date_start": "2026-09-02",
                "date_end": "2026-09-22",
                "metrics": {
                    "event_count": 5,
                    "approved_findings_count": 1,
                    "media_count": 3,
                    "measurement_count": 1,
                    "weighed_debris_kg": 320.0,
                },
                "total_events": 5,
                "approved_findings": 1,
                "media_count": 3,
                "measurements_count": 1,
                "weighed_debris_kg": 320.0,
            }),
        }
        store.save_impact_story(db, story_data)

        # 11. Impact Story Events (Chronological Timeline)
        story_events = [
            {
                "id": "evt_momb_1",
                "event_order": 0,
                "timestamp_date": "2026-09-02",
                "event_type": "before",
                "title": "Baseline Environmental Assessment",
                "description": "Pre-cleanup inspection of Nyali Creek mangrove banks. High-tide accumulation of single-use plastics and packaging flotsam observed.",
                "site_id": DEMO_SITE_ID,
                "site_name": "Nyali Creek Mangrove Shoreline",
                "asset_ids_json": json.dumps(["ast_mombasa_before"]),
                "primary_media_url": f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_baseline_debris.jpg",
                "thumbnail_url": f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/setowa/creek_baseline_debris.jpg",
                "media_type": "image",
                "frame_id": None,
                "observation_id": None,
                "measurement_id": None,
                "intelligence_id": "mi_mombasa_before",
                "verification_status": "pending",
                "tags_json": json.dumps(["coastal", "vegetation", "litter"]),
                "signals_json": json.dumps(["marine_debris", "vegetation_cover"]),
                "warnings_json": json.dumps([]),
                "uncertainty": "None",
                "evidence_json": json.dumps({"source": "Field Camera · Nyali Baseline GPS Tagged"}),
            },
            {
                "id": "evt_momb_2",
                "event_order": 1,
                "timestamp_date": "2026-09-14",
                "event_type": "activity",
                "title": "Volunteer Cleanup Walkthrough & Debris Bagging",
                "description": "Community volunteer crew actively extracting and bagging marine debris along the mangrove waterline.",
                "site_id": DEMO_SITE_ID,
                "site_name": "Nyali Creek Mangrove Shoreline",
                "asset_ids_json": json.dumps(["ast_mombasa_video"]),
                "primary_media_url": f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/setowa/t014_live_walkthrough.mp4",
                "thumbnail_url": f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_0/setowa/t014_live_walkthrough.jpg",
                "media_type": "video",
                "frame_id": None,
                "observation_id": None,
                "measurement_id": None,
                "intelligence_id": "mi_mombasa_video",
                "verification_status": "pending",
                "tags_json": json.dumps(["coastal", "vegetation", "litter", "cleanup_activity"]),
                "signals_json": json.dumps(["human_activity", "marine_debris"]),
                "warnings_json": json.dumps([]),
                "uncertainty": "Documented field walkthrough",
                "evidence_json": json.dumps({"source": "Action Cam · Volunteer Cleanup Walkthrough", "fps": 30}),
            },
            {
                "id": "evt_momb_3",
                "event_order": 2,
                "timestamp_date": "2026-09-14",
                "event_type": "measurement",
                "title": "Official Weighing Verification: 320.0 kg",
                "description": "Collected waste transported directly to Nyali Municipal Station. Official weigh slip recorded 320.0 kg net weight.",
                "site_id": DEMO_SITE_ID,
                "site_name": "Nyali Creek Mangrove Shoreline",
                "asset_ids_json": json.dumps([]),
                "primary_media_url": None,
                "thumbnail_url": None,
                "media_type": "document",
                "frame_id": None,
                "observation_id": None,
                "measurement_id": msr_id,
                "intelligence_id": None,
                "verification_status": "approved",
                "tags_json": json.dumps([]),
                "signals_json": json.dumps([]),
                "warnings_json": json.dumps([]),
                "uncertainty": "Certified weigh bridge measurement",
                "evidence_json": json.dumps({"source": "Nyali Municipal Disposal & Weigh Station Slip #4892", "verified_by": "Farhan (Field Lead)"}),
            },
            {
                "id": "evt_momb_4",
                "event_order": 3,
                "timestamp_date": "2026-09-22",
                "event_type": "after",
                "title": "Post-Cleanup Verification Audit",
                "description": "Verification visit to identical GPS coordinates confirming cleared mangrove prop roots and absence of surface macro-plastic.",
                "site_id": DEMO_SITE_ID,
                "site_name": "Nyali Creek Mangrove Shoreline",
                "asset_ids_json": json.dumps(["ast_mombasa_after"]),
                "primary_media_url": f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_post_cleanup.jpg",
                "thumbnail_url": f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/setowa/creek_post_cleanup.jpg",
                "media_type": "image",
                "frame_id": None,
                "observation_id": None,
                "measurement_id": None,
                "intelligence_id": "mi_mombasa_after",
                "verification_status": "pending",
                "tags_json": json.dumps(["coastal", "vegetation"]),
                "signals_json": json.dumps(["vegetation_cover"]),
                "warnings_json": json.dumps([]),
                "uncertainty": "None",
                "evidence_json": json.dumps({"source": "Field Camera · Post-Intervention Verification"}),
            },
            {
                "id": "evt_momb_5",
                "event_order": 4,
                "timestamp_date": "2026-09-23",
                "event_type": "verified_finding",
                "title": "Human-in-the-Loop Verified Finding",
                "description": "Field lead verified observation: Significant reduction of macro-plastic debris along the high-tide mangrove root zone.",
                "site_id": DEMO_SITE_ID,
                "site_name": "Nyali Creek Mangrove Shoreline",
                "asset_ids_json": json.dumps(["ast_mombasa_before", "ast_mombasa_after"]),
                "primary_media_url": f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_post_cleanup.jpg",
                "thumbnail_url": f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/setowa/creek_post_cleanup.jpg",
                "media_type": "image",
                "frame_id": None,
                "observation_id": obs_id,
                "measurement_id": None,
                "intelligence_id": None,
                "verification_status": "approved",
                "tags_json": json.dumps([]),
                "signals_json": json.dumps([]),
                "warnings_json": json.dumps([]),
                "uncertainty": "Verified on-site with matching GPS coordinates and tidal benchmark.",
                "evidence_json": json.dumps({"reviewer": "Farhan (Field Lead)", "reviewed_at": "2026-09-23T14:30:00Z"}),
            },
        ]
        store.save_impact_story_events(db, DEMO_STORY_ID, story_events)

    # Also seed legacy riverbank sample so previous unit tests retain their expected rows
    try:
        from scripts.seed_local_demo import seed as seed_legacy
    except ImportError:
        from seed_local_demo import seed as seed_legacy
    seed_legacy()

    print(f"[OK] SETOWA Demo Dataset seeded successfully:")
    print(f"  Project: {DEMO_PROJECT_ID} (Mombasa Marine Litter & Mangrove Restoration)")
    print(f"  Site: {DEMO_SITE_ID} (Nyali Creek Mangrove Shoreline)")
    print(f"  Assets: 3 (Baseline Image, Cleanup Action Video, Post-Verification Image)")
    print(f"  Video Frames: 3 with Cloudinary offset derivations")
    print(f"  Impact Story: {DEMO_STORY_ID} (Published)")
    print(f"  Public Share Token: {DEMO_SHARE_TOKEN}")
    print(f"  Public URL: /share/{DEMO_SHARE_TOKEN}")

    return {
        "project_id": DEMO_PROJECT_ID,
        "site_id": DEMO_SITE_ID,
        "story_id": DEMO_STORY_ID,
        "share_token": DEMO_SHARE_TOKEN,
        "asset_count": 3,
        "frame_count": 3,
    }


if __name__ == "__main__":
    seed_demo_dataset()
