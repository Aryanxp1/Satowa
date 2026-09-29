# Release candidate status — 2026-09-29

This is an implementation checkpoint, not a declaration that the complete execution brief is finished. Base: main `49c50f8`; branch: `codex/setowa-release-candidate`.

## Implemented in this branch

- Optional NVIDIA embedding adapter, strict response checks, bounded retry and safe failure messages.
- Explicit bounded indexing; search performs no background document embedding. Honest FTS5 fallback.
- Registered/granted single-image and frame NVIDIA analysis; version/model/schema-aware intelligence cache.
- Gemini no longer gates readiness; no external AI is needed for manual workflows.
- Stale campaign bodies and links withheld when source fingerprint changes.
- Corrected independent-audit language and upload/capture-date labels.
- Hosted showcase fallback, explicit CORS, CSP/security headers, request IDs.
- Optional PostgreSQL adapter and versioned schema initializer; no private data import.
- SQLite backup with disposable restore verification, dependency pins, test CI, local FTS benchmark.

## Verified

- Baseline: 309 passed / 1 skipped. Updated suite: 317 passed / 2 opt-in live tests skipped; PostgreSQL integration separately passed.
- PostgreSQL: empty public schema inspected, schema initialized; disposable-schema integration passed (migration repeat, parameters, reconnect persistence, rollback). The PostgreSQL API lifecycle also passed: visit, pair, manual approval, report, campaign and revoked-source suppression. No production records used for the test.
- SQLite backup/restore integrity and table counts passed; original database unchanged.
- Local browser: synthetic media workspace and no-key keyword discovery return source-linked results, visibly labeled as keyword mode.
- Dependency audit of pinned requirements: no known vulnerabilities reported at execution time. This is not a security certification.

## Outstanding release gates

- Live NVIDIA vision/embedding success and model capability evaluation. Rotated key is in Render, not local; no live success claimed.
- Full account authentication (Argon2id passwords, admin/reviewer/viewer roles, project ACLs, secure sessions, CSRF, rate limiting).
- Full PostgreSQL API/browser parity, hosted restart/redeploy verification, backup/restore drill, and Render DATABASE_URL configuration.
- Real permissioned field-pair dataset and labeled real-world AI evaluation.
- End-to-end campaign/share/revocation validation of this deployed revision, complete mobile/accessibility QA, video-format/abuse audit.
- True collection/end-to-end concurrency benchmarks and hosted performance measurements.
- Final secret/dependency/security gates, dev/main promotion and hosted smoke checks before any release tag.

Existing token pilot behavior remains supported. Production mode refuses startup while production authorization is incomplete. No paid service was enabled.
