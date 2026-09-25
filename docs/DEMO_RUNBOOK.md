# LEX Demo Runbook

This document provides a concise, step-by-step guide to run and present the LEX (Land Evidence Exchange) verification workflow for judges and evaluators.

---

## 1. Prerequisites

- **Python**: 3.11+ (with `venv`)
- **Web Browser**: Modern Chromium, Firefox, or Safari
- **Optional CLI Utilities**: `curl`, `bash` (for `run_local.sh`), `node` (for linting demo JS)
- **External Accounts (Optional for live mode)**:
  - Cloudinary account (Cloud name, API Key, API Secret)
  - Google Gemini API Key

*Note: In local simulated mode, no external credentials or network connectivity are required.*

---

## 2. Environment Variables

> **CRITICAL SECURITY RULE:** Never commit or hardcode credential values. Store in `.env` (ignored by git) or set directly in your shell environment.

Required/supported variable names:

| Variable Name | Purpose | Required in Mock Mode? |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini multimodal AI evaluation | No (falls back to local/mock) |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary asset hosting cloud name | No |
| `CLOUDINARY_API_KEY` | Cloudinary API access key | No |
| `CLOUDINARY_API_SECRET` | Cloudinary API access secret | No |
| `LEX_PORT` | Port for the backend service (default: `8000`) | No |
| `LEX_DB_PATH` | Path to SQLite database (default: `lex.sqlite3`) | No |
| `LEX_UPLOAD_SECRET` | Secret token required for review/upload mutations | No (defaults to local development token) |

---

## 3. Backend Startup

### Standard Single-Command Launch (Recommended)
From repository root:
```bash
./run_local.sh
```

### Manual Fresh Start (Cross-Platform)
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
python scripts/setup_local_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Verify backend is healthy:
- Navigate to: `http://localhost:8000/health` (or `http://127.0.0.1:8000/demo/`)

---

## 4. Frontend Startup

The judge review interface is served directly from the FastAPI application as static, zero-dependency HTML/CSS/JavaScript.

1. Once the backend is running, open:
   ```
   http://127.0.0.1:8000/demo/
   ```
2. The UI loads automatically with live API connectivity.
3. No Node.js build process or webpack dev server is needed.

---

## 5. Cloudinary Setup

### For Live Cloudinary Uploads:
1. In the demo UI top navigation, enter:
   - **Cloud Name**
   - **API Key**
   - **API Secret**
2. Click **Save Credentials Locally**. These credentials are stored strictly in session storage and transmitted securely via bearer auth headers.
3. When evidence files are uploaded via **Add Evidence**, they are dispatched to Cloudinary and return verified public URLs.

### Without Cloudinary:
- Enter valid image URLs directly into the Asset URL field or use pre-populated demo evidence.

---

## 6. Gemini Setup

### For Live Gemini Multimodal Comparison:
1. In the demo UI top navigation, enter:
   - **Gemini API Key**
2. Click **Save Credentials Locally**.
3. During pair validation, the backend invokes the Gemini multimodal vision model (`gemini-2.5-flash`) to generate visual difference analysis and confidence estimates.

### Without Gemini (Local Mock / Simulation):
- Leave the Gemini API Key blank.
- The system automatically engages the simulated AI engine, providing structured visual difference proposals without external network requests.

---

## 7. Exact Demo Sequence (Happy Path)

Follow this 8-step journey:

```
CREATE / SELECT SITE
        ↓
ADD BEFORE EVIDENCE (Visit 1)
        ↓
ADD AFTER EVIDENCE (Visit 2)
        ↓
VALIDATE PAIR
        ↓
RUN GEMINI ANALYSIS
        ↓
SHOW AI PROPOSAL
        ↓
HUMAN REVIEW
        ↓
APPROVE / EDIT / REJECT
        ↓
GENERATE REPORT
```

1. **Create Site**:
   - In the **Sites** panel, click **+ New Site**.
   - Enter Name (e.g., `Mangrove Restoration Project`) and Location (`Sector 7 Inlet`).
   - Click **Save Site**.

2. **Add Baseline Visit (Before)**:
   - Under Visits, click **+ Add Visit**.
   - Date: `2026-09-01`, Label: `Baseline Assessment`. Click **Save Visit**.

3. **Add Followup Visit (After)**:
   - Click **+ Add Visit**.
   - Date: `2026-09-15`, Label: `Post-Cleanup Followup`. Click **Save Visit**.

4. **Add Evidence Assets**:
   - For Visit 1: Click **Add Evidence**, supply baseline image URL, Source (`Field Photo`), ensure Permission is `granted`.
   - For Visit 2: Click **Add Evidence**, supply followup image URL, Source (`Field Photo`), ensure Permission is `granted`.

5. **Validate Pair & Run Gemini Analysis**:
   - In the **Evidence Pairing & Comparison** panel, select Before Asset and After Asset.
   - Click **Compare Evidence with Gemini**.
   - Observe loading state (`"Comparing with Gemini..."`).
   - Pair validation verifies chronological ordering, matching site, and permission validity.

6. **Inspect AI Proposal**:
   - The UI displays **AI-Generated Visual Assessment** with confidence, detected category changes, and draft summary.
   - Initial status is explicitly displayed as: **Pending Human Review**.
   - *Note: Notice that the official site report does NOT include this observation yet.*

7. **Human Review (Approve / Edit / Reject)**:
   - Click **Review Observation**.
   - Review the AI proposal text, refine observation text if desired.
   - Click **Approve Observation**.
   - The observation status updates to **Human-Verified Observation** (`Approved`).

8. **Generate Official Report**:
   - In the Report panel, click **Generate Report** or **Download Report (.md)**.
   - Confirm that the approved observation and human-verified findings are rendered in the certified export.

---

## 8. Expected Result

- **Integrity**: Only human-verified observations appear in the final report. Unapproved proposals remain strictly excluded.
- **Audit Trail**: The report includes timestamps, visit chronology, asset provenance, reviewer identity, and revision history.
- **Safety**: Language explicitly distinguishes between **AI-generated visual assessments** and **Human-verified observations**.

---

## 9. Failure Handling & Recovery Steps

| Failure Scenario | Visual Indicator | System Behavior | Recovery Action |
|---|---|---|---|
| **Missing Cloudinary Config** | Error banner: `"Upload failed"` | No asset created, no partial records. | Enter Cloudinary credentials or provide direct image URL. |
| **Invalid Visit Chronology** | Error banner: `"Before visit date must precede after visit date"` | HTTP 400 rejection; database remains clean. | Select assets where Before visit is older than After visit. |
| **Revoked Permission** | Error banner: `"Asset has ungranted permission status"` | HTTP 400 rejection. | Use assets with `granted` permission status. |
| **Gemini Unavailable / Timeout** | Error banner: `"Gemini service unavailable. Please retry or verify API credentials."` | Safe fallback or explicit user notice; no crash. | Verify internet connectivity or use mock mode. |
| **Uncertain Comparison (e.g. Angle Mismatch)** | Status badge: `Uncertain`, reason details displayed. | Review status remains pending; observation is flagged for manual inspection. | Reviewer manually enters field notes or requests re-photographing. |
| **Concurrent Review Conflict** | Error banner: `"Review conflict: this observation was updated by another reviewer"` | HTTP 409 rejection; prevents stale overwrites. | Refresh the page and review the latest revision. |

---

## 10. Judge Safety Reminders

- **Never state**: *"AI proved cleanup happened."*
- **Always state**: *"AI-generated visual assessment. Human verification required."*
- **Approved status**: *"Human-verified observation."*
