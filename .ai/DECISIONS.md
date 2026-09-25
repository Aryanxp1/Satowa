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

