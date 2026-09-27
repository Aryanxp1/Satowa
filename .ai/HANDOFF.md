# HANDOFF.md — Setowa / LEX
# Updated: 2026-09-26 by AGY

## Current Handoff: Cline / AGY → User (Aryan)

## What Was Completed This Session

**T001:** `.ai/` control plane initialized.  
**T003 (Test Baseline):** Complete read-only audit of all test files, service files, routes, and configuration. Full test suite executed (45 passed, 1 failed, 2 errors).  
**T002 (Schema Alignment):**
1. Added `permission_status TEXT NOT NULL DEFAULT 'granted'` and nullable `thumbnail_url TEXT` to `assets` table.
2. Implemented non-destructive migration guards using column inspection (`PRAGMA table_info`) and `ALTER TABLE`.
3. Persisted `thumbnail_url` and validated `permission_status` on image upload.
4. Mapped unreliable AI comparisons to `review_status = 'pending'`, preserving `reliability_reason` and preventing text fabrication or auto-approval.
5. Safely migrated legacy `unreliable` review status rows to `pending`.
6. Updated `observations.review_status` `CHECK` constraint to `('pending','approved','rejected')`.
7. Exposed `AssetResponse` and `PermissionStatus` in Pydantic API schemas.
8. Added regression and unit tests: 48 tests pass. Zero regressions.  

**T004 (Defuse Mock Accuracy Claim):**
1. Identified all instances of `99.4` and ungrounded accuracy claims across codebase.
2. Updated `backend/app/routes/analyze.py`: defused `AI Accuracy` metric by removing `99.4%` and `10x`, labeling values as `Unbenchmarked (Demo)` and `Assisted Review / Human In The Loop`.
3. Updated `backend/app/services/ai_engine.py`: updated mock prompt analysis response to explicitly state demo mode and human verification requirement; replaced `0.994` with `0.95`.
4. Updated `backend/tests/test_api.py`: verified no `99.4` percentage remains in metrics and accuracy is explicitly identified as demo/synthetic.
5. All 48 tests pass; zero regressions.

**T005 (Evidence / Pair Validation Hardening):**
1. Hardened authoritative server-side `validate_pair` in `backend/app/routes/evidence.py`:
   - Same cleanup site validation across before and after visits.
   - Strict chronological visit ordering (`before_visit['visited_on'] < after_visit['visited_on']`).
   - Persistent asset existence verification in `assets` table (404 for missing before or after asset).
   - Relational consistency check between assets, visits, and sites.
   - Forgery and tamper protection against manually changed asset or site IDs.
   - Media validity checks (`jpeg`, `jpg`, `png`, `webp`, positive dimensions, secure URL).
   - Permission status validation (only `'granted'` permission permitted for pairs and reports).
   - Rejection of cross-site observation modification (`422 Cannot change the site of an observation`).
   - Filtered `report_rows` to guarantee only assets with `permission_status='granted'` appear in approved reports.
2. Extended `PairInput` and `EditInput` schemas to allow optional client-specified `site_id`, `before_visit_id`, and `after_visit_id`.
3. Added 13 matrix tests in `backend/tests/test_evidence.py` covering tests A through M (`test_pair_validation_matrix_*`).
4. Verified 61 passed tests; zero regressions.

**T006 (Structured AI Comparison / Uncertainty):**
1. Structured AI Result Contract:
   - Implemented 4-state `ComparisonStatus` enum: `changed`, `unchanged`, `uncertain`, `insufficient_evidence`.
   - Bounded model confidence `[0.0, 1.0]` (representing model certainty, explicitly not factual accuracy).
   - Implemented controlled vocabulary `UncertaintyReason` enum with machine/human-readable reasons.
   - Structured `VisualChange` list (`type`, `description`, `evidence`).
   - Summary and evidence notes for technical inspection.
2. Safety & Trust Model:
   - Rejected unverified quantitative claims (weights, counts, percentages, bags) via `QUANTITATIVE_CLAIM_PATTERN` (`unverified_quantitative_claim`).
   - Resilient error handling: malformed JSON, provider failures, network timeouts, invalid enum values, and out-of-range confidence scores safely fail to `uncertain`/`provider_error`.
   - Visual observations are explicitly separated from factual measurements.
