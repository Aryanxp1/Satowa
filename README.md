# Setowa · by Team LEX

Setowa turns field photos and videos into traceable sustainability evidence. Cloudinary stores originals, optional AI interprets visual signals, people review proposed observations, and saved approved evidence becomes reports, timelines, and campaign drafts.

**Current release state: single-reviewer pilot, not a completed production release.** See [PROJECT_STATUS.md](PROJECT_STATUS.md) for verified results and outstanding gates. Synthetic walkthrough images are not real field impact.

## Run locally

```bash
./run_local.sh
```

Open http://127.0.0.1:8000/demo/. Local credentials belong in ignored `credential.json` at the repository root or `backend/.env`. Never commit credentials or local databases. Cloudinary uploads work independently of AI. With no NVIDIA key, manual observations, review, reports, template campaigns, and keyword discovery remain available.

## Providers and discovery

- NVIDIA is the default optional visual/embedding provider. Configuration placeholders are in [backend/.env.example](backend/.env.example).
- `POST /api/v1/projects/{id}/search-index` explicitly indexes at most 24 records. It uses passage embeddings; queries use query embeddings. Search itself never indexes the collection.
- `POST /api/v1/projects/{id}/semantic-search` uses current cached vectors when available. Provider failure or an empty index returns **labeled SQLite FTS5 keyword search**, not simulated semantic results.
- Permission changes, edits, review state changes, and model changes invalidate affected cached vectors on the next retrieval/index operation.
- Visual analysis only sends registered, permission-granted Cloudinary evidence to NVIDIA. Its outputs remain unreviewed. Automatic NVIDIA two-image comparison is not enabled until live behavior is validated; manual comparison remains supported.
- Gemini is optional legacy support (`AI_PROVIDER=gemini`) and is not required for readiness. Campaigns use deterministic templates rather than an external generation call.

## Evidence rules

Same site and valid before/after dates are required. Approval is never automatic. Editing text or evidence invalidates approval. Reports use saved approved text; quantities require recorded sources. Stale campaign drafts with changed sources withhold their old text and links. Reviewer approval is not independent certification.

## Storage and hosting

SQLite remains the local default and is ephemeral on a free Render filesystem. Optional `DATABASE_URL` selects PostgreSQL; initialize it with `cd backend && .venv/bin/python scripts/migrate_postgres.py`. This creates schema, not an import of local/private data. See [DEPLOYMENT.md](DEPLOYMENT.md).

The existing reviewer-token pilot is supported. Account/password authentication with admin/reviewer/viewer project permissions remains outstanding. Production mode is deliberately blocked until those release gates are implemented and verified.

## Verification

```bash
backend/.venv/bin/python -m pytest -q backend/tests
node --check backend/app/demo/app.js
backend/.venv/bin/python backend/scripts/benchmark_discovery.py
```

Tests isolate their databases and clear live NVIDIA/Postgres configuration. Opt-in PostgreSQL tests use a disposable schema. [EVALUATION.md](EVALUATION.md) distinguishes local synthetic benchmarks from real AI evaluation.

Changes go through feature branches → `dev` → `main`. Preserve history and provenance. The repository remains private; Setowa is the product and LEX is the team.
