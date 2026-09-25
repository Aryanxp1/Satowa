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

## [ ] T003a — Sanitize Mock Stats
**Owner:** Cline (Builder)  
**Dependencies:** T002  
**Status:** NOT STARTED

**Scope:**
- `backend/app/routes/analyze.py` → Replace `"99.4%"` and `"10x"` hardcoded values in `get_mock_stats()`.
- Add a `get_stats()` method to `evidence_store.py` returning `{sites: int, visits: int, approved_observations: int}`.
- `get_mock_stats()` should query real counts and return them (or 0 if empty DB).
- Update `test_api.py::test_mock_stats` to validate real-count structure (not specific string values).

**Acceptance Criteria:**
- GET `/api/v1/mock-stats` returns dynamic database counts.
- Response no longer contains `"99.4%"` or any fabricated accuracy claim.
- All tests pass.

---

## [ ] T004 — Gemini Prompt Schema Enhancement
**Owner:** Cline (Builder)  
**Dependencies:** T002  
**Status:** NOT STARTED

**Scope:**
- `backend/app/services/image_comparison.py` → Extend `Comparison` model to add `confidence: float | None` and `limitations: str | None`.
- Extend Gemini prompt to request 4-state status enum: `supported`, `uncertain`, `insufficient_evidence`, `provider_unavailable`.
- Map responses to existing `reliable: bool` output while adding new fields.
- Keep all existing guardrails (numerical impact rejection, untrusted URL rejection).

**Acceptance Criteria:**
- `test_image_comparison.py` — all 5 tests still pass.
- New test for `uncertain` and `insufficient_evidence` Gemini outputs pass.

---

## [ ] T005 — Cloudinary Live Validation Script
**Owner:** Cline (Builder)  
**Dependencies:** T002  
**Status:** NOT STARTED

---

## [ ] T006 — Gemini Live Validation Script
**Owner:** Cline (Builder)  
**Dependencies:** T004  
**Status:** NOT STARTED

---

## [ ] T007 — Demo UI: Uncertainty Badge
**Owner:** Cline (Builder)  
**Dependencies:** T004  
**Status:** NOT STARTED

---

## [ ] T008 — CI GitHub Actions
**Owner:** Cline (Builder)  
**Dependencies:** T002, T003a, T004  
**Status:** NOT STARTED

---

## [ ] T009 — Demo Script & Documentation
**Owner:** AGY + User  
**Dependencies:** T007  
**Status:** NOT STARTED
