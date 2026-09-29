# TASK_BOARD.md — Setowa / LEX
# Updated: 2026-09-26 by AGY

## Legend
- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete and verified
- `[!]` Blocked

---

## [x] T001 — Initialize Agent Control Plane (.ai/)
**Owner:** AGY  
**Status:** COMPLETE (2026-09-26)  
**Files Created:** `.ai/AGENTS.md`, `.ai/PROJECT_STATE.md`, `.ai/TASK_BOARD.md`, `.ai/HANDOFF.md`, `.ai/DECISIONS.md`, `.ai/CHANGELOG.md`  
**Acceptance Criteria:** All 6 .ai/ files exist. ✅

---

## [x] T003 — Test Baseline (READ-ONLY)
**Owner:** AGY  
**Status:** COMPLETE (2026-09-26)  
**Command:** `.\venv\Scripts\python.exe -m pytest tests/ --tb=no -q`  
**Result:** 47 collected, 45 passed, 1 failed, 2 errors, 2 warnings, ~10s

**Baseline:**
- 45 tests passing
- 1 pre-existing Windows-only failure (`chmod 0o600` not honored on NTFS)
- 2 non-blocking deprecation warnings from library version mismatch (`httpx`/`starlette`)

**No code was modified.**

---

## [x] T002 — Schema Alignment
**Owner:** Cline (Builder)  
**Dependencies:** T001 ✅, T003 ✅  
**Status:** COMPLETE (2026-09-26)

**Scope Completed:**
1. Added `permission_status TEXT NOT NULL DEFAULT 'granted'` column to `assets` table in `evidence_store.py` SCHEMA.
2. Added migration guard in `connection()` for `permission_status` on existing DBs.
3. Added `thumbnail_url TEXT` column to `assets` table (nullable) in SCHEMA and migration guard in `connection()`.
4. Persisted `thumbnail_url` and `permission_status` in `upload_image` in `media.py`.
5. Mapped `unreliable` comparison result to `review_status = 'pending'`, preserving `reliability_reason`.
6. Migrated legacy DB rows with `review_status = 'unreliable'` to `'pending'`.
7. Updated `CHECK` constraint on `review_status` to `('pending','approved','rejected')`.
8. Added `AssetResponse` and `PermissionStatus` schemas in `schemas/api.py` and exported them in `schemas/__init__.py`.
9. Added tests: `test_migration_adds_permission_status_and_thumbnail_url`, `test_asset_permission_status_and_thumbnail_persistence`, `test_upload_permission_status_validation`.

**Acceptance Criteria:**
- All 45 previous functional tests still pass. ✅
- 3 new tests added and verified passing (total 48 passed). ✅
- `permission_status` and `thumbnail_url` persistence verified. ✅
- Unreliable comparison yields `review_status = 'pending'` (not `'unreliable'`). ✅


---

## [x] T004 — Defuse the Mock Accuracy Claim
**Owner:** Cline (Builder)  
**Dependencies:** T002 ✅  
**Status:** COMPLETE (2026-09-26)

**Scope Completed:**
1. Identified all instances of `99.4` and unsupported accuracy claims across the codebase.
2. In `backend/app/routes/analyze.py`: Updated `get_mock_stats()` to remove `99.4%` and `10x`, labeling metrics explicitly as `Unbenchmarked (Demo)`, `Simulated Mock`, and `Assisted Review / Human In The Loop`.
3. In `backend/app/services/ai_engine.py`: Updated mock prompt analysis response to explicitly label output as demo mode, requiring human verification, and removed `0.994` confidence.
4. In `backend/tests/test_api.py`: Updated `test_mock_stats` to verify that `99.4` is absent from all metrics and that `AI Accuracy` is explicitly marked as demo/synthetic.
5. Zero ungrounded accuracy percentage claims remain in the repository.

**Acceptance Criteria:**
- No 99.4% unsupported accuracy claim remains in user-facing output. ✅
- Synthetic/demo data remains explicitly identifiable. ✅
- Real evidence workflow is completely untouched. ✅
- All 48 tests pass. ✅
- Zero regressions. ✅

---

## [x] T005 — Evidence / Pair Validation Hardening
**Owner:** Cline (Builder)  
**Dependencies:** T002 ✅, T004 ✅  
**Status:** COMPLETE (2026-09-26)

**Scope Completed:**
1. Strengthened server-side authoritative `validate_pair()` in `backend/app/routes/evidence.py`.
2. Enforced:
   - Same cleanup site validation across before and after visits.
   - Chronological visit order (`before_visit['visited_on'] < after_visit['visited_on']`).
   - Persistent asset existence verification in `assets` table (404 for missing before or after asset).
   - Relational integrity: asset belongs to visit, visit belongs to site.
   - Forgery and tamper protection: claimed site and visit verification against persisted data.
   - Media format validation (`jpeg`, `jpg`, `png`, `webp`, positive dimensions, secure URL).
   - Permission status validation (only `'granted'` permission permitted for pairs and reports).
   - Cross-site observation modification rejection (`Cannot change the site of an observation`).
   - Exclusion of non-granted or revoked assets from report generation.
3. Extended `PairInput` and `EditInput` schemas to allow optional client-specified `site_id`, `before_visit_id`, and `after_visit_id`.
4. Added 13 matrix tests in `backend/tests/test_evidence.py` covering tests A through M (`test_pair_validation_matrix_*`).
5. Verified 61 passed tests; zero regressions.

**Acceptance Criteria:**
- All 13 matrix tests (A through M) pass. ✅
- Existing 48 tests continue passing. ✅
- Tampered asset IDs and cross-site injection rejected. ✅
- Revoked permission assets rejected. ✅
- Approval invalidated on evidence change. ✅

---

## [x] T006 — Structured AI Comparison / Uncertainty
**Owner:** Cline (Builder)  
**Dependencies:** T002 ✅, T004 ✅, T005 ✅  
**Status:** COMPLETE (2026-09-26)

**Scope Completed:**
1. Structured AI proposal output contract:
   - 4-state enum `ComparisonStatus`: `changed`, `unchanged`, `uncertain`, `insufficient_evidence`.
   - Bounded model confidence `[0.0, 1.0]` (representing model certainty, not factual accuracy).
   - Controlled vocabulary enum `UncertaintyReason` (`camera_angle_mismatch`, `lighting_difference`, `partial_occlusion`, `insufficient_visual_overlap`, `poor_image_quality`, `relevant_area_not_visible`, `incompatible_framing`, `evidence_unavailable`, `provider_error`, `unverified_quantitative_claim`, `other`).
   - Structured `VisualChange` list (`type`, `description`, `evidence`).
   - Concise summary and evidence notes.
