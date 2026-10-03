# Verification Suite & Testing Standards

Per project design rules, every browser interaction, DOM selector, LLM translation, data schema, and rate limiter must be proven via an isolated, standalone executable script in `verify/` before it is integrated into the production pipeline.

---

## 1. Master Verification Script Catalog (Scripts 01 to 32)

| Script Path | Target Subsystem | Validation Criteria | Status |
| :--- | :--- | :--- | :--- |
| `verify/01_test_playwright_launch.sh` | Browser Engine | Verifies headful Playwright persistent context launch on macOS | **PASSED** |
| `verify/02_test_resume_store.py` | Schema Store | Validates `ResumeProfile` Pydantic models, JSON Resume compliance, and experience helpers | **PASSED** |
| `verify/03_test_approval_gate.py` | Dashboard Backend | Validates FastAPI state transitions, queue reading, and approval persistence | **PASSED** |
| `verify/04_test_playwright_cdp.sh` | Chrome CDP | Tests remote debugging port 9222 connection and session navigation | **PASSED** |
| `verify/05_test_pdf_engine.py` | PDF Engine | Generates sample ATS PDF from candidate profile using Playwright | **PASSED** |
| `verify/06_audit_resume_accuracy.py` | Data Integrity | Audits exact text match between `singlepageresume.json` and `resume_profile.json` | **PASSED** |
| `verify/07_test_easy_apply_flow.py` | Easy Apply Automation | Tests multi-step form traversal, text inputs, radio groups, and dry-run safety | **PASSED** |
| `verify/08_test_job_finder_and_tailorer.py` | Discovery & Tailor | Tests search query construction, job card extraction, and initial keyword tailoring | **PASSED** |
| `verify/09_test_llm_integration.py` | LLM Integration | Tests `HybridLLMProvider` initialization, structured Pydantic schemas, and Gemini/Ollama routing | **PASSED** |
| `verify/10_test_linkedin_live_flow.py` | Live Scraper Flow | Tests live LinkedIn job detail expansion, noise filtering, and pending queue persistence | **PASSED** |
| `verify/11_test_main_orchestrator.py` | Main Orchestrator | Tests CLI flags, configuration loading, and application history logging | **PASSED** |
| `verify/12_test_search_and_filter.py` | Search & Deduplication | Tests single browser session reuse, deduplication index `processed_jobs.json`, and filter logic | **PASSED** |
| `verify/13_test_job_finder_optimization.py` | Query Optimization | Tests Boolean search query injection (`f_WT=2,3`, `f_E=4`, `f_TPR=r604800`) | **PASSED** |
| `verify/14_test_multi_channel_discovery.py` | 4-Channel Scraper | Tests pagination across Search, Recommended feed, Recruiter posts, and Similar jobs | **PASSED** |
| `verify/15_test_scraper_bug_fixes.py` | DOM Scraper Resilience | Tests bracket query formatting, card decoupling, and multi-scroll container loading | **PASSED** |
| `verify/18_test_dynamic_pagination.py` | Pagination Guards | Tests early break on empty pages and configurable recommended feed page limits | **PASSED** |
| `verify/20_test_easy_apply_resilience.py` | Selector Resilience | Tests `try...finally` context cleanup and fallback Easy Apply button locators | **PASSED** |
| `verify/21_test_description_and_diff.py` | Diff & Cleaning Engine | Tests boilerplate noise removal and visual diff badging (`is_tailored`) | **PASSED** |
| `verify/24_test_knowledge_translation.py` | Notes Translator | Tests markdown bullet extraction, chunking, MD5 dedup, and atomic vault replacement | **PASSED** |
| `verify/25_test_fabrication_detector.py` | Fabrication Detector | Proves hallucinated tools (Playwright/Cypress) are detected and purged | **PASSED** |
| `verify/26_test_pipeline_runner.py` | Pipeline Runner & CLI | Tests unified `argparse` subparsers and `JobSearchPipelineRunner` orchestration | **PASSED** |
| `verify/27_test_kinematics_and_stealth.py` | Anti-Detection Kinematics | Validates cubic Bézier curves, log-normal typing jitter, and CDP evasion JS | **PASSED** |
| `verify/28_test_ollama_local.py` | Local Ollama Client | Tests async connection, token speed benchmarks, and offline fallback | **PASSED** |
| `verify/29_test_ats_ingestion.py` | Direct ATS Collectors | Tests keyless unauthenticated Greenhouse, Lever, and Ashby ingestion in <3s | **PASSED** |
| `verify/30_test_tailoring_and_compilation.py` | Whitelist Gate & Typst | Tests 100% false-skill purging and single-column ATS PDF compilation | **PASSED** |
| `verify/31_test_assisted_autofill.py` | Assisted Autofill Copilot | Verifies form field heuristics, candidate contact resolver, and 404 guards | **PASSED** |
| `verify/32_test_governance_and_sqlite.py` | SQLite DB & Rate Governor | Verifies audit logging transactions and 15/day quota safety cutoff | **PASSED** |
| `verify/33_test_resume_and_knowledge_regeneration.py` | Resume & Knowledge Vault | Verifies 100% Pydantic compliance and 11 authentic STAR achievements | **PASSED** |
| `verify/34_test_dashboard_data_flow.py` | Dashboard Flow | Verifies API responses, job card schema, and payload sanitization | **PASSED** |
| `verify/35_test_approval_gate_coercion.py` | Approval Gate Coercion | Tests string notice periods and type coercion during job approval | **PASSED** |
| `verify/36_test_queue_status_flow.py` | Real-Time Queue Status | Tests `/api/queue-status` counts and state transitions between queues | **PASSED** |
| `verify/37_test_approved_queue_ui_flow.py` | Approved Queue & PDF Preview | Verifies `/api/approved-jobs`, inline `/api/pdf/{job_id}`, and PDF rendering | **PASSED** |
| `verify/38_test_static_cache_headers.py` | Cache-Busting & Headers | Tests no-cache headers and static asset version query parameters | **PASSED** |
| `verify/39_test_ats_filler_resilience.py` | ATS URL & Trigger Resilience | Tests canonical ATS URL resolution and 'Apply' button trigger detection | **PASSED** |
| `verify/40_test_new_tab_ats_handling.py` | Multi-Tab & Popup Autofill | Tests target="_blank" and window.open() new-tab switching, focus, and form filling | **PASSED** |

