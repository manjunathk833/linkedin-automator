Below are the three standalone, agent-executable Markdown specification files designed to drop directly into your repository's existing `docs/sprints/` directory (following your `docs/sprints/sprint_[1-4]_plan.md` convention from Milestone 40).

Each file is structured as a deterministic prompt and execution specification for **Gemini 3.8** (`gemini-3.8-flash` / Antigravity IDE), enforcing your repository's core governance rules: zero architectural bloat, strict employer boundary isolation, 100% pass rate on `python main.py test --tier core`, zero Ruff lint errors (`python main.py lint`), and branch isolation on `develop`.

---

### 1. Sprint 5 Markdown File (`docs/sprints/sprint_5_plan.md`)

Save the following file as `docs/sprints/sprint_5_plan.md`. It instructs the agent to ground **AI Evaluation** (`DeepEval`, `RAGAS`, `Promptfoo`), **AI Security Red-Teaming** (`OWASP LLM`, `Garak`), and **Browser Automation** (`CDP`) inside your knowledge vault (`data/candidate_notes.md`) and whitelist (`data/profile/allowed_tools_whitelist.json`) while strictly isolating those tools to your `Technical Projects` section so they never contaminate your historical work experience at ValueLabs, Dunzo, or Tata Elxsi.

# Sprint 5 Execution Plan: AI Evaluation & Red-Teaming Knowledge Grounding

> **Target Agent / Model:** `gemini-3.8-flash` / Antigravity Coding Agent
> **Target Branch:** `develop` (Rule 9: Zero direct push to `main`)
> **Architectural Constraint:** Zero-Bloat. Do NOT add new classes, databases, or LLM pipelines. Extend existing JSON/Markdown data stores and verify boundary isolation via `TIER_1_CORE`.

---

## 1. Objective & Context

Upgrade the candidate's grounded knowledge bank (`data/candidate_notes.md` -> `data/master_knowledge_bank.json`) and deterministic tool whitelist (`data/profile/allowed_tools_whitelist.json`) so the resume tailorer (`src/tailor/resume_tailorer.py`) can legitimately tailor resumes for **AI QA Engineer**, **LLM Evaluation Engineer**, **DevSecOps QA**, and **Browser Automation (CDP)** requisitions without triggering `FabricationDetector` (`src/tailor/fabrication_detector.py`) or `ResumeVerificationGate` (`src/llm/validator.py`) purge actions.

### Domain Invariants to Preserve

1. **Strict Employer Boundary Isolation (Gates 51, 52, 61):** New AI evaluation and security red-teaming tools (`deepeval`, `ragas`, `promptfoo`, `garak`, `pyrit`, `owasp llm`, `langsmith`, `cdp`) must be scoped strictly to `Technical Projects (Independent Architecture)` / `Personal` achievements. They must **never** leak into historical employer experience blocks (`Value Labs`, `Dunzo`, `Tata Elxsi`).
2. **Zero Third-Party Cost:** Syncing must execute through the existing `HybridLLMProvider` (`python main.py sync`) using the 4.0s rate pacer and local Ollama fallback.

---

## 2. Step-by-Step Implementation Tasks

### Task 1: Append Authentic AI Evaluation & CDP Achievements to `data/candidate_notes.md`

Open `data/candidate_notes.md` and locate the `## Technical Projects (Independent Architecture)` section. Append the following two structured engineering notes (preserving all existing notes):