3. Review Workflow Integrity:
   - AI results remain strictly proposals: created observations are ALWAYS `review_status = 'pending'` and `approved_text = None`.
   - Unapproved observations are strictly excluded from downstream reports until explicit human review approval.
4. Backward Compatibility:
   - Maintained legacy `reliable`, `observation`, and `reason` properties via `@model_validator(mode='before')`.
5. Testing:
   - Added full 15-item Test Matrix (A through O): 34 new tests in `test_image_comparison.py`, 1 new test in `test_evidence.py`.
   - All 96 tests pass; zero regressions.

**T007 (Real Cloudinary -> Gemini End-to-End Integration):**
1. Real Cloudinary -> Gemini Integration Pipeline:
   - Ingestion: verified upload of images to Cloudinary, persisting `secure_url`, `public_id`, `width`, `height`, `format`, `permission_status`, and `thumbnail_url`.
   - Local Binary Safety: images are never stored locally; only trusted Cloudinary references and metadata are stored.
   - Multimodal Gemini Client: sends inline base64 streams retrieved directly from trusted Cloudinary paths; strips markdown code fences before JSON decoding; validates output against Pydantic model.
   - Review Workflow Integrity: AI proposals default strictly to `review_status='pending'` and `approved_text=None`.
   - Approval Invalidation: editing or mutating evidence immediately invalidates approvals back to `pending`.
   - Report Generation: traceable observations with before/after URLs, dates, and reviewer attribution. Unapproved or revoked permission assets are excluded.
2. Error Matrix (A through J) with Isolated Deterministic Tests:
   - A: Missing Cloudinary credentials -> 503 error, no fake asset stored.
   - B: Cloudinary upload failure -> 502 error, credentials redacted, no partial state.
   - C: Invalid Cloudinary response -> 502 error.
   - D: Missing Gemini credentials -> safe fallback, pending review status preserved.
   - E: Gemini timeout / provider failure -> safe uncertain result, observation stays pending.
   - F: Malformed Gemini response -> safe fallback without crash.
   - G: Invalid structured Gemini response -> safe fallback to uncertain.
   - H: Valid Gemini response -> draft proposed, strictly pending human review, excluded from report.
   - I: Uncertain Gemini response -> preserves uncertainty_reason, pending for review.
   - J: Insufficient evidence response -> preserves reason, pending for review.
3. Live Integration Suite:
   - `test_live_cloudinary_and_gemini_pipeline` executes real API calls ONLY when `RUN_LIVE_INTEGRATION=1` is set AND real credentials are configured in `.env`/environment.
   - Skips cleanly when flag is not set or when credentials are dummy/placeholder values.
   - Added read-only safe connectivity check script `backend/scripts/check_gemini.py` (matching `backend/scripts/check_cloudinary.py`).
4. Testing & Verification:
   - 107 passed tests (+11 new tests in `test_integration_pipeline.py`).
   - 1 cleanly skipped test (live test without flag).
   - Zero regressions.

**T008 (Judge-Facing Review Experience):**
1. UI Components & Visual Comparison:
   - Added provenance cards displaying Site, Visit dates/labels, Source asset IDs, Permission status (`granted`, `pending_verification`, `revoked`), and Cloudinary verified badge.
   - Dual display modes: side-by-side comparison and interactive split-reveal comparison slider with toggle button.
   - High-resolution modal lightbox dialog for detailed visual inspection of evidence assets.
   - Real-time client-side pair validation warning (chronology, permissions, distinct assets).
2. Structured AI Proposal Presentation:
   - Status badge (`Changed`, `Unchanged`, `Uncertain`, `Insufficient Evidence`).
   - Concise AI observation summary and structured visual change list (`type`, `description`, `evidence`).
   - Bounded Model Confidence gauge labeled `MODEL CONFIDENCE` with certainty disclaimer.
   - Supporting evidence visual notes.
3. Trust Invariant Distinction:
   - Clear visual distinction: `AI PROPOSAL` (amber border, `⚠ AI suggestion — Human verification required` banner) vs `HUMAN VERIFIED RECORD` (emerald border, `✓ HUMAN VERIFIED RECORD` banner, reviewer identity, approval timestamp).
   - Approval Invalidation: editing an approved observation immediately resets review status to `pending` and purges it from official reports.
