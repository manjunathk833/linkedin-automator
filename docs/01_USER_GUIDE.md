# To the User: The Plain-English System Guide & Copilot Manual

> **Welcome!** If you want to understand how this system works, how to use it every day, and how to customize or critique it without getting buried in technical jargon, this document was written specifically for you.

---

## 1. What is This System in Plain English?

Think of this software as your **personal Senior SDET Job Search & Application Copilot**.

Applying to 100+ jobs manually is exhausting: searching LinkedIn, opening company career portals, tailoring bullet points for each job description, formatting PDFs, and typing the same contact info into 10-step forms over and over again.

This copilot does all the tedious heavy lifting for you:
1. It **scans company job boards and LinkedIn** in the background for jobs that match your exact level (Senior SDET / QA Lead, 5+ years experience, Bengaluru or India Remote).
2. It **tailors your authentic resume bullet points** to match what each employer is looking for.
3. **It has a strict "Lie Detector" (Anti-Fabrication Gate):** It is physically blocked from inventing tools you never worked with. If a job requires "Cypress" and you only know "Selenium", it will never lie or claim you used Cypress.
4. It compiles a clean, **single-column ATS-friendly PDF resume**.
5. It brings everything to a **private local web screen on your computer (`http://localhost:8000`)** where you can see the job description side-by-side with your tailored resume.
6. When you click **"Open & Autofill Copilot"**, a real Google Chrome window opens, types your answers naturally, attaches your custom PDF resume, and **stops right at the final "Review / Submit" step**. It will **never** click submit on its own—you always review the pre-filled form with your own eyes and click Submit yourself.

---

## 2. The 5-Step Journey of a Job Application

Here is what happens behind the scenes from the moment a job is posted until you click submit:

```
[Candidate Notes] ────────> [Raw Job Posting] (Greenhouse, Lever, Ashby, LinkedIn)
       │                                │
       ▼                                ▼
[Grounded Knowledge Vault]    [Senior SDET Filter] (Only 4-10 yrs exp & BLR/Remote)
       │                                │
       └──────────────┬─────────────────┘
                      ▼
        [Strict AI Resume Tailoring]
                      │
                      ▼
     [Lie Detector / Whitelist Gate] (Blocks 100% of fake skills)
                      │
                      ▼
        [Single-Page ATS PDF Created]
                      │
                      ▼
     [Your Web Dashboard (localhost:8000)] ──> You inspect & click "Open & Autofill"
                      │
                      ▼
     [Real Chrome Opens & Auto-fills] ──────> 🛑 STOPS AT FINAL STEP
                                                │
                                                ▼
                                   [You review and click Submit!]
```

### Step 1: Your Authentic Experience (Source of Truth)
* You have a notes file: `data/candidate_notes.md`. Whenever you achieve something new at work, you just write a casual bullet point in plain English.
* The system reads your notes and translates them into professional STAR achievements (Situation, Task, Action, Result) saved in `data/master_knowledge_bank.json`.

### Step 2: Dual-Track Job Discovery
Most job search tools only scrape LinkedIn. This system has two separate discovery radars:
* **Track A (Direct Company Portals):** It directly queries the official, public application portals (Greenhouse, Lever, Ashby) of 37+ top tech companies (like Stripe, Cloudflare, Postman, BrowserStack, Linear, Docker, Figma) in less than 3 seconds without even opening a browser.
* **Track B (LinkedIn Stealth Search):** It opens your persistent Chrome browser session to search LinkedIn keyword queries, your personalized Recommended feed, and recruiter posts.

### Step 3: Tailoring & The "Lie Detector" Gate
* When a matching job description is found, the AI selects which of your real achievements best highlight the skills requested by the job.
* **The Whitelist Lock:** Next, the text runs through a deterministic code gate (`data/profile/allowed_tools_whitelist.json`). If the AI ever hallucinates a tool you didn't approve (for example, Kubernetes, Cypress, or Go), the code immediately purges it or replaces it with your authentic tool (like Docker or Selenium).
* The tailored profile is instantly compiled into a clean, single-page ATS-optimized PDF in `data/resumes/`.

### Step 4: Your Local 1-Click Approval Command Center (`http://localhost:8000`)
* The dashboard features a **Dual-Mode Command Center**:
  * **📋 Staging Review Tab:** Review fresh, incoming candidate matches. See employer job descriptions side-by-side with tailored resume bullet points (**✨ Tailored** diff badges) and matched tech tags. No tedious per-job screening questionnaire inputs! Simply click **"Approve"** (moves to Ready to Apply queue with custom PDF compiled) or **"Reject & Skip"**.
  * **🚀 Ready to Apply Tab:** Displays all approved jobs compiled with single-column ATS PDF resumes. Includes a **Live Search Bar** to filter by company or title, an **Inline PDF Preview modal** (`/api/pdf/{job_id}`) to inspect the exact resume before applying, a **Safety Cap Banner** tracking your daily submissions, and individual **"🚀 Launch Copilot"** triggers.

