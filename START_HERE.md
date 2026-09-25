# LEX: start here

LEX is a cleanup evidence app for Code Cubicle's Cloudinary problem statement.
It links field images to dated visits, helps compare a before/after pair, keeps
AI suggestions separate from human decisions, and exports only reviewed
observations and measurements a person explicitly entered.

## What we have done so far

1. **Started with Aryan's LEX repository.** We inspected its branches,
   planning files, backend scaffold, showcase, and submission material. The
   original documents assigned Aryan integration, Farhan backend/AI, and Shubh
   UI/showcase responsibilities.
2. **Selected one problem statement.** Of the three supplied challenges, LEX
   now focuses on the Cloudinary impact and sustainability media platform.
   The organizer's message said combining problem statements was not allowed.
3. **Narrowed the product.** Instead of trying to build many disconnected AI
   features, the team defined one demo path: visits → before/after evidence →
   draft → human review → report. Photos alone must never imply kilograms of
   waste or environmental impact.
4. **Built the first backend.** FastAPI gained Cloudinary image upload with
   source metadata, SQLite site/visit/asset records, pair validation, cautious
   Gemini comparison, observation revisions, and an approved-only report.
5. **Moved to Farhan's repository.** The working GitHub repository is
   [farhanakhtar0x66/LEX](https://github.com/farhanakhtar0x66/LEX). The earlier
   Aryan repository remains separate. The new repository began from a snapshot
   of existing work; its short commit history does not mean the work began
   there. Disclose earlier work according to the event's rules.
6. **Made review safer.** Named reviewer tokens identify edit/review actions.
   Version checks reject stale approvals. PR
   [#1](https://github.com/farhanakhtar0x66/LEX/pull/1) targets `dev` and is
   open for review.
7. **Built this local walkthrough.** The showcase now explains the real
   product. The app has a seeded synthetic riverbank project, before/after
   viewing, review actions, media filtering, optional source-backed
   measurements, and report export. The sample images are not field evidence.

## Run it on this Mac

From the repository root:

```bash
./run_local.sh
```

The script creates `backend/.venv`, installs the Python requirements, creates
a local reviewer token in gitignored `backend/.env` if needed, seeds the sample
project, and starts FastAPI on `127.0.0.1:8000`. On first setup it prints the
new token once so you can paste it into the app. If `.env` already has reviewer
tokens, use one of those instead. Open:

- Landing page: <http://127.0.0.1:8000/showcase/>
- Working app: <http://127.0.0.1:8000/demo/>
- API docs: <http://127.0.0.1:8000/docs>

In the app, connect with your reviewer token, open **demo-riverbank**, inspect
the sample pair, approve or edit the proposed human-written observation, and
download the Markdown report. The report marks synthetic evidence clearly.

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

Leave `gemini.api_key` empty if you do not have one yet. Restart `./run_local.sh`
after editing the file. Existing environment variables or `backend/.env`
values take priority over the JSON file. Never put keys in JavaScript or Git.

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