4. Uncertainty UX:
   - Prominent callouts when AI cannot determine outcome with sufficient confidence or has insufficient evidence.
   - Controlled human-friendly reasons displayed (Camera angle mismatch, Lighting difference, Insufficient visual overlap, etc.).
5. Review Actions & Live Report Preview:
   - Wired `[ Approve ]`, `[ Save Draft / Edit ]`, and `[ Reject ]` review actions.
   - In-page live report preview: strictly excludes unapproved AI suggestions; includes Markdown export and raw JSON toggle.
6. Testing:
   - Added `backend/tests/test_demo_ui.py` covering static delivery and all 9 critical behaviors (11 tests).
   - Total test suite now passes 118 tests (+11 new tests, zero regressions).

**T009 (Demo Hardening & End-to-End QA):**
1. Fresh-Start Hardening:
   - `run_local.sh`: Portable virtualenv detection (`.venv` or `venv`, Windows Git Bash vs Linux/macOS `bin/activate` vs `Scripts/activate`).
   - `setup_local_demo.py`: Tolerant chmod protection (`try...except OSError`) for seamless database and session initialization on all filesystems.
2. Demo UX & Loading States (`backend/app/demo/`):
   - `app.js`: Added loading states (`"Comparing with Gemini..."`, `"Uploading to Cloudinary..."`, `"Approving..."`, `"Saving..."`, `"Rejecting..."`, `"Generating report..."`) and disabled button states during in-flight network requests to prevent duplicate submissions.
   - Comprehensive error sanitization for HTTP 400, 403, 404, 409, 413, 415, 422, 502, 503, network disconnects, stripping raw Python tracebacks.
   - Replaced platform-specific UI copy with OS-neutral copy in `index.html`.
3. Secret & Security Audit:
   - Zero `.env`, credentials, or local sqlite3 databases committed to git.
   - Validated that logs, API responses, and client telemetry never expose API keys or secrets.
   - Verified zero ungrounded accuracy or performance claims across the codebase.
4. Comprehensive End-to-End Test Suite:
   - Created `backend/tests/test_e2e_journey.py` (9 tests) testing:
     - Fresh-start clean database migration and table integrity
     - Full happy path: Site -> Visits -> Assets -> Pair -> Gemini -> AI Proposal -> Human Review -> Approval -> Certified Report
     - Approval invalidation lifecycle (re-editing approved observation resets to pending)
     - Chronological visit order rejection (HTTP 400)
     - Revoked permission rejection (HTTP 400)
     - Cross-site evidence pairing rejection (HTTP 400)
     - Version conflict / stale overwrite prevention (HTTP 409)
     - Uncertainty and insufficient evidence preservation
     - Static bundle and script syntax contract
5. Demo Runbook (`docs/DEMO_RUNBOOK.md`):
   - Clear prerequisites, environment variable reference (names only, no values), backend/frontend startup instructions, Cloudinary/Gemini setup, exact 8-step demo sequence, failure recovery guide, and judge demo safety guidelines.
6. Test Baseline:
   - 129 collected, 127 passed, 1 skipped (live test), 1 known pre-existing failure (Windows chmod), 2 deprecation errors. Zero regressions.

**T010 (Setowa Migration + Architecture Design):**
- Verified architectural transition from single-purpose LEX to the Setowa platform model (`SETOWA_MASTER_PLAN.md`).
- Domain partitioning defined: Media Domain, Skill Domain, Workflow Domain, Intelligence Domain, Verification Domain, Impact Domain, CLI Domain.
- Roadmap confirmed: T011 through T018.

**T011 (Media Pipeline + Bulk Ingestion):**
1. Database Schema & Assets Table Migration (`backend/app/services/evidence_store.py`):
   - Non-destructive migration adding `site_id`, `media_type`, `processing_status`, `original_filename`, `duration`, `preview_url`, `created_at`, and `metadata_json` to `assets` table.
   - Added persistence helper methods: `ensure_ingestion_visit(db, site_id, visit_date)`, `save_asset(db, asset_data)`, `get_media_item(db, asset_id)`, `list_media(db, project_id, media_type, permission_status, limit, offset)`.
