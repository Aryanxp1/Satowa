"""Deterministic Demo Data Seed for SETOWA Hackathon Showcase (Milestone T020-A).

Expanded mass media demonstration dataset:
- 4 Sites across Coastal Kenya (Nyali Creek, Tudor Creek, Sabaki Riverbank, Watamu Beach)
- 13 Chronological Visits across August–September 2026
- 51 Total Media Assets (48 Images + 3 Full Videos)
- 7 Derived Video Frames with Cloudinary offset transformations
- 7 Frame Analyses with detected visual signals and observations
- 51 Rich Media Intelligence records with controlled environmental tags & signals
- 2 Field Debris Measurements (320 kg at Nyali Creek, 145 kg at Sabaki Riverbank)
- 4 Before/After Comparative Pairs (2 Approved Field Findings + 2 Pending Auditor Proposals)
- 1 Published Public Impact Story (pst_demo_mombasa_coastal_2026) with verified timeline events
- Full transparency: all records clearly labeled with DEMO DATASET / SYNTHETIC SCENARIO markers.
"""
from pathlib import Path
import json
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.services import evidence_store as store

DEMO_PROJECT_ID = "proj_mombasa_marine"
DEMO_SITE_ID = "site_nyali_creek"
DEMO_STORY_ID = "story_mombasa_marine"
DEMO_SHARE_TOKEN = "pst_demo_mombasa_coastal_2026"


