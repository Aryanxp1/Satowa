# CHANGELOG.md — Setowa / LEX
# Tracking all changes made across sessions and agents

## [Unreleased]

### 2026-09-26
- **AGY**: Initialized `.ai/` control plane (T001) with `AGENTS.md`, `PROJECT_STATE.md`, `TASK_BOARD.md`, `DECISIONS.md`, `HANDOFF.md`, and `CHANGELOG.md`.
- **AGY**: Established verified test baseline (T003): 47 tests collected, 45 passed, 1 pre-existing Windows-specific permission failure (`chmod 0o600`), 2 library deprecation errors.
- **AGY**: Documented root causes and verified zero code regressions.
- **AGY**: Prepared detailed task specification and constraints for T002 (Schema Alignment).
- **Cline**: Completed T002 (Schema Alignment):
  - Updated `assets` table schema with `permission_status TEXT NOT NULL DEFAULT 'granted'` and nullable `thumbnail_url TEXT`.
  - Added non-destructive schema migration guards with column inspection and `ALTER TABLE`.
  - Persisted `thumbnail_url` and validated `permission_status` on image upload.
  - Mapped unreliable AI comparisons to `review_status = 'pending'`, preserving `reliability_reason` without text fabrication.
  - Migrated legacy `unreliable` observation records to `pending`.
  - Updated `CHECK` constraint on `observations.review_status` to `('pending','approved','rejected')`.
  - Added `AssetResponse` and `PermissionStatus` to `schemas/api.py` and exported them in `schemas/__init__.py`.
  - Added 3 focused migration, persistence, and validation tests; verified all 48 tests pass (1 pre-existing Windows failure unchanged, zero regressions).
- **Cline**: Completed T004 (Defuse the Mock Accuracy Claim):
  - Removed unsupported `99.4%` and `10x` claims from `backend/app/routes/analyze.py` (`get_mock_stats`).
  - Labeled showcase metrics explicitly as `Unbenchmarked (Demo)`, `Simulated Mock`, and `Assisted Review / Human In The Loop`.
  - Updated `backend/app/services/ai_engine.py` mock prompt reasoning to explicitly state demo mode and human verification requirement; replaced `0.994` confidence with `0.95`.
  - Updated `backend/tests/test_api.py` to assert that no `99.4` percentage exists and that accuracy metric is identified as demo/synthetic.
  - Verified complete test suite: 48 passed, zero regressions.
- **Cline**: Completed T005 (Evidence / Pair Validation Hardening):
  - Strengthened `validate_pair` in `backend/app/routes/evidence.py` to authoritatively enforce server-side validation invariants:
    - Same cleanup site validation across before and after visits.
    - Strict chronological visit ordering (`before_visit['visited_on'] < after_visit['visited_on']`).
    - Persistent asset existence verification in `assets` table (404 for missing before or after asset).
    - Asset-to-visit and visit-to-site relational consistency with tamper detection against forged IDs.
    - Media validity checks (supported image formats `jpeg/jpg/png/webp`, positive dimensions, secure URL).
    - Evidence permission status enforcement (only `'granted'` permission permitted for pairs and reports).
    - Rejection of cross-site tampering when editing existing observations (`422 Cannot change the site of an observation`).
    - Filtered `report_rows` to guarantee only assets with `permission_status='granted'` appear in approved reports.
  - Extended `PairInput` and `EditInput` schemas to support optional client-claimed `site_id`, `before_visit_id`, and `after_visit_id` with strict server-side validation.
  - Added 13 focused tests covering Test Matrix items A through M (`test_pair_validation_matrix_*`).
  - Verified full test suite: 61 passed, 1 pre-existing Windows-specific failure unchanged, zero regressions.