2. Cloudinary Programmable Media Delivery (`backend/app/services/media.py`):
   - Optimized delivery (`f_auto,q_auto`), responsive preview transformations (`w_1200,h_900,c_limit`), square thumbnails (`w_640,h_480`), and video poster frames at offset 0 (`so_0`).
   - Magic bytes container validation (`validate_video_header`) for MP4, WebM, and MOV with 50 MiB limit.
   - Video ingestion (`ingest_video`) with Cloudinary `resource_type="video"`, duration extraction, and derived poster frames.
   - Unified `ingest_media` dispatcher.
3. Media API Endpoints (`backend/app/routes/media.py`):
   - `POST /api/v1/media/bulk`: Multi-file upload with safe per-file error isolation preventing entire-batch rollback on individual file failure.
   - `POST /api/v1/media/videos`: Direct video upload with poster frame generation.
   - `GET /api/v1/media`: Filtered media library retrieval (by project, media type, permission status, with pagination).
   - `GET /api/v1/media/{asset_id}`: Single media asset inspection.
4. Setowa Workspace Media Library UI (`backend/app/demo/`):
   - Added Media Library tab (`#tab-media-library`) with media type filter, permission filter, and text search.
   - Built bulk ingestion accordion form (`#bulk-upload-form`) with real-time feedback and per-file result summaries.
   - Rendered media cards with poster frames, duration tags, Cloudinary tags, dimensions, quick CDN URL copying, and inline video playback via lightbox modal.
5. Standalone Ingestion CLI (`backend/scripts/ingest_collection.py`):
   - Built CLI supporting directory ingestion with `--dir`, `--project`, `--source`, `--date`, `--permission`, `--json`.
6. Testing & Quality Assurance:
   - Fixed pytest byte serialization hanging in `backend/tests/test_media.py` by adding explicit test IDs.
   - Added `backend/tests/test_bulk_media.py` (5 tests) verifying video upload, container header validation, mixed image/video bulk upload, partial failure resilience, and media library filtering.
   - Added ADR D012 in `DECISIONS.md`.
   - Total test suite: 133 tests passed, 1 skipped, 1 known pre-existing Windows chmod failure, 0 regressions.

## Milestone T012 — SETOWA Skill Runtime Summary (COMPLETED)

1. Core Architecture & Models (`backend/app/skills/`):
   - `SkillManifest`, `SkillInputDefinition`, `SkillOutputDefinition`, `SkillExecutionStatus` (`success`, `failed`, `invalid_input`, `unavailable`), `SkillExecutionRequest`, `SkillExecutionResult` in `models.py`.
   - Semantic versioning parsing, namespace:action permission syntax checking, and strict type verification (`string`, `integer`, `float`, `boolean`, `object`, `array`, `image`, `video`, `asset_id`) in `validation.py`.
   - `BaseSkill` abstract base class with `async def execute(inputs, context)` in `loader.py`.
   - Multi-version `SkillRegistry` with exact (`name@version`) and latest semver resolution, duplicate prevention without `overwrite=True`, and discovery/listing with `kind` filtering in `registry.py`.
   - `SkillRuntime` orchestrating permission grants, input type checking, latency timing, safe error handling, and structured evidence/warning outputs in `runtime.py`.
2. Built-in Skills:
   - `media-metadata@1.0.0` (deterministic): Inspects Cloudinary delivery URLs (`secure_url`, `thumbnail_url`, `preview_url`), dimensions, format, video duration, and SQLite asset lookups without artificial AI scoring.
   - `evidence-comparison@1.0.0` (AI-backed): Reuses existing Gemini `image_comparison` service for structured before/after comparison with 4-state output and bounded confidence. Safely marks status as `unavailable` when `GEMINI_API_KEY` is missing.
3. REST API Endpoints (`backend/app/routes/skills.py`):
   - `GET /api/v1/skills`: Lists all registered skills with optional `kind` filter (`deterministic` vs `ai`).
   - `GET /api/v1/skills/{skill_name}`: Retrieves manifest details by name or name@version.
   - `POST /api/v1/skills/{skill_name}/execute`: Executes skill with typed inputs and optional execution context.
4. Setowa Workspace UI (`backend/app/demo/`):
   - Added Skills tab (`#tab-skills`) with interactive card grid, version badges, permission tags, and model provider indicator.
   - Built live Skill Tester panel (`#skill-tester-panel`) with dynamic JSON input editor and formatted execution output display.