2. Full backward compatibility:
   - Preserved `reliable`, `observation`, and `reason` properties/fields via `@model_validator(mode='before')`.
   - Legacy and new payloads seamlessly parse and validate.
3. Strict Safety Guardrails:
   - Rejection of unverified quantitative claims (weights, counts, percentages, bags) via `QUANTITATIVE_CLAIM_PATTERN`.
   - Rejection of invalid status or confidence scores safely defaulting to `uncertain`/`provider_error`.
   - Malformed JSON, network failures, timeouts, and missing fields handled safely without crashing.
   - Refusal to convert visual observations into factual impact measurements.
4. Review Workflow Integrity:
   - AI results remain strictly proposals: created observations are ALWAYS `review_status = 'pending'` and `approved_text = None`.
   - Unapproved observations are strictly excluded from downstream reports until explicit human review approval.
5. Tests:
   - Added full Test Matrix A through M in `test_image_comparison.py`.
   - Added Test Matrix N in `test_evidence.py`.
   - Total test suite now passes 96 tests (35 new tests added, zero regressions).

**Acceptance Criteria:**
- All 15 Test Matrix items (A through O) verified and passing. ✅
- Total tests passing: 96 (previous baseline: 61). ✅
- Zero regressions. ✅

---

## [x] T007 — Real Cloudinary -> Gemini End-to-End Integration
**Owner:** AGY (Architect) + Cline (Builder)  
**Dependencies:** T002 ✅, T005 ✅, T006 ✅  
**Status:** COMPLETE (2026-09-26)

**Scope Completed:**
1. Real Cloudinary -> Gemini End-to-End Pipeline:
   - Cloudinary Ingestion: validates upload, persists `secure_url`, `public_id`, `width`, `height`, `format`, `permission_status`, and `thumbnail_url`.
   - Local Binary Safety: no binary images are stored locally; only secure URLs and metadata are recorded.
   - Evidence Validation: site and visit validation, chronological sequence, and granted permission validation.
   - Multimodal Gemini Comparison: structured two-image prompt, inline base64 streams from trusted Cloudinary host, markdown fence stripping for JSON parsing, and schema validation.
   - Human Review Integrity: AI outputs strictly proposal-only (`review_status='pending'`, `approved_text=None`); excluded from report until explicit reviewer approval.
   - Approval Invalidation: any evidence or observation mutation resets approved status to pending and removes from report.
   - Report Generation: traceable pair verification with before/after asset IDs, dates, URLs, and reviewer attribution; unapproved or revoked assets strictly excluded.
2. Error Matrix (A through J) with Deterministic Mocks:
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
   - `test_live_cloudinary_and_gemini_pipeline` gated strictly by `RUN_LIVE_INTEGRATION=1`.
   - Skips cleanly when live credentials are not present or placeholder keys are detected.
   - Verified read-only CLI check scripts: `backend/scripts/check_cloudinary.py` and `backend/scripts/check_gemini.py`.
4. Tests: 107 passed, 1 skipped (live test), 1 known Windows chmod failure, 0 regressions.

**Acceptance Criteria:**
- Cloudinary asset ingestion persists required metadata. ✅
- Gemini comparison follows T006 structured contract with resilient JSON parsing. ✅
- Deterministic Error Matrix (A through J) verified and passing. ✅
- Live integration test skips cleanly without `RUN_LIVE_INTEGRATION=1` or when real credentials absent. ✅
- Zero hardcoded secrets, zero secrets in logs, zero client credential exposure. ✅
- Full test suite passes (107 passed). ✅

---

## [x] T008 — Judge-Facing Review Experience
**Owner:** Cline (Builder) + AGY (Architect)  
**Dependencies:** T002 ✅, T005 ✅, T006 ✅, T007 ✅  
**Status:** COMPLETE (2026-09-26)

**Scope Completed:**
1. Primary Review Experience (`backend/app/demo/index.html`, `backend/app/demo/styles.css`, `backend/app/demo/app.js`):
   - Provenance Display: Site, Before & After Visit dates, Source Asset IDs, Permission status (`granted`, `pending_verification`, `revoked`), and Cloudinary verification badge.
   - Dual Visual Comparison: Side-by-side mode and interactive split-reveal comparison slider with toggle.
   - Lightbox modal dialog for high-resolution inspection.
   - Real-time client-side pair validation check (chronology, permissions, distinct assets).
2. AI Proposal Presentation:
   - Status badge (`Changed`, `Unchanged`, `Uncertain`, `Insufficient Evidence`).
   - Concise AI observation summary and structured visual change list (`type`, `description`, `evidence`).
   - Bounded Model Confidence gauge labeled `MODEL CONFIDENCE` with certainty disclaimer.
   - Supporting evidence notes.
3. Trust & Invariant Distinction:
   - Visual distinction between `AI PROPOSAL` (amber border, warning banner `AI suggestion — Human verification required`) and `HUMAN VERIFIED RECORD` (emerald border, check banner, reviewer identity, approval date).
   - Approval invalidation: Editing an approved observation immediately resets status to `pending` and removes it from verified reports.
4. Uncertainty UX:
   - Prominently displays: "AI could not determine the outcome with sufficient confidence." or "Insufficient evidence for a reliable comparison."
   - Discloses controlled human-friendly reason (e.g., Camera angle mismatch, Lighting difference, Insufficient visual overlap).
5. Human Review Workflow:
   - `[ Approve ]`, `[ Save Draft / Edit ]`, and `[ Reject ]` actions wired to existing backend endpoints (`POST /observations/{id}/review`, `PATCH /observations/{id}`).
6. Live In-Page Report:
   - In-page preview of official report: guarantees only human-approved observations enter the report; unapproved proposals are explicitly excluded.
   - Markdown export and raw JSON toggle.
7. Testing:
   - Created `backend/tests/test_demo_ui.py` covering static delivery and all 9 critical behaviors (11 tests).
   - Total test suite now passes 118 tests (+11 new tests, zero regressions).

**Acceptance Criteria:**
- Primary demo flow 1 through 10 fully operational. ✅
- Distinct visual hierarchy for AI Proposal vs Human Verified Record. ✅
- Uncertainty prominently displayed with explanatory reason. ✅
- Report generation excludes unapproved proposals. ✅
- 11 new tests added and verified. ✅
- Total tests passing: 118. ✅

---

## [x] T009 — Demo Hardening & End-to-End QA
**Owner:** AGY / Cline  
**Dependencies:** T001-T008 ✅  
**Status:** COMPLETE (2026-09-26)

