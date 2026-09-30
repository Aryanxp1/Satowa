# Setowa: start here

Setowa is Team LEX's cleanup evidence app for Code Cubicle's Cloudinary problem statement.
It links field images to dated visits, helps compare a before/after pair, keeps
AI suggestions separate from human decisions, and exports only reviewed
observations and measurements a person explicitly entered.

## What we have done so far

1. **Started with Aryan's LEX repository.** We inspected its branches,
   planning files, backend scaffold, showcase, and submission material. The
   original documents assigned Aryan integration and backend/AI, and Shubh
   UI/showcase responsibilities.
2. **Selected one problem statement.** Of the three supplied challenges, Setowa
   now focuses on the Cloudinary impact and sustainability media platform.
   The organizer's message said combining problem statements was not allowed.
3. **Narrowed the product.** Instead of trying to build many disconnected AI
   features, the team defined one demo path: visits → before/after evidence →
   draft → human review → report. Photos alone must never imply kilograms of
   waste or environmental impact.
4. **Built the first backend.** FastAPI gained Cloudinary image upload with
   source metadata, SQLite site/visit/asset records, pair validation, cautious
   Gemini comparison, observation revisions, and an approved-only report.
5. **Maintained in Aryan's repository.** The working GitHub repository is
   [Aryanxp1/Satowa](https://github.com/Aryanxp1/Satowa). The repository
   contains the full backend, showcase UI, evaluation records, and demo assets.
6. **Made review safer.** Named reviewer tokens identify edit/review actions.
   Version checks reject stale approvals. Feature work is reviewed through
   pull requests into `dev` under the team's workflow.
7. **Built this local walkthrough.** The showcase now explains the real
   product. The app has a seeded synthetic riverbank project, before/after
   viewing, review actions, media filtering, optional source-backed
   measurements, and report export. The sample images are not field evidence.
8. **Named the product Setowa.** *Setu* (bridge) and *Wa* (harmony) describe
   the link between field media and a shared, supportable account of change.
   LEX remains the team name.

## Run it on this Mac

From the repository root:

```bash
./run_local.sh
```

The script creates `backend/.venv`, installs the Python requirements, creates
a local reviewer token in gitignored `backend/.env` if needed, seeds the sample
project, and starts FastAPI on `127.0.0.1:8000`. Open:

- Setup, projects, and working app: <http://127.0.0.1:8000/>
- Project story: <http://127.0.0.1:8000/showcase/>
- API docs: <http://127.0.0.1:8000/docs>

The first page shows provider readiness and can save Cloudinary/Gemini keys to
the private local file. Click **Open projects**; the loopback-only app creates
an HttpOnly local reviewer session, so you do not need to copy a token into the
browser. Open the highlighted synthetic sample, follow **Your next step** to
review its observation, then open **Report** and download the Markdown file.
The sample report marks synthetic evidence clearly. For the system boundaries, see [ARCHITECTURE.md](ARCHITECTURE.md); for Aryan's acceptance criteria and current status, see [LEX_Milestone.md](LEX_Milestone.md). New projects can record a
name, location, description, dated visits, photos, observations, and sourced
measurements. The theme switch persists light/dark preference in this browser.

## Turn on live services

Fill the gitignored `credential.json` at the repository root. It uses the same
shape as `credential.example.json`:

```json
{
  "cloudinary": {
    "cloud_name": "your-cloud-name",
    "api_key": "your-api-key",
    "api_secret": "your-api-secret"
  },
  "gemini": {
    "api_key": "your-gemini-key"
  }
}
```

Leave `gemini.api_key` empty if you do not have one yet. If you edit the JSON
file manually, restart `./run_local.sh`; saving via the local setup page applies
keys immediately. Existing environment variables or `backend/.env` values take
priority over the JSON file. The setup API is restricted to this Mac's loopback
browser and returns readiness flags, never provider keys. Never put keys in Git.

Cloudinary upload uses signed server-side SDK calls. With its three fields
configured, create a new site and dated visits, then upload photos that you
have permission to use on Cloudinary. Gemini is optional: without a real key,
the comparison says it cannot draft an AI finding and a person may write the
observation manually. The supplied synthetic photos never trigger an AI call
or a Cloudinary upload.

You can check Cloudinary credentials without uploading anything by running
`python scripts/check_cloudinary.py` from `backend/` with the local virtual
environment active.

The live-image evaluation helper is documented in
[`backend/EVIDENCE_WORKFLOW.md`](backend/EVIDENCE_WORKFLOW.md). No real cleanup
photo pair or live Gemini comparison has been validated yet. The local demo
database is `backend/lex.sqlite3` and is gitignored.
