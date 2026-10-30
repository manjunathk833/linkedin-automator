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
Before navigating, compile the complete candidate lookup dictionary into memory:
* **Personal & Contact:**
  * Full Legal Name: `Manjunath H K` (First: `Manjunath`, Last: `H K`, Prefix: `Mr.`)
  * Email: `manjunathhk833@gmail.com`
  * Phone: `+917337813770` (Country: `India (+91)`, Dial Code: `+91`, Number: `7337813770`)
  * Address: `Bengaluru`, City: `Bengaluru`, State: `Karnataka`, Postal Code: `560076`, Country: `India`
* **Profiles & Portfolio:**
  * LinkedIn: `https://www.linkedin.com/in/manjunath-h-k-ab30b1146/`
  * GitHub: `https://github.com/manjunathk833`
  * Portfolio: `https://manjunathhk.netlify.app/`
* **Compensation & Notice Period:**
  * Current CTC: `₹17,00,000 INR` (`17 LPA` / `1700000`)
  * Expected CTC: `₹27,00,000 INR` (`27 LPA` / `2700000`). If range required: `25–30 Lakhs` (`2500000 - 3000000 INR`)
  * Notice Period: `60 Days` (Numeric: `60`)
* **Experience & Skills Overview:**
  * Total Experience: `7 years` (Senior SDET / QA Automation Architect)
  * Primary Stack: `Java`, `Selenium`, `REST Assured`, `Playwright`, `API Testing`, `Python`, `BDD`, `Cucumber`, `CI/CD`, `SQL`, `Docker`, `Kafka`
* **Repeatable Experience Records (for `+ Add Experience Details`):**
  1. `Value Labs` | `Senior Engineer - QE` | Start: `June 2023` | End: `Present` (Currently Working: `Yes`) | Location: `Bengaluru, India` | Summary: `Architected UI and API automation frameworks for airline projects leveraging REST Assured, Selenium, and BDD with Harness CI/CD.`
  2. `Dunzo` | `SDET-1` | Start: `August 2022` | End: `June 2023` (Currently Working: `No`) | Location: `Bengaluru, India` | Summary: `Automated end-to-end API flows and DB validations using Ekam Java Framework, achieving 60% test coverage in microservices suite.`
  3. `Tata Elxsi` | `Engineer -> Senior Engineer, QA` | Start: `December 2019` | End: `August 2022` (Currently Working: `No`) | Location: `Bengaluru, India` | Summary: `Designed BDD automation framework using Python and Appium, automated ~50% sanity suite saving ~5 man-days/month.`
* **Repeatable Education Record (for `+ Add Education Details`):**
  * Institution: `Sri Jayachamarajendra College of Engineering (SJCE), Mysore` | Degree: `Bachelor of Engineering (B.E.)` | Dates: `2015 – 2019` | GPA: `8.02 / 10`
* **Standard Screening Answers:**
  * Prior employment: `No` | Authorized to work: `Yes` | Require Sponsorship: `No` | Relatives at company: `No` | Non-compete: `No`
  * Anyone working in company / Employee referral: `No` | If details asked: `NA`
  * Gender: `Male` | Veteran: `I am not a protected veteran` | Disability: `No, I do not have a disability`

### Step 4: High-Speed Hybrid Fast-Path Application Architecture
For each approved job in the queue:
1. Identify target URL and application type:
   * If `application_type == "EASY_APPLY"`: target `job_url` (`https://www.linkedin.com/jobs/view/<job_id>/`).
   * If `application_type == "LINKEDIN_EXTERNAL"` or direct ATS: target `external_url` or `job_url`.
2. **Fail-Fast Rule (Strict Zero Over-Exploration):**
   * Check target URL for 404, "Job closed", "No longer accepting applications", or expired notice (max 2 quick checks).
   * **STRICTLY PROHIBITED:** Do NOT search Google, browse career search portals, or explore alternate job postings.
   * If the job is unavailable or expired: log as `UNAVAILABLE`, purge the file from `data/approved_queue/`, and **immediately advance to the next job**.
3. **Execution Priority 1: Native Headful Playwright Fast-Path (3–5 Seconds Execution):**
   * Trigger the local Command Center autofill engine directly:
     ```bash
     curl -s -X POST http://127.0.0.1:8000/api/autofill/{job_id}
     ```
   * Populates 20+ fields (60 Days notice, 17 LPA current CTC, 27 LPA expected CTC, Value Labs, Dunzo, Tata Elxsi experience, SJCE education) and attaches the tailored PDF resume in **under 5 seconds** in local headful Chrome, stopping at the final Review step.
4. **Execution Priority 2: Multimodal `browser_subagent` Fallback:**
   * For non-standard or custom career portals (e.g. Keka, bespoke wizards):
     * Launch `browser_subagent` passing the inlined candidate lookup dictionary compiled in Step 3.
     * **Zero-Hallucination Directive:** STRICTLY populate fields from the candidate dictionary; never fabricate metrics or dates.
     * **Expand Repeatable Containers:** Click `+ Add Experience Details` to add Value Labs, Dunzo, and Tata Elxsi; click `+ Add Education Details` to add SJCE degree; add primary skills tags.
     * **Negative Referral Fields:** Answer `No` to company employee questions and enter `NA` in follow-up relation textboxes.
     * Enforce a hard budget of **20 actions maximum** per job.

### Step 5: Targeted Human-in-the-Loop Clarification Interceptor & Anti-Looping Safeguard
* The agent executes independently across jobs without interrupting for known data bank values.
* Form filling operations leverage `AutofillSelfHealer` with real-time telemetry streaming to `data/logs/autofill_events.jsonl`.
* **Anti-Looping Diagnostic Lock (Max 2 Attempts):**
  * NEVER attempt the exact same sequence or operation (login, account creation, form submission, button click, page navigation) more than twice if it results in an error, timeout, crash, or unchanged state.
  * On the 2nd failure, immediately halt further retries, capture DOM element dumps/screenshots, determine the root cause (e.g. pending email verification, pointer interception, CAPTCHA, or DOM selector mismatch), patch the code/selector, or escalate to the user with actionable instructions. Repeating the same failed attempt 3+ times without diagnosis is strictly prohibited.
* **Only halt and invoke `ask_question` for:**
  * Specific numerical salary expectations requiring candidate input.
  * Novel questions completely missing from `workday_field_mappings.json`.
  * Security challenges (CAPTCHA, Cloudflare, 2FA, OTP, email verification link).
* Once answered, apply the response, cache the mapping into `workday_field_mappings.json`, and continue.

### Step 6: Final Review Step & Real-Time Server Synchronization
1. Submit application at the final Review step (or prompt user if in assisted mode).
2. **Synchronize Server & Database via REST API:**
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/tracking/mark-applied/{job_id}
   ```
   * **Automated Actions Performed by the Endpoint:**
     * Marks the job as `applied` in SQLite `ApplicationDatabase`.
     * Archives the compiled PDF resume from `data/approved_queue/` into `data/resumes/`.
     * Safely purges temporary JSON and PDF files from `data/approved_queue/`.
     * Refreshes Tab 2 (`Approved Queue`) and Tab 3 (`Applied Tracking`) on `http://localhost:8000` live.
3. Automatically proceed to the next approved job until the queue is clear.
