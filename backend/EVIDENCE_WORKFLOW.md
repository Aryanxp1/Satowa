# Cleanup evidence workflow API

Open the private demo page at `http://localhost:8000/demo/`. Configure
`REVIEWER_TOKENS` as a JSON map of reviewer names to distinct secret tokens,
for example `{"Farhan":"replace-with-long-random-token"}`. Use one of these
tokens as `Authorization: Bearer <token>` for the demo workflow. The older
`MEDIA_UPLOAD_TOKEN` still works for uploads and read access, but cannot edit
or review observations. The server derives reviewer names from the token;
request bodies cannot choose a reviewer. Tokens are held in page memory and
must be entered again after a reload.

Records persist to SQLite at `LEX_DB_PATH` (default `./lex.sqlite3`, relative
to the process working directory). Mount a persistent volume in deployment.
Named demo tokens are a small step toward attribution; they are not full user
accounts, and anyone sharing a token can act as its owner.

Call these endpoints in order:

1. `GET /api/v1/sites` lists saved sites. `POST /api/v1/sites` creates one
   with `{"id":"river","name":"River Bend"}`.
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
5. `PATCH /api/v1/observations/{id}` with `expected_version` plus
   `working_text` or changed evidence IDs edits the observation. For example,
   `{"expected_version":1,"working_text":"Less visible litter"}`. Every
   actual edit increments `version` and clears approval. Changing evidence
   clears the old AI draft and requires manual review of the new pair.
6. `POST /api/v1/observations/{id}/review` with
   `{"decision":"approve","expected_version":1,"text":"..."}` or
   `{"decision":"reject","expected_version":1}`. Approval requires
   nonblank text. The server returns `409` if the version changed since the
   reviewer loaded it; reload before retrying. `GET /api/v1/observations/{id}`
   returns persisted text and revision events. `GET
   /api/v1/sites/river/observations` lists site records.
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

### Evaluating actual comparisons

With permissioned photos uploaded to different visits at the same site and a
working `GEMINI_API_KEY`, copy `scripts/evaluation.example.json` outside the
repository, replace the asset IDs, and mark whether a careful human thinks the
pair is comparable. From `backend/`, run
`python scripts/evaluate_pairs.py /path/to/private-pairs.json`. The script calls
the real Cloudinary and Gemini services and reports which reliability decisions
matched the human labels. Include both comparable and deliberately poor
viewpoint/lighting pairs. Do not use a matching reliability label as proof that
the drafted observation is factually correct; a reviewer still checks the text.
No real cleanup photo pair was available for validation during this change.