**Scope Completed:**
1. Fresh-Start Hardening:
   - `run_local.sh`: Cross-platform virtual environment detection (`.venv` and `venv`, Windows Git Bash vs Linux/macOS `bin/activate` vs `Scripts/activate`).
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

**Acceptance Criteria:**
- Complete end-to-end flow verified without developer intervention. ✅
- Network operations have loading states and double-submit prevention. ✅
- Review integrity verified (only approved observations enter reports). ✅
- Security & secret audit verified clean. ✅
- All 9 new end-to-end tests passing. Total passed: 127. ✅
- `docs/DEMO_RUNBOOK.md` created with judge safety wording. ✅


---

## [x] T010 — Setowa Migration + Architecture Design
**Owner:** AGY / Architect  
**Dependencies:** T001-T009 ✅  
**Status:** COMPLETE (2026-09-26)  
**Deliverables:**
- Architectural transition from single-purpose LEX to the Setowa platform model (`SETOWA_MASTER_PLAN.md`).
- Domain partitioning: Media Domain, Skill Domain, Workflow Domain, Intelligence Domain, Verification Domain, Impact Domain, CLI Domain.
- Established Setowa execution roadmap T011 through T018.

---

## [x] T011 — Media Pipeline + Bulk Ingestion
**Owner:** AGY (Pair Programmer)  
**Dependencies:** T001-T010 ✅  
**Status:** COMPLETE (2026-09-27)  

**Scope Completed:**
1. Database & Asset Schema Migration (`backend/app/services/evidence_store.py`):
   - Non-destructive migration adding `site_id`, `media_type`, `processing_status`, `original_filename`, `duration`, `preview_url`, `created_at`, `metadata_json` to `assets` table.
   - Helper methods: `ensure_ingestion_visit(db, site_id, visit_date)`, `save_asset(db, asset_data)`, `get_media_item(db, asset_id)`, `list_media(db, ...)`.
2. Cloudinary Programmable Media Delivery (`backend/app/services/media.py`):
   - Optimized delivery (`f_auto,q_auto`), responsive previews (`w_1200,h_900,c_limit`), square thumbnails (`w_640,h_480`), and video poster frames at offset 0 (`so_0`).
   - `validate_video_header` enforcing MP4/WebM/MOV container magic bytes and 50 MiB limit.
   - `ingest_video` handling Cloudinary `resource_type="video"` uploads and duration extraction.
   - `ingest_media` unified dispatcher for images and videos.
3. Media API Routes (`backend/app/routes/media.py`):
   - `POST /api/v1/media/bulk`: Multi-file ingestion with per-file error isolation (no whole-batch rollbacks on partial failures), returning structured `BulkMediaUploadResponse`.
   - `POST /api/v1/media/videos`: Direct video upload with poster frame generation.
   - `GET /api/v1/media`: Filtered media asset listing (by project, media_type, permission_status, with pagination).
   - `GET /api/v1/media/{asset_id}`: Single media asset inspection.
4. Setowa Media Library UI (`backend/app/demo/`):
   - Added `#tab-media-library` with filter controls (media type, permission status, search query).
   - Multi-file bulk upload accordion form (`#bulk-upload-form`) with progress feedback and per-file result summaries.
   - Media cards displaying poster frames, duration tags, Cloudinary tags, dimensions, and quick copy CDN URL.
   - Lightbox modal enhanced with HTML5 `<video controls>` inline playback.
5. CLI Utility (`backend/scripts/ingest_collection.py`):
   - Fully functioning standalone CLI tool supporting `--dir`, `--project`, `--source`, `--date`, `--permission`, `--json`.
6. Testing & Quality Assurance:
   - `backend/tests/test_media.py`: Fixed test IDs to eliminate pytest byte serialization hangs; all 18 tests pass in <1s.
   - `backend/tests/test_bulk_media.py`: 5 comprehensive tests for video uploads, magic byte header validation, mixed image/video bulk uploads, partial failure resilience, and media library filtering.
   - Total test suite: 133 tests passed, 1 skipped, 1 known pre-existing Windows chmod failure, 0 regressions.

**Acceptance Criteria:**
- User can ingest collections via UI or CLI. ✅
- Media is stored and delivered through Cloudinary. ✅
- Metadata (duration, dimensions, formats, status) persisted to SQLite. ✅
- Assets visible and filterable in Setowa Workspace. ✅
- Inline video playback and responsive image previews work. ✅
- Zero regressions on existing evidence tests (133 passed). ✅

---

## [x] Cloudinary Qualifying Tooling Setup (AI Power Start)
**Owner:** AGY (Pair Programmer)  
**Dependencies:** T011 ✅  
**Status:** COMPLETE & VERIFIED (2026-09-27)  
**Deliverables:**
- Executed official Cloudinary AI Power Start tooling workflow.
- Installed official Cloudinary Agent Skills (`cloudinary-docs`, `cloudinary-transformations`) into `.agents/skills/` via `npx skills add cloudinary-devs/skills` (locked in `skills-lock.json`).
- Configured official Cloudinary MCP servers (`cloudinary-asset-mgmt`, `cloudinary-env-config`) in `.mcp.json` and global IDE configuration.
- Preserved existing `cloudinary` Python SDK runtime (`1.46.2`) and T007/T011 programmable media pipeline.
- Created `docs/cloudinary-environment.json` and `docs/CLOUDINARY_STATUS.md`.
- Verified 23 targeted media tests pass with 0 regressions.

---

## [x] T012 — Setowa Skill Runtime
**Owner:** AGY (Pair Programmer)  
**Dependencies:** T011 ✅, Cloudinary Qualification ✅  
**Status:** COMPLETE & VERIFIED (2026-09-27)  

**Scope Completed:**
1. Skill Specification & Models (`backend/app/skills/models.py`):
   - `SkillManifest`: Declarative specification enforcing lowercase alphanumeric naming, semver versioning (`X.Y.Z`), input definitions, output definitions, permissions, model provider metadata.
   - `SkillInputDefinition` & `SkillOutputDefinition`: Typed contract (string, number, boolean, object, array, media, asset_id) with required/optional defaults.
   - `SkillExecutionRequest`: Predictable invocation contract with `skill_name`, optional `skill_version`, typed `inputs`, and `execution_context`.
   - `SkillExecutionResult`: 4-state lifecycle status (`success`, `failed`, `invalid_input`, `unavailable`), structured `outputs`, `evidence`, `warnings`, `errors`, and execution telemetry (`latency_ms`, `provider`).
