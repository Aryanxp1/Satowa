# Setowa single-reviewer Render pilot

This is a short-lived, private-team demo configuration. The browser asks for one named reviewer token and keeps it only in tab memory. Every remote `/api/v1/` route except health and readiness requires that token, including older Skills and Workflows routes. The local credential editor is unavailable remotely.

## Configure the existing Render web service

Use the service already connected to this GitHub repository. Set its branch to the tested release branch. For a Python service rooted at `backend`, use `pip install -r requirements.txt` as the build command and `uvicorn app.main:app --host 0.0.0.0 --port $PORT` as the start command. For a Docker service, keep the existing `backend/Dockerfile` build configuration. Do not create a paid service or disk without asking Farhan.

Set these environment variables in Render's private dashboard, never in Git:

| Variable | Pilot value |
| --- | --- |
| `ENVIRONMENT` | `pilot` |
| `LOCAL_DEMO` | `false` |
| `REVIEWER_TOKENS` | JSON mapping one reviewer name to one long random token, for example `{"Farhan":"<generate-a-unique-random-token>"}` |
| `GEMINI_API_KEY` | Your Gemini key, required for semantic search |
| `USE_MOCK` | `false` for real Gemini comparisons, or `true` if using only the synthetic walkthrough |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Your Cloudinary project credentials for new uploads |
| `ALLOWED_ORIGINS` | Your public Render origin, for example `https://your-service.onrender.com` |

`MEDIA_UPLOAD_TOKEN` can remain unset because the named reviewer token also authorizes media routes. Keep `REVIEWER_TOKENS` private; enter only its token value in the browser's pilot form. Cloudinary and Gemini credentials are server-side only.

Render's free local filesystem can be reset on redeploy or restart. This pilot still uses SQLite, so new visits, approvals, semantic embeddings, and campaign drafts **are not durable** there. Keep the authoritative local database backed up, and do not treat the hosted pilot as a permanent archive. Supabase/Postgres migration and account-based access remain separate work.

## Verify after deployment

1. Open the public `.onrender.com` URL. Confirm the pilot token form appears; the local credential editor must be hidden.
2. Check `/api/v1/health` responds, then verify `/api/v1/projects` returns `401` without the token. Do not put the token in a URL.
3. Enter the named token in the form, open a project, and check the Media, Review, Discover, and Campaign tabs. A fresh hosted SQLite database may have only an empty project until demo data is seeded or permissioned media is uploaded.
4. With a Gemini key configured, search a project with records. The UI should show indexed/total coverage and source links. Use “Index the next 24 records” until coverage is complete. Each batch uses Gemini quota; stop if the account leaves its free allowance.
5. Confirm only approved observations and sourced measurements appear in reports or campaign drafts. Do not publish a synthetic or unverified story as real impact.

`/api/v1/ready` checks database connectivity and whether provider keys are configured; it does not prove that a live provider request succeeded. Keep the hosted URL within the team because this is a shared-token pilot rather than public user authentication.