---

## 2. Running Verification Test Suites

You can execute all test suites individually using the project's virtual environment:

```bash
# Activate virtual environment
source venv/bin/activate

# 1. Test Anti-Detection & Kinematics
python verify/27_test_kinematics_and_stealth.py

# 2. Test Keyless ATS Ingestion
python verify/29_test_ats_ingestion.py

# 3. Test Deterministic Whitelist & PDF Compilation
python verify/30_test_tailoring_and_compilation.py

# 4. Test Assisted Autofill Form Mapping
python verify/31_test_assisted_autofill.py

# 5. Test SQLite Database & Rate Governor
python verify/32_test_governance_and_sqlite.py

# 6. Test ATS URL Resolution & Form Resilience
python verify/39_test_ats_filler_resilience.py

# 7. Test Multi-Tab & Popup ATS Form Autofill
python verify/40_test_new_tab_ats_handling.py
```

---

## 3. Code Quality & Linting Standards

* **Linter Engine:** Ruff (`.ruff.toml`) configured for Python 3.9 compatibility.
* **Standards Enforced:** Clean type annotations, modern string formatting, import ordering (`isort`), and structured exception handling.
* **Auto-Fix Command:**
  ```bash
  python main.py lint
  ```
  Runs across all 104 codebase files in <1 second and maintains **0 remaining linter errors**.
