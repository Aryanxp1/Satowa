# Setowa backend

Setowa is Team LEX's FastAPI service for cleanup sites, visits, Cloudinary media references, cautious before/after comparisons, reviewer decisions, sourced measurements, and approved-only reports.

From the repository root, run `./run_local.sh`, then open <http://127.0.0.1:8000/>. The guided local setup is in [START_HERE.md](../START_HERE.md), the data flow is in [ARCHITECTURE.md](../ARCHITECTURE.md), and the route sequence is in [EVIDENCE_WORKFLOW.md](EVIDENCE_WORKFLOW.md). Interactive API docs are at <http://127.0.0.1:8000/docs>.

For manual setup: create a Python virtual environment, install `requirements.txt`, copy `.env.example` to ignored `.env`, and run `uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend/`. Keep real credentials out of Git. Run `python -m pytest -q` to check server rules; the tests do not perform real provider calls.
