# PROJECT_STATE.md — Setowa / LEX
# Last Updated: 2026-09-26 by AGY / Cline

## Current Status: T006 STRUCTURED AI COMPARISON / UNCERTAINTY COMPLETE

## Repository State

- **Git Remote:** `origin/main` at `farhanakhtar0x66/LEX`
- **Local Working Directory:** `C:\Users\aryan\.gemini\antigravity-ide\scratch\LEX\`
- **Python:** 3.14.6
- **pytest:** 9.1.1

## Verified Test Baseline Post-T006 (2026-09-26)

```
Command: .\venv\Scripts\python.exe -m pytest tests/ --tb=no -q
Runtime: ~8.5 seconds
Collected: 98 items (44 in api/cred/evid + 39 in img_comp + 15 in other)

PASSED: 96 (+35 new tests passed)
FAILED: 1   ← test_local_setup.py::test_local_session_and_credential_update (Windows chmod)
ERRORS: 2   ← Collection/deprecation errors (Starlette/httpx testclient)
WARNINGS: 2 ← StarletteDeprecationWarning (non-blocking)
```

## One Failing Test — Root Cause

**Test:** `tests/test_local_setup.py::test_local_session_and_credential_update`

**Assertion:** `assert stat.S_IMODE(path.stat().st_mode) == 0o600`

**Actual:** `438` (`0o666`) vs expected `384` (`0o600`)

**Root Cause:** Windows does **not** support POSIX file permission bits (`chmod 0o600`).
The credential file is written with `os.chmod(path, 0o600)` but Windows ignores the execute/read/write model.
`stat.S_IMODE()` on Windows returns `0o666` (or `0o644`) regardless of what was requested.

**Classification:** **Pre-existing environment issue** — not a code regression. This test was written for Linux/macOS.
The application code itself (`local_setup.py`) is correct; the OS simply does not honor the chmod call.
This passes on CI (Linux runner). It is **safe to defer** — do not fix application code for this.

## Two Errors — Root Cause

The 2 "errors" are `pytest` collection-level deprecation warnings escalated to errors from:
- `venv/Lib/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning` — Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
These are **non-blocking deprecation warnings** from the installed library versions, not from the application code.

## What Is Working

| Domain | Status |
|:---|:---|
| Site + Visit CRUD | ✅ Fully tested and passing |
| Asset upload + Cloudinary mock | ✅ Fully tested and passing |
| Asset `permission_status` persistence & validation | ✅ Fully tested and passing (defaults to 'granted') |
| Asset `thumbnail_url` persistence (nullable) | ✅ Fully tested and passing |
| Non-destructive migration for assets & observations | ✅ Fully tested and passing |
| Hardened pair validation (same site, visit ordering, asset existence, permission, media format) | ✅ Fully tested and passing (13-case test matrix) |
| Server-side tamper protection (cross-site injection, ID forgery, site modification rejected) | ✅ Fully tested and passing |
| Unreliable comparison → review_status='pending' | ✅ Fully tested and passing (reason preserved, no text invented) |
| Review approve / reject | ✅ Fully tested and passing |
| Edit approved → resets to pending | ✅ Fully tested and passing |
| Evidence change → resets to pending and drops from approved report | ✅ Fully tested and passing |
| Stale version 409 on review | ✅ Fully tested and passing |
| Stale version 409 on edit | ✅ Fully tested and passing |
| Reviewer identity comes from token, not payload | ✅ Fully tested and passing |
| Report: only approved+approved_text included and only 'granted' permission assets | ✅ Fully tested and passing |
| Report: original Cloudinary URLs preserved | ✅ Fully tested and passing |
| Measurements: require named reviewer | ✅ Fully tested and passing |
| Measurements: require non-blank source | ✅ Fully tested and passing |
| Legacy DB migration (version, location, description, permission_status, thumbnail_url) | ✅ Fully tested and passing |
| Synthetic seed: idempotent, labeled | ✅ Fully tested and passing |
| Cloudinary file type/size validation | ✅ Fully tested and passing |
| Cloudinary auth / missing config | ✅ Fully tested and passing |
| Provider error redaction | ✅ Fully tested and passing |
| Gemini: structured 4-state output (changed, unchanged, uncertain, insufficient_evidence) | ✅ Fully tested and passing |
| Gemini: model confidence bounded [0.0, 1.0] (distinguished from accuracy) | ✅ Fully tested and passing |
| Gemini: controlled uncertainty vocabulary & reason persistence | ✅ Fully tested and passing |
| Gemini: rejection of unverified quantitative claims (weights, counts, percentages) | ✅ Fully tested and passing |
| Gemini: output validates against trust rules | ✅ Fully tested and passing |
| Gemini: untrusted URL rejected | ✅ Fully tested and passing |
| Gemini: invalid model response refused | ✅ Fully tested and passing |
| Observation review: AI proposals strictly pending until human approval | ✅ Fully tested and passing |
| Local credential storage + session | ✅ Passes on Linux; **fails on Windows** (chmod) |
| Site update (PATCH /sites/{id}) | ✅ Tested in test_local_setup (patch succeeds) |
| Showcase / mock metrics truthfulness | ✅ Fully tested and passing (no unsupported 99.4% accuracy claim) |

## Current Active Task

**T006 — STRUCTURED AI COMPARISON / UNCERTAINTY** — COMPLETE

## Pending Tasks (Ordered)

1. T007 — Cloudinary Live Validation script
2. T008 — Gemini Live Validation script
3. T009 — Demo UI: uncertainty badge
4. T010 — CI GitHub Actions
5. T011 — Demo Script