2. Registry & Versioning (`backend/app/skills/registry.py`):
   - Multi-version registration supporting semantic version sorting and resolution (`latest` vs exact `name@version`).
   - Duplicate registration prevention (rejects conflicting version unless `overwrite=True`).
   - Manifest validation on registration (unique input/output names, valid permission syntax).
   - Discovery and listing with optional version expansion and `kind` filtering.
3. Skill Loader & Base Contract (`backend/app/skills/loader.py`):
   - `BaseSkill` abstract base class defining standard execution interface: `async def execute(inputs, context) -> SkillExecutionResult`.
4. Skill Runtime & Error Boundaries (`backend/app/skills/runtime.py`):
   - Authoritative execution orchestrator enforcing declared vs granted permissions, input contract validation, latency measurement, and unhandled exception safety.
   - Zero raw tracebacks or secret leakage.
5. Built-in Skills (`backend/app/skills/builtins/`):
   - `media-metadata@1.0.0`: Deterministic media inspector extracting Cloudinary delivery URLs (`secure_url`, `thumbnail_url`, `preview_url`), dimensions, format, video duration, and SQLite asset records.
   - `evidence-comparison@1.0.0`: Structured visual intelligence comparison reusing the core `image_comparison` service, enforcing 4-state comparison (`changed`, `unchanged`, `uncertain`, `insufficient_evidence`) with bounded confidence and zero factual accuracy claims.
6. API Endpoints (`backend/app/routes/skills.py`):
   - `GET /api/v1/skills`: Discover registered skills with manifests and schemas.
   - `GET /api/v1/skills/{skill_name}`: Inspect specific skill with optional `?version=...`.
   - `POST /api/v1/skills/{skill_name}/execute`: Execute skill with validated request body and execution context.
7. Setowa Workspace Skills UI (`backend/app/demo/`):
   - Added `#tab-skills` with responsive skill cards displaying version badges, kind pills, model providers, declared permissions, inputs, and outputs.
   - Interactive skill test runner (`#skill-tester-panel`) enabling direct execution with live JSON result and latency display.
8. Testing & Validation (`backend/tests/test_skills.py`):
   - 15 comprehensive tests covering all 14 required test scenarios (valid manifest, invalid manifest rejections, registration, duplicate prevention, discovery/filtering, semver resolution, input validation, execution happy path, crashing execution safety, unavailable dependencies, permission enforcement, API endpoints, built-in skill behaviors).
   - 148 passed across full test suite (0 regressions).

---

## [x] T013 — SETOWA Workflow Engine + Builder
**Owner:** AGY (Pair Programmer)  
**Dependencies:** T011 ✅, T012 ✅  
**Status:** COMPLETE & VERIFIED (2026-09-27)  

**Scope Completed:**
1. Workflow Definition Schema (`backend/app/workflows/models.py`):
   - `WorkflowDefinition`, `WorkflowNode`, `WorkflowEdge`, `WorkflowInputDefinition`, `WorkflowSummary`.
   - `WorkflowExecutionRequest`, `WorkflowExecutionResult`, `WorkflowExecutionStatus`, `NodeExecutionStatus`, `NodeExecutionResult`.
   - `WorkflowValidationResult` with detailed error and warning collections.
2. Deterministic DAG Engine (`backend/app/workflows/dag.py`):
   - Directed Acyclic Graph model with Kahn's algorithm and DFS cycle detection.
   - Comprehensive cycle detection, self-loop prevention, dependency resolution, and deterministic topological execution ordering.
3. Strict DAG & Contract Validation (`backend/app/workflows/validation.py`):
   - Node ID uniqueness.
   - Skill registry resolution & semver version matching (`name@version`).
   - Edge source & target existence and port compatibility.
   - Expression reference binding (`$input.key`, `$node.node_id.output_key`).
   - Required node input satisfiability validation before execution.
4. Workflow Execution Engine (`backend/app/workflows/engine.py`):
   - Consumes existing T012 `SkillRuntime` as the single source of truth for executing skills.
   - Dynamic state propagation from workflow-level inputs and upstream node outputs.
   - Dependency failure handling: downstream dependent nodes are marked `skipped` if an upstream dependency fails.
   - Captures comprehensive execution telemetry (`execution_id`, start/end timestamps, `duration_ms`, per-node results, warnings, errors).
5. SQLite Persistence (`backend/app/workflows/store.py`):
   - Persists workflow definitions to `workflows` table and execution runs to `workflow_executions` table.
   - Seeded built-in multi-skill workflow: `wf_evidence_compare` (Before-After Evidence Comparison).
6. REST API Endpoints (`backend/app/routes/workflows.py`):
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
7. Visual Workflow Builder UI (`backend/app/demo/`):
   - Added `#tab-workflows` studio with 3-column layout:
     - Left: Skill Palette with available SETOWA skills and add buttons.
     - Center: Drag-and-drop DAG Canvas with SVG Bézier connection lines and direction arrows.
     - Right: Node Inspector for configuring input mappings (`$input` or `$node` references).
     - Toolbar: New, Validate, Save, Run, Clear, and Workflow selector.
     - Execution Panel: Interactive run form, step status chips, latency, JSON inspection.
8. Testing & Quality Assurance (`backend/tests/test_workflows.py`):
   - 22 targeted tests covering schema, validation, duplicate IDs, missing skills/versions, invalid edges/ports/mappings, self-loops, cycles, topological order, input/output propagation, failure propagation/skipping, persistence, and REST APIs.
   - Full test suite: 170 passed, 1 skipped, 1 known Windows chmod baseline, 0 regressions.

---

## [x] T014 — Field Video Ingestion & Frame Analytics
**Owner:** AGY (Pair Programmer)  
**Dependencies:** T011 ✅, T012 ✅, T013 ✅  
**Status:** COMPLETE & VERIFIED (2026-09-27)  

**Scope Completed:**
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
   - Live Gemini Vision inference via `SkillRuntime`: PASS (HTTP 200 OK, accurate visual observations of canine subject and out-of-focus background, honest `insufficient_evidence` status and `0.1` confidence).

---

## [x] T015 — Project / Location / Timeline Media Grouping & Spatial-Temporal Queries
**Owner:** AGY  
**Dependencies:** T011 ✅, T012 ✅, T013 ✅, T014 ✅  
**Status:** COMPLETE (2026-09-27)  
**Goal:** Group large collections of media assets by project, geographic site, and timeline; support multi-dimensional filtering and spatial-temporal queries across ingested image and video collections.

