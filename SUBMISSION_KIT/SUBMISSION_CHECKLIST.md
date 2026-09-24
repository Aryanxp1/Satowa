# ✅ Zero-Failure Hackathon Submission Checklist — Team LEX

> **Target:** Submit everything at least **2 hours before the portal deadline**.  
> Never wait until the last 30 minutes — portal servers frequently crash or become sluggish under traffic!

---

## 🛑 Stage 1: T-Minus 24 Hours (Code Freeze & Stability)

- [ ] **Feature Freeze Declared:** No new features or database schema changes permitted.
- [ ] **Clean Seed Data:** Pre-load realistic demo data (users, metrics, cards) so the app never displays empty states or raw placeholders like "Lorem Ipsum".
- [ ] **Error Handling:** Verify invalid inputs show clean alerts rather than crashing with an unhandled exception or white screen.
- [ ] **Environment Check:** Create `.env.example` with dummy values for all required environment variables.
- [ ] **Build Test:** Run `npm run build` (or backend equivalent) locally to verify zero build or bundling errors.

---

## 🎥 Stage 2: T-Minus 12 Hours (Demo Video & Live Deploy)

- [ ] **Production Deployment:**
  - Live link accessible on Vercel / Netlify / Render.
  - Test the live link on both a Laptop and a Mobile phone.
  - Test the live link in an **Incognito / Private Window** (to ensure it doesn't rely on local cookies or localhost).
- [ ] **Demo Video Recording:**
  - Follow the [DEMO_VIDEO_SCRIPT.md](./DEMO_VIDEO_SCRIPT.md).
  - Video resolution: 1080p (60fps preferred).
  - Audio: Clear voiceover without background noise or room echo.
  - Length: Strictly between **2:00 and 3:00 minutes**.
- [ ] **Video Upload:**
  - Uploaded to YouTube (or Loom / Google Drive as specified by hackathon rules).
  - Visibility set to **Public** or **Unlisted** (NEVER "Private").
  - Test opening the YouTube link in Incognito mode to confirm anyone with the link can view it.

---

## 📊 Stage 3: T-Minus 6 Hours (PPT Deck & Landing Page)

- [ ] **Presentation Pitch Deck (PPT):**
  - Follow the [PPT_OUTLINE.md](./PPT_OUTLINE.md).
  - 8–10 slides maximum.
  - Include high-res screenshots of the live app.
  - Include system architecture diagram.
  - Export as **PDF** (safe formatting) AND keep original Google Slides / Canva / PPT link.
- [ ] **Showcase Landing Page:**
  - Deployed showcase website highlighting key features, team info, and a prominent "Launch Live App" button.
- [ ] **GitHub Repository Polish:**
  - Repository `README.md` updated with:
    - Catchy project title, tagline, and badges.
    - 2–3 high-quality screenshots or demo GIF.
    - Problem & Solution summary.
    - Tech stack list.
    - Live Demo link + Video link + Pitch deck link.
    - Clear local setup and installation instructions.

---

## 🚀 Stage 4: T-Minus 2 Hours (Portal Form Submission)

- [ ] **Pre-Draft Submission Text:**
  - [ ] Project Title
  - [ ] Tagline / Elevator Pitch (1 sentence)
  - [ ] Problem Statement & Inspiration
  - [ ] What it does (Core functionality)
  - [ ] How we built it (Architecture & Tech Stack)
  - [ ] Challenges faced & how we overcame them
  - [ ] Accomplishments that we're proud of
  - [ ] What's next / Future roadmap
- [ ] **Verify All URLs:**
  - [ ] GitHub Repository URL (Make sure repo is Public if required by rules, or collaborators added).
  - [ ] Live Demo / Web App URL.
  - [ ] Video Demo URL (YouTube/Loom).
  - [ ] Pitch Deck URL (Google Drive / Canva view-only or PDF upload).
- [ ] **Click Submit & Take Screenshot:**
  - Submit on HackCulture / Unstop / Devfolio.
  - Save a screenshot of the "Submission Received" confirmation screen.

---

## 🎤 Stage 5: Pitching & Live Q&A Preparation

- [ ] **Demo Fallback Ready:** Have the app running locally on `localhost` AND keep a pre-recorded backup video ready in case Wi-Fi fails during live judging.
- [ ] **Prepare for Common Judge Questions:**
  1. *"How does this differ from existing solutions?"*
  2. *"How does your AI/backend actually work under the hood?"*
  3. *"How would you scale this to 100,000 users?"*
  4. *"What is your business / monetization model?"*
  5. *"What was the hardest technical challenge your team solved in the last 48 hours?"*
