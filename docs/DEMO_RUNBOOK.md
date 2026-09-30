# SETOWA Demo Runbook

This document provides a concise, step-by-step guide to run and present the complete **SETOWA (Sustainability Evidence, Tracking & Observation Workflow Architecture)** system for judges, evaluators, and teammates.

---

## 1. Prerequisites

- **Python**: 3.11+ (with `venv`)
- **Web Browser**: Modern Chromium, Firefox, Safari, or Edge
- **Optional CLI Utilities**: `curl`, `bash` (for `run_local.sh`)
- **External Accounts (Optional for live mode)**:
  - Cloudinary account (`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`)
  - Google Gemini API (`GEMINI_API_KEY`)

*Note: In local mode with pre-seeded demonstration data or fallback mode, no active network calls to AI providers are required to explore the full UI, DAG workflows, and public impact stories.*

---

## 2. Environment Variables

> **CRITICAL SECURITY RULE:** Never commit or hardcode credential values. Store in `backend/.env` (gitignored) or `credential.json` (gitignored), or set directly in your shell environment.

Supported variable names:

| Variable Name | Purpose | Required in Mock Mode? |
|---|---|---|
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud account name | No (falls back to local URLs) |
| `CLOUDINARY_API_KEY` | Cloudinary API access key | No |
| `CLOUDINARY_API_SECRET` | Cloudinary API access secret | No |
| `GEMINI_API_KEY` | Google Gemini multimodal AI evaluation | No (falls back to deterministic heuristics) |
| `GEMINI_VISION_MODEL` | Gemini vision model override (default: `gemini-3.8-flash`) | No |
| `ENVIRONMENT` | Environment name (`development` or `production`) | No |
| `USE_MOCK` | Explicitly enforce mock mode (`true`/`false`) | No |
| `PORT` | Local server port (default: `8000`) | No |
| `LEX_DB_PATH` | Path to SQLite database (default: `./lex.sqlite3`) | No |

---

## 3. Database & Demo Data Initialization

SETOWA automatically seeds a deterministic, verified coastal restoration demonstration dataset upon startup or via direct command:

```bash
cd backend
python scripts/seed_demo.py
```

This populates:
1. **Project**: `proj_mombasa_marine` (Mombasa Marine Litter & Mangrove Restoration)
2. **Site**: `site_nyali_creek` (Nyali Creek Mangrove Shoreline)
3. **Chronological Visits**: Baseline Assessment (Sept 2), Cleanup Action (Sept 14), Post-Audit (Sept 22)
4. **Cloudinary Assets**: Pre-cleanup photo, field walkthrough video, post-cleanup verification photo
5. **Video Frame Analytics**: Timestamped frame extractions via Cloudinary offset transformations
6. **Media Intelligence**: Multi-label ecological tags (`coastal`, `vegetation`, `litter`), signals, observations
7. **Approved Evidence**: Human-verified before/after pair with field lead signature
8. **Physical Measurement**: Certified municipal weigh slip (320.0 kg net waste collected)
9. **Published Impact Story**: Chronological timeline, comparative proof cards, and public share token (`pst_demo_mombasa_coastal_2026`)

---

## 4. One-Command Startup

### Universal Launch (Windows / macOS / Linux — Recommended)
From repository root (`LEX`):
```bash
python run_local.py
```
*Automatically detects/creates `backend/venv`, installs packages if needed, sets environment, seeds data, and starts the server.*

### Native Windows Launch
From repository root (`LEX`):

- **PowerShell**:
  ```powershell
  .\run_local.ps1
  ```
- **Command Prompt (CMD)**:
  ```cmd
  run_local.bat
  ```
- **Direct Virtualenv Python**:
  ```powershell
  .\backend\venv\Scripts\python.exe backend\scripts\start_demo.py
  ```
- **Direct Uvicorn (Note: require `--app-dir backend`)**:
  ```powershell
  .\backend\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
  ```

### Linux / macOS / Git Bash Launch
From repository root (`LEX`):
```bash
./run_local.sh
```

The startup runner will:
- Safely audit environment variables without exposing secret values
- Ensure reviewer authorization credentials exist (`backend/.env`)
- Seed the deterministic demo dataset across 4 sites
- Print the live workspace, showcase, and public URLs
- Start FastAPI on `http://127.0.0.1:8000`

---

## 5. System Health & Readiness Verification

Verify service status before presenting:

- **Liveness Probe**: `GET http://127.0.0.1:8000/api/v1/health`
- **Readiness Probe**: `GET http://127.0.0.1:8000/api/v1/ready`
  - Returns database readiness, Cloudinary configuration status, and Gemini readiness.
- **Automated Smoke Test**:
  ```bash
  cd backend
  python scripts/smoke_test.py
  ```
  Runs through all 9 lifecycle phases in ~2 seconds.

---

## 6. The 5-Minute Judge Demo Sequence

The presentation follows ONE coherent, verifiable narrative:

```
FIELD MEDIA  →  CLOUDINARY  →  WORKSPACE  →  MEDIA INTELLIGENCE
     ↓
   SKILLS    →  WORKFLOWS   →  EVIDENCE   →  HUMAN VERIFICATION
     ↓
IMPACT STORY →  PUBLIC SHARE
```

### Step 1: Open the Setowa Workspace
- Navigate to `http://127.0.0.1:8000/demo/`
- Click **Open projects →** and select **Mombasa Marine Litter & Mangrove Restoration** (`proj_mombasa_marine`).

