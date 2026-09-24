# Cleanup evidence workflow API

The private demo API uses `Authorization: Bearer <MEDIA_UPLOAD_TOKEN>` for all
workflow routes. Records persist to SQLite at `LEX_DB_PATH` (default
`./lex.sqlite3`, relative to the process working directory). Mount a persistent
volume in deployment. The shared token is not a user identity system; `actor`
and `reviewer` are labels supplied by the caller.

Call these endpoints in order:

1. `POST /api/v1/sites` with `{"id":"river","name":"River Bend"}`.
2. `POST /api/v1/sites/river/visits` twice with
   `{"visited_on":"2026-09-01","label":"Before"}` and a later date. Each
   response has a visit `id`.
3. `POST /api/v1/media/images` with the existing multipart fields plus
   `visit_id`. The `project_id` must be the site ID and `visit_date` must match
   `visited_on`. Uploads without `visit_id` keep the old behavior but cannot be
   selected as evidence until registered with a visit.
4. `GET /api/v1/sites/river/visits` lists visits and saved Cloudinary assets.
   `POST /api/v1/pairs` with
   `{"before_asset_id":"...","after_asset_id":"..."}` validates the same
   site and strictly ordered visit dates, then stores one observation. The
   response contains `ai_draft`, `working_text`, `review_status`, and
   `reliability_reason`.
5. `PATCH /api/v1/observations/{id}` with `actor` plus `working_text` or
   changed evidence IDs edits the observation. Every actual edit clears
   approval. Changing evidence clears the old AI draft and requires manual
   review of the new pair.
6. `POST /api/v1/observations/{id}/review` with
   `{"decision":"approve","reviewer":"Farhan","text":"..."}` or
   `{"decision":"reject","reviewer":"Farhan"}`. Approval requires
   nonblank text. `GET /api/v1/observations/{id}` returns persisted text and
   revision events. `GET /api/v1/sites/river/observations` lists site records.
7. `GET /api/v1/sites/river/report` returns JSON with only approved
   observations, original Cloudinary URLs and asset versions. Add
   `?format=markdown` to download a human-readable report. The measurements
   array is empty until a recorded measurement feature exists; photos never
   imply waste mass.

Comparison uses Gemini only when `GEMINI_API_KEY` is set. It sends two stored
Cloudinary images to `GEMINI_VISION_MODEL`, which must return a structured JSON
judgment. If configuration, image retrieval, model response, or visual evidence
is inadequate, the observation is saved as `unreliable` with no AI draft and
an explanation. A human can write and approve their own text after inspecting
photos. The older `/api/v1/analyze` mock behavior is separate and does not
create cleanup claims. Tests mock Cloudinary and Gemini; no live image
comparison has been verified. The frontend should show uncertainty and never
present an AI draft as an approved finding.

Upload only photos permissioned for public Cloudinary delivery. Image bytes are
sent to Gemini for comparison when configured. A public app needs user
accounts, rate limits, backups, database migrations, and a persistent database
service.