5. Testing & Quality Assurance:
   - Created `backend/tests/test_skills.py` with 15 comprehensive tests covering all required edge cases (valid/invalid manifests, duplicate registration, version resolution, invalid inputs, permissions, execution success/failure/unavailability, API listing, API execution).
   - Total test suite: 148 tests passed (+15 new tests), 1 skipped, 1 known pre-existing Windows chmod failure, 0 regressions.

## Milestone T013 — SETOWA Workflow Engine + Builder Summary (COMPLETED)

1. Core Architecture & Models (`backend/app/workflows/`):
   - `WorkflowDefinition`, `WorkflowNode`, `WorkflowEdge`, `WorkflowInputDefinition`, `WorkflowSummary` in `models.py`.
   - `DAGGraph` in `dag.py`: Kahn's algorithm and DFS cycle detection for cycle and self-loop rejection, dependency analysis, and deterministic topological ordering.
   - Comprehensive validation in `validation.py`: node uniqueness, skill registry resolution, semver matching, edge port compatibility, and reference binding (`$input.key`, `$node.node_id.output_key`).
   - `WorkflowEngine` in `engine.py`: executes nodes strictly via T012 `SkillRuntime`, resolves dynamic state propagation, marks downstream nodes as `skipped` on dependency failure, and produces structured execution reports with latency metrics.
   - SQLite persistence in `store.py`: `workflows` and `workflow_executions` tables, with built-in seeding for `wf_evidence_compare` (Before-After Evidence Comparison multi-skill workflow).
2. REST API Endpoints (`backend/app/routes/workflows.py`):
   - `GET /api/v1/workflows`: List workflow summaries.
   - `POST /api/v1/workflows`: Create workflow definition.
   - `GET /api/v1/workflows/{id}`: Retrieve workflow definition.
   - `PUT /api/v1/workflows/{id}`: Update workflow definition.
   - `DELETE /api/v1/workflows/{id}`: Delete workflow definition.
   - `POST /api/v1/workflows/{id}/validate`: Validate stored workflow DAG.
   - `POST /api/v1/workflows/validate-draft`: Validate draft workflow DAG without saving.
   - `POST /api/v1/workflows/{id}/execute`: Topologically execute workflow with inputs.
   - `GET /api/v1/workflows/{id}/executions`: List workflow run history.
   - `GET /api/v1/workflow-executions/{id}`: Retrieve specific execution run.
3. Visual Workflow Builder UI (`backend/app/demo/`):
   - Added `#tab-workflows` studio with 3-column layout (Skill Palette, interactive DAG Canvas with SVG connections, Node Inspector for `$input`/`$node` mapping, and Step Execution Panel).
   - Toolbar with New, Validate, Save, Run, Clear, and Workflow selector.
   - Full bidirectional wiring to backend `/api/v1/workflows` endpoints.
4. Testing & Quality Assurance:
   - Created `backend/tests/test_workflows.py` with 22 comprehensive tests covering all required test scenarios (valid/invalid schemas, duplicate IDs, missing skills/versions, invalid edges/ports/mappings, self-loops, cycles, topological order, input/output propagation, failure propagation/skipping, persistence, and REST APIs).
   - Total test suite: 170 tests passed (+22 new tests), 1 skipped, 1 known pre-existing Windows chmod failure, 0 regressions.

## Milestone T014 — Field Video Ingestion & Frame Analytics Summary (COMPLETED)

1. Cloudinary Permission & Precheck:
   - Verified MASTER ADMIN authenticated access and video creation/upload capability (`ping: ok`).
   - Re-verified existing T011 video ingestion pipeline (`resource_type="video"`), container header validation, duration persistence, and poster frame generation.
2. Frame Extraction & Transformation (`backend/app/services/video_frames.py`):
   - Offset-based on-the-fly frame derivation using Cloudinary video transformations (`start_offset="so_<ts>"`, `.jpg` format, and `c_fill,h_225,w_400,so_<ts>` thumbnails).
   - Zero local video download or re-encoding required.
   - Deterministic interval, uniform, and custom timestamp sampling with safety bounds (`max_frames <= 60`).
