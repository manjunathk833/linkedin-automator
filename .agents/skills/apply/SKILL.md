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

### Step 4: Deterministic Application via `browser_subagent`
For each approved job in the queue:
1. Identify target URL:
   * If `application_type == "EASY_APPLY"`: target `job_url` (`https://www.linkedin.com/jobs/view/<job_id>/`).
   * If `application_type == "LINKEDIN_EXTERNAL"`: target `external_url` (or navigate to `job_url` and click external Apply).
2. **Fail-Fast Rule (Strict Zero Over-Exploration):**
   * Check target URL for 404, "Job closed", "No longer accepting applications", or expired notice (max 2 quick checks).
   * **STRICTLY PROHIBITED:** Do NOT search Google, browse career search portals, or explore alternate job postings.
   * If the job is unavailable or expired: log as `UNAVAILABLE`, purge the file from `data/approved_queue/`, and **immediately advance to the next job**.
3. Launch `browser_subagent` with strict instructions:
   * Pass the **exact candidate lookup dictionary** compiled in Step 3 directly in the prompt.
   * **Zero-Hallucination Directive:** STRICTLY populate fields from the provided candidate dictionary. Never hallucinate or improvise numbers or text.
   * **Expand Repeatable Containers:** If an `+ Add Experience Details` or `+ Add Education Details` button is present, click it and populate each job and education record.
   * **Skills Container:** If a skills input exists, enter the primary skills tags.
   * **Negative Referral Fields:** Answer `No` to company employee questions and enter `NA` in follow-up relation textboxes.
   * Attach the matching tailored PDF resume located in `data/approved_queue/`.
   * Enforce a hard budget of **20 actions maximum** per job.

### Step 5: Targeted Human-in-the-Loop Clarification Interceptor
* The agent executes independently across jobs without interrupting for known data bank values.
* **Only halt and invoke `ask_question` for:**
  * Specific numerical salary expectations requiring candidate input.
  * Novel questions completely missing from `workday_field_mappings.json`.
  * Security challenges (CAPTCHA, Cloudflare, 2FA, OTP).
* Once answered, apply the response, cache the mapping into `workday_field_mappings.json`, and continue.

### Step 6: Final Review Step & Database Audit
1. Submit application at the final Review step.
2. Record the application in the SQLite database:
   ```bash
   ./venv/bin/python -c "from src.storage.database import ApplicationDatabase; ApplicationDatabase().record_application(job_id='{job_id}', source='{source}', company_name='{company}', job_title='{title}', job_url='{url}', status='applied')"
   ```
3. Safely delete the processed JSON and archive the PDF to `data/resumes/`.
4. Automatically proceed to the next approved job until the queue is clear.