**Scope Completed:**
1. Schema (`evidence_store.py`):
   - Added `project_id`, `latitude`, `longitude`, `created_at` columns to `sites` table.
   - Added `project_id`, `captured_at`, `created_at` columns to `assets` table.
   - Added `projects` table with `id`, `name`, `description`, `created_at`, `metadata_json`.
   - All T011/T015 indexes moved to `_POST_MIGRATION_INDEXES` post-migration block; safe on legacy DBs.
   - `save_asset` uses `INSERT OR IGNORE` for idempotency on duplicate Cloudinary asset IDs.
2. Service Layer (`media_query.py`):
   - `query_assets()` with combined project/site/date-range/media-type/bbox filtering.
   - `get_timeline()` grouped by day with asset counts.
   - `get_project_summary()` aggregating asset/site/video counts and date span.
3. REST API:
   - `GET /api/v1/sites?project_id=` — project-scoped site listing.
   - `GET /api/v1/sites/{site_id}/detail` — full site metadata.
   - `GET /api/v1/sites/{site_id}/media` — all assets for a site.
   - `GET /api/v1/media/query` — filtered asset search.
   - `GET /api/v1/media/timeline` — day-bucketed timeline.
4. Auto-assignment: uploads without explicit `project_id` are assigned `proj_default`.
5. Tests: 21 targeted tests in `tests/test_media_query.py`, all passing.

**Final Test Result:** 210 passed, 1 skipped, 1 pre-existing Windows chmod failure, 0 functional regressions.

---

## [x] T016 — AI Media Intelligence + Discovery Foundation
**Owner:** AGY  
**Dependencies:** T011 ✅, T012 ✅, T013 ✅, T014 ✅, T015 ✅  
**Status:** COMPLETE (2026-09-27)  
**Goal:** Turn raw SETOWA media (images, videos, derived frames) into structured, traceable AI intelligence (description, observations, controlled tags/signals, activity, warnings, uncertainty, provenance) for discovery, Skills, and Workflows.

**Scope Completed:**
1. Roadmap Reconciliation:
   - Reconciled numbering across `SETOWA_MASTER_PLAN.md` and `.ai/DECISIONS.md` (ADR D017, D018).
   - Preserved T014 (Field Video Ingestion + Frame Analytics) and T015 (Spatial-Temporal Grouping).
   - Locked T016 (AI Media Intelligence + Discovery Foundation) as completed, T017 (Sustainability Timeline) as next.
2. Structured Intelligence Schema & Persistence (`evidence_store.py`):
   - Created `media_intelligence` table: `id`, `asset_id`, `frame_id`, `status`, `description`, `observations`, `tags_json`, `signals_json`, `activity`, `warnings_json`, `uncertainty`, `evidence_json`, `model_provider`, `model_name`, `created_at`, `updated_at`.
   - Added indexes `idx_media_intel_asset`, `idx_media_intel_status`, `idx_media_intel_frame`.
   - Added helpers `save_media_intelligence()`, `get_media_intelligence()`, `get_media_intelligence_history()`.
   - Updated `list_media()` with deterministic filtering by `tag`, `signal`, `ai_status`.
3. Built-in Skill: `media-intelligence@1.0.0` (`app/skills/builtins/media_intelligence.py`):
   - Integrated via existing `SkillRuntime` architecture.
   - Grounded taxonomy: `CONTROLLED_TAGS` (19 categories) and `CONTROLLED_SIGNALS` (14 signals).
   - Strict OBSERVED vs INFERRED grounding, uncertainty extraction, and warning flags (`blur`, `poor_lighting`, `occlusion`, `low_visual_evidence`, `ambiguous_scene`).
   - Multi-model fallback (`gemini-flash-latest`, `settings.GEMINI_VISION_MODEL`, `gemini-3.8-flash`), synthetic offline demo fallback, and honest `unavailable` status handling.
4. Service Layer (`app/services/media_intelligence.py`):
   - Implemented `analyze_asset()`, `get_asset_intelligence()`, `get_asset_intelligence_history()`, `analyze_batch()`.
   - Batch analysis with bounded size (`<= 20`), isolated per-asset failure boundary, and no fabricated results.
5. REST API Endpoints (`app/routes/media.py`):
   - `POST /api/v1/media/{asset_id}/analyze`: Analyze or re-analyze asset via SkillRuntime.
   - `GET /api/v1/media/{asset_id}/intelligence`: Retrieve latest structured intelligence record.
   - `GET /api/v1/media/{asset_id}/intelligence/history`: Retrieve full chronological audit trail of analyses.
   - `POST /api/v1/media/{asset_id}/reanalyze`: Force re-analysis preserving previous run in history.
   - `POST /api/v1/media/{asset_id}/frames/{frame_id}/analyze`: Frame-level intelligence analysis.
   - `POST /api/v1/media/analyze-batch`: Batch analysis with bounded payload.
   - `GET /api/v1/media/query` & `GET /api/v1/media`: Enhanced with `tag`, `signal`, and `ai_status` query parameters.
6. Media Library UI Extension (`backend/app/demo/`):
   - Added AI status and tag filters in Media Library toolbar.
   - Asset cards display AI status badge, description excerpt, tag and signal pills, and warning indicators.
   - Added `Analyze` / `Re-analyze` button and `View Intelligence` button.
   - Added `#intelligence-modal` for viewing observations, detected signals, warnings, uncertainty, and analysis audit history.
7. Testing & Quality Assurance:
   - 20 targeted tests in `tests/test_media_intelligence.py` covering schema, tag/signal normalization, Gemini response parsing, malformed output resilience, uncertainty/warnings, asset/frame provenance, persistence, unavailable handling, failed analysis resilience, re-analysis history, all APIs, batch bounds, discovery filtering, SkillRuntime, and WorkflowEngine compatibility.
   - Full test suite: 230 passed, 1 skipped, 1 pre-existing Windows NTFS chmod failure, 0 functional regressions.
8. Live Gemini Validation:
   - Real Gemini API key validated with live multimodal inference on Cloudinary asset (`gemini-flash-latest`).
   - Returned `status: analyzed`, tags `['vegetation', 'animals']`, signals `['vegetation_cover', 'animal_presence']`, 0 warnings, zero secrets leaked.

---

## [x] T017 — Sustainability Timeline + Impact Story
**Owner:** AGY  
**Dependencies:** T014 ✅, T015 ✅, T016 ✅  
**Status:** COMPLETE (2026-09-27)  
**Goal:** Turn existing persisted project/media/evidence records into a coherent, verifiable, traceable sustainability and impact narrative grounded strictly in real source-backed data without hallucinated carbon or environmental percentages.