* **Note A (LLM & RAG Evaluation + AI Security Red-Teaming Harness):**
Architected an automated 2-stage AI Quality and Security CI/CD evaluation gate in Python, PyTest, and GitHub Actions (`llm-rag-eval-redteam-harness`). Stage 1 executes deterministic contract assertions and automated OWASP LLM Top 10 adversarial red-teaming (prompt injection, jailbreak, and PII leakage detection) using Promptfoo and Garak. Stage 2 executes semantic LLM-as-a-Judge evaluation on Retrieval-Augmented Generation (RAG) outputs using DeepEval and RAGAS to measure Faithfulness, Answer Relevancy, and Context Recall, blocking staging builds on hallucination regressions.
* **Note B (Autonomous CDP Browser Automation & Grounded AI Pipeline):**
Engineered a production-grade autonomous browser automation and LLM orchestration platform using Python, Playwright, Chrome DevTools Protocol (CDP port 9222 reuse), and FastAPI. Implemented cubic Bézier cursor kinematics, closed-loop DOM self-healing (`AutofillSelfHealer`), hybrid Gemini/Ollama routing with Pydantic schema validation, and a deterministic anti-hallucination verification gate (`FabricationDetector`).

### Task 2: Expand `data/profile/allowed_tools_whitelist.json`

Open `data/profile/allowed_tools_whitelist.json` and add the following canonical tool tokens to the allowed whitelist array (and project-scoped boundary list in `src/tailor/knowledge_translator.py` / `src/tailor/fabrication_detector.py` if hardcoded sets exist):

* `"deepeval"`
* `"ragas"`
* `"promptfoo"`
* `"langsmith"`
* `"langfuse"`
* `"owasp llm"`
* `"garak"`
* `"pyrit"`
* `"cdp"`
* `"chrome devtools protocol"`
* `"pydantic"`
* `"fastapi"`

### Task 3: Verify Boundary Scoping in `src/tailor/knowledge_translator.py` & `src/tailor/fabrication_detector.py`

1. Inspect `src/tailor/knowledge_translator.py` and `src/tailor/fabrication_detector.py` (specifically the company-exclusive marker mapping from Milestones 28 and 61).
2. Ensure that `deepeval`, `ragas`, `promptfoo`, `garak`, `pyrit`, `owasp llm`, and `langsmith` are registered in the **Project-Only / Independent Architecture** scope so that:
* Bullet generation for `Technical Projects` retains these tools.
* Bullet generation for `Value Labs`, `Dunzo`, and `Tata Elxsi` strips or blocks these tools if the LLM attempts to inject them into past employment history.


3. Run `python main.py sync` to translate the updated markdown notes into `data/master_knowledge_bank.json` via atomic `os.replace()`.

### Task 4: Author Verification Gate `verify/82_test_sprint5_ai_eval_grounding.py`

Create a standalone offline test script `verify/82_test_sprint5_ai_eval_grounding.py` and register it in `verify/run_regressions.py` under `TIER_1_CORE`. The test must assert:

1. `allowed_tools_whitelist.json` contains `"deepeval"`, `"ragas"`, `"promptfoo"`, `"owasp llm"`, `"garak"`, and `"cdp"`.
2. `FabricationDetector` / `ResumeVerificationGate` permits a `Technical Projects` bullet containing `"DeepEval, RAGAS, and Promptfoo for OWASP LLM red-teaming"`.
3. `FabricationDetector` / company boundary validator rejects or strips `"DeepEval"` and `"Promptfoo"` when passed inside a `Tata Elxsi` or `Dunzo` employer bullet.
4. `master_knowledge_bank.json` passes Pydantic schema validation with zero cross-employer contamination.

---

## 3. Acceptance & Governance Gate

Execute the following commands in sequence and do not finish until both return `0` exit codes:

1. `python main.py test --tier core` (Must pass 63/63 tests including Gate 82 in <45s)
2. `python main.py lint` (Must pass Ruff check with 0 errors)

---

### 2. Sprint 6 Markdown File (`docs/sprints/sprint_6_plan.md`)

Save the following file as `docs/sprints/sprint_6_plan.md`. It instructs the agent to upgrade your existing filter functions (`src/ingestion/filters.py` and `src/filter/job_filter.py`), priority router (`src/tailor/referral_generator.py`), and enterprise registry (`data/config/target_companies.json`) to capture high-paying **AI QA / LLM Evaluation** and **DevSecOps QA** roles, block low-paying SOC/Pentest career resets and manual data-labeling roles, and implement the 3-stage **Global Remote USD/EUR & EOR (`Deel`/`Oyster`/`B2B`)** classifier.

