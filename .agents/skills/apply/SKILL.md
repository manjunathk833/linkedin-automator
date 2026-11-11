---
name: apply
description: Autonomous Job Application Skill. Inspects data/approved_queue/ and deterministically applies to all approved jobs using the 2-Phase UniversalBatchFormFiller and candidate data bank, prompting the user via ask_question when clarifications or CAPTCHAs are required. Use when the user asks to apply for approved jobs, run the apply agent, or types /apply.
---

# Autonomous Apply Agent Workflow (`/apply`)

Use this skill whenever the user triggers `/apply` or asks to apply for jobs staged in `data/approved_queue/`.

---

## Operational Runbook

### Step 1: Ensure Server & Browser Session Readiness
1. Verify the Command Center server is active on `http://127.0.0.1:8000` (`lsof -i :8000`). If inactive, start it in the background (`./venv/bin/python -m uvicorn src.ui.app:app --host 127.0.0.1 --port 8000`, `IsDaemon: true`).
2. Reuse the existing headful Chrome session on CDP port `9222` (`src/browser/cdp_stealth.py` attaches automatically without profile lock collisions).

### Step 2: Inspect Approved Queue
1. Scan `data/approved_queue/*.json` (excluding `*_resume.json`).
2. If empty, notify the user (`⚠️ No approved jobs found in data/approved_queue/ — approve jobs at http://localhost:8000`) and stop.
3. List queued roles with company, title, application type, and matched tailored PDF path (`data/approved_queue/*_Resume.pdf`). Respect any user-specified company exclusions.

### Step 3: Load Candidate Ground Truth from Local Profile Store
Load authentic candidate details directly from the local gitignored profile files (never guess or fabricate values):
* **Primary Profile Store:** `data/profile/candidate_master_data.json` (Legal name, email, `+91` phone number, Bengaluru/Karnataka/560076 address, LinkedIn/GitHub/Portfolio URLs, EEOC disclosures).
* **Compensation & Notice Invariants:**
  * Notice Period: `60 Days` (Numeric: `60`)
  * Current CTC: `17,00,000 INR` (`17 LPA`)
  * Expected CTC: `27,00,000 INR` (`27 LPA`; Range: `25–30 Lakhs`)
  * Total Experience: `6.8 years` / `7 years` (Senior SDET / QA Automation Architect)
* **Repeatable Work & Education History (`data/resume_profile.json`):**
  1. `Value Labs` — `Senior Engineer - QE` (`June 2023 – Present`, Bengaluru)
  2. `Dunzo` — `SDET-1` (`August 2022 – June 2023`, Bengaluru)
  3. `Tata Elxsi` — `Senior Engineer, QA` (`December 2019 – August 2022`, Bengaluru)
  4. Education: `Sri Jayachamarajendra College of Engineering (SJCE), Mysore` — `B.E.` (`2015 – 2019`, GPA `8.02/10`)
* **Screening Mappings:** `data/profile/workday_field_mappings.json` & `data/logs/learned_field_mappings.json` (Authorized to work in India: `Yes`, Sponsorship required: `No`, Prior employment / Relatives / Referral at company: `No`, Referral details if asked: `NA`).

