# Setowa backend

Setowa is Team LEX's cleanup-evidence app. This FastAPI service stores sites, dated visits, media records, before/after observations, reviewer decisions, and sourced measurements in SQLite. It exports reports from approved records only.

From the repository root, run `./run_local.sh` and open <http://127.0.0.1:8000/>. See [START_HERE.md](../START_HERE.md) for the guided synthetic walkthrough and private provider setup. API documentation is at <http://127.0.0.1:8000/docs>.

Cloudinary uploads use server-side signed calls. Gemini comparison is optional and may return an explicit uncertainty or unavailable result. The seeded sample uses synthetic images and does not call either provider. Store credentials only in ignored `credential.json` or `backend/.env`; never commit them.

The main API routes live in `app/routes/evidence.py`, `media.py`, `local_setup.py`, `analyze.py`, and `health.py`. Tests are in `tests/`. Run them with `python -m pytest -q` from `backend/` after installing `requirements.txt`.
