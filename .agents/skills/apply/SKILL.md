---
name: apply
description: Autonomous Job Application Skill. Inspects data/approved_queue/ and deterministically applies to all approved jobs using browser_subagent and the candidate data bank, prompting the user via ask_question when clarifications or CAPTCHAs are required. Use when the user asks to apply for approved jobs, run the apply agent, or types /apply.
---

# Autonomous Apply Agent Workflow (`/apply`)

Use this skill whenever the user triggers `/apply` or asks to apply for jobs currently staged in the Approved Queue (`data/approved_queue/`).

---

## Operational Runbook

### Step 1: Ensure Server & Environment Readiness
1. Check if the local Command Center server is active on `http://127.0.0.1:8000`:
   ```bash
   lsof -i :8000
   ```
2. If inactive or unresponsive, launch in the background:
   ```bash
   ./venv/bin/python -m uvicorn src.ui.app:app --host 127.0.0.1 --port 8000
   ```
   *(Set `IsDaemon: true`)*

### Step 2: Read Approved Queue
1. Scan `data/approved_queue/` for JSON job payloads:
   * Inspect all `*.json` files (excluding any named `*_resume.json`).
2. If the directory contains **no approved jobs**:
   * Output a clear notification:
     ```markdown
     ⚠️ **No approved jobs found in `data/approved_queue/`!**
     👉 Please review and approve pending jobs in the Command Center first: [http://localhost:8000](http://localhost:8000)
     ```
   * Conclude the workflow.
3. If approved jobs are found:
   * List the approved roles to the user with company, title, application type, and matched tailored resume PDF path (`data/approved_queue/Manjunath_HK_*.pdf`).

### Step 3: Candidate Ground Truth Assembly
Before navigating, load candidate facts into memory:
* Personal and contact details from `data/profile/candidate_master_data.json` and `data/resume_profile.json` (Full Name: `Manjunath H K`, Email: `manjunathhk833@gmail.com`, Phone: `+917337813770`, Location: `Bengaluru, Karnataka, India`).
* Links: LinkedIn (`https://www.linkedin.com/in/manjunath-h-k-ab30b1146/`), GitHub (`https://github.com/manjunathk833`), Portfolio (`https://manjunathhk.netlify.app/`).
* Standard screening answers from `data/profile/workday_field_mappings.json` (Prior employment: `No`, Authorized: `Yes`, Sponsorship: `No`, Relatives: `No`, Non-compete: `No`, Prefix: `Mr.`).

### Step 4: Deterministic Application via `browser_subagent`
For each approved job in the queue:
1. Identify target URL:
   * If `application_type == "EASY_APPLY"`: target `job_url` (`https://www.linkedin.com/jobs/view/<job_id>/`).
   * If `application_type == "LINKEDIN_EXTERNAL"`: target `external_url` (or navigate to `job_url` and click external Apply).
2. Launch `browser_subagent` with detailed instructions:
   * Navigate to the target application URL.
   * Fill personal and contact details with synthetic event dispatching.
   * Attach the matching tailored PDF resume located in `data/approved_queue/`.
   * Resolve known screening questions using `data/profile/workday_field_mappings.json`.
   * Enforce a hard budget of **25 actions maximum** per job to prevent dynamic SPA loops.

### Step 5: Human-in-the-Loop Clarification Interceptor
* If an unhandled screening question, ambiguous multi-choice option, or CAPTCHA appears:
  * **DO NOT ABORT.**
  * Call `ask_question` with the question text and clear selectable options for the user.
  * Once the user responds, instruct the browser agent to select/fill that answer.
  * Cache the answer into `data/profile/workday_field_mappings.json` or `data/logs/autofill_learning_vault.json` for future automated runs.

### Step 6: Final Review Step & Database Audit
1. Pause at the final "Review your application" screen.
2. If user confirms or auto-submit is desired:
   * Submit the application.
3. Record the application in the SQLite database:
   ```bash
   ./venv/bin/python -c "from src.storage.database import ApplicationDatabase; ApplicationDatabase().record_application(job_id='{job_id}', source='{source}', company_name='{company}', job_title='{title}', job_url='{url}', status='applied')"
   ```
4. Safely delete the processed JSON and PDF from `data/approved_queue/`.
5. Proceed to the next approved job until the queue is clear.