### Step 5: The Human-in-the-Loop Browser Fill & Modular Vendor Copilot
* When you click **"🚀 Launch Copilot"**, a real Google Chrome window opens.
* **Pattern Recognition Engine:** Upon navigation, the copilot immediately identifies which ATS vendor pattern the application form uses (`GREENHOUSE_STANDARD`, `OKTA_BRANDED_GREENHOUSE`, `LEVER_STANDARD`, `ASHBY_STANDARD`, `WORKDAY_STANDARD`, `LINKEDIN_EASY_APPLY`).
* **Standardized Vendor Schemas & Custom Org Schemas:** Instead of guessing form structures, the copilot uses verified vendor standards and custom branded schemas (e.g. Okta custom career forms) mapped to your **Central Candidate Master Profile** (`data/profile/candidate_master_data.json`). Your portfolio website (`https://manjunathhk.netlify.app/`), LinkedIn profile, phone, email, and answers to screening questions are automatically mapped.
* **Canonical ATS Routing:** If the job link is an enterprise wrapper (e.g. Coinbase `gh_jid`), the copilot automatically resolves it to the canonical Greenhouse/Lever board where fields are immediately accessible.
* **Multi-Tab & Popup Window Auto-Switching:** If clicking "Apply for this job" opens a new browser tab (`target="_blank"` or JavaScript `window.open()`), the copilot's context page listener intercepts the new tab, automatically switches active page control to it, brings the application tab to the front of your screen, and detects any nested ATS iframes.
* **Kinematics & Typing:** It uses **humanized mouse kinematics**: mouse cursors move along natural Bézier curves and types with natural log-normal intervals (15–90 ms per keystroke).
* **Multi-Section Completion:** In Greenhouse and Workday, it populates contact info, adds work experience and education cards, and attaches the tailored PDF resume. In Lever, Ashby, and Okta, it populates custom URLs, candidate portfolio, screening questions, and voluntary demographic surveys.
* **Pause-Before-Submit Gate:** It fills all fields, attaches the tailored PDF resume, and **intentionally yields control back to you on the final review screen**.
* You verify the answers, give the final nod, and manually click "Submit application".
* The submission is logged in a local SQLite database (`data/app_database.db`), and your daily budget counter advances (configurable via `config.yaml` to keep your applications running smoothly).

---

## 3. How to Use the System (Your Daily Workflow)

You only need three simple commands:

### Morning Workflow: One-Shot Discovery & Review
```bash
# 1. Activate your Python environment
source venv/bin/activate

# 2. Ingest fresh jobs directly from 37+ tech ATS boards into your review queue
python scripts/run_ingestion.py --queue

# 3. Launch your approval dashboard
python main.py dashboard
```
Open **`http://localhost:8000`** in your browser. Review the staged jobs, inspect the tailored bullets, and click **`🚀 Open & Autofill Copilot`** on the roles you want to apply to!

### Full Pipeline Workflow (Including LinkedIn Search):
```bash
# Runs everything sequentially: Syncs notes -> Searches LinkedIn -> Filters experience -> Opens dashboard
python main.py run
```

---

## 4. How to Critique & Customize the System

The entire system is modular and transparent. If you want to change how it behaves, here is your cheat sheet:

### 1. "I want to change my target location or search keywords"
* **File to edit:** [`config.yaml`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/config.yaml)
* Under `search_profiles`, you can change keywords (e.g. `"Lead SDET"`, `"Staff QA Engineer"`) or locations (e.g. `"Bengaluru"`, `"Remote India"`).

### 2. "I want to adjust the experience filter (e.g. 4–10 years to 5–12 years)"
* **File to edit:** [`src/filter/job_filter.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/filter/job_filter.py)
* Lines 13–15 define:
  ```python
  self.min_exp_years = 5
  self.max_exp_years = 12
  self.candidate_exp_years = 6.8
  ```

### 3. "I learned a new tool or want to disallow a specific framework"
* **File to edit:** [`data/profile/allowed_tools_whitelist.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/profile/allowed_tools_whitelist.json)
* Add your new tool to `"allowed_tools"` (e.g. `"playwright"`, `"graphql"`) so the AI is permitted to use it when tailoring.
* Add unwanted buzzwords to `"disallowed_hallucinations"` to permanently ban them.

### 4. "I want to add or remove target companies from the direct ATS search"
* **File to edit:** [`data/config/target_companies.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/config/target_companies.json) or [`scripts/seed_companies.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/scripts/seed_companies.py)
* Add any company that uses Greenhouse, Lever, or Ashby:
  ```json
  {"name": "Notion", "ats_provider": "ashby", "slug": "notion", "domain": "notion.so"}
  ```

### 5. "I want to change the daily application limit (budget cap)"
* **Option A (Recommended):** In [`config.yaml`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/config.yaml), update `safety_governor.daily_limit` (e.g. `200` or any custom value).
* **Option B:** In [`src/autofill/governor.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/governor.py), change `DEFAULT_DAILY_LIMIT = 200`.

### 6. "I want to update my personal contact info, phone, or LinkedIn URL"
* **File to edit:** [`data/resume_profile.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/resume_profile.json)
* Modify `personal_details` (phone number, email, portfolio links). Both the PDF generator and the autofill mapper will instantly pick up the updated information.

---

## 5. Account Safety & Anti-Detection FAQ

* **Q: Will LinkedIn ban or flag my account?**
  * **A: No.** Unlike cloud scrapers that run headless browsers from data-center IP addresses, this system uses your **real, installed Google Chrome profile** on your local Mac. It moves the mouse in natural curved trajectories, types with human delays, and never sends automated requests faster than a real person could click.
* **Q: Does it ever apply to a job without my knowledge?**
  * **A: Never.** Every single application requires you to click "Open & Autofill" from your dashboard. Furthermore, the browser intentionally pauses on the final modal screen so that you click the final "Submit" button yourself.
* **Q: How much does this cost to run?**
  * **A: Exactly $0.00.** It uses Google Gemini 2.5 Flash Free Tier APIs or 100% offline local inference via Ollama (`qwen2.5:7b`). It queries public, unauthenticated ATS endpoints without paying for third-party scraping APIs.