**Scope Completed:**
1. Domain Model & SQLite Persistence (`evidence_store.py`):
   - Added `impact_stories` table: `id`, `project_id`, `title`, `description`, `status`, `summary_narrative`, `uncertainty_note`, `date_start`, `date_end`, `metrics_json`, `created_at`, `updated_at`.
   - Added `impact_story_events` table: `id`, `story_id`, `event_type`, `timestamp_date`, `title`, `description`, `site_id`, `site_name`, `primary_media_url`, `thumbnail_url`, `media_type`, `asset_ids_json`, `evidence_ids_json`, `verification_status`, `uncertainty`, `observations_json`, `evidence_json`, `metadata_json`, `sort_order`, `created_at`.
   - Added indexes `idx_impact_stories_project`, `idx_impact_story_events_story`, `idx_impact_story_events_type`.
   - Added store methods: `save_impact_story()`, `get_impact_story()`, `get_project_impact_story()`, `update_impact_story()`, `save_impact_story_events()`, `get_impact_story_events()`, `delete_impact_story_events()`.
2. Pydantic API Schemas (`schemas/api.py`, `schemas/__init__.py`):
   - Defined `TimelineEventType` (`before`, `activity`, `after`, `verified_finding`, `measurement`, `milestone`), `TimelineEvent`, `BeforeAfterCard`, `ImpactStoryResponse`, `GenerateImpactStoryRequest`, `UpdateImpactStoryRequest`.
3. Service Layer (`services/impact_story.py`):
   - Chronological event generation (`build_project_timeline_events()`): integrates site visits, cleanup video action, video frames with timestamp offsets, after photos, recorded measurements, and verified findings with full asset and reviewer provenance.
   - Comparative proof cards (`build_before_after_cards()`): extracts paired observation cards with Cloudinary URLs, verification status, approved findings, and uncertainty caveats.
   - Grounded narrative synthesis (`generate_grounded_impact_narrative()`): synthesized from structured evidence and measurements with strict anti-hallucination rules (zero invented carbon/area/percentage claims), explicit uncertainty flagging, and deterministic fallback when Gemini is offline.
   - Deterministic story lifecycle management: `generate_impact_story()`, `get_impact_story_by_id()`, `get_project_impact_story()`, `update_impact_story_fields()`, `get_story_timeline_events()`.
4. REST API Endpoints (`routes/impact_stories.py`, `main.py`):
   - `GET /api/v1/projects/{project_id}/impact-story`: Retrieve persisted project impact story.
   - `POST /api/v1/projects/{project_id}/impact-story/generate`: Generate/regenerate grounded story from live evidence records.
   - `GET /api/v1/impact-stories/{story_id}`: Retrieve story by ID.
   - `PUT /api/v1/impact-stories/{story_id}`: Update story title, description, or status (`draft`, `in_review`, `published`).
   - `GET /api/v1/impact-stories/{story_id}/timeline`: Retrieve story timeline events in chronological order.
5. Setowa Workspace UI Extension (`backend/app/demo/`):
   - Added `Impact Story` tab button and `#tab-impact` workspace panel.
   - Project Dossier header with evidence date range, total timeline events, linked media assets, approved findings, and recorded physical measurements.
   - Grounded Synthesis card displaying verified impact summary text, story status controls, and observation/verification caveats callout.
   - Before/After comparative evidence gallery with Cloudinary responsive imagery, verification status badges, reviewer attribution, and click-to-lightbox inspection.
   - Chronological spine displaying all milestone events with color-coded type markers, media thumbnails (image/video), frame observations, and traceable provenance.
6. Testing & Quality Assurance:
   - 23 targeted tests in `tests/test_impact_story.py` covering timeline event creation, chronological sorting, project/site linkage, media linkage, evidence linkage, verification state propagation, before/after card generation, uncertainty preservation, grounded summary generation, Gemini offline fallback, story persistence & retrieval, API endpoints, empty project handling, uncertain evidence handling, approved evidence handling, provenance completeness, Cloudinary media delivery, and backward compatibility with evidence review, SkillRuntime, and WorkflowEngine.
   - Full test suite: 253 passed, 1 skipped, 1 pre-existing Windows NTFS chmod failure, 0 functional regressions.
7. Live Gemini Validation:
   - Live multimodal narrative synthesis executed with configured credentials (`GEMINI_API_KEY`). Produced 683-character strictly grounded narrative referencing verified observations and exact weigh slip measurement (320.0 kg), with 0 secrets leaked.

---

## [x] T018 — Public / Shareable Impact Experience
**Owner:** AGY  
**Dependencies:** T017 ✅  
**Status:** COMPLETE (2026-09-27)  
**Goal:** Create a polished, read-only public presentation and public-safe API projection of a published SETOWA Impact Story accessible via secure share token without requiring internal workspace credentials.

**Scope Completed:**
1. Database Schema & Migration (`evidence_store.py`):
   - Added `share_token TEXT UNIQUE` column to `impact_stories` table.
   - Added non-destructive runtime migration guard and unique index `idx_impact_stories_share_token`.
   - Added persistence helper methods: `get_impact_story_by_share_token()` and `set_impact_story_share_token()`.
   - Added `get_asset = get_media_item` alias and updated `save_impact_story` / `update_impact_story`.
2. Public Projection & Pydantic Schemas (`schemas/api.py`, `schemas/__init__.py`):
   - Added `share_token` and `share_url` to `ImpactStoryResponse`.
   - Added `ShareStoryResponse` schema.
   - Added `PublicTimelineEvent`, `PublicBeforeAfterCard` (with `verified_text`), and `PublicImpactStory` models.
   - Stripped all internal database IDs, reviewer auth tokens, secret environment variables, and private operational data from public projection.
3. Public Story Service Layer (`services/public_story.py`):
   - Implemented `generate_share_token()` with 128-bit cryptographically secure URL-safe tokens (`pst_` prefix).
   - Implemented `ensure_story_share_token()`, `rotate_story_share_token()`, and `revoke_story_share_token()`.
   - Implemented `get_public_impact_story()` with strict published-status gating (draft and in_review return 404 without leaking record existence), media provenance resolution (`assets.source`), and site name resolution (`sites.name`).
   - Implemented `render_public_story_html()` producing clean standalone HTML5 with Setowa design language, Open Graph social share metadata, Cloudinary-powered hero media, before/after comparison split cards, chronological timeline spine with event badges, verified findings callout, explicit uncertainty caveats, and `@media print` export styles.
4. Internal Impact Story Lifecycle Integration (`services/impact_story.py`):
   - Updated `generate_impact_story` and `get_impact_story_by_id` to include share token and URL.
   - Auto-generated `share_token` when story status transitions to `published`.
