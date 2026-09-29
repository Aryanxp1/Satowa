# Setowa architecture

The FastAPI service serves the HTML/CSS/JavaScript workspace at `/demo/`, protected APIs under `/api/v1`, and read-only published story pages under `/share/`. Cloudinary stores original media and derives display/video-frame URLs. Application records store identity, version, source, permission, site, and visit references.

## Evidence model

Project → Site → Visit → Asset. Observations link a dated before/after asset pair. Draft text, working text, approved text, review state, reviewer identity, timestamps, and optimistic version are separate records/fields. Measurements reference visits and explicitly supplied measurement sources. Reports query saved approved records and current media permission. Campaign templates use approved observations and sourced measurements; changed source fingerprints suppress stale draft contents.

## Providers

`app/providers/nvidia.py` centralizes NVIDIA requests: server-side SecretStr key, fixed HTTPS host, bounded timeout, at most three attempts for 429/5xx, sanitized failures, strict vector/vision validation. No API key is delivered to the browser. Vision URLs are resolved from registered granted assets/frames, never accepted as arbitrary provider inputs.

The primary visual path uses one image at a time. Automatic NVIDIA pair comparison is deliberately unavailable pending a live two-image contract test. The optional legacy Gemini implementation remains selectable. Neither external provider is required for manual review or readiness.

## Retrieval

The permission-filtered document set comprises media metadata, unreviewed visual descriptions, video frame observations, approved comparisons, and sourced measurements. Explicit index requests embed at most 24 documents in passage mode; queries embed only the query. Content/evidence/review fingerprints and the embedding model identify cache entries. Retrieval removes obsolete cache entries before ranking.

If vectors or the provider are unavailable, an in-memory FTS5 index searches the current allowed text. This rebuild costs CPU proportional to collection size. It is not semantic search. Indexed/total coverage remains visible. Neither rank score nor model confidence is an accuracy estimate.

## Persistence

`evidence_store.connection()` defaults to SQLite and its existing local migrations. A nonempty `DATABASE_URL` uses the psycopg repository adapter. `scripts/migrate_postgres.py` applies version 1 under an advisory transaction lock. SQL translation is limited to audited repository syntax: positional/named parameters, INSERT OR IGNORE, identity columns, and review transaction locking. PostgreSQL review edits lock the observations table to preserve the current read-modify-write behavior; row-level optimization remains future work.

Supabase connection, migration idempotence, reconnect persistence, rollback, and parameter handling have passed a disposable-schema integration test. Full API/browser parity and a PostgreSQL backup/restore drill are still release gates. No local private data is automatically copied to Supabase.

## Access and operating modes

The current remote pilot gates APIs with a named reviewer token held in tab memory. The local session/credential editor is loopback-only. Public health/readiness expose configuration states, not credentials. Public story pages project only eligible current evidence.

Full account authentication, per-project roles, login rate limiting, and session CSRF verification are not implemented by this change. Production startup is blocked rather than presenting the pilot as multi-user production. CORS no longer falls back to a wildcard; workspace/story pages have CSP and response security headers.

PostgreSQL migration 2 enables row-level security on every Setowa table, with no public policies. Supabase anon/authenticated Data API roles must not bypass FastAPI authorization. Use the trusted server database connection only; never expose it in browser code.