3. Frame Provenance & Persistence (`backend/app/services/evidence_store.py`):
   - `video_frames` table schema and data access helpers (`save_video_frame`, `get_video_frames_by_asset`, `get_video_frame`, `delete_video_frames_by_asset`).
   - Frame model captures unambiguous provenance answering *"Which exact video and timestamp produced this frame?"*: `frame_id`, `asset_id`, `frame_index`, `timestamp_seconds`, `frame_url`, `thumbnail_url`, `source_video_url`, `width`, `height`, `extraction_method`.
4. Built-in Skill: `field-frame-observation@1.0.0` (`backend/app/skills/builtins/field_frame_observation.py`):
   - Structured visual intelligence observation skill consuming frame image via Gemini multimodal API.
   - Outputs: `observations`, `detected_signals`, `status` (`analyzed` | `uncertain` | `insufficient_evidence`), `confidence` (bounded [0.0, 1.0]), and `warnings`.
   - Automatic multi-model fallback (`gemini-flash-latest`, `gemini-3.8-flash`) and safe offline handling when `GEMINI_API_KEY` is not present.
   - Zero fabricated confidence or unsupported claims.
   - Persistence in `frame_analyses` table with aggregated video-level summary and signal deduplication.
5. REST API Endpoints (`backend/app/routes/media.py`):
   - `POST /api/v1/media/{asset_id}/frames/extract`: Extract and persist sampled video frames.
   - `GET /api/v1/media/{asset_id}/frames`: List all extracted frames for video asset.
   - `GET /api/v1/media/{asset_id}/frames/{frame_id}`: Retrieve single extracted frame.
   - `POST /api/v1/media/{asset_id}/frames/analyze`: Analyze selected or all frames via SkillRuntime.
   - `GET /api/v1/media/{asset_id}/frame-analysis`: Retrieve aggregated video frame analysis report.
6. Setowa Workspace UI Extension (`backend/app/demo/`):
   - Media Library card action: `🎬 Frame Analytics` button for video assets.
   - Interactive `#frames-modal` dialog: inline HTML5 video player, sampling strategy selector (interval vs uniform), extraction trigger, batch/single-frame analysis trigger, and aggregated observation summary card.
   - Responsive frame timeline rendering thumbnails, timestamps, signal tags, observations, and confidence pills.
7. Testing & Quality Assurance (`backend/tests/test_video_frames.py`):
   - 19 targeted tests covering video validation, non-video rejection, invalid sampling parameters, frame limit enforcement, deterministic sampling strategies, timestamp edge cases, Cloudinary transformation generation, frame provenance, SQLite persistence, extraction API, listing API, inspection API, analysis API, SkillRuntime execution, Gemini unavailable handling, multi-frame selective analysis, failure behavior, WorkflowEngine compatibility, and invalid asset handling.
   - Full test suite: 189 passed, 1 skipped, 1 known pre-existing Windows chmod baseline, 0 regressions.
8. Live End-to-End Validation:
   - Authenticated Cloudinary video upload: PASS (`setowa/t014_live_walkthrough`, 13.41s, 854x480).
   - Frame derivation and delivery: PASS (HTTP 200, 23,702 bytes, image/jpeg).
   - Live Gemini Vision inference via `SkillRuntime`: PASS (HTTP 200 OK, accurate visual observations, honest `insufficient_evidence` status and `0.1` confidence).

**T015 (Project / Location / Timeline Media Grouping & Spatial-Temporal Queries):**
- Schema: Added `projects` table, `project_id`, `latitude`, `longitude` to `sites`, and `project_id`, `captured_at` to `assets`.
- Query Service: Multi-dimensional asset filtering (`/media/query`), day-bucketed timeline (`/media/timeline`), project summary.
- Testing: 21 targeted tests passed; 210 total tests passed.

**T016 (AI Media Intelligence + Discovery Foundation):**
- Schema: Added `media_intelligence` table and indexes in SQLite.
- Skill: Built-in `media-intelligence@1.0.0` registered in SkillRuntime with controlled tags/signals, grounding, uncertainty, and warning flags.
- Service & APIs: Asset-level and frame-level intelligence analysis, history/audit trail, bounded batch analysis (`<= 20`), and discovery query filters.
- UI: Media Library tags, badges, analysis buttons, and intelligence modal.
- Testing: 20 targeted tests passed; 230 total tests passed, 0 regressions.
- Live Gemini Validation: Real multimodal inference verified with `gemini-flash-latest`.