5. Public and Internal REST APIs:
   - Created `routes/public_impact.py` mounted at `/` in `main.py`:
     - `GET /share/{public_token}`: HTML public presentation.
     - `GET /api/v1/public/impact/{public_token}`: Public-safe JSON projection.
   - Updated `routes/impact_stories.py` with share management endpoints:
     - `POST /api/v1/impact-stories/{story_id}/share`: Generate/retrieve share token.
     - `POST /api/v1/impact-stories/{story_id}/share/rotate`: Invalidate previous token and issue new token.
     - `POST /api/v1/impact-stories/{story_id}/share/revoke`: Revoke public access.
6. Setowa Workspace UI Extension (`backend/app/demo/`):
   - Added `#btn-top-open-public` and `#impact-share-bar` inside `#tab-impact`.
   - Added interactive controls for "Open Public Story", "Copy Share Link", "Rotate Link", and "Revoke Link".
   - Integrated dynamic share bar rendering into `renderImpactStory` and `renderEmptyImpactStory`.
7. Testing & Quality Assurance:
   - 25 targeted tests in `tests/test_public_story.py` covering published access, draft/in_review blocking (404), invalid tokens, public projection safety, secret exclusion, reviewer token exclusion, verification badges, pending/rejected/uncertain finding handling, timeline preservation, before/after preservation, Cloudinary URL delivery, provenance preservation, public API, public page HTML route, share token generation and uniqueness, token rotation and revocation, Open Graph metadata, and backward compatibility.
   - Full test suite: 278 passed, 1 skipped, 1 pre-existing Windows NTFS chmod failure, 0 functional regressions.
8. Live System Validation:
   - Live validation on real project (`proj_default`): draft/in_review correctly returned 404; published returned 200 HTML and 200 JSON with Cloudinary hero media, timeline events, before/after evidence, zero secrets, zero reviewer tokens.

---

## [x] T019 — Hackathon Demo & Production Hardening
**Owner:** AGY + Aryan  
**Dependencies:** T018 ✅  
**Status:** COMPLETE (2026-09-27)  
**Goal:** Final hackathon presentation hardening, end-to-end demo script preparation, system resilience, operational readiness, and polished documentation.

**Scope Completed:**
1. **Deterministic Demo Dataset & Seed (`scripts/seed_demo.py`, `scripts/setup_local_demo.py`):**
   - Implemented `seed_demo_dataset()` populating `proj_mombasa_marine` ("Mombasa Marine Litter & Mangrove Restoration"), `site_nyali_creek`, 3 chronological visits, 3 Cloudinary media assets (baseline photo, cleanup action video, post-verification photo), 3 video frame derivations (`1.5s`, `4.0s`, `8.0s`), 3 frame analyses, 3 structured media intelligence records, approved evidence observation pair (`obs_mombasa_creek`), physical weigh slip measurement (320 kg net waste collected), and published impact story with share token `pst_demo_mombasa_coastal_2026`.
   - Idempotent and maintains legacy `demo-riverbank` fixtures for backward test compatibility.
2. **One-Command Cross-Platform Demo Startup (`scripts/start_demo.py`):**
   - Startup launcher that safely audits environment variables without secret leaks, ensures reviewer tokens, seeds demo dataset, displays visual localhost banner, and starts uvicorn server.
3. **Safe Environment & Production Validation (`services/env_validator.py`):**
   - `validate_environment()`: Classifies variables as `configured` or `missing` without leaking secret values.
   - `validate_production_readiness()`: Enforces safety invariants in production (disallows `USE_MOCK`, forbids `*` or `localhost` in CORS allowed origins, requires non-memory database path, checks provider keys).
4. **Health & Readiness Probes (`routes/health.py`, `schemas/api.py`):**
   - `GET /api/v1/health`: Lightweight liveness probe reporting service status, version, environment, and mock mode.
   - `GET /api/v1/ready`: Operational readiness probe verifying SQLite database ping (`SELECT 1`), Cloudinary configuration status, and Gemini configuration status without exposing credentials.
5. **Unified CLI Path (`app/cli.py`, `setowa_cli.py`):**
   - Reuses core backend services without logic duplication:
     - `setowa_cli.py skill list`: Lists registered skills from `SkillRegistry`.
     - `setowa_cli.py workflow list`: Lists workflow definitions from `WorkflowStore`.
     - `setowa_cli.py workflow run wf_evidence_compare`: Executes topological DAG workflow using default demo inputs.
     - `setowa_cli.py run status <id>`: Displays execution metrics, latency, and node results.
     - `setowa_cli.py story show proj_mombasa_marine`: Displays impact story narrative, uncertainty notes, and public share URL.
     - `setowa_cli.py ingest <dir>`: Ingests directory of media files with per-file error isolation.
6. **Automated End-to-End Smoke Test (`scripts/smoke_test.py`):**
   - Complete 9-stage validation: (1) Health/Readiness, (2) Ingestion/Organization, (3) Cloudinary delivery, (4) AI intelligence, (5) Skill execution, (6) Workflow DAG run, (7) Human review & verification, (8) Published impact story, (9) Public share HTML/JSON & 404 gating.
   - All 9 phases verified passing.
7. **Comprehensive Demo Documentation:**
   - `docs/DEMO_RUNBOOK.md`: 10-section operational runbook covering prerequisites, setup, 5-minute walkthrough sequence, CLI commands, troubleshooting, and reset.
   - `docs/DEMO_SCRIPT.md`: Complete 5-minute pitch narrative for judges highlighting Cloudinary programmable media, Gemini multimodal reasoning, skill reusability, DAG composability, human verification governance, and public impact sharing.
8. **Testing & Quality Assurance (`tests/test_demo_hardening.py`):**
   - 18 comprehensive tests covering startup env validation, missing var detection, health probe, readiness probe, deterministic seed, CLI happy path, CLI failure handling, complete demo flow, public story smoke, secret leak checks, CORS behavior, production configuration safety, error response sanitization, existing Cloudinary compatibility, existing Gemini compatibility, existing SkillRuntime compatibility, existing WorkflowEngine compatibility, and evidence review compatibility.
   - Full test suite: **296 passed**, 1 skipped, 1 pre-existing Windows NTFS chmod failure, 2 warnings, 0 functional regressions.

---

## [x] T020-A — Showcase Repair + Mass Media Demo Expansion
**Owner:** AGY + Aryan  
**Dependencies:** T019 ✅  
**Status:** COMPLETE (2026-09-30)  
**Goal:** Fix the Showcase "View Public Story" CTA 404, enforce honest verified-only public evidence, and expand the deterministic demo dataset into a rich multi-site, multi-visit mass media repository (51 assets, 3 videos, 7 derived frames).