# Sprint 6 Execution Plan: AI QA & DevSecOps Filters, USD/EOR Classifier & GCC Registry Expansion

> **Target Agent / Model:** `gemini-3.8-flash` / Antigravity Coding Agent
> **Target Branch:** `develop` (Rule 9: Zero direct push to `main`)
> **Architectural Constraint:** Zero-Bloat. Modify ONLY existing filter functions (`src/ingestion/filters.py`, `src/filter/job_filter.py`), router heuristics (`src/tailor/referral_generator.py`), and config registries (`config.yaml`, `data/config/target_companies.json`).

---

## 1. Objective & Context

Refine upstream discovery and filtering heuristics to maximize interview conversion at Tier-1 Bengaluru Global Capability Centers (GCCs), Indian product unicorns, and cross-border USD/EUR remote organizations:

1. Capture emerging AI Quality Engineering, LLM Evaluation, and DevSecOps/AI-Security QA titles.
2. Prevent seniority/CTC resets by explicitly blocking L1/L2 SOC Analyst, pure Penetration Testing, GRC, and manual AI data-annotation roles.
3. Upgrade global remote detection beyond naive location headers by detecting USD/EUR compensation and EOR/B2B contractor keywords (`Deel`, `Oyster`, `Remote.com`, `Multiplier`, `B2B contract`) while aggressively rejecting US/EU residency locks (`W-2 only`, `no C2C`, `ITAR`).

---

## 2. Step-by-Step Implementation Tasks

### Task 1: Expand Title Taxonomy in `src/ingestion/filters.py` (`is_sdet_title`) & `config.yaml`

1. In `src/ingestion/filters.py` (`is_sdet_title`), add the following case-insensitive positive title patterns:
* `"ai qa"`, `"ai test"`, `"llm evaluation"`, `"ai quality"`, `"genai qa"`, `"ml quality"`, `"agentic qa"`, `"qa lead - ai"`, `"qa lead, ai"`
* `"devsecops qa"`, `"security automation engineer"`, `"ai red team"`, `"browser automation engineer"`


2. In `src/ingestion/filters.py` (`is_sdet_title`), append the following negative exclusions to prevent low-CTC security resets and data-labeling noise:
* `"soc analyst"`, `"soc l1"`, `"soc l2"`, `"grc"`, `"information security auditor"`, `"iam administrator"`, `"penetration tester"`, `"ethical hacker"`, `"dataset reviewer"`, `"data annotator"`, `"ai trainer"`, `"manual tester"`


3. In `config.yaml` (and `src/scraper/job_finder.py` default boolean queries), add `"AI QA Engineer"`, `"LLM Evaluation Engineer"`, and `"AI Test Engineer"` to the boolean search profile list.

### Task 2: Implement 3-Stage Global Remote USD/EUR & EOR Classifier in `src/ingestion/filters.py` & `src/filter/job_filter.py`

1. Create a deterministic helper function `evaluate_global_remote_signal(title: str, location: str, description: str, compensation_str: str = "") -> dict` in `src/ingestion/filters.py` (and invoke it inside `src/filter/job_filter.py`):
* **Stage 1 (Foreign Currency Regex):** Match `(?:\$\s?\d{2,3}(?:,\d{3})+(?:\s?-\s?\$\s?\d{2,3}(?:,\d{3})+)?|\$\d{2,3}[kK]\s?-\s?\$\d{2,3}[kK]|\bUSD\s?\d{2,3}[kK]?|\b(?:EUR|€|GBP|£)\s?\d{2,3}[kK,]+|\$\d{2,3}\s?/\s?(?:hr|hour))`.
* **Stage 2 (Cross-Border EOR & B2B Signal):** Match `\b(?:Deel|Oyster\s?HR|Remote\.com|Multiplier|Papaya\s?Global|B2B\s+contract(?:or)?|independent\s+contractor|work\s+from\s+anywhere|global\s+remote|async-first)\b`.
* **Stage 3 (Hard Geo-Lock Exclusion in `has_jurisdiction_restriction`):** Expand `has_jurisdiction_restriction` to return `True` if description matches `\b(?:must\s+reside\s+in\s+(?:the\s+)?(?:US|USA|United\s+States|Canada|UK|EU)|US\s+citizens?\s+only|W-?2\s+only|no\s+C2C|no\s+corp-to-corp|security\s+clearance|ITAR|FedRAMP|authorized\s+to\s+work\s+in\s+the\s+US\s+without\s+sponsorship)\b`, UNLESS `"India"` or `"Bengaluru"` is explicitly present as a co-listed hub.


