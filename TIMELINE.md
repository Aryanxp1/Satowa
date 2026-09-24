# ⏱️ Master Timeline & Sprint Tracker — Team LEX

> **Rule of Thumb:** Whatever the total hackathon duration is, divide it as:  
> - **20%** Ideation & Architecture  
> - **50%** Development & Integration  
> - **20%** Testing, Demo Video & PPT Polish  
> - **10%** Buffer & Submission Verification  

---

## 🗓️ Scenario A: Multi-Day / 5-to-7 Day Hackathon Format

If the hackathon gives 5 to 7 days from PS release to submission:

| Phase | Days | Focus Objectives | Deliverable Checkpoint |
| :--- | :--- | :--- | :--- |
| **Stage 1** | **Days 1 & 2** | • Problem Statement deep-dive<br>• Ideation & 3-idea comparison<br>• Tech stack & system architecture lock<br>• API contracts & wireframing | [x] Approved Idea & Architecture diagram<br>[x] Mock JSON schemas defined |
| **Stage 2** | **Days 3 to (N-2)** | • Core feature build in parallel<br>• Frontend views & responsive styling<br>• Backend APIs & Database schemas<br>• AI logic & algorithmic integration | [x] Working API endpoints<br>[x] Functional Frontend UI<br>[x] Core user flow connected |
| **Stage 3** | **Day (N-1)** | **🚨 FEATURE FREEZE 🚨**<br>• End-to-end integration test<br>• Edge cases & error handling<br>• Pre-populate demo data<br>• Zero new feature additions | [x] All core user journeys functioning<br>[x] Staging deployment healthy on Vercel/Render |
| **Stage 4** | **Final 24 Hours** | • Record & edit 2-3 min demo video<br>• Build 8-10 slide pitch deck (PPT)<br>• Deploy showcase landing page<br>• Draft submission descriptions & submit 2h early | [x] Demo video link uploaded<br>[x] PPT exported to PDF/Canva<br>[x] Submission form submitted! |

---

## ⚡ Scenario B: 48-Hour Weekend Sprint Model

If the hackathon is a 48-hour continuous sprint:

```mermaid
gantt
    title 48-Hour Hackathon Execution Timeline
    dateFormat HH:mm
    axisFormat %H h
    section Ideation
    PS Review & Ideation       :done,    00:00, 06:00
    Architecture & API Specs   :done,    06:00, 09:00
    section Core Build
    Backend & AI Engine        :active,  09:00, 24:00
    Frontend & UI Development  :active,  09:00, 24:00
    Full-Stack Integration     :crit,    24:00, 30:00
    section Feature Freeze & Polish
    FEATURE FREEZE & Testing   :crit,    30:00, 36:00
    section Pitch & Submission
    Demo Video Recording       :         36:00, 42:00
    PPT Deck & Showcase Page   :         40:00, 45:00
    Final Submission Buffer    :crit,    45:00, 48:00
```

### Hour-by-Hour Breakdown:

- **Hours 00:00 – 06:00 (Ideation & Selection):**
  - Read problem statement thoroughly.
  - Brainstorm 3 distinct angles using [IDEATION_FRAMEWORK.md](./IDEATION_FRAMEWORK.md).
  - Pick ONE idea with highest demo impact.

- **Hours 06:00 – 09:00 (Architecture Lock):**
  - Draw data flow diagram and user journey.
  - Write API endpoints request/response schemas.
  - Create Git feature branches (`feature/ui`, `feature/api`, `feature/ai`).

- **Hours 09:00 – 24:00 (Core Sprint):**
  - Aryan: Full-stack integration, auth/database models, core logic orchestration.
  - Farhan: Backend endpoints, AI prompt pipelines, calculations, third-party integrations.
  - Shubh: Responsive UI components, state management, interactive controls.

- **Hours 24:00 – 30:00 (Integration Milestone):**
  - Connect Frontend to live Backend APIs.
  - Test the entire happy path user flow.
  - Resolve CORS, environment variables, and authentication bugs.

- **Hours 30:00 – 36:00 (🚨 FEATURE FREEZE 🚨):**
  - Stop adding code.
  - Polish styling, add loading skeletons, error states, and realistic mock seed data.
  - Deploy production build to Vercel/Netlify.

- **Hours 36:00 – 42:00 (Demo Video Sprint):**
  - Write script using [DEMO_VIDEO_SCRIPT.md](./SUBMISSION_KIT/DEMO_VIDEO_SCRIPT.md).
  - Record screencast walkthrough (OBS/Loom).
  - Edit: Add callouts, highlight key features, export 1080p, upload to YouTube.

- **Hours 42:00 – 45:00 (Presentation Deck & Landing Page):**
  - Create 8–10 slide pitch deck using [PPT_OUTLINE.md](./SUBMISSION_KIT/PPT_OUTLINE.md).
  - Polish product landing page with live demo link.

- **Hours 45:00 – 48:00 (Submission Buffer):**
  - Fill HackCulture / Unstop submission form.
  - Complete checklist in [SUBMISSION_CHECKLIST.md](./SUBMISSION_KIT/SUBMISSION_CHECKLIST.md).
  - Submit early, relax, and prepare for Q&A / pitching!

---

## 📞 Standup & Sync Cadence

To maintain velocity without exhausting the team:

| Time | Agenda | Duration |
| :--- | :--- | :--- |
| **Morning Sync (10:00 AM)** | Yesterday's wins, today's targets, dependency handoffs | 15 mins |
| **Midday Checkpoint (03:00 PM)** | Quick blocker removal & API verification | 10 mins |
| **Evening Demo & Merge (09:00 PM)** | Screen share demo of day's work, review PRs, merge to `dev` | 20 mins |

---

## 📌 Progress Milestones Tracker

- [ ] **M0: Setup Ready** (Repo initialized, collaborators added, accounts ready)
- [ ] **M1: Problem Statement Analyzed** (Problem breakdown & pain points listed)
- [ ] **M2: Winning Idea Chosen** (Evaluated against competitors & hackathon criteria)
- [ ] **M3: Architecture & Schema Locked** (API specs and wireframes done)
- [ ] **M4: MVP Functional** (Frontend + Backend working end-to-end)
- [ ] **M5: Feature Freeze Declared** (No new code, focus on stability)
- [ ] **M6: Live App Deployed** (Accessible URL with working demo data)
- [ ] **M7: Pitch Deck Completed** (Clean PPT with problem-solution story)
- [ ] **M8: Demo Video Uploaded** (Crisp 2-3 minute YouTube video)
- [ ] **M9: Final Submission Completed** (Submitted >2 hours ahead of deadline)