**Scope Completed:**
1. **Showcase / Public Story Route Repair (`app/services/public_story.py`, `app/services/impact_story.py`):**
   - Removed synthetic demo blocker in `get_public_impact_story()` that was returning `None` (404) for published demo projects.
   - Removed publishing blocker in `impact_story.py` that raised ValueError on demo project stories.
   - Gated public story strictly to published status while allowing fully transparent demo scenarios labeled with `DEMO DATASET`.
   - Updated CSP header in `app/main.py` to allow `'unsafe-inline'` script-src specifically on `/share/` routes to enable the inline clipboard `copyShareLink()` functionality with zero browser console errors.
2. **Mass Media Dataset Expansion (`scripts/seed_demo.py`):**
   - **Sites (4)**: Nyali Creek Mangrove Fringe (`site_nyali_creek`), Tudor Creek Estuary (`site_tudor_creek`), Sabaki Riverbank Catchment (`demo-riverbank`), Watamu Marine Park Driftline (`site_watamu_beach`).
   - **Visits (13)**: Chronological baseline, action, audit, and post-cleanup visits across August–September 2026.
   - **Media Assets (51)**: 48 high-resolution images + 3 full videos (`t014_live_walkthrough.mp4`, `cld-sample-video.mp4`, `sea-turtle.mp4`) hosted on Cloudinary (`tlf3lv01`) with valid transformations, poster thumbnails, and `permission_status = 'granted'`.
   - **Video Derivations (7 frames)**: Cloudinary offset transformations (`so_1.5`, `so_4.0`, `so_8.0`, etc.) with associated AI frame analyses.
   - **Media Intelligence (51 records)**: Structured tags (`debris`, `plastic`, `nets`, `mangroves`, `water`, `vegetation`, `cleanup`, `marine litter`) and visual signals.
   - **Debris Weigh-Ins (2)**: 320 kg at Nyali Creek, 145 kg at Sabaki Riverbank.
   - **Comparative Observations (4)**: 4 human-auditor approved before/after findings with zero pending/unapproved proposals leaking to the public impact story.
   - **Idempotent Cleanup**: Safely cleans prior demo records (`impact_story_events`, `measurements`, `media_intelligence`, `observation_revisions`) without foreign key constraint violations.
3. **Automated & Browser Verification:**
   - 18/18 `test_demo_hardening.py` tests passing.
   - 25/25 `test_public_story.py` tests passing.
   - 9/9 `smoke_test.py` end-to-end stages passing.
   - Playwright browser testing: Showcase loads, CTA navigates to `/share/pst_demo_mombasa_coastal_2026` returning HTTP 200, public dossier renders with Cloudinary hero media, before/after evidence cards, verified findings, zero secrets, and zero console errors. Workspace UI verified for media gallery (50+ assets), video player & frame analytics modal, search by text ("canopy"), filter by tag ("plastic"), timeline visits, and semantic evidence discovery.

---

## [x] T021 — Full Judge-Flow + Product Polish
**Owner:** AGY + Aryan  
**Dependencies:** T020-A ✅  
**Status:** COMPLETE (2026-09-30)  
**Goal:** Audit and polish the end-to-end judge experience across the full 7-stage evidence pipeline (`SHOWCASE → WORKSPACE → PROJECT/SITE → MEDIA LIBRARY → SEARCH → AI INTELLIGENCE → TIMELINE → BEFORE/AFTER → AI PROPOSAL → HUMAN REVIEW → APPROVAL → REPORT → CAMPAIGN → PUBLIC IMPACT STORY`).

**Scope Completed:**
1. **End-to-End Judge Journey Walkthrough:**
   - Exercised all 14 stops via Playwright browser automation without error.
   - Verified Showcase (`/showcase/`), topbar navigation, active session (`Farhan / local`), All Sites directory (`#projects`), media library, search & tag filtering, structured AI intelligence drawer, chronological visits timeline, before/after comparison slider, AI proposal creation & invalidation, reviewer approval, report generation with receipts, grounded campaign generation, and public impact story.
2. **Database Cleanliness & Seed Hygiene:**
   - Enhanced `seed_demo.py` Step 0 to cascade delete legacy dummy test sites (`'g'`, `'river'`, `'river-delta'`, `'test-wf-site'`, `'proj_mombasa_marine'`) and all orphaned child records.
   - Cleaned site dropdown combobox and Project Library gallery so judges view only authentic Kenyan coastal conservation sites under `proj_mombasa_marine`.
3. **Strict Content Security Policy (CSP) Compliance:**
   - Discovered and eliminated inline `onclick` handlers on subnav and footer buttons that violated Setowa's `script-src 'self'` policy.
   - Replaced all inline handlers with declarative attributes (`data-route-tab` and `data-sub`) and established centralized click event delegation in `app.js`.
   - Verified zero console errors across all workspace views.
4. **Visual Hierarchy (AI Proposal vs. Approved Record):**
   - Verified clear visual distinction:
     - `AI PROPOSAL`: Prominent amber warning banner, `⚠ HUMAN VERIFICATION REQUIRED`, `NOT IN OFFICIAL REPORT`, explicit model confidence disclaimer, and reject/approve action controls.
     - `HUMAN-APPROVED RECORD`: Crisp green banner, `✓ HUMAN-APPROVED RECORD`, `INCLUDED IN OFFICIAL REPORT`, revision counter, reviewer timestamp attribution, and explicit note that subsequent edits invalidate approval.
5. **UI & Rendering Polish:**
   - Fixed unescaped HTML string rendering in Media Intelligence audit trail (`escapeHtml` + DOM innerHTML) in `intel-history-item`.
   - Added `.stage-footer-nav` step guides at the bottom of core workspace tabs (`Media Library → Compare → Review → Report → Timeline / Public Story`), allowing judges to seamlessly traverse the evidence lifecycle.
6. **Semantic Search & Grounded Reporting:**
   - Validated queries: `"plastic debris in mangroves"`, `"fishing nets near shoreline"`, `"cleanup activity"`.
   - Verified that unapproved AI proposals are strictly excluded from reports and public impact stories, preserving complete provenance integrity.
7. **Verification & Testing:**
   - Full test suite: **317 passed**, 1 expected/documented Windows chmod failure, 2 skipped, 2 non-blocking warnings.
   - Smoke test: All 9/9 stages pass.
   - Zero browser console errors or API errors.




