# Deployment

This branch supports a single-reviewer pilot. Do not set `ENVIRONMENT=production` yet: production account authorization remains unfinished and startup is deliberately blocked.

Render Docker root: `backend`; Dockerfile relative to that root: `Dockerfile`. Render supplies `PORT`. Health path `/api/v1/health`; readiness `/api/v1/ready` reports configuration presence, not proof a provider accepts its key.

| Variable | Pilot value |
|---|---|
| ENVIRONMENT | pilot |
| LOCAL_DEMO | false |
| USE_MOCK | false |
| AI_PROVIDER | nvidia |
| REVIEWER_TOKENS | `{"Aryan":"ptMAR0cW8MYHQda3CgG3uli7HMJ5r8R_WQS_MOyFTsuARg0Lwto6gXwogc-S2rrO"}` |
| CLOUDINARY_CLOUD_NAME | `<cloud-name>` |
| CLOUDINARY_API_KEY | `<server-key>` |
| CLOUDINARY_API_SECRET | `<server-secret>` |
| NVIDIA_API_KEY | `<optional-server-key>` |
| ALLOWED_ORIGINS | `https://setowa.onrender.com` |
| DATABASE_URL | `<PostgreSQL-session-pooler-connection-string>` |

Leave MEDIA_UPLOAD_TOKEN unset when named reviewers authorize uploads. Leave Gemini keys unset for NVIDIA/manual operation. NVIDIA base and model defaults are in `.env.example`; override only after checking capability. Same-origin frontend requests do not need CORS permission, but setting the exact deployed origin is explicit and safe.

Before switching storage, initialize the dedicated PostgreSQL database using `scripts/migrate_postgres.py`, then set the same DATABASE_URL in Render secret settings. The migration does not transfer old SQLite data. No paid disk is required. Do not commit or paste a connection string into logs/chat. PostgreSQL integration tests use `SETOWA_POSTGRES_TEST_URL` and create/drop only a uniquely named test schema.

Without DATABASE_URL, SQLite remains ephemeral and this must be disclosed in the demo. Back up local SQLite with `scripts/backup_sqlite.py SOURCE NEW_DESTINATION`. A PostgreSQL backup/restore drill and complete hosted journey remain mandatory before claiming durable production readiness.

PostgreSQL migration 2 enables row-level security on every Setowa table, with no public policies. Supabase anon/authenticated Data API roles must not bypass FastAPI authorization. Use the trusted server database connection only; never expose it in browser code.
