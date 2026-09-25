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

## Test Summary Post-T006

| Metric | Value |
|:---|:---|
| **Command** | `.\venv\Scripts\python.exe -m pytest tests/ --tb=no -q` |
| **Python** | 3.14.6 |
| **pytest** | 9.1.1 |
| **Total Collected** | 98 |
| **Passed** | 96 (+35 new tests passed) |
| **Failed** | 1 (pre-existing Windows chmod test in `test_local_setup.py`) |
| **Errors** | 2 (collection/deprecation, non-blocking) |
| **Warnings** | 2 (httpx/starlette deprecation) |
| **Runtime** | ~8.5s |

## What Is Ready Next

- T006 is **COMPLETE**.
- Next task on the board: **T007 — Cloudinary Live Validation Script**.

## Open Questions for User

None. Awaiting user review and authorization to proceed with next milestone.