2. **Override Rule:** If a job location header says `"San Francisco, CA (Remote)"` or `"Remote - US"`, normally `is_india_or_remote_location` would reject it. Update the check so that if `"remote"` is in the location AND Stage 2 (`has_eor_or_b2b_signal`) is `True` AND Stage 3 (`has_jurisdiction_restriction`) is `False`, the job is **retained** and tagged with `is_usd_eor_remote: True` in the payload metadata.

### Task 3: Boost Priority in `InterviewRouter` (`src/tailor/referral_generator.py`)

In `InterviewRouter.classify_job_strategy`:

* If a non-Workday job has `is_usd_eor_remote == True` or matches the new AI Evaluation title keywords AND was posted within `<24h`, ensure it routes directly to `TIER_1_SNIPER_APPLY` (unless a `TIER_0_POST_AUTHOR` lead exists).

### Task 4: Expand `data/config/target_companies.json` with Bengaluru AI GCCs & EOR Remote Startups

Append validated entries to `data/config/target_companies.json` using the exact existing JSON schema (`name`, `ats`, `slug` / Workday `tenant`/`datacenter`/`site`, `is_dream_org: true`) for:

* **Bengaluru AI-First GCCs & Product Hubs:** Microsoft IDC, Walmart Global Tech, Goldman Sachs, JPMorgan Chase, Intuit, SAP Labs, Target, Penguin Solutions, Autodesk, Bosch Global Software.
* **Global Remote / Ashby / Greenhouse / Lever AI Orgs:** Deel, LangChain, Weights & Biases, Arize AI, PostHog, GitLab, Sprinto HQ, HighLevel, Twilio.

### Task 5: Author Verification Gate `verify/83_test_sprint6_filters_and_usd_remote.py`

Create `verify/83_test_sprint6_filters_and_usd_remote.py` and register it in `verify/run_regressions.py` (`TIER_1_CORE`). Assert:

1. `is_sdet_title()` returns `True` for `"AI QA Engineer"`, `"LLM Evaluation Engineer"`, `"QA Lead, AI Agents"`, and `"Browser Automation Engineer"`.
2. `is_sdet_title()` returns `False` for `"SOC Analyst L2"`, `"AI Dataset Reviewer"`, `"Penetration Tester"`, and `"GRC Analyst"`.
3. `evaluate_global_remote_signal()` retains a job with location `"San Francisco (Remote)"` and description `"Compensation: $120k - $145k USD. We hire globally via Deel or B2B contractor."`
4. `has_jurisdiction_restriction()` rejects a job with location `"Remote"` and description `"Must reside in the United States. W-2 only, no C2C."`
5. `target_companies.json` parses cleanly with zero duplicate slugs.

---

## 3. Acceptance & Governance Gate

Execute in sequence and verify `0` exit codes:

1. `python main.py test --tier core` (Must pass 64/64 tests in <45s)
2. `python main.py lint` (0 Ruff errors)

---

### 3. Sprint 7 Markdown File (`docs/sprints/sprint_7_plan.md`)

