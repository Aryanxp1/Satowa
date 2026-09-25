# Setowa evidence API

The local app is at `http://127.0.0.1:8000/demo/`; run `./run_local.sh` from the repository root. API docs are at `/docs`. The script creates a loopback-only reviewer session and a clearly labeled synthetic project. The sample does not call Cloudinary or Gemini.

For API clients, configure `REVIEWER_TOKENS` as a JSON map of names to distinct tokens in ignored `backend/.env`. Send `Authorization: Bearer <token>`. The server derives the reviewer name from the token. `MEDIA_UPLOAD_TOKEN` is retained for upload/read access but cannot approve or edit observations. The browser's local session uses an HttpOnly cookie on loopback; it is not production authentication.

## Workflow

1. `POST /api/v1/sites` creates a site; `GET /api/v1/sites` lists projects. `PATCH /api/v1/sites/{id}` edits site details.
2. `POST /api/v1/sites/{id}/visits` records dated visits. `GET /api/v1/sites/{id}/visits` returns visits and registered assets.
3. `POST /api/v1/media/images` accepts a permissioned JPEG/PNG/WebP, `project_id`, `source`, `visit_date`, and `visit_id`. The server checks the visit belongs to that site and date, then uploads to Cloudinary. The application stores original public ID, version, and secure URL.
4. `POST /api/v1/pairs` takes `before_asset_id` and `after_asset_id`. Different assets, the same site, and strictly earlier-before-later visits are mandatory. It stores an observation with an AI draft when reliable or an explicit `unreliable` status/reason when not.
5. `PATCH /api/v1/observations/{id}` edits working text or evidence with `expected_version`. Any actual edit invalidates prior approval; changing evidence also clears the old AI draft.
6. `POST /api/v1/observations/{id}/review` accepts `decision: approve|reject`, `expected_version`, and approved `text` when approving. A stale version returns `409`. `GET /api/v1/observations/{id}` includes revision history.
7. `GET /api/v1/sites/{id}/report` returns JSON from saved approved observations; `?format=markdown` downloads a report. Original evidence references are included. Pending, unreliable, and rejected observations never enter the report.
8. `POST /api/v1/sites/{id}/measurements` stores a positive quantity, unit (`kg`, `bags`, `items`), visit, source, and reviewer. Measurements are never inferred from photos.

## Provider and reliability behavior

Cloudinary is the source of truth for uploaded originals. Gemini is optional and receives selected images only when configured. When credentials, image retrieval, model output, or visual comparison are inadequate, Setowa records uncertainty instead of a confident change. A human can write and approve their own observation after inspecting the media. The legacy `/api/v1/analyze` mock route is separate from this evidence workflow.

Tests mock both providers. No real cleanup pair has yet been validated in this repository. To evaluate live comparison, put private asset IDs and human comparability labels in a copy of `scripts/evaluation.example.json` outside Git, then run `python scripts/evaluate_pairs.py /path/to/private-pairs.json` from `backend/`. Include comparable and deliberately poor pairs. A correct reliability label does not prove the wording of an AI draft; review every sentence.

SQLite defaults to `backend/lex.sqlite3` when run from `backend/`. It and `credential.json`/`.env` are ignored. Public deployment needs user accounts, authorization, rate limits, persistent storage, backups, migrations, and an explicit media-permission review.