def seed_demo_dataset():
    now = store.timestamp()
    cloud = settings.CLOUDINARY_CLOUD_NAME or "tlf3lv01"

    with store.connection() as db:
        # -------------------------------------------------------------
        # 0. Clean prior demo story & events to ensure pure idempotency
        # -------------------------------------------------------------
        db.execute("DELETE FROM impact_story_events WHERE story_id=?", (DEMO_STORY_ID,))
        db.execute("DELETE FROM measurements WHERE id IN ('msr_mombasa_weigh', 'msr_sabaki_weigh')")
        db.execute("DELETE FROM media_intelligence WHERE asset_id LIKE 'ast_%' OR id LIKE 'mi_%'")
        db.execute("DELETE FROM observation_revisions WHERE observation_id = 'ea905f2ba32146ada699bafc09721682'")
        db.execute("DELETE FROM observations WHERE id = 'ea905f2ba32146ada699bafc09721682'")

        # -------------------------------------------------------------
        # 1. Projects
        # -------------------------------------------------------------
        projects = [
            (
                DEMO_PROJECT_ID,
                "Mombasa Coastal Marine Litter & Mangrove Restoration · illustrative demo",
                "SYNTHETIC DEMO DATASET · illustrative demo · Community-driven marine litter collection, tidal mangrove prop-root clearing, and estuarine ecological monitoring along the Kenyan coast.",
                now,
                json.dumps({"status": "demo", "synthetic_demo": True, "category": "marine_conservation"}),
            ),
            (
                "proj_default",
                "Setowa Coastal Habitat Restoration Network · illustrative demo",
                "SYNTHETIC DEMO DATASET · Integrated national coastal habitat verification and marine debris audit initiative.",
                now,
                json.dumps({"status": "demo", "synthetic_demo": True, "category": "coastal_network"}),
            ),
        ]
        for p in projects:
            db.execute(
                """INSERT OR REPLACE INTO projects(id, name, description, created_at, metadata_json)
                   VALUES (?, ?, ?, ?, ?)""", p
            )

        # -------------------------------------------------------------
        # 2. Sites (4 distinct locations)
        # -------------------------------------------------------------
        sites = [
            (
                DEMO_SITE_ID,
                "Nyali Creek Mangrove Fringe · DEMO DATASET",
                "Mombasa, Kenya (-4.0435, 39.6892)",
                "SYNTHETIC DEMO DATASET · Intertidal mangrove forest fringe subjected to high-tide plastic drift and flotsam accumulation.",
                DEMO_PROJECT_ID,
                -4.0435,
                39.6892,
                now,
                json.dumps({"ecosystem": "mangrove", "synthetic_demo": True, "reach_meters": 45}),
            ),
            (
                "site_tudor_creek",
                "Tudor Creek Estuary · DEMO DATASET",
                "Mombasa, Kenya (-4.0321, 39.6645)",
                "SYNTHETIC DEMO DATASET · Protected tidal creek estuary featuring extensive Rhizophora mucronata mangrove stands and seasonal mudflats.",
                DEMO_PROJECT_ID,
                -4.0321,
                39.6645,
                now,
                json.dumps({"ecosystem": "estuarine_mangrove", "synthetic_demo": True, "reach_meters": 60}),
            ),
            (
                "demo-riverbank",
                "Sabaki Riverbank Catchment · DEMO DATASET",
                "Malindi, Kenya (-3.1550, 40.1320)",
                "SYNTHETIC DEMO DATASET · Riparian buffer zone at the Sabaki River delta trapping agricultural runoff and inland plastic debris.",
                DEMO_PROJECT_ID,
                -3.1550,
                40.1320,
                now,
                json.dumps({"ecosystem": "riverbank_riparian", "synthetic_demo": True, "reach_meters": 80}),
            ),
            (
                "site_watamu_beach",
                "Watamu Marine Park Driftline · DEMO DATASET",
                "Watamu, Kenya (-3.3540, 40.0150)",
                "SYNTHETIC DEMO DATASET · High-energy sandy beach driftline and coral rag shoreline adjacent to marine turtle nesting grounds.",
                DEMO_PROJECT_ID,
                -3.3540,
                40.0150,
                now,
                json.dumps({"ecosystem": "coastal_beach", "synthetic_demo": True, "reach_meters": 120}),
            ),
        ]
        for s in sites:
            db.execute(
                """INSERT OR REPLACE INTO sites(id, name, location, description, project_id, latitude, longitude, created_at, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", s
            )

        # -------------------------------------------------------------
        # 3. Chronological Visits (13 visits across August–September 2026)
        # -------------------------------------------------------------
        visits = [
            # Nyali Creek (4 visits: baseline < action < audit < after)
            ("v_mombasa_before", DEMO_SITE_ID, "2026-08-15", "Nyali Baseline Ecological Survey & Debris Mapping"),
            ("v_mombasa_action", DEMO_SITE_ID, "2026-08-28", "Nyali Volunteer Cleanup Action & Debris Weighing"),
            ("v_mombasa_audit", DEMO_SITE_ID, "2026-09-08", "Nyali High-Tide Estuarine Inspection"),
            ("v_mombasa_after", DEMO_SITE_ID, "2026-09-18", "Nyali Post-Cleanup Verification Visit"),

            # Tudor Creek (3 visits: baseline < action < after)
            ("v_tudor_baseline", "site_tudor_creek", "2026-08-18", "Tudor Creek Estuary Baseline Assessment"),
            ("v_tudor_action", "site_tudor_creek", "2026-09-02", "Tudor Creek Community Mangrove Debris Clearing"),
            ("v_tudor_after", "site_tudor_creek", "2026-09-20", "Tudor Creek Estuary Shoreline Verification"),

            # Sabaki Riverbank (3 visits: baseline < action < after)
            ("demo-visit-before", "demo-riverbank", "2026-08-20", "Sabaki Riverbank Riparian Baseline Survey"),
            ("v_sabaki_action", "demo-riverbank", "2026-09-05", "Sabaki River Flotsam & Net Removal Campaign"),
            ("demo-visit-after", "demo-riverbank", "2026-09-22", "Sabaki Riparian Catchment Verification"),

            # Watamu Beach (3 visits: baseline < cleanup < verify)
            ("v_watamu_baseline", "site_watamu_beach", "2026-08-25", "Watamu Marine Litter Driftline Survey"),
            ("v_watamu_cleanup", "site_watamu_beach", "2026-09-12", "Watamu Beach Driftline & Ghost Net Sweep"),
            ("v_watamu_after", "site_watamu_beach", "2026-09-25", "Watamu Shoreline Nesting Ground Audit"),
        ]
        for v in visits:
            db.execute("INSERT OR REPLACE INTO visits(id, site_id, visited_on, label) VALUES (?, ?, ?, ?)", v)

        # -------------------------------------------------------------
        # 4. Media Assets (48 Images + 3 Videos = 51 Assets)
        # All using Cloudinary storage (tlf3lv01) with granted permissions
        # -------------------------------------------------------------
        asset_defs = [
            # Nyali Creek Images
            ("ast_mombasa_before", "v_mombasa_before", DEMO_SITE_ID, "setowa/creek_baseline_debris", "jpg", "image", 1200, 800, None, "creek_baseline_debris.jpg", "2026-08-15T09:30:00Z"),
            ("ast_nyali_img_02", "v_mombasa_before", DEMO_SITE_ID, "samples/cup-on-a-table", "jpg", "image", 1200, 800, None, "nyali_debris_cup.jpg", "2026-08-15T10:15:00Z"),
            ("ast_nyali_img_03", "v_mombasa_before", DEMO_SITE_ID, "samples/shoe", "jpg", "image", 1200, 800, None, "nyali_litter_shoe.jpg", "2026-08-15T11:00:00Z"),
            ("ast_nyali_img_04", "v_mombasa_before", DEMO_SITE_ID, "samples/balloons", "jpg", "image", 1200, 800, None, "nyali_plastic_fragments.jpg", "2026-08-15T11:45:00Z"),
            ("ast_nyali_img_05", "v_mombasa_before", DEMO_SITE_ID, "samples/landscapes/architecture-signs", "jpg", "image", 1200, 800, None, "nyali_site_marker.jpg", "2026-08-15T12:00:00Z"),

            ("ast_nyali_img_06", "v_mombasa_action", DEMO_SITE_ID, "samples/animals/cat", "jpg", "image", 1200, 800, None, "nyali_crew_burlap_sacks.jpg", "2026-08-28T08:30:00Z"),
            ("ast_nyali_img_07", "v_mombasa_action", DEMO_SITE_ID, "samples/people/boy-snow-hoodie", "jpg", "image", 1200, 800, None, "nyali_volunteer_clearing.jpg", "2026-08-28T09:15:00Z"),
            ("ast_nyali_img_08", "v_mombasa_action", DEMO_SITE_ID, "samples/people/smiling-man", "jpg", "image", 1200, 800, None, "nyali_field_supervisor.jpg", "2026-08-28T10:00:00Z"),
            ("ast_nyali_img_09", "v_mombasa_action", DEMO_SITE_ID, "samples/people/kitchen-bar", "jpg", "image", 1200, 800, None, "nyali_weighing_station.jpg", "2026-08-28T14:00:00Z"),
            ("ast_nyali_img_10", "v_mombasa_action", DEMO_SITE_ID, "samples/ecommerce/accessories-bag", "jpg", "image", 1200, 800, None, "nyali_weighed_bags.jpg", "2026-08-28T14:45:00Z"),
            ("ast_nyali_img_11", "v_mombasa_action", DEMO_SITE_ID, "samples/ecommerce/analog-classic", "jpg", "image", 1200, 800, None, "nyali_time_audit.jpg", "2026-08-28T15:30:00Z"),

            ("ast_nyali_img_12", "v_mombasa_audit", DEMO_SITE_ID, "samples/waves", "jpg", "image", 1200, 800, None, "nyali_tidal_flushing.jpg", "2026-09-08T09:00:00Z"),
            ("ast_nyali_img_13", "v_mombasa_audit", DEMO_SITE_ID, "samples/look-up", "jpg", "image", 1200, 800, None, "nyali_mangrove_canopy.jpg", "2026-09-08T10:30:00Z"),

            ("ast_mombasa_after", "v_mombasa_after", DEMO_SITE_ID, "setowa/creek_post_cleanup", "jpg", "image", 1200, 800, None, "creek_post_cleanup.jpg", "2026-09-18T10:00:00Z"),
            ("ast_nyali_img_15", "v_mombasa_after", DEMO_SITE_ID, "cld-sample-5", "jpg", "image", 1200, 800, None, "nyali_root_aeration_check.jpg", "2026-09-18T11:15:00Z"),

            # Tudor Creek Images
            ("ast_tudor_before", "v_tudor_baseline", "site_tudor_creek", "samples/food/pot-mussels", "jpg", "image", 1200, 800, None, "tudor_baseline_mudflat.jpg", "2026-08-18T09:00:00Z"),
            ("ast_tudor_img_02", "v_tudor_baseline", "site_tudor_creek", "samples/animals/kitten-playing", "jpg", "image", 1200, 800, None, "tudor_entangled_debris.jpg", "2026-08-18T10:00:00Z"),
            ("ast_tudor_img_03", "v_tudor_baseline", "site_tudor_creek", "samples/dessert-on-a-plate", "jpg", "image", 1200, 800, None, "tudor_mudflat_flotsam.jpg", "2026-08-18T11:30:00Z"),
            ("ast_tudor_img_04", "v_tudor_baseline", "site_tudor_creek", "samples/coffee", "jpg", "image", 1200, 800, None, "tudor_water_clarity.jpg", "2026-08-18T12:00:00Z"),

            ("ast_tudor_img_05", "v_tudor_action", "site_tudor_creek", "samples/food/spices", "jpg", "image", 1200, 800, None, "tudor_debris_sorting.jpg", "2026-09-02T08:30:00Z"),
            ("ast_tudor_img_06", "v_tudor_action", "site_tudor_creek", "samples/people/outdoor-woman", "jpg", "image", 1200, 800, None, "tudor_volunteer_extractor.jpg", "2026-09-02T09:45:00Z"),
            ("ast_tudor_img_07", "v_tudor_action", "site_tudor_creek", "samples/people/jazz", "jpg", "image", 1200, 800, None, "tudor_community_briefing.jpg", "2026-09-02T11:00:00Z"),
            ("ast_tudor_img_08", "v_tudor_action", "site_tudor_creek", "samples/people/man-on-a-street", "jpg", "image", 1200, 800, None, "tudor_net_removal.jpg", "2026-09-02T12:15:00Z"),
            ("ast_tudor_img_09", "v_tudor_action", "site_tudor_creek", "samples/ecommerce/leather-bag-gray", "jpg", "image", 1200, 800, None, "tudor_waste_staging.jpg", "2026-09-02T14:00:00Z"),
            ("ast_tudor_img_10", "v_tudor_action", "site_tudor_creek", "cld-sample", "jpg", "image", 1200, 800, None, "tudor_prop_root_clearance.jpg", "2026-09-02T15:30:00Z"),

            ("ast_tudor_after", "v_tudor_after", "site_tudor_creek", "samples/landscapes/girl-urban-view", "jpg", "image", 1200, 800, None, "tudor_post_estuary_view.jpg", "2026-09-20T09:30:00Z"),
            ("ast_tudor_img_12", "v_tudor_after", "site_tudor_creek", "cld-sample-2", "jpg", "image", 1200, 800, None, "tudor_cleared_mudflat.jpg", "2026-09-20T11:00:00Z"),

            # Sabaki Riverbank Images
            ("ast_sabaki_before", "demo-visit-before", "demo-riverbank", "samples/landscapes/nature-mountains", "jpg", "image", 1200, 800, None, "sabaki_riparian_baseline.jpg", "2026-08-20T09:00:00Z"),
            ("ast_sabaki_img_02", "demo-visit-before", "demo-riverbank", "samples/animals/reindeer", "jpg", "image", 1200, 800, None, "sabaki_riverbank_nets.jpg", "2026-08-20T10:15:00Z"),
            ("ast_sabaki_img_03", "demo-visit-before", "demo-riverbank", "samples/chair", "jpg", "image", 1200, 800, None, "sabaki_driftwood_litter.jpg", "2026-08-20T11:30:00Z"),
            ("ast_sabaki_img_04", "demo-visit-before", "demo-riverbank", "samples/chair-and-coffee-table", "jpg", "image", 1200, 800, None, "sabaki_plastic_accumulation.jpg", "2026-08-20T12:45:00Z"),
            ("ast_sabaki_img_05", "demo-visit-before", "demo-riverbank", "samples/paper", "jpg", "image", 1200, 800, None, "sabaki_agricultural_packaging.jpg", "2026-08-20T14:00:00Z"),

            ("ast_sabaki_img_06", "v_sabaki_action", "demo-riverbank", "samples/sheep", "jpg", "image", 1200, 800, None, "sabaki_volunteer_haul.jpg", "2026-09-05T08:30:00Z"),
            ("ast_sabaki_img_07", "v_sabaki_action", "demo-riverbank", "samples/ecommerce/car-interior-design", "jpg", "image", 1200, 800, None, "sabaki_truck_staging.jpg", "2026-09-05T14:30:00Z"),

            ("ast_sabaki_after", "demo-visit-after", "demo-riverbank", "samples/landscapes/landscape-panorama", "jpg", "image", 1200, 800, None, "sabaki_riparian_verified.jpg", "2026-09-22T09:30:00Z"),
            ("ast_sabaki_img_09", "demo-visit-after", "demo-riverbank", "samples/bike", "jpg", "image", 1200, 800, None, "sabaki_cleared_bank.jpg", "2026-09-22T11:00:00Z"),
            ("ast_sabaki_img_10", "demo-visit-after", "demo-riverbank", "sample", "jpg", "image", 1200, 800, None, "sabaki_water_flow_restoration.jpg", "2026-09-22T12:30:00Z"),

            # Watamu Beach Images
            ("ast_watamu_before", "v_watamu_baseline", "site_watamu_beach", "samples/landscapes/beach-boat", "jpg", "image", 1200, 800, None, "watamu_driftline_baseline.jpg", "2026-08-25T08:30:00Z"),
            ("ast_watamu_img_02", "v_watamu_baseline", "site_watamu_beach", "samples/food/fish-vegetables", "jpg", "image", 1200, 800, None, "watamu_tangled_monofilament.jpg", "2026-08-25T09:45:00Z"),
            ("ast_watamu_img_03", "v_watamu_baseline", "site_watamu_beach", "samples/ecommerce/shoes", "jpg", "image", 1200, 800, None, "watamu_footwear_drift.jpg", "2026-08-25T11:00:00Z"),
            ("ast_watamu_img_04", "v_watamu_baseline", "site_watamu_beach", "samples/breakfast", "jpg", "image", 1200, 800, None, "watamu_plastic_driftline.jpg", "2026-08-25T12:15:00Z"),

            ("ast_watamu_img_05", "v_watamu_cleanup", "site_watamu_beach", "samples/animals/three-dogs", "jpg", "image", 1200, 800, None, "watamu_beach_sweepers.jpg", "2026-09-12T07:30:00Z"),
            ("ast_watamu_img_06", "v_watamu_cleanup", "site_watamu_beach", "samples/people/two-ladies", "jpg", "image", 1200, 800, None, "watamu_volunteers_bagging.jpg", "2026-09-12T08:45:00Z"),
            ("ast_watamu_img_07", "v_watamu_cleanup", "site_watamu_beach", "samples/man-portrait", "jpg", "image", 1200, 800, None, "watamu_marine_ranger.jpg", "2026-09-12T10:00:00Z"),
            ("ast_watamu_img_08", "v_watamu_cleanup", "site_watamu_beach", "cld-sample-3", "jpg", "image", 1200, 800, None, "watamu_ghost_net_extraction.jpg", "2026-09-12T11:30:00Z"),

            ("ast_watamu_after", "v_watamu_after", "site_watamu_beach", "cld-sample-4", "jpg", "image", 1200, 800, None, "watamu_nesting_shoreline.jpg", "2026-09-25T09:00:00Z"),
            ("ast_watamu_img_10", "v_watamu_after", "site_watamu_beach", "samples/people/bicycle", "jpg", "image", 1200, 800, None, "watamu_clean_sand_patrol.jpg", "2026-09-25T10:30:00Z"),
            ("ast_watamu_img_11", "v_watamu_after", "site_watamu_beach", "samples/smile", "jpg", "image", 1200, 800, None, "watamu_community_celebration.jpg", "2026-09-25T12:00:00Z"),

            # 3 High-Impact Demonstration Videos
            ("ast_mombasa_video", "v_mombasa_action", DEMO_SITE_ID, "setowa/t014_live_walkthrough", "mp4", "video", 1280, 720, 13.4, "t014_live_walkthrough.mp4", "2026-08-28T10:30:00Z"),
            ("ast_sabaki_action_video", "v_sabaki_action", "demo-riverbank", "samples/cld-sample-video", "mp4", "video", 1280, 720, 10.7, "cld-sample-video.mp4", "2026-09-05T09:30:00Z"),
            ("ast_watamu_turtle_video", "v_watamu_cleanup", "site_watamu_beach", "samples/sea-turtle", "mp4", "video", 1280, 720, 13.1, "sea-turtle.mp4", "2026-09-12T09:00:00Z"),
        ]

        for aid, vid, sid, pid, fmt, mtype, w, h, dur, fname, cap_at in asset_defs:
            if mtype == "video":
                sec_url = f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/{pid}.{fmt}"
                thumb_url = f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_0/{pid}.jpg"
                prev_url = f"https://res.cloudinary.com/{cloud}/video/upload/so_0/{pid}.jpg"
            else:
                sec_url = f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/{pid}.{fmt}"
                thumb_url = f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/{pid}.{fmt}"
                prev_url = None

            db.execute("""INSERT OR REPLACE INTO assets(
                asset_id, visit_id, public_id, version, secure_url, source, width, height, format,
                permission_status, thumbnail_url, site_id, media_type, processing_status,
                original_filename, duration, preview_url, created_at, metadata_json, project_id, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                aid, vid, pid, 1, sec_url,
                "DEMO DATASET · Coastal Monitoring Sensor / Volunteer Photo",
                w, h, fmt, "granted", thumb_url, sid, mtype, "ready",
                fname, dur, prev_url, now,
                json.dumps({"synthetic_demo": True, "demonstration_scenario": True, "cloud_hosted": True}),
                DEMO_PROJECT_ID, cap_at,
            ))

        # -------------------------------------------------------------
        # 5. Video Frames (Derived frame extractions across all 3 videos)
        # -------------------------------------------------------------
        frames = [
            # Mombasa walkthrough video frames
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

            # Sabaki riverbank action video frames
            ("frm_sabaki_1", "ast_sabaki_action_video", 0, 2.0,
             f"https://res.cloudinary.com/{cloud}/video/upload/so_2.0/samples/cld-sample-video.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_2.0/samples/cld-sample-video.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/samples/cld-sample-video.mp4",
             854, 480, "cloudinary_offset"),
            ("frm_sabaki_2", "ast_sabaki_action_video", 1, 6.0,
             f"https://res.cloudinary.com/{cloud}/video/upload/so_6.0/samples/cld-sample-video.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_6.0/samples/cld-sample-video.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/samples/cld-sample-video.mp4",
             854, 480, "cloudinary_offset"),

            # Watamu sea turtle & driftline video frames
            ("frm_watamu_1", "ast_watamu_turtle_video", 0, 3.0,
             f"https://res.cloudinary.com/{cloud}/video/upload/so_3.0/samples/sea-turtle.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_3.0/samples/sea-turtle.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/samples/sea-turtle.mp4",
             854, 480, "cloudinary_offset"),
            ("frm_watamu_2", "ast_watamu_turtle_video", 1, 7.5,
             f"https://res.cloudinary.com/{cloud}/video/upload/so_7.5/samples/sea-turtle.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_7.5/samples/sea-turtle.jpg",
             f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/samples/sea-turtle.mp4",
             854, 480, "cloudinary_offset"),
        ]
        for f in frames:
            db.execute("""INSERT OR REPLACE INTO video_frames(
                frame_id, asset_id, frame_index, timestamp_seconds, frame_url, thumbnail_url,
                source_video_url, width, height, extraction_method, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (*f, now, json.dumps({"synthetic_demo": True})))

        # -------------------------------------------------------------
        # 6. Frame Analyses
        # -------------------------------------------------------------
        frame_analyses = [
            ("fa_mombasa_1", "ast_mombasa_video", "frm_mombasa_1", "field-frame-observation", "1.0.0", "analyzed",
             json.dumps(["Volunteer crew clearing tidal mangrove root area"]),
             json.dumps(["human_activity", "vegetation_cover", "mangrove_roots"]), 0.94,
             json.dumps([]), 380.0, now, json.dumps({"model": "gemini-3.8-flash", "synthetic_demo": True})),
            ("fa_mombasa_2", "ast_mombasa_video", "frm_mombasa_2", "field-frame-observation", "1.0.0", "analyzed",
             json.dumps(["Gathering discarded plastic containers and bottles into reusable burlap sacks"]),
             json.dumps(["human_activity", "marine_debris", "plastic_waste"]), 0.92,
             json.dumps([]), 410.0, now, json.dumps({"model": "gemini-3.8-flash", "synthetic_demo": True})),
            ("fa_mombasa_3", "ast_mombasa_video", "frm_mombasa_3", "field-frame-observation", "1.0.0", "analyzed",
             json.dumps(["Staging weighed cleanup bags at high-tide access path"]),
             json.dumps(["cleanup_activity", "human_activity"]), 0.95,
             json.dumps([]), 395.0, now, json.dumps({"model": "gemini-3.8-flash", "synthetic_demo": True})),

            ("fa_sabaki_1", "ast_sabaki_action_video", "frm_sabaki_1", "field-frame-observation", "1.0.0", "analyzed",
             json.dumps(["Extracting entangled polypropylene fishing nets from riparian brush"]),
             json.dumps(["cleanup_activity", "fishing_gear", "riparian_vegetation"]), 0.89,
             json.dumps([]), 420.0, now, json.dumps({"model": "gemini-3.8-flash", "synthetic_demo": True})),
            ("fa_sabaki_2", "ast_sabaki_action_video", "frm_sabaki_2", "field-frame-observation", "1.0.0", "analyzed",
             json.dumps(["Loading recovered agricultural plastic wrap onto collection trailer"]),
             json.dumps(["cleanup_activity", "human_presence", "plastic_waste"]), 0.91,
             json.dumps([]), 390.0, now, json.dumps({"model": "gemini-3.8-flash", "synthetic_demo": True})),

            ("fa_watamu_1", "ast_watamu_turtle_video", "frm_watamu_1", "field-frame-observation", "1.0.0", "analyzed",
             json.dumps(["Endangered green sea turtle navigating cleared nearshore reef channel"]),
             json.dumps(["marine_wildlife", "water_turbidity", "habitat_clearance"]), 0.97,
             json.dumps([]), 450.0, now, json.dumps({"model": "gemini-3.8-flash", "synthetic_demo": True})),
            ("fa_watamu_2", "ast_watamu_turtle_video", "frm_watamu_2", "field-frame-observation", "1.0.0", "analyzed",
             json.dumps(["Absence of discarded fishing monofilament along turtle entry path"]),
             json.dumps(["post_cleanup_clearance", "marine_wildlife"]), 0.93,
             json.dumps([]), 415.0, now, json.dumps({"model": "gemini-3.8-flash", "synthetic_demo": True})),
        ]
        for fa in frame_analyses:
            db.execute("""INSERT OR REPLACE INTO frame_analyses(
                analysis_id, asset_id, frame_id, skill_name, skill_version,
                status, observations_json, detected_signals_json, confidence,
                warnings_json, latency_ms, created_at, raw_result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", fa)

        # -------------------------------------------------------------
        # 7. Media Intelligence (All 51 Assets + Frames)
        # Provides rich tags (debris, plastic, nets, mangroves, water, etc.)
        # -------------------------------------------------------------
        intel_lookup = {
            # Nyali Creek
            "ast_mombasa_before": ("Baseline inspection of Nyali Creek mangrove fringe showing visible surface marine debris, discarded plastic bottles, and entangled flotsam in prop roots.", ["High density of single-use plastic bottles, beverage bags, and synthetic ropes trapped in roots"], ["debris", "plastic", "mangroves", "marine litter", "litter", "vegetation", "water"], ["marine_debris", "plastic_waste", "mangrove_roots"], "baseline_survey"),
            "ast_nyali_img_02": ("Macro inspection of plastic containers and cups wedged in intertidal sediment.", ["Expanded polystyrene fragments and rigid beverage containers"], ["debris", "plastic", "waste"], ["plastic_waste", "marine_debris"], "baseline_survey"),
            "ast_nyali_img_03": ("Discarded synthetic footwear and textile waste stranded at the high-water line.", ["Degraded synthetic polyurethane sole trapped in mud"], ["debris", "marine litter", "water"], ["marine_debris"], "baseline_survey"),
            "ast_nyali_img_04": ("Accumulated polymer fragments and weathered plastic debris along tidal fringe.", ["Micro-fragmentation of synthetic packaging materials"], ["plastic", "debris", "coastal"], ["plastic_waste"], "baseline_survey"),
            "ast_nyali_img_05": ("Permanent environmental GPS benchmark post establishing photographic survey boundaries.", ["Photographic monitoring marker #1 at high-tide datum"], ["coastal", "mangroves", "monitoring"], ["site_marker"], "none"),

            "ast_nyali_img_06": ("Volunteer field crew gathering recovered marine plastic into heavy-duty burlap sacks.", ["Burlap sacks filled with recovered macro-debris staged above high-water line"], ["cleanup", "volunteers", "bags", "debris", "plastic"], ["cleanup_activity", "marine_debris"], "volunteer_cleanup"),
            "ast_nyali_img_07": ("Community volunteer clearing tangled plastic ropes from stilt mangrove roots.", ["Manual untangling of monofilament line from Avicennia prop roots"], ["cleanup", "volunteers", "mangroves", "nets"], ["cleanup_activity", "mangrove_roots"], "volunteer_cleanup"),
            "ast_nyali_img_08": ("Field supervisor documenting batch debris manifests and volunteer team locations.", ["Field monitoring clipboard and digital photo registry"], ["cleanup", "volunteers", "coastal"], ["human_presence"], "field_lead"),
            "ast_nyali_img_09": ("Field weigh-in staging station with hanging digital crane scale at Nyali Creek roadhead.", ["Digital hanging scale suspended from tripod for bulk batch recording"], ["weighing", "measurement", "cleanup", "bags"], ["measurement_staging"], "measurement"),
            "ast_nyali_img_10": ("Stacked burlap sacks containing 320 kg of weighed marine litter ready for recycling transfer.", ["Calibrated batch weigh-in of 320 kg marine litter completed"], ["cleanup", "bags", "debris", "plastic", "marine litter"], ["debris_collection", "measurement_staging"], "measurement"),
            "ast_nyali_img_11": ("Time-stamped audit record documenting completion of volunteer cleanup shift.", ["Official field audit verification log signed by team leads"], ["monitoring", "audit", "coastal"], ["field_timestamp"], "audit"),

            "ast_nyali_img_12": ("Tidal surge flushing through cleared Nyali Creek mangrove channel during incoming spring tide.", ["Unimpeded seawater flow through prop roots with no floating plastic damming"], ["water", "coastal", "mangroves", "vegetation"], ["water_turbidity", "coastal_tide"], "verification_audit"),
            "ast_nyali_img_13": ("Upward canopy inspection confirming intact mangrove canopy cover and healthy foliage.", ["Dense Rhizophora foliage with healthy pneumatophore emergence"], ["mangroves", "vegetation", "canopy"], ["vegetation_cover"], "verification_audit"),

            "ast_mombasa_after": ("Post-cleanup verification photograph from identical fixed-point coordinates at Nyali Creek showing cleared mangrove roots and absence of surface plastic debris.", ["Prop root zone completely cleared of macro-plastic bottles and ropes; unobstructed tidal flushing"], ["mangroves", "coastal", "water", "vegetation", "cleanup", "post-cleanup"], ["post_cleanup_clearance", "vegetation_cover"], "verification_audit"),
            "ast_nyali_img_15": ("Close-up verification inspection of mangrove pneumatophores showing clean sediment and zero plastic strangulation.", ["Sediment surface free of macro-litter; prop roots aerating normally"], ["mangroves", "vegetation", "water", "post-cleanup"], ["post_cleanup_clearance"], "verification_audit"),

            # Tudor Creek
            "ast_tudor_before": ("Baseline survey of Tudor Creek estuarine mudflat with abandoned fishing nets and trapped bottles.", ["Ghost fishing nets entangled in estuarine mudflat with trapped plastic flotsam"], ["debris", "plastic", "nets", "mangroves", "marine litter"], ["marine_debris", "fishing_gear"], "baseline_survey"),
            "ast_tudor_img_02": ("High-density accumulation of discarded plastic beverage bottles along high-tide mangrove fringe.", ["Dense clustering of PET bottles and polypropylene twine"], ["plastic", "debris", "mangroves", "water"], ["plastic_waste"], "baseline_survey"),
            "ast_tudor_img_03": ("Estuary sediment mudflat strewn with synthetic flotsam and plastic packaging.", ["Surface litter concentration across tidal mudflat"], ["debris", "plastic", "marine litter"], ["marine_debris"], "baseline_survey"),
            "ast_tudor_img_04": ("Estuary water turbidity and surface foam caused by organic decay trapped in debris dams.", ["Visible turbidity and plastic film floating at river mouth"], ["water", "debris", "estuary"], ["water_turbidity"], "baseline_survey"),

            "ast_tudor_img_05": ("Debris segregation station sorting recovered plastics into recyclable polymers and unrecyclable nets.", ["Volunteers sorting HDPE jugs, PET bottles, and nylon nets"], ["cleanup", "debris", "plastic", "nets"], ["cleanup_activity", "plastic_waste"], "volunteer_cleanup"),
            "ast_tudor_img_06": ("Volunteer extractor wading through tidal mudflat to free deeply embedded polypropylene rope.", ["Manual excavation of buried maritime ropes"], ["cleanup", "volunteers", "mangroves", "water"], ["cleanup_activity", "human_presence"], "volunteer_cleanup"),
            "ast_tudor_img_07": ("Community briefing and safety protocol review before entering mangrove channel.", ["Local community volunteers receiving field gear and instructions"], ["volunteers", "cleanup", "mangroves"], ["human_presence"], "volunteer_cleanup"),
            "ast_tudor_img_08": ("Ranger team cutting heavy abandoned nylon gill net from mangrove branch.", ["Heavy monofilament gill net severed and extracted"], ["nets", "fishing nets", "cleanup", "mangroves"], ["fishing_gear", "cleanup_activity"], "volunteer_cleanup"),
            "ast_tudor_img_09": ("Consolidated waste sacks loaded onto estuary transfer boat.", ["Sacks loaded on small vessel for transport to mainland recycling facility"], ["cleanup", "bags", "debris", "water"], ["debris_collection"], "volunteer_cleanup"),
            "ast_tudor_img_10": ("Prop root inspection showing extraction of trapped plastic wrapping.", ["Clearing tight root forks of synthetic bags"], ["mangroves", "cleanup", "vegetation"], ["cleanup_activity"], "volunteer_cleanup"),

            "ast_tudor_after": ("Post-cleanup verification panorama of Tudor Creek estuary showing cleared mudflat and restored water flow.", ["Tidal mudflat clear of abandoned gill nets and macro-plastics"], ["estuary", "mangroves", "water", "vegetation", "cleanup", "post-cleanup"], ["post_cleanup_clearance", "vegetation_cover"], "verification_audit"),
            "ast_tudor_img_12": ("Restored estuarine mudflat during receding tide with natural crab burrowing re-established.", ["Mudflat surface showing healthy fiddler crab activity and zero surface litter"], ["estuary", "mangroves", "water", "post-cleanup"], ["post_cleanup_clearance"], "verification_audit"),

            # Sabaki Riverbank
            "ast_sabaki_before": ("Baseline inspection of Sabaki Riverbank riparian corridor with snagged plastic sheeting and nylon nets.", ["Agricultural mulch plastic and flood debris clinging to riparian vegetation"], ["riverbank", "vegetation", "debris", "plastic", "nets"], ["riparian_vegetation", "plastic_waste", "fishing_gear"], "baseline_survey"),
            "ast_sabaki_img_02": ("Entangled riverine drift nets wrapping riparian willow and acacia roots.", ["Nylon cast nets discarded along riverbank snagging river flotsam"], ["riverbank", "nets", "fishing nets", "vegetation"], ["fishing_gear"], "baseline_survey"),
            "ast_sabaki_img_03": ("Riverbank eddy accumulating dense floating drift of beverage bottles and agrochemical jugs.", ["River eddy concentrating floating plastic bottles"], ["riverbank", "debris", "plastic", "water"], ["plastic_waste"], "baseline_survey"),
            "ast_sabaki_img_04": ("Plastic waste and torn woven fertilizer sacks embedded in riverbank sediment.", ["Torn woven polypropylene bags embedded in silty bank"], ["riverbank", "debris", "plastic"], ["plastic_waste"], "baseline_survey"),
            "ast_sabaki_img_05": ("Decaying cardboard packaging and agricultural trash along river access trail.", ["Mixed solid waste along riparian trail"], ["riverbank", "debris", "waste"], ["marine_debris"], "baseline_survey"),

            "ast_sabaki_img_06": ("Volunteer team hauling consolidated riverbank trash sacks to collection truck.", ["Crew carrying 145 kg of riverine plastics to transport point"], ["cleanup", "volunteers", "riverbank", "bags"], ["cleanup_activity", "human_presence"], "volunteer_cleanup"),
            "ast_sabaki_img_07": ("Weighbridge check-in for Sabaki Riverbank recovery batch totaling 145 kg.", ["Official batch slip recording 145 kg river plastic"], ["riverbank", "weighing", "measurement", "cleanup"], ["measurement_staging"], "measurement"),

            "ast_sabaki_after": ("Post-cleanup audit of Sabaki Riverbank showing restored riparian bank and clear river water flow.", ["Riparian bank completely free of snagged plastic sheeting and drift nets"], ["riverbank", "vegetation", "water", "cleanup", "post-cleanup"], ["post_cleanup_clearance", "vegetation_cover"], "verification_audit"),
            "ast_sabaki_img_09": ("Clear riparian bank with re-emerging river grass and stable embankment.", ["Grassed riverbank without plastic debris obstruction"], ["riverbank", "vegetation", "post-cleanup"], ["vegetation_cover"], "verification_audit"),
            "ast_sabaki_img_10": ("Active water flow through Sabaki river bend without plastic bottleneck dams.", ["River water flowing smoothly along unobstructed riparian corridor"], ["riverbank", "water", "post-cleanup"], ["water_turbidity"], "verification_audit"),

            # Watamu Beach
            "ast_watamu_before": ("Baseline marine litter driftline survey at Watamu Beach showing washed-up ghost nets and plastic debris.", ["Stranded commercial trawl net fragments, ropes, and beverage bottles on turtle nesting beach"], ["beach", "coastal", "debris", "plastic", "nets", "marine litter"], ["marine_debris", "fishing_gear", "plastic_waste"], "baseline_survey"),
            "ast_watamu_img_02": ("Close-up of monofilament line and nylon net ropes half-buried in sandy beach.", ["Dangerous monofilament line hazard for nesting sea turtles"], ["beach", "nets", "fishing nets", "marine litter"], ["fishing_gear"], "baseline_survey"),
            "ast_watamu_img_03": ("Washed-up plastic flip-flops and rigid footwear fragments along tidal driftline.", ["High concentration of synthetic foam footwear litter"], ["beach", "debris", "plastic", "marine litter"], ["marine_debris"], "baseline_survey"),
            "ast_watamu_img_04": ("Plastic beverage containers and aerosol cans tossed above the spring tide line.", ["Weathered plastic packaging along high beach ridge"], ["beach", "plastic", "debris"], ["plastic_waste"], "baseline_survey"),

            "ast_watamu_img_05": ("Community volunteers and marine park rangers conducting coordinated beach sweep.", ["Ranger-led volunteer grid sweep collecting marine litter"], ["beach", "volunteers", "cleanup", "coastal"], ["cleanup_activity", "human_presence"], "volunteer_cleanup"),
            "ast_watamu_img_06": ("Volunteers packing washed-up marine plastics into recyclable collection sacks.", ["Volunteers bagging maritime flotsam and plastic drift"], ["beach", "volunteers", "cleanup", "plastic"], ["cleanup_activity"], "volunteer_cleanup"),
            "ast_watamu_img_07": ("Marine park warden supervising extraction of deeply embedded ghost net.", ["Park warden verifying ghost net removal from coral rag fringe"], ["beach", "volunteers", "coastal"], ["human_presence"], "field_lead"),
            "ast_watamu_img_08": ("Excavating heavy polypropylene ghost net with hand winches and cutting shears.", ["Large 30-meter ghost net bundle successfully dislodged"], ["nets", "cleanup", "beach", "debris"], ["fishing_gear", "cleanup_activity"], "volunteer_cleanup"),

            "ast_watamu_after": ("Post-cleanup audit of Watamu beach driftline showing pristine coral sand ready for sea turtle nesting.", ["Pristine sand surface free of ghost nets, ropes, and plastic fragments"], ["beach", "coastal", "water", "cleanup", "post-cleanup"], ["post_cleanup_clearance", "marine_habitat"], "verification_audit"),
            "ast_watamu_img_10": ("Ranger beach patrol surveying clean driftline for sea turtle tracks.", ["Clean sandy beach verified suitable for nocturnal nesting crawls"], ["beach", "coastal", "monitoring", "post-cleanup"], ["post_cleanup_clearance"], "verification_audit"),
            "ast_watamu_img_11": ("Community team celebrating successful marine park shoreline restoration.", ["Volunteer group assembled on clean beach post-campaign"], ["beach", "volunteers", "community", "post-cleanup"], ["human_presence"], "none"),

            # Videos
            "ast_mombasa_video": ("Documentary video walkthrough showing community volunteer team actively recovering marine debris from Nyali Creek mangrove root zone.", ["Volunteer team actively clearing and bagging tidal flotsam from prop roots"], ["video", "coastal", "mangroves", "cleanup", "volunteers", "plastic", "debris"], ["cleanup_activity", "human_activity", "marine_debris"], "volunteer_cleanup"),
            "ast_sabaki_action_video": ("Action footage of Sabaki Riverbank cleanup crew extracting tangled drift nets and loading recovered plastics.", ["Riverbank extraction crew dislodging embedded nets and hauling bags"], ["video", "riverbank", "cleanup", "nets", "plastic", "volunteers"], ["cleanup_activity", "fishing_gear", "plastic_waste"], "volunteer_cleanup"),
            "ast_watamu_turtle_video": ("Underwater footage confirming clean reef channel and sea turtle swimming freely in cleared nearshore waters.", ["Green sea turtle navigating clean nearshore channel free of ghost nets"], ["video", "wildlife", "marine", "turtle", "water", "coastal"], ["marine_wildlife", "water_turbidity"], "verification_audit"),
        }

        for aid, (desc, obs, tags, signals, act) in intel_lookup.items():
            mi_id = f"mi_{aid}"
            db.execute("""INSERT OR REPLACE INTO media_intelligence(
                id, asset_id, frame_id, status, description, observations, tags_json, signals_json,
                activity, warnings_json, uncertainty, evidence_json, model_provider, model_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mi_id, aid, None, "analyzed", desc,
                json.dumps(obs), json.dumps(tags), json.dumps(signals),
                act, json.dumps([]), "High confidence demonstration analysis",
                json.dumps({"synthetic_demo": True, "source": "DEMO DATASET · Coastal Monitoring Record"}),
                "gemini", "gemini-3.8-flash", now, now
            ))

        # -------------------------------------------------------------
        # 8. Field Debris Measurements (320 kg at Nyali, 145 kg at Sabaki)
        # -------------------------------------------------------------
        measurements = [
            (
                "msr_mombasa_weigh", DEMO_SITE_ID, "v_mombasa_action",
                "Recovered marine debris & plastic waste", 320.0, "kg",
                "Digital hanging crane scale at Nyali Creek staging station",
                "Farhan (Field Lead)", "2026-08-28T14:30:00Z"
            ),
            (
                "msr_sabaki_weigh", "demo-riverbank", "v_sabaki_action",
                "Riverine plastic & entangled nylon nets", 145.0, "kg",
                "Weighbridge certified batch slip #402",
                "Field Coordinator Roy", "2026-09-05T16:00:00Z"
            ),
        ]
        for m in measurements:
            db.execute("""INSERT OR REPLACE INTO measurements(id, site_id, visit_id, label, quantity, unit, source, recorded_by, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", m)

        # -------------------------------------------------------------
        # 9. Observations / Comparative Pairs
        # - 2 Approved Findings (Nyali Creek & Sabaki Riverbank)
        # - 2 Pending Proposals (Tudor Creek & Watamu Beach) for reviewer demos
        # -------------------------------------------------------------
        observations = [
            # 1. Nyali Creek (Approved - Verified Finding for Public Story)
            {
                "id": "obs_mombasa_creek",
                "site_id": DEMO_SITE_ID,
                "before_asset_id": "ast_mombasa_before",
                "after_asset_id": "ast_mombasa_after",
                "ai_draft": "AI Finding: Fixed-point visual comparison confirms substantial clearance of macro-debris and plastic flotsam from the 45m mangrove fringe, restoring tidal water flow.",
                "working_text": "DEMO DATASET · Verified demonstration finding: 45-meter intertidal mangrove fringe cleared of macro-plastic bottles, single-use bags, and entangled synthetic lines with documented re-aeration of pneumatophores.",
                "approved_text": "DEMO DATASET · Verified demonstration finding: 45-meter intertidal mangrove fringe cleared of macro-plastic bottles, single-use bags, and entangled synthetic lines with documented re-aeration of pneumatophores.",
                "review_status": "approved",
                "reliability_reason": "DEMO DATASET · Auditor confirmed: fixed-point coordinates match within 1.2m tolerance with identical tide-height benchmarks.",
                "reviewed_by": "Farhan (Field Lead)",
                "reviewed_at": "2026-09-19T10:00:00Z",
                "created_at": now,
                "updated_at": now,
                "version": 2,
            },
            # 2. Sabaki Riverbank (Approved - Verified Finding)
            {
                "id": "obs_sabaki_riverbank",
                "site_id": "demo-riverbank",
                "before_asset_id": "ast_sabaki_before",
                "after_asset_id": "ast_sabaki_after",
                "ai_draft": "AI Finding: Riparian embankment cleared of agricultural mulch film and drift netting along high-water mark.",
                "working_text": "DEMO DATASET · Verified demonstration finding: 80-meter riparian corridor cleared of entangled nylon drift nets and floating plastic sacks; unobstructed river flow restored.",
                "approved_text": "DEMO DATASET · Verified demonstration finding: 80-meter riparian corridor cleared of entangled nylon drift nets and floating plastic sacks; unobstructed river flow restored.",
                "review_status": "approved",
                "reliability_reason": "DEMO DATASET · Auditor verified photographic coordinates and haul slip documentation.",
                "reviewed_by": "Auditor Roy",
                "reviewed_at": "2026-09-23T11:00:00Z",
                "created_at": now,
                "updated_at": now,
                "version": 2,
            },
            # 3. Tudor Creek (Approved - Verified Finding)
            {
                "id": "obs_tudor_estuary",
                "site_id": "site_tudor_creek",
                "before_asset_id": "ast_tudor_before",
                "after_asset_id": "ast_tudor_after",
                "ai_draft": "AI Finding: Estuary mudflat demonstrates marked reduction in ghost fishing net density and surface plastic accumulation.",
                "working_text": "DEMO DATASET · Verified demonstration finding: Estuary mudflat demonstrates marked reduction in ghost fishing net density and surface plastic accumulation post-clearing campaign.",
                "approved_text": "DEMO DATASET · Verified demonstration finding: Estuary mudflat demonstrates marked reduction in ghost fishing net density and surface plastic accumulation post-clearing campaign.",
                "review_status": "approved",
                "reliability_reason": "DEMO DATASET · Auditor confirmed: fixed-point coordinates match within 1.0m tolerance and tide benchmark aligned.",
                "reviewed_by": "Dr. Aisha (Mangrove Ecologist)",
                "reviewed_at": "2026-09-21T09:30:00Z",
                "created_at": now,
                "updated_at": now,
                "version": 2,
            },
            # 4. Watamu Beach (Approved - Verified Finding)
            {
                "id": "obs_watamu_driftline",
                "site_id": "site_watamu_beach",
                "before_asset_id": "ast_watamu_before",
                "after_asset_id": "ast_watamu_after",
                "ai_draft": "AI Finding: Tidal driftline shows successful extraction of stranded monofilament trawl nets and plastic bottles from sea turtle nesting zone.",
                "working_text": "DEMO DATASET · Verified demonstration finding: Tidal driftline shows extraction of commercial trawl net fragments and beverage bottles across 120m nesting beach.",
                "approved_text": "DEMO DATASET · Verified demonstration finding: Tidal driftline shows extraction of commercial trawl net fragments and beverage bottles across 120m nesting beach.",
                "review_status": "approved",
                "reliability_reason": "DEMO DATASET · Auditor confirmed: 120-meter driftline inspection and haul manifest verified.",
                "reviewed_by": "Marcus (Marine Auditor)",
                "reviewed_at": "2026-09-24T16:00:00Z",
                "created_at": now,
                "updated_at": now,
                "version": 2,
            },
        ]

        for obs in observations:
            db.execute("""INSERT OR REPLACE INTO observations(
                id, site_id, before_asset_id, after_asset_id, ai_draft, working_text,
                approved_text, review_status, reliability_reason, reviewed_by,
                reviewed_at, created_at, updated_at, version
            ) VALUES (:id, :site_id, :before_asset_id, :after_asset_id, :ai_draft, :working_text,
                      :approved_text, :review_status, :reliability_reason, :reviewed_by,
                      :reviewed_at, :created_at, :updated_at, :version)""", obs)

        # -------------------------------------------------------------
        # 10. Published Public Impact Story & Timeline Events
        # Token: pst_demo_mombasa_coastal_2026 -> Returns HTTP 200
        # Contains ONLY approved/verified evidence
        # -------------------------------------------------------------
        story_data = {
            "id": DEMO_STORY_ID,
            "project_id": DEMO_PROJECT_ID,
            "title": "Nyali Creek Mangrove Restoration · illustrative demo",
            "description": "SYNTHETIC DEMO DATASET · illustrative demo · Verified community-led mangrove fringe cleanup, tidal flotsam recovery, and marine litter audit along the Nyali Creek coastline.",
            "status": "published",
            "summary_narrative": "DEMO DATASET · During August and September 2026, field volunteers and coastal conservation teams conducted targeted cleanup campaigns across the Nyali Creek mangrove fringe. Over 320 kg of entangled marine plastic, synthetic rope, and discarded debris were extracted, opening critical pneumatophore aeration zones and restoring unhindered tidal water circulation.",
            "uncertainty_note": "DEMO DATASET · illustrative demo scenario. In real field deployments, continuous multi-season visual monitoring is required to confirm vegetative recovery.",
            "share_token": DEMO_SHARE_TOKEN,
            "metadata_json": json.dumps({
                "synthetic_demo": True,
                "demonstration_scenario": True,
                "date_range": {"start_date": "2026-08-15", "end_date": "2026-09-19"},
                "metrics": {
                    "approved_findings_count": 1,
                    "pending_findings_count": 1,
                    "measurement_count": 1,
                    "site_count": 2,
                }
            }),
            "created_at": now,
            "updated_at": now,
        }
        db.execute("""INSERT OR REPLACE INTO impact_stories(
            id, project_id, title, description, status, summary_narrative,
            uncertainty_note, share_token, metadata_json, created_at, updated_at
        ) VALUES (:id, :project_id, :title, :description, :status, :summary_narrative,
                  :uncertainty_note, :share_token, :metadata_json, :created_at, :updated_at)""", story_data)

        # Timeline events for the public story (all verified & approved)
        events = [
            (
                "evt_mombasa_1_baseline", DEMO_STORY_ID, 1, "2026-08-15", "before",
                "Baseline Ecological Survey & Debris Mapping",
                "Initial environmental baseline survey documenting extensive plastic debris, discarded bottles, and entangled ropes throughout the 45m mangrove fringe.",
                DEMO_SITE_ID, "Nyali Creek Mangrove Fringe · DEMO DATASET",
                json.dumps(["ast_mombasa_before"]),
                f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_baseline_debris.jpg",
                f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/setowa/creek_baseline_debris.jpg",
                "image", None, None, None, "mi_ast_mombasa_before", "approved",
                json.dumps(["debris", "plastic", "mangroves", "marine litter"]),
                json.dumps(["marine_debris", "plastic_waste", "mangrove_roots"]),
                json.dumps([]), "High confidence visual baseline",
                json.dumps({"synthetic_demo": True, "source_provenance": "DEMO DATASET · Coastal Monitoring Sensor"}),
                now, now
            ),
            (
                "evt_mombasa_2_action", DEMO_STORY_ID, 2, "2026-08-28", "action",
                "Community Volunteer Cleanup Campaign",
                "Coordinated community cleanup team clearing accumulated marine litter, extracting trapped bottles from mangrove prop roots, and packing materials into reusable burlap sacks.",
                DEMO_SITE_ID, "Nyali Creek Mangrove Fringe · DEMO DATASET",
                json.dumps(["ast_mombasa_video"]),
                f"https://res.cloudinary.com/{cloud}/video/upload/f_auto,q_auto/v1/setowa/t014_live_walkthrough.mp4",
                f"https://res.cloudinary.com/{cloud}/video/upload/c_fill,h_225,w_400,so_0/setowa/t014_live_walkthrough.jpg",
                "video", None, None, None, "mi_ast_mombasa_video", "approved",
                json.dumps(["cleanup", "volunteers", "mangroves", "plastic"]),
                json.dumps(["cleanup_activity", "human_presence"]),
                json.dumps([]), "Documented field action video",
                json.dumps({"synthetic_demo": True, "source_provenance": "DEMO DATASET · Volunteer Video Record"}),
                now, now
            ),
            (
                "evt_mombasa_3_measurement", DEMO_STORY_ID, 3, "2026-08-28", "measurement",
                "Field Debris Weigh-In: 320 kg Recovered Marine Litter",
                "Digital hanging scale verified batch weigh-in of 320 kg marine litter and tangled fishing nets staged at high-tide roadhead point.",
                DEMO_SITE_ID, "Nyali Creek Mangrove Fringe · DEMO DATASET",
                json.dumps(["ast_nyali_img_10"]),
                f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/samples/ecommerce/accessories-bag.jpg",
                f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/samples/ecommerce/accessories-bag.jpg",
                "image", None, None, "msr_mombasa_weigh", "mi_ast_nyali_img_10", "approved",
                json.dumps(["weighing", "measurement", "cleanup", "bags"]),
                json.dumps(["measurement_staging", "debris_collection"]),
                json.dumps([]), "Digital scale calibration verified",
                json.dumps({"synthetic_demo": True, "source_provenance": "DEMO DATASET · Certified Scale Manifest"}),
                now, now
            ),
            (
                "evt_mombasa_4_after", DEMO_STORY_ID, 4, "2026-09-18", "after",
                "Post-Intervention Verification Survey",
                "High-resolution verification photograph from identical fixed-point monitoring coordinates confirming complete clearance of plastic debris along the waterline.",
                DEMO_SITE_ID, "Nyali Creek Mangrove Fringe · DEMO DATASET",
                json.dumps(["ast_mombasa_after"]),
                f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_post_cleanup.jpg",
                f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/setowa/creek_post_cleanup.jpg",
                "image", None, None, None, "mi_ast_mombasa_after", "approved",
                json.dumps(["mangroves", "coastal", "water", "vegetation", "cleanup", "post-cleanup"]),
                json.dumps(["post_cleanup_clearance", "vegetation_cover"]),
                json.dumps([]), "Auditor-confirmed photographic match",
                json.dumps({"synthetic_demo": True, "source_provenance": "DEMO DATASET · Verification Audit Photograph"}),
                now, now
            ),
            (
                "evt_mombasa_5_observation", DEMO_STORY_ID, 5, "2026-09-19", "observation",
                "Auditor Verified Environmental Finding",
                "Field Lead Farhan formally approved the before/after finding confirming 45m mangrove fringe cleared of macro-plastic bottles and restoration of unimpeded tidal flushing.",
                DEMO_SITE_ID, "Nyali Creek Mangrove Fringe · DEMO DATASET",
                json.dumps(["ast_mombasa_before", "ast_mombasa_after"]),
                f"https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/v1/setowa/creek_post_cleanup.jpg",
                f"https://res.cloudinary.com/{cloud}/image/upload/c_thumb,w_300/v1/setowa/creek_post_cleanup.jpg",
                "image", None, "obs_mombasa_creek", None, "mi_ast_mombasa_after", "approved",
                json.dumps(["mangroves", "verified", "cleanup"]),
                json.dumps(["post_cleanup_clearance"]),
                json.dumps([]), "Full auditor verification record",
                json.dumps({"synthetic_demo": True, "source_provenance": "DEMO DATASET · Field Auditor Review"}),
                now, now
            ),
        ]

        for ev in events:
            db.execute("""INSERT OR REPLACE INTO impact_story_events(
                id, story_id, event_order, timestamp_date, event_type, title, description,
                site_id, site_name, asset_ids_json, primary_media_url, thumbnail_url, media_type,
                frame_id, observation_id, measurement_id, intelligence_id, verification_status,
                tags_json, signals_json, warnings_json, uncertainty, evidence_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", ev)

    # Legacy riverbank compatibility (seed_local_demo)
    try:
        from scripts.seed_local_demo import seed as seed_legacy
    except ImportError:
        from seed_local_demo import seed as seed_legacy
    seed_legacy()

    with store.connection() as db:
        # Ensure legacy assets have permission_status='granted'
        db.execute("UPDATE assets SET permission_status='granted'")

    total_assets = len(asset_defs)
    total_frames = len(frames)

    print(f"[OK] SETOWA Demo Dataset seeded successfully:")
    print(f"  Project: {DEMO_PROJECT_ID} (illustrative Mombasa coastal scenario)")
    print(f"  Sites: 4 (Nyali Creek, Tudor Creek, Sabaki Riverbank, Watamu Beach)")
    print(f"  Visits: {len(visits)} chronological visits across Aug-Sep 2026")
    print(f"  Assets: {total_assets} ({total_assets - 3} Images, 3 Full Videos)")
    print(f"  Video Frames: {total_frames} Cloudinary offset derivations with frame analyses")
    print(f"  Intelligence Records: {len(intel_lookup)} structured records")
    print(f"  Measurements: {len(measurements)} verified debris weigh-ins")
    print(f"  Observations: {len(observations)} (2 Approved, 2 Pending Proposals)")
    print(f"  Impact Story: {DEMO_STORY_ID} (Published, Share Token: {DEMO_SHARE_TOKEN})")

    return {
        "project_id": DEMO_PROJECT_ID,
        "site_id": DEMO_SITE_ID,
        "story_id": DEMO_STORY_ID,
        "share_token": DEMO_SHARE_TOKEN,
        "asset_count": total_assets,
        "frame_count": total_frames,
    }


if __name__ == "__main__":
    seed_demo_dataset()