Save the following file as `docs/sprints/sprint_7_plan.md`. It instructs the agent to build two lightweight discovery collectors (`src/ingestion/hirist.py` and `src/ingestion/instahyre.py`) that plug straight into your existing `ATSDiscoveryCoordinator` (`src/ingestion/ats_discovery.py`), connect discovered Hirist jobs to your already-built `_fill_hirist()` state machine (`HIRIST_TECH_STANDARD`), and upgrade `scripts/naukri_pinger.py` and `com.linkedin.automator.daily.plist` to execute twice-daily micro-saves with negotiable 30-day buyout framing.

# Sprint 7 Execution Plan: Hirist & Instahyre Discovery Collectors + 2x Daily Naukri Resdex Trap

> **Target Agent / Model:** `gemini-3.8-flash` / Antigravity Coding Agent
> **Target Branch:** `develop` (Rule 9: Zero direct push to `main`)
> **Architectural Constraint:** Reuse existing `ATSDiscoveryCoordinator`, `JobListing` Pydantic schema, `is_cdp_port_open(9222)` browser attachment, and `HIRIST_TECH_STANDARD` autofill handler. Never scrape Naukri outbound jobs; use Naukri strictly as a 2x daily inbound Resdex trap.

---

## 1. Objective & Context

1. **Close the Hirist Discovery Loop:** Module 17 (`src/autofill/ats_filler.py` and `src/autofill/vendor_schemas.py`) already implements a verified 5-stage autofill state machine for `hirist.tech` (`HIRIST_TECH_STANDARD` / `_fill_hirist()`), but `src/ingestion/` lacks a discovery collector to feed it jobs automatically.
2. **Add Curated Product Discovery via Instahyre:** Product companies and AI startups in Bengaluru actively post high-CTC (`₹26–45 LPA`) `"QA Engineer - AI"`, `"SDET III"`, and `"Browser Automation (Playwright/CDP)"` roles on `instahyre.com`.
3. **Maximize Naukri Resdex Inbound Calls:** Recruiters filter out 97% of Naukri candidates using `[✓] Last Active: 1 Day` and `Notice Period <= 30 Days`. Upgrading `scripts/naukri_pinger.py` to run twice daily (8:30 AM & 2:15 PM IST) with explicit 30-day buyout/negotiable framing in the headline keeps the profile in the top 1.2% recruiter shortlist pool.

---

## 2. Step-by-Step Implementation Tasks

### Task 1: Build Lightweight Hirist Collector (`src/ingestion/hirist.py`)

Create `src/ingestion/hirist.py` implementing `HiristCollector`:

1. Query `hirist.tech` search endpoints/pages for targeted queries (`"SDET"`, `"Playwright"`, `"AI QA"`, `"Automation Architect"`) scoped to Bengaluru (`Bangalore`) and Remote.
2. Pass raw titles and locations through `is_sdet_title()` and `is_india_or_remote_location()` from `src/ingestion/filters.py`.
3. Normalize matching postings into the existing Pydantic `JobListing` schema with `source="hirist"` and canonical `job_url` pointing to `[https://www.hirist.tech/j/](https://www.hirist.tech/j/)...` so `classify_ats_pattern()` automatically maps approved cards to `HIRIST_TECH_STANDARD`.

### Task 2: Build CDP-Backed Instahyre Collector (`src/ingestion/instahyre.py`)

Create `src/ingestion/instahyre.py` implementing `InstahyreCollector`:

1. Reuse `launch_stealth_browser` / `is_cdp_port_open(9222)` from `src/browser/cdp_stealth.py` (Gate 81 fast-path) or clean HTTP fetch for public skill pages:
* `[https://www.instahyre.com/playwright-jobs-in-bangalore/](https://www.instahyre.com/playwright-jobs-in-bangalore/)`
* `[https://www.instahyre.com/remote-playwright-jobs/](https://www.instahyre.com/remote-playwright-jobs/)`
* `[https://www.instahyre.com/remote-automation-testing-jobs/](https://www.instahyre.com/remote-automation-testing-jobs/)`
* Authenticated candidate match feed (`/candidate/opportunities`) when session cookies exist.


