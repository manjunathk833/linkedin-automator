# Technical Specification & Module Architecture

This document provides exhaustive, code-level engineering specifications for all 10 subsystems of the application copilot.

---

## 1. System Module Catalog

```
src/
├── browser/                     # Module 2: Anti-detection browser & kinematics
├── ingestion/                   # Module 7: Multi-source keyless ATS collectors
├── scraper/                     # Module 3: 4-Channel LinkedIn discovery scraper
├── tailor/                      # Module 4: Grounded AI resume tailor & translator
├── llm/                         # Module 8: Ollama client & verification gate
├── compiler/                    # Module 8: Single-column ATS PDF generator
├── filter/                      # Module 5: Experience & location policy filter
├── autofill/                    # Module 9: Assisted Easy Apply & ATS form copilot
├── storage/                     # Module 10: Pydantic models & SQLite persistence
├── ui/                          # Module 9: Local FastAPI approval gate dashboard
└── pipeline/                    # Module 1: One-shot pipeline runner orchestrator
```

---

## 2. Module-by-Module Technical Deep Dive

### Module 1: CLI Entrypoint & Pipeline Orchestration
* **Source:** [`main.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/main.py), [`src/pipeline/runner.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/pipeline/runner.py)
* **Architecture:** Decoupled subcommand architecture using `argparse.add_subparsers()` routing into `JobSearchPipelineRunner`.
* **Execution Modes:**
  * `python main.py run` (`pipeline`): Executes end-to-end one-shot pipeline (`sync` $\rightarrow$ `search` $\rightarrow$ `filter` $\rightarrow$ `dashboard`).
  * `python main.py search`: Scrapes and tailors LinkedIn listings across 4 channels.
  * `python main.py sync`: Syncs unstructured notes (`candidate_notes.md`) to `master_knowledge_bank.json`.
  * `python main.py filter`: Scans `data/pending_queue/` and purges non-matching experience postings.
  * `python main.py dashboard`: Launches local FastAPI web UI on port 8000.
  * `python main.py apply [--no-dry-run]`: Executes batch Easy Apply submissions.
  * `python main.py login`: Launches headful persistent Chrome for manual one-time LinkedIn authentication.
  * `python main.py lint`: Runs Ruff auto-fix linter and code formatter.

---

### Module 2: Browser Context, Anti-Detection & Kinematics Engine
* **Source:** [`src/browser/cdp_stealth.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/cdp_stealth.py), [`src/browser/kinematics.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/kinematics.py)
* **CDP Evasion Mechanisms:**
  * Overrides `navigator.webdriver` getter to return `undefined`.
  * Mocks complete `window.chrome` object (runtime, loadTimes, csi, app).
  * Emulates authentic macOS Chrome plugins (PDF Viewer, Chromium PDF Viewer).
  * Passes anti-automation Chrome arguments: `--disable-blink-features=AutomationControlled`, `--disable-infobars`, `--exclude-switches=enable-automation`.
* **Kinematics Math:**
  * Cursor trajectories calculated via cubic Bézier curves:
    $$B(t) = (1-t)^3 P_0 + 3(1-t)^2 t P_1 + 3(1-t) t^2 P_2 + t^3 P_3, \quad t \in [0, 1]$$
  * Intermediate control points $P_1$ and $P_2$ generated with randomized perpendicular offsets proportional to distance ($0.25 \times \text{dist}$).
  * Acceleration modulated with smoothstep easing ($S(t) = 3t^2 - 2t^3$) and Gaussian micro-tremor jitter ($\mu=0, \sigma=0.75$).
  * Keystrokes generated from log-normal distribution ($\mu=\ln(95), \sigma=0.35$, bounded between $40–240$ ms).

---