### Step 4: High-Speed Multi-Tab Hybrid Application Execution (20–30+ Apps/Hr)
1. **Execution Priority 0: Organization-Grouped & Multi-Tab Parallel Fast-Track Engine (`0` LLM Tokens, `concurrency=5`):**
   * Run the deterministic multi-tab batch engine first across `data/approved_queue/` (or target specific multi-job organizations via `--org "<company_or_host>"`):
     ```bash
     ./venv/bin/python main.py bulk-apply --batch-size 15 --ignore-tiers
     # Or target a specific multi-job Workday/ATS organization:
     ./venv/bin/python main.py bulk-apply --org "HPE" --batch-size 20 --ignore-tiers
     ```
   * **Workday Sign-In-First $\rightarrow$ Register Fallback & `Use My Last Application`:**
     * On every Workday Auth Gate, the engine tries **`Sign In` first** (`[data-automation-id="auth_signin_link"]` / `signInLink`). Only if `Sign In` returns an error (`[data-automation-id="errorMessage"]` / `"wrong email address or password"`), it switches to **`Create Account`** (`[data-automation-id="createAccountLink"]`), registers once, and fast-parks at Email Verification (`EMAIL_VERIFY_REQUIRED`) with the floating Candidate Cheat Sheet badge.
     * In the Workday `'Start Your Application'` modal, the engine prioritizes **`Use My Last Application`** (`[data-automation-id="useMyLastApplication"]`) ahead of `Apply Manually`, while still attaching the job-specific tailored PDF on Stage 2 (`My Experience`).
     * For multi-job Workday tenants (`HPE`, `LSEG`, `Amgen`, `Thermo Fisher`, `Nvidia`, `Citi`, `Danaher`, `Dexcom`, etc.), `execute_batch()` serializes the **Lead Job (`#1`)** first: if the tenant requires Email Verification or Auth HITL, remaining jobs on that same tenant are deferred (`DEFERRED_AWAITING_TENANT_AUTH`) instead of spawning duplicate registration tabs; once Lead Job `#1` authenticates, all remaining jobs at that org fast-track in waves!
   * After you click email verification links or complete parked tabs in Chrome, sweep all open tabs in one command:
     ```bash
     ./venv/bin/python main.py bulk-apply resume
     ```
2. **Strict Fail-Fast Policy (Zero Over-Exploration):**
   * If the job URL returns 404, "Job closed", or "No longer accepting applications" (max 2 checks), **never** search Google or browse external career portals. Log `JOB_UNAVAILABLE`, purge the payload from `data/approved_queue/`, and immediately advance to the next job.
3. **Execution Priority 1: Native Headful Playwright Fast-Path (`3–5s`):**
   * Call `curl -s -X POST http://127.0.0.1:8000/api/autofill/{job_id}` for single-job assisted autofill on standard supported vendors (`EASY_APPLY`, `GREENHOUSE_STANDARD`, `LEVER_STANDARD`, `ASHBY_STANDARD`, `WORKDAY_STANDARD`).
4. **Execution Priority 2: 2-Phase `form-batch` Universal DOM Engine (`<10s`):**
   * **Phase A (Single-Call DOM Extract + Deterministic Batch Fill):**
     ```bash
     ./venv/bin/python main.py form-batch inspect --job-id {job_id}
     ```
     Tags visible controls with `data-agy-id`, fills all known fields (`60 Days` notice, `17 LPA` / `27 LPA`, `India (+91)` with `British Indian Ocean Territory (+246)` strictly excluded via `TERRITORY_EXCLUSIONS`), verifies filled values via DOM read-back, and prints only `unmapped_fields` JSON.
   * **Phase B (1-Turn Custom Field Batch Fill + Closed-Loop Learning):**
     Resolve all remaining `unmapped_fields` in **one single turn** and apply in one batch call:
     ```bash
     ./venv/bin/python main.py form-batch apply --job-id {job_id} --actions '{"agy_field_8": "Yes"}'
     ```
     Custom answers are automatically banked into `data/logs/learned_field_mappings.json` for zero-LLM reuse on future applications.
   * Expand repeatable sections (`+ Add Experience Details`, `+ Add Education Details`) when present.

### Step 5: Targeted HITL Clarification & Anti-Looping Lock
* **Anti-Looping Lock (Max 2 Attempts):** Never repeat the same failed click, login, or navigation more than twice. On the 2nd failure, capture DOM diagnostics and either patch or escalate via `ask_question`.
* **Targeted HITL (`ask_question`):** Prompt the user *only* for novel screening questions absent from the data bank or security challenges (CAPTCHA, OTP, 2FA).

### Step 6: Submission Confirmation & HTTP 412 Verification Gate
1. Confirm authentic submission screen in Chrome (e.g., `"Application sent"`, `"Thank you for applying"`), capture visual proof to `data/logs/screenshots/`, and ensure `SUBMISSION_CONFIRMED` is logged in `data/logs/autofill_events.jsonl`.
2. Verify proof via REST gate:
   ```bash
   curl -s http://127.0.0.1:8000/api/tracking/verify/{job_id}
   ```
   *(If `verified != true`, DO NOT mark applied; keep Chrome open and alert the user).*
3. Once verified, mark applied and purge queue payload:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/tracking/mark-applied/{job_id}
   ```
4. At the end of the batch run, if any job had `failed_count > 0`, run `./venv/bin/python main.py autofill --audit`.