2. Filter titles via `is_sdet_title()` and normalize into `JobListing` with `source="instahyre"`.
3. Add `"instahyre"` and `"hirist"` badge normalization rules in `normalize_job_source_metadata()` inside `src/ui/app.py` and `formatSourceBadge()` in `src/ui/static/app.js`.

### Task 3: Wire Collectors into `ATSDiscoveryCoordinator` (`src/ingestion/ats_discovery.py`)

1. Register `HiristCollector` and `InstahyreCollector` inside `ATSDiscoveryCoordinator` alongside Greenhouse, Lever, Ashby, and Workday.
2. Ensure cross-source MD5 composite hash deduplication (`company:title:location`) and `ApplicationDatabase().get_applied_job_ids()` pre-ingestion purge defense apply identically to `hirist` and `instahyre` listings.

### Task 4: Upgrade `scripts/naukri_pinger.py` & `com.linkedin.automator.daily.plist` for 2x Daily Resdex Touch

1. Open `scripts/naukri_pinger.py`:
* Implement deterministic rotation of the Naukri Resume Headline between two high-signal variants on each micro-save so Resdex re-indexes the profile timestamp:
* **Variant A:** `"Senior SDET (7 YOE) | Playwright, Java, Python, AI & LLM Evaluation (DeepEval, RAGAS) | Ex-Dunzo, Tata Elxsi | Notice: 60 Days (Negotiable to 30d / Buyout)"`
* **Variant B:** `"Senior SDET & AI QA Architect | Playwright, REST Assured, Python, Agentic AI & CI/CD | Ex-Dunzo, Tata Elxsi | Notice: 60 Days (Early Release / 30d Buyout)"`


* Log execution status (`NAUKRI_RESDEX_TOUCH_SUCCESS`) with timestamp to `data/logs/daily_runs.jsonl`.


2. Open `com.linkedin.automator.daily.plist` (or `scripts/setup_daily_runner.sh`):
* Configure `StartCalendarInterval` array to run the morning full pipeline at `08:00` IST and an afternoon lightweight Naukri Resdex micro-save (`python scripts/naukri_pinger.py`) at `14:15` IST.



### Task 5: Author Verification Gate `verify/84_test_sprint7_hirist_instahyre_and_naukri.py`

Create `verify/84_test_sprint7_hirist_instahyre_and_naukri.py` and register it in `verify/run_regressions.py` (`TIER_1_CORE`). Assert:

1. Mocked HTML/JSON fixtures from `hirist.tech` and `instahyre.com` parse into valid Pydantic `JobListing` objects with `source="hirist"` and `source="instahyre"`.
2. `classify_ats_pattern()` maps discovered `hirist.tech` job URLs to `HIRIST_TECH_STANDARD`.
3. `normalize_job_source_metadata()` in `src/ui/app.py` accurately attributes `"hirist"` and `"instahyre"` sources.
4. `scripts/naukri_pinger.py` headline rotator produces strings within Naukri's character limit (`<= 250` chars) and includes `"30d"` / `"Buyout"` notice framing and `"DeepEval"` / `"Playwright"` keywords.

---

## 3. Acceptance & Governance Gate

Execute in sequence and verify `0` exit codes:

1. `python main.py test --tier core` (Must pass 65/65 tests in <45s)
2. `python main.py lint` (0 Ruff errors)

---

### How to Drive Each Sprint in Antigravity / Gemini 3.8

Once you save those three files into `docs/sprints/`, you can execute them one by one in your terminal or Antigravity IDE chat with a single prompt:

Read docs/sprints/sprint_5_plan.md and execute all tasks on the `develop` branch. Follow .agents/rules/00-core-instructions.md and do not stop until `python main.py test --tier core` and `python main.py lint` pass with 0 errors.