### Step 2: Cloudinary-Powered Media Library
- Click the **Media library** tab.
- Highlight the multi-type evidence collection:
  - Baseline image (`creek_baseline_debris.jpg`)
  - Cleanup action video (`creek_cleanup_action.mp4`) with poster frame derived at offset 0
  - Post-intervention verification photo (`creek_post_cleanup.jpg`)
- Show Cloudinary URL badges and filter by Media Type or Permission Status.

### Step 3: Frame Analytics on Video Asset
- On the video card, click **🎬 Frame Analytics**.
- Show the video playback modal with derived frame intervals (1.5s, 4.0s, 8.0s).
- Demonstrate that frames are extracted on-the-fly via Cloudinary video transformations without re-encoding.

### Step 4: AI Media Intelligence
- In the Media Library, click **View Intelligence** on an asset.
- Show structured Gemini visual intelligence:
  - Strictly observed facts vs inferred hypotheses
  - Controlled tags (`coastal`, `vegetation`, `litter`, `cleanup_activity`)
  - Controlled signals (`marine_debris`, `human_activity`)
  - Model provenance and execution latency.

### Step 5: Skills Runtime
- Click the **Skills** tab.
- Explain the 4 modular, contract-bound skills:
  - `media-metadata@1.0.0`
  - `evidence-comparison@1.0.0`
  - `field-frame-observation@1.0.0`
  - `media-intelligence@1.0.0`
- Open the in-page execution tester to demonstrate bounded inputs and schema validation.

### Step 6: Visual Workflow Builder
- Click the **Workflows** tab.
- Select the built-in **Before-After Evidence Comparison** pipeline (`wf_evidence_compare`).
- Show the interactive DAG canvas:
  - Node 01 (`before_meta`) and Node 02 (`after_meta`) run media inspection.
  - Node 03 (`compare`) ingests metadata and performs structured AI evidence comparison.
- Click **Run Workflow** to show real-time topological execution, latency metrics, and failure boundaries.

### Step 7: Human Review & Verification (The Trust Boundary)
- Click the **Review** tab.
- Emphasize the core thesis of SETOWA: **AI output is strictly a proposal, never an unverified fact.**
- Show the side-by-side comparative inspection with the split-reveal slider.
- Review the observation:
  - State: **Approved** (or demonstrate editing/rejecting).
  - Reviewer: **Aryan (Field Lead)** with timestamp audit.
  - Explicit uncertainty notes: visual boundaries, lighting caveats.

### Step 8: Impact Story & Sustainability Timeline
- Click the **Impact Story** tab.
- Present the synthesized Project Dossier:
  - Grounded summary narrative referencing only verified evidence and the 320.0 kg certified municipal weigh slip.
  - Zero fabricated carbon offsets or ungrounded percentages.
  - Chronological spine ordering baseline photos, action video, physical measurements, and approved findings.

### Step 9: Public Share Experience
- At the top of the Impact Story tab, click **Open Public Story ↗** (or visit `http://127.0.0.1:8000/share/pst_demo_mombasa_coastal_2026`).
- Present the read-only, high-fidelity public experience:
  - High-resolution Cloudinary hero image and responsive media.
  - Interactive before/after split slider.
  - Chronological timeline spine with event badges.
  - Verified findings counter showing only approved observations.
  - Prominent uncertainty caveats callout.
  - Press `Ctrl+P` (or Print) to show the built-in print stylesheet for offline PDF reporting.

---

## 7. Command-Line Interface (CLI) Demo Path

For technical evaluators, SETOWA features a first-class CLI sharing the exact same backend domain services:

```bash
cd backend

# 1. List registered skills
python setowa_cli.py skill list

# 2. List available workflow DAGs
python setowa_cli.py workflow list

# 3. Execute the before-after comparison workflow
python setowa_cli.py workflow run wf_evidence_compare

# 4. Inspect workflow execution details
python setowa_cli.py run status <execution_id>

# 5. Display published Impact Story with public share URL
python setowa_cli.py story show proj_mombasa_marine
```

---

## 8. Troubleshooting

- **Database Lock / Busy**:
  - If SQLite reports `database is locked`, ensure no long-running interactive database browsers hold write locks.
- **Port 8000 Already in Use**:
  - Run on a custom port: `PORT=8080 python scripts/start_demo.py` or `./run_local.sh`.
- **Cloudinary Media Not Loading**:
  - Check network connectivity or verify credentials with `python scripts/check_cloudinary.py`.
- **Gemini Offline / Rate-Limited**:
  - The system automatically engages deterministic offline heuristics; the full workflow continues to execute without crashing.

---

## 9. Known Limitations

- **POSIX Permissions on Windows**:
  - Windows NTFS file systems do not enforce POSIX permission bits (`chmod 0o600`), resulting in one environment-specific test skip/assertion difference in `test_local_setup.py`. This does not affect application functionality or Linux/macOS production environments.
- **Microplastics Scope**:
  - Visual models cannot detect subsurface soil microplastics; this limitation is explicitly surfaced in the Impact Story uncertainty notes.

---

## 10. Demo Reset & Cleanup

To restore the demo to its pristine initial state:
```bash
cd backend
python scripts/seed_demo.py
```
This idempotently resets all projects, visits, assets, workflow executions, and impact stories.