### Module 3: Multi-Channel LinkedIn Discovery Scraper
* **Source:** [`src/scraper/job_finder.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/scraper/job_finder.py)
* **Discovery Channels:**
  1. *Paginated Keyword Search:* Iterates `start=0, 25, 50` with Boolean filters (`f_AL=true`, `f_WT=2,3`, `f_E=4`, `sortBy=DD`).
  2. *Recommended Feed:* Iterates `/jobs/collections/recommended/` with container scrolling.
  3. *Recruiter Posts:* Queries `/search/results/content/` for posts with `#hiring #sdet`.
  4. *Similar Jobs:* Scrapes related listings sidebar from viewed cards.
* **Resilience Heuristics:** Decoupled card metadata extraction before page navigation to prevent stale Playwright element handles.

---

### Module 4: Grounded AI Resume Tailoring & Translation
* **Source:** [`src/tailor/resume_tailorer.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/resume_tailorer.py), [`src/tailor/llm_provider.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/llm_provider.py), [`src/tailor/knowledge_translator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/knowledge_translator.py)
* **LLM Architecture:**
  * `HybridLLMProvider`: Primary engine Google Gemini 2.5 Flash (`temperature=0.0`); automatic offline fallback to local Ollama (`qwen2.5:7b`).
  * `KnowledgeBankTranslator`: Parses unstructured notes from `data/candidate_notes.md`, chunks them into batches of 5, translates into STAR format, deduplicates via MD5 hashing, and writes to `data/master_knowledge_bank.json`.

---

### Module 5: Experience & Policy Filter Engine
* **Source:** [`src/filter/job_filter.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/filter/job_filter.py)
* **Rules:**
  * Senior SDET Experience Bounds: Requires $\ge 4$ years and $\le 10$ years.
  * Candidate Profile Baseline: 6.8 years (Senior SDET baseline profile).
  * Context-guarded regex ignores false positives (e.g. "20+ years in business", "15 locations").
  * Location policy: Bengaluru (onsite/hybrid/remote) or India (remote only). Non-Bengaluru onsite roles are automatically purged.

---

### Module 6: Easy Apply Execution Engine
* **Source:** [`src/automation/easy_apply.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/automation/easy_apply.py)
* **Workflow:** Attaches to persistent browser, detects Easy Apply triggers, iterates multi-step modals, answers screening questions via LLM solver, attaches tailored PDF, and logs to `data/application_history.json`.

---

### Module 7: Multi-Source Keyless ATS Ingestion Engine
* **Source:** [`src/ingestion/greenhouse.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/greenhouse.py), [`src/ingestion/lever.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/lever.py), [`src/ingestion/ashby.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/ashby.py), [`src/ingestion/ats_discovery.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/ats_discovery.py)
* **Public REST Endpoints:**
  * Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`
  * Lever: `https://api.lever.co/v0/postings/{slug}?mode=json`
  * Ashby: `https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true`
* **Concurrency:** Parallel non-blocking HTTP requests managed via `asyncio.Semaphore(10)`.

---

### Module 8: Deterministic Verification Gate & Typst Resume Compiler
* **Source:** [`src/llm/validator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/llm/validator.py), [`src/compiler/typst_generator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/compiler/typst_generator.py)
* **Deterministic Token Gate:** `ResumeVerificationGate` validates bullets against `data/profile/allowed_tools_whitelist.json`. Automatically purges or substitutes unallowed tools:
  * `playwright` / `cypress` $\rightarrow$ `Selenium`
  * `kubernetes` / `k8s` $\rightarrow$ `Docker`
  * `golang` / `go` $\rightarrow$ `Python`
  * `kafka` $\rightarrow$ `REST API`
* **Compilation:** Compiles clean single-column ATS PDFs into `data/resumes/{company}_{job_id}_{role_slug}.pdf` using Typst CLI with HTML/Playwright fallback.

---

### Module 9: Dual-Mode Application Command Center & Assisted Copilot
* **Source:** [`src/autofill/form_mapper.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/form_mapper.py), [`src/autofill/linkedin_filler.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/linkedin_filler.py), [`src/autofill/ats_filler.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/ats_filler.py), [`src/ui/app.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ui/app.py)
* **Features:**
  * **Dual-Mode Command Center:** Dual tabs (`📋 Staging Review` and `🚀 Ready to Apply`), live queue count polling via `/api/queue-status`, and keyword search filtering.
  * **Approval Pipeline:** Type-coercion approval endpoints (`/api/approve-job`, `/api/approve-all`) that compile single-column ATS PDFs into `data/resumes/` and move jobs to `data/approved_queue/`.
  * **Inline PDF Preview:** `/api/pdf/{job_id}` endpoint serving compiled PDFs directly into a preview modal.
  * **Canonical ATS Routing:** `resolve_canonical_ats_url` translates wrapper career URLs (e.g. Coinbase `gh_jid`) into canonical Greenhouse board URLs.
  * **Multi-Tab & Popup Interception:** Captures `<a target="_blank">` or `window.open()` popups via `page.context.on("page", ...)` event listeners, switches active page focus, calls `bring_to_front()`, and navigates embedded ATS iframes.
  * **Session Longevity:** `_ACTIVE_SESSIONS` global registry keeps headful browser windows alive indefinitely until candidate submission.
  * **Pause-Before-Submit:** Types inputs with humanized Bézier movements and keystroke jitter, attaches tailored PDF, and halts before final submission.

---

### Module 10: Governance, SQLite Audit Trails & Rate Governor
* **Source:** [`src/storage/database.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/storage/database.py), [`src/autofill/governor.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/governor.py)
* **Safety Policy:** Daily quota of $\le 15$ applications per 24 hours. Blocks with HTTP 429 once budget is reached.
* **Audit Trail:** Logs every application into local SQLite database (`data/app_database.db`).

---

## 3. Data Schemas

### Relational Database Schema (`data/app_database.db`)

```sql
CREATE TABLE IF NOT EXISTS job_applications (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    company_name TEXT NOT NULL,
    job_title TEXT NOT NULL,
    job_url TEXT NOT NULL,
    resume_path TEXT NOT NULL,
    tailored_data_json TEXT NOT NULL,
    screening_qa_json TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_submission_limits (
    date_bucket TEXT PRIMARY KEY,
    submission_count INTEGER DEFAULT 0
);
```

### Normalized Pydantic Models (`src/storage/models.py`)

```python
class JobListing(BaseModel):
    id: str = Field(description="Unique composite key: {source}_{company}_{external_id}")
    source: str = Field(description="greenhouse | lever | ashby | linkedin")
    company_name: str
    job_title: str
    location: str
    is_remote: bool = False
    job_description_raw: str
    job_description_clean: str
    url: str
    salary_range: Optional[str] = None
    extracted_skills: list[str] = Field(default_factory=list)
    screening_questions: list[dict[str, Any]] = Field(default_factory=list)
    posted_at: Optional[datetime] = None
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending", description="pending | approved | rejected | applied")


class TargetCompany(BaseModel):
    name: str
    ats_provider: str = Field(description="greenhouse | lever | ashby")
    slug: str
    domain: Optional[str] = None
    active: bool = True
    industry: Optional[str] = None
```
