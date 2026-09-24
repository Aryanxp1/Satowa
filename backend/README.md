# ⚡ Project LEX — Backend & AI Engine

> **Owner:** Farhan Akhtar (Core Backend / Logic & AI Engineer)  
> **Service:** REST API & AI Reasoning Engine for Team LEX (Code Cubicle Hackathon)

---

## 🌟 Highlights

- **FastAPI Core:** High-speed asynchronous Python web framework with auto-generated OpenAPI documentation (`/docs`).
- **Resilient AI Pipeline:** Integrated with Google Gemini API with an **automatic fallback mock mode** (`USE_MOCK=true`) to guard against rate limits or connectivity loss during hackathon demos.
- **Contract-First Mock Routes:** Exposes `/api/v1/mock-stats` and `/api/v1/analyze` out of the box so frontend UI can be built and previewed without waiting for live model keys.
- **CORS Configured:** Pre-configured for Vite/Next.js client development (`localhost:3000`, `localhost:5173`) and Vercel deployments.

---

## 📁 Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization, middleware, routers
│   ├── config.py            # Pydantic Settings & environment variables
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── api.py           # Request & response data models
│   ├── services/
│   │   ├── __init__.py
│   │   └── ai_engine.py     # AI inference handler with mock fallback
│   └── routes/
│       ├── __init__.py
│       ├── health.py        # /api/v1/health endpoint
│       └── analyze.py       # /api/v1/analyze & /api/v1/mock-stats
├── tests/
│   ├── __init__.py
│   └── test_api.py          # Pytest suite
├── .env.example             # Environment template
├── Dockerfile               # Production container definition
├── requirements.txt         # Python dependencies
└── README.md                # Documentation & quickstart
```

---

## 🚀 Quickstart (Local Development)

### 1. Prerequisites
- Python 3.10+
- `pip` or `uv`

### 2. Environment Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create local environment config
cp .env.example .env
```

### 3. Run the Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

- **Interactive API Documentation (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc Docs:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Healthcheck:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **Private evidence demo:** [http://localhost:8000/demo/](http://localhost:8000/demo/) (set `REVIEWER_TOKENS` and Cloudinary credentials in `.env` first)

---

## 🔌 API Endpoints Contract

### 1. Health Check
`GET /api/v1/health`
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development",
  "mock_mode": true
}
```

### 2. Analyze / AI Reasoning
`POST /api/v1/analyze`
- **Request Body:**
```json
{
  "prompt": "Analyze incoming system telemetry for anomalies",
  "task_type": "classification",
  "parameters": {}
}
```
- **Response Body:**
```json
{
  "status": "success",
  "task_type": "classification",
  "source": "mock-engine",
  "result": "[LEX Intelligence Engine (Classification)] ...",
  "confidence": 0.994,
  "latency_ms": 120.0
}
```

### 3. Showcase Live Stats
`GET /api/v1/mock-stats`
```json
{
  "metrics": [
    { "label": "Response Latency", "value": "~120ms", "trend": "Optimized", "status": "positive" },
    { "label": "AI Accuracy", "value": "99.4%", "trend": "High-Confidence", "status": "positive" },
    { "label": "Automation Gain", "value": "10x", "trend": "Time Saved", "status": "positive" }
  ],
  "timestamp": "2026-09-17T23:00:00Z"
}
```

---

## 🧪 Running Tests

```bash
pytest
```

## Cloudinary image ingestion (private demo)

Install `requirements.txt` and set `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`,
`CLOUDINARY_API_SECRET`, and a random `MEDIA_UPLOAD_TOKEN` in the server environment
or local `.env`. The Cloudinary key needs image upload/create permission.
Never commit credentials.json or real secrets. AI `USE_MOCK` has no effect on uploads.

### Frontend contract

`POST /api/v1/media/images` uses multipart form data and
`Authorization: Bearer <MEDIA_UPLOAD_TOKEN>`. Required fields:

| Field | Contract |
| --- | --- |
| `file` | One JPEG, PNG or WebP; matching MIME; 1 byte–10 MiB; single frame; at most 25 megapixels |
| `project_id` | 1–64 lowercase letters, digits, `_` or `-`; first character alphanumeric |
| `source` | 1–200 characters; nonblank attribution/permission reference |
| `visit_date` | ISO date, e.g. `2026-09-23`; supplied by uploader, not independently verified |

Success (`201`) returns `asset_id`, `public_id`, `version`, `resource_type`,
`format`, `width`, `height`, `secure_url`, `thumbnail_url`, `tags`, and `context`.
Context contains the submitted project, source, visit date, and original SHA-256.
The thumbnail is a versioned, maximum 640×480 optimized derivative; the original
is retained. Each request creates a unique asset without overwriting existing media.
The response is the handoff to the UI; database persistence is not implemented.

Errors: `401` invalid token, `413` file too large, `415` unsupported/mismatched type,
`422` invalid image or fields, `503` missing server configuration, `502` Cloudinary
failure. A provider timeout can occur after storage: inspect Cloudinary before
retrying, since retries create new assets. No fabricated success or mock fallback.

Use a private demo client/server proxy to supply the token; do not embed it in a
public frontend bundle. Before internet deployment, add user authentication,
rate limits, and a reverse-proxy request-body limit (e.g. 11 MiB including multipart
overhead). The application limits file reads, but multipart parsing can spool a
larger request before the route validates it. Assets use public Cloudinary delivery:
upload only media explicitly permissioned for public demo use.

Validation: `python -m pytest -q`. Cloudinary is mocked in API tests; tests do not
consume credits. A separate SDK smoke test validated upload, metadata/tags and a
320×180 delivered transformation using a synthetic image. Video ingestion,
semantic search, before/after comparison and impact reporting remain separate work.

The site/visit, before-and-after, review, and report API contract is in
[EVIDENCE_WORKFLOW.md](./EVIDENCE_WORKFLOW.md).
