# 🤝 Roles, Responsibilities & Git Workflow — Team LEX

> **Team Members:**  
> 1. **Aryan Vishwakarma** (Team Lead / Full-Stack Architect)  
> 2. **Farhan Akhtar** (Core Backend / Logic & AI Engineer)  
> 3. **Shubh Gunjan** (Frontend UI/UX / Web Showcase & Presentation Lead)  

---

## 👥 Responsibility Matrix

| Team Member | Primary Domain | Core Deliverables |
| :--- | :--- | :--- |
| **Aryan Vishwakarma** *(Lead)* | • Overall Architecture & Tech Stack Selection<br>• Full-Stack Integration & Database Schema<br>• Git Repository Admin & Deployment Pipeline<br>• End-to-end user journey validation | • Working cloud database & auth<br>• Integrated API & Client connections<br>• Staging & Production deployments (Vercel/Render)<br>• Submission portal ownership |
| **Farhan Akhtar** | • Backend Services & API Endpoints<br>• AI Model Integration (Gemini/Groq/OpenAI)<br>• Business Logic, Calculations & Algorithmic Engine<br>• Data models, mock seed data, & fallback routes | • Clean REST/GraphQL endpoints<br>• Robust AI prompt chains / pipelines<br>• Error handling & fallback mock modes<br>• API documentation for frontend |
| **Shubh Gunjan** | • Frontend Interface & Component Design<br>• User Experience, Animations & Micro-interactions<br>• Responsive Design (Mobile & Desktop)<br>• App Showcase Landing Page & PPT Design | • Beautiful, intuitive user interface<br>• Interactive dashboard / workflows<br>• Pitch Deck (PPT) visuals & layout<br>• Showcase website for judges |

---

## 🌿 Git Branching Strategy

To prevent merge conflicts, accidental overwrites, and broken builds:

```
[main] (Production - ONLY working, deployed releases)
   ▲
   │ (Merged only after testing)
[dev] (Staging / Integration - All features merge here)
   ▲
   ├── feature/aryan-db-integration
   ├── feature/farhan-api-ai-pipeline
   └── feature/shubh-ui-dashboard
```

### Branch Rules:
1. **Never commit directly to `main`:** `main` must ALWAYS be in a working, deployable state.
2. **Feature Branches:** Every task gets its own branch branched off `dev`:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/<name>-<feature-name>
   ```
3. **Keep branches small:** Commit and push frequently rather than holding huge uncommitted changes.
4. **Pull `dev` frequently:** Before pushing your work, rebase or merge `dev` into your feature branch to catch conflicts early:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout feature/<name>-<feature-name>
   git merge dev
   ```

---

## 📝 Commit Message Conventions

Use clear, standardized commit prefixes:

| Prefix | Usage | Example |
| :--- | :--- | :--- |
| `feat:` | A new feature or user story | `feat: add AI summarization endpoint` |
| `fix:` | A bug fix | `fix: resolve auth token expiration bug` |
| `ui:` | Frontend styling or layout change | `ui: polish dashboard cards and responsive layout` |
| `docs:` | Documentation, planning, or submission files | `docs: add demo video script and PPT outline` |
| `refactor:` | Code restructuring without feature change | `refactor: extract reusable API client helper` |
| `chore:` | Config files, dependencies, build scripts | `chore: install lucide-react and tailwindcss` |

---

## 🚀 Collaboration Etiquette

1. **API Contracts First:**
   - Farhan and Aryan define endpoint signatures (`/api/v1/analyze`) with sample JSON inputs and outputs before coding.
   - Shubh can mock this JSON locally and build the entire frontend without waiting for the backend to be online.

2. **The "15-Minute Blocker" Rule:**
   - If you are stuck on a bug or library issue for more than 15 minutes, **do not suffer in silence**.
   - Ping the team chat immediately. Hop on a 5-minute screen share or pair-program to resolve it.

3. **Code Review Protocol:**
   - Aryan will review and approve PRs into `dev`.
   - Before merging, verify:
     - Does the app build (`npm run build` or python test)?
     - Are there any leftover debug statements or sensitive keys?
     - Does the change break existing pages?

4. **Environment Variables Safety:**
   - **NEVER** commit `.env` files containing real API keys to GitHub!
   - Commit `.env.example` showing required keys with dummy values.
   - Share secret keys via private team chat or secure notes.
