# DECISIONS.md — Setowa / LEX Architecture Decisions
# Updated: 2026-09-26

## Decision Log

| ID | Date | Decision | Rationale | Decided By |
|:---|:---|:---|:---|:---|
| D001 | 2026-09-25 | Accept `unreliable` as 4th review state for now; map to `pending` in T002 | Audited code uses `unreliable`; master spec shows 3 states. Mapping is clean. | AGY + Aryan |
| D002 | 2026-09-25 | No microservices, Redis, vector DB, MomentSearch, SentrySearch | Hackathon scope; existing single-process FastAPI is correct | Aryan |
| D003 | 2026-09-25 | Report generation must have zero LLM calls | Trust model integrity | Aryan |
| D004 | 2026-09-25 | Cline = Builder; AGY = Architect. No role inversion. | Avoids conflicting code edits | AGY + Aryan |
| D005 | 2026-09-26 | Windows chmod failure in test_local_setup is a known baseline; NOT fixed in app code | OS limitation; CI runs on Linux where it passes | AGY |
| D006 | 2026-09-26 | `permission_status` column defaults to `'granted'` (not `NULL`) | Keeps existing demo flow working; backward compatible | AGY |
| D007 | 2026-09-26 | Do NOT rewrite the pair validation logic | It satisfies all 17 product rules; zero regressions | AGY |
| D008 | 2026-09-26 | Structured AI Comparison Contract (4-state: `changed`, `unchanged`, `uncertain`, `insufficient_evidence`) with bounded confidence [0.0, 1.0], controlled uncertainty vocabulary, rejection of quantitative claims, and mandatory human review | AI is a proposal engine, not a source of truth. Model confidence is not accuracy. Visual observations must be distinct from measurements. Human approval is strictly required before an observation is included in reports. | AGY + Aryan |
| D009 | 2026-09-26 | Live vs. Deterministic Integration Separation for Cloudinary & Gemini Pipeline | Deterministic unit tests cover the full Error Matrix (A through J) with explicit mocks. Live end-to-end testing against real Cloudinary and Gemini APIs is gated strictly by `RUN_LIVE_INTEGRATION=1` and skips cleanly when live credentials are absent or placeholder values. Secret hygiene is enforced (no secrets in logs or APIs, no local binary caching). AI proposals remain strictly pending until human approval, and evidence mutations immediately invalidate approvals. | AGY + Aryan |
| D010 | 2026-09-26 | Judge-Facing Review Experience & In-Page Evidence Verification UI | Expose backend AI proposals, visual comparison, provenance metadata, uncertainty UX, human review workflow (approve/edit/reject), and live report generation in the vanilla JS demo client. AI proposals are visually and structurally distinguished from human verified records. Live report preview excludes unapproved proposals. Approvals are immediately invalidated upon observation edits. Tested via deterministic UI unit tests (11 tests). | AGY + Aryan |
| D011 | 2026-09-26 | Demo Hardening, Loading UX, and End-to-End QA | End-to-end judge flow hardened with full loading and disabled button states to prevent double submission across all network operations (uploads, comparisons, reviews, exports). Error sanitization prevents raw stack traces and leaks. Zero-feature-addition discipline maintained: no vector DB, RAG, or new architectures. Complete 9-test E2E suite (`test_e2e_journey.py`) verifies clean-slate DB, judge happy path, lifecycle invalidation, chronological & permission checks, 409 conflict handling, and uncertainty preservation. Demo runbook (`docs/DEMO_RUNBOOK.md`) created with strict judge safety guidelines ("AI-generated visual assessment", "Human-verified observation"). | AGY + Aryan |