**T017 (Sustainability Timeline + Impact Story):**
- Domain Model & SQLite Schema: Added `impact_stories` and `impact_story_events` tables with indexes on `project_id`, `story_id`, and `event_type`.
- Chronological Spine: Generated chronological events across site visits, cleanup video action, sampled video frames with timestamp offsets, after photos, recorded measurements, and verified findings.
- Before / After Proof Cards: Comparative proof cards linking before/after Cloudinary URLs, verification status (`approved`, `pending`, `rejected`), reviewer provenance, and uncertainty caveats.
- Grounded Narrative Synthesis: Grounded summary generation via Gemini with strict anti-hallucination rules (zero invented carbon/area/percentage claims), explicit uncertainty flagging, and deterministic offline fallback.
- REST API Endpoints: Added `/api/v1/projects/{project_id}/impact-story`, `/generate`, `/api/v1/impact-stories/{story_id}`, and `/timeline`.
- Setowa Workspace UI: Added `Impact Story` tab button and `#tab-impact` workspace view in `index.html` with Project Dossier header, dynamic metrics, Grounded Synthesis card with status controls, Before/After Cards grid, and interactive Chronological Spine.
- Testing: 23 targeted tests in `tests/test_impact_story.py` passed; 253 total tests passed (+23 new tests, zero regressions).
- Live Gemini Validation: Real multimodal narrative synthesis verified with `GEMINI_API_KEY` (683 characters, strictly grounded, zero secrets leaked).
- Added ADR D019 in `DECISIONS.md`.

**T018 (Public / Shareable Impact Experience):**
- Database Schema & Migration: Added `share_token TEXT UNIQUE` column to `impact_stories` table with unique index `idx_impact_stories_share_token` and non-destructive migration guard.
- Share Token Architecture: Generated 128-bit cryptographically secure URL-safe tokens (`pst_` prefix via `secrets.token_urlsafe(16)`), with support for generation, rotation, and revocation.
- Published Status Gating: Only stories with `status == "published"` are publicly accessible. Draft and in_review stories strictly return 404 without leaking whether unpublished records exist.
- Public-Safe Data Projection (`PublicImpactStory`): Sanitized projection stripping internal DB IDs, reviewer auth tokens, secret environment variables, and private operational data.
- Read-Only Public Presentation:
  - HTML route: `GET /share/{public_token}` returning responsive standalone HTML5 with Setowa design language, Open Graph social share metadata, Cloudinary-powered hero media, before/after comparison split cards, chronological timeline spine with event badges, verified findings callout, explicit uncertainty caveats, and `@media print` export styles.
  - JSON API route: `GET /api/v1/public/impact/{public_token}` returning public-safe projection.
- Internal Workspace Share Controls: Added share bar in `#tab-impact` with "Open Public Story", "Copy Share Link", "Rotate", and "Revoke" buttons, dynamically rendered based on story publication status.
- Testing: 25 targeted tests in `tests/test_public_story.py` passed; 278 total tests passed (+25 new tests, zero regressions).
- Live System Validation: Tested against `proj_default` on live server; verified draft/in_review 404, published 200 HTML & JSON, Cloudinary hero media, timeline events, before/after evidence, zero secrets, zero reviewer tokens.
- Added ADR D020 in `DECISIONS.md`.

## Test Summary Post-T018

| Metric | Value |
|:---|:---|
| **Command** | `.\venv\Scripts\python.exe -m pytest tests/ -q` |
| **Python** | 3.14.6 |
| **pytest** | 9.1.1 |
| **Total Collected** | 280 |
| **Passed** | 278 (+25 new T018 tests, 0 regressions) |
| **Skipped** | 1 (live integration test gated by RUN_LIVE_INTEGRATION=1) |
| **Failed** | 1 (pre-existing Windows chmod test in `test_local_setup.py`) |
| **Warnings** | 2 (httpx/starlette deprecation, non-blocking) |
| **Runtime** | ~50s |

## What Is Ready Next

- T018 is **COMPLETE**.
- Next assigned milestone: **T019 — Hackathon Demo & Production Hardening**.
  - Goal: Final hackathon presentation hardening, end-to-end demo script preparation, system resilience, and polished documentation.

## Open Questions for User

None. T018 is fully implemented, tested, verified live on real project data, and ready for review.








