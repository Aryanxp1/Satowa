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

