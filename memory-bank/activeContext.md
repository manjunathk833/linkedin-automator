# Current Plan & Active Tasks
**Project:** AI-Powered LinkedIn & Keyless ATS Job Finder, Tailorer, and Assisted Applier
**Constraint:** Zero running costs. No paid scraping APIs. 100% authentic candidate data.

**Current Operational Status:**
- Sprints 1–5 complete and verified across all modules (kinematics, CDP stealth, ATS ingestion, grounded tailoring, Typst compiler, assisted copilot, SQLite repository, rate governor).
- Data reset completed: Runtime queues (`approved_queue/`, `resumes/`) and deduplication caches wiped; 30 fresh ATS jobs seeded into `pending_queue/` across target tech enterprises with upfront location warnings and rich metadata.
- Resume profile & Master Knowledge Bank regenerated:
  - `singlepageresume.json` sanitized: Playwright replaced with Selenium.
  - `data/resume_profile.json` regenerated: 100% compliant with Pydantic `ResumeProfile`.
  - `data/master_knowledge_bank.json` regenerated: 11 STAR achievements strictly grounded in candidate experience and notes, zero hallucinations.
  - Verification Gate 33 (`verify/33_test_resume_and_knowledge_regeneration.py`) and schema verification (`verify/02_test_resume_store.py`, `verify/06_audit_resume_accuracy.py`) passing 100%.
  - Dashboard approval gate type coercion fix implemented and verified (Gate 35: `verify/35_test_approval_gate_coercion.py`).
  - Dynamic queue state tracking & live count synchronization implemented and verified (Gate 36: `verify/36_test_queue_status_flow.py`).
  - Dual-mode Application Command Center with Approved Queue & PDF delivery deployed and verified (Gate 37: `verify/37_test_approved_queue_ui_flow.py`).
  - Static asset cache-busting & middleware revalidation verified (Gate 38: `verify/38_test_static_cache_headers.py`).
  - ATS Assisted Copilot resilience, canonical URL resolution, and form detection verified (Gate 39: `verify/39_test_ats_filler_resilience.py`).
  - ATS Multi-Tab & Popup Window auto-detection and focus switching verified (Gate 40: `verify/40_test_new_tab_ats_handling.py`).
  - Standardized Vendor Autofill Schemas & Centralized Candidate Master Profile verified across Greenhouse, Lever, Ashby, Workday, and LinkedIn Easy Apply (Gate 41: `verify/41_test_standardized_vendor_autofill.py`).
  - Pre-fill question inputs stripped from Dashboard UI; transformed into rapid 1-click Approval Gate.
  - Safety Rate Governor application cap scaled to 200/day and made dynamically configurable via `config.yaml` (Gate 42: `verify/42_test_safety_governor_cap_200.py`).
  - React-Select Combobox Autofill, Multi-Job Experience Loop ("Add another" for Value Labs, Dunzo, Tata Elxsi), Education, and React synthetic event dispatching verified in Gate 43 (28 fields pre-filled live: `verify/43_test_coinbase_greenhouse_live_fill.py`).
  - Professional Candidate Resume Naming (`Manjunath_HK_<Company>_<Token>_Resume.pdf`), backward compatibility for existing approved queues, and clean download headers verified in Gate 44 (`verify/44_test_resume_professional_naming.py`).
  - Upfront Staging Job Intelligence (US-only location alert badges, context-aware experience extraction, direct job posting link, and compensation view) verified in Gate 45 (`verify/45_test_staging_job_metadata_enrichment.py`).
  - Vendor Pattern Discovery & Banking Engine (`ATSVendorPattern`, `classify_ats_pattern`, `VENDOR_SCHEMAS`, `get_vendor_schema`) formalized and banked into `.agents/rules/` (Rule 7) and critic architect checklist.
  - Custom Branded Vendor Schema for Okta (`OKTA_BRANDED_GREENHOUSE`) added to `src/autofill/vendor_schemas.py` and modular `_fill_okta` implemented in `src/autofill/ats_filler.py`.
  - Candidate Portfolio / Website (`https://manjunathhk.netlify.app/`) mapped to `#edit-question-69483962`, LinkedIn Profile mapped to `#edit-question-69483961`, screening dropdowns, consent checkboxes, and voluntary EEOC verified live on Okta job page (17 fields filled + resume attached).
  - Verification Gate 46 (`verify/46_test_okta_autofill_heuristics.py`) and live test (`verify/46b_test_okta_live_page_autofill.py`) passing 100%.
  - Custom Branded Vendor Schema for Databricks (`DATABRICKS_CUSTOM_GREENHOUSE`) added to `src/autofill/vendor_schemas.py` and modular `_fill_databricks` implemented in `src/autofill/ats_filler.py`.
  - Form selectors mapped for Databricks: Preferred Name (`#preferred_name`), Current Firm (`#question_35489441002`), Phone Country Dial Code (`+91`), Location Combobox (`Bengaluru`), LinkedIn (`#question_35489440002`), Work Auth (`#question_35489442002`), Prior Employment (`#question_35489443002`), and Resume PDF upload.
  - Canonical URL resolver updated to preserve Databricks URLs on `databricks.com` to prevent Greenhouse 302-redirect loops.
  - Verification Gate 47 (`verify/47_test_databricks_autofill_heuristics.py`) passing 100% (12 fields filled live + resume attached).
  - ATS Autofill Debugger subagent created in `.agents/agents/ats_autofill_debugger.md` incorporating proven live probing procedures, anti-collision selector rules, React-Select async handling, and synthetic event dispatching.
  - Mandatory Tri-Agent Auto-Invocation Protocol established in `.agents/rules/02-agent-review-protocol.md` with auto-invoked `ats_autofill_debugger` quality lens to fast-track vendor debugging and prevent regressions.
  - Custom Branded Vendor Schema for Coinbase (`COINBASE_CUSTOM_GREENHOUSE`) added to `src/autofill/vendor_schemas.py` and routed to hardened Greenhouse autofill engine in `src/autofill/ats_filler.py`.
  - Coinbase canonical URL resolver updated to resolve directly to Greenhouse embed endpoint (`https://job-boards.greenhouse.io/embed/job_app?token={job_id}&for=coinbase&gh_jid={job_id}`), preventing Greenhouse 302-redirect loops and bypassing Coinbase Cloudflare challenges.
  - Tab autofocus & iframe switching hardened: Playwright now waits for new tabs to navigate away from `about:blank`, and iframe target switching is guarded against hijacking pages where form inputs are already present on the root document.
  - Verification Gate 48 (`verify/48_test_coinbase_autofill_heuristics.py`) passing 100% (28 fields filled live + resume attached).
  - Full regression test suite passing (Gates 39, 41, 44, 45, 46, 47, 48).
  - `python main.py lint` clean with 0 errors across 112 files.
  - Multi-channel LinkedIn discovery executed (`python main.py search`): 50 live Senior SDET & Automation Lead Easy Apply jobs scraped, deduplicated, tailored, and seeded into `data/pending_queue/` for human review in the Command Center UI (`http://localhost:8000`).
  - LinkedIn External ATS Discovery & Dynamic Pivot Engine implemented:
    - 30-day filter restriction eliminated in favor of a high-velocity 7-day window (`time_posted: "past_week"`, `f_TPR=r604800`), configurable down to 24 hours (`past_24h`).
    - Explicit search radius parameter introduced (`distance: 25` miles / ~40 km for Bengaluru metro).
    - Easy Apply restriction eliminated (`easy_apply_only: false`), unlocking the 80%+ enterprise opportunities linking out to external ATS platforms while retaining full Easy Apply discovery when requested.
    - Card extraction engine updated to detect apply button text and aria labels, classifying jobs upfront as `EASY_APPLY` vs `LINKEDIN_EXTERNAL` and storing external redirect URLs.
    - `autofill_linkedin_external` implemented in `src/autofill/ats_filler.py`: dynamically navigates to LinkedIn job views, detects external Apply buttons, captures launched external ATS popup windows/tabs via dual `page.on("popup")` and `context.on("page")` listeners, resolves canonical URLs, classifies matching vendor ATS schemas (`GREENHOUSE_STANDARD`, `LEVER_STANDARD`, `ASHBY_STANDARD`, etc.), and autofills the form before pausing for human review.
    - FastAPI endpoint `/api/autofill/{job_id}` updated in `src/ui/app.py` to route `LINKEDIN_EXTERNAL` jobs to `ats_filler.autofill_linkedin_external()`.
    - Verification Gate 49 (`verify/49_test_linkedin_external_ats_pivot.py`) passing 100% across URL construction, apply type heuristics, and Playwright tab pivot simulation.
    - `python main.py lint` clean with 0 errors across 113 files.
  - Fresh Multi-Channel Job Discovery Executed (`python main.py search`):
    - Completely cleared previous staging queue and reset deduplication ledger.
    - Successfully scraped and tailored **46 high-velocity jobs** across Bengaluru (25-mile radius) and Remote India posted within the last 7 days.
    - **Application Type Composition:** 30 `LINKEDIN_EXTERNAL` jobs (65%) + 16 `EASY_APPLY` jobs (35%).
    - Discovered top-tier enterprise tech opportunities: GE HealthCare, Accenture, LSEG, EY, Hewlett Packard Enterprise, Birlasoft, Zluri, HTC Global Services, Jobgether, etc.
    - All 46 listings are staged in `data/pending_queue/` and live on the Command Center UI (`http://localhost:8000`).
  - Rate-Paced LLM Tailoring Upgrade, Circuit Breaker & Structured Request Diagnostics Logging (Gate 50):
    - Config upgraded to `primary_model: "models/gemini-flash-lite-latest"` with multi-model fallback (`models/gemini-flash-latest`, `models/gemini-3.5-flash`, `gemini-3.8-flash`).
    - Enforced 4.0-second rate pacer (`_pace_request()`) to strictly adhere to Google AI Studio's 15 RPM free-tier ceiling.
    - Implemented 60-second Quota Cooldown Circuit-Breaker (`_model_cooldowns`): on HTTP 429, immediately marks model in cooldown for 60s, skipping it with 0ms penalty for subsequent jobs and routing directly to the active model.
    - Implemented structured file diagnostics logging in `data/logs/llm_requests.log` tracking timestamp, provider, model, operation, status (SUCCESS/FAILED), duration (ms), and error details.
    - Verification Gate 50 (`verify/50_test_gemini_38_flash_pacer.py`) passing 100%.
    - Codebase linted cleanly via `./verify/autofix_lint.sh` (0 errors across 114 files).
  - High-Speed Multi-Channel Discovery & AI Tailoring Reseed:
    - Queues and deduplication ledger wiped clean.
    - Successfully scraped and tailored **42 fresh jobs** across Bengaluru and Remote India within ~7 minutes (down from 25+ minutes).
    - **100% AI Tailored STAR Achievements:** All 42 listings in `data/pending_queue/` received custom, verified STAR bullets (`tailoring_method: "ai_grounded_star"`) with 0 fallbacks to base heuristics.
    - Average LLM request duration dropped to **1.77 seconds** with 0 rate limit pressure.
    - All 42 jobs loaded and ready on the local Command Center UI (`http://localhost:8000`).
  - Company Boundary Isolation & Cross-Company Contamination Defense (Gates 51 & 52):
    - Audited `data/master_knowledge_bank.json` and `data/resume_profile.json`; confirmed pristine alignment with `singlepageresume.json`.
    - Structured `data/candidate_notes.md` with explicit organization sections (`## Value Labs`, `## Dunzo`, `## Tata Elxsi`).
    - Implemented `COMPANY_EXCLUSIVE_MARKERS`, `check_company_contamination()`, and `validate_company_bullets()` in `src/tailor/fabrication_detector.py`.
    - Implemented `COMPANY_SCOPED_STAR_PROMPT` and `generate_company_tailored_bullets()` in `src/tailor/llm_provider.py`.
    - Partitioned master vault by employer in `src/tailor/resume_tailorer.py`; experience blocks are tailored strictly within their own company boundary.
    - Verification Gate 51 (`verify/51_test_company_boundary_isolation.py`) passing 100%.
    - Completely wiped contaminated queues and executed fresh multi-channel reseed (`python main.py search`).
    - Successfully scraped and tailored 25 fresh jobs in `data/pending_queue/` with 100% AI Grounded STAR tailoring.
    - Executed Verification Gate 52 (`verify/52_audit_queue_zero_contamination.py`): Audited all 25 staged jobs (225 experience bullets) with **0 contamination violations (100% SUCCESS)**.
    - Codebase linted cleanly via `./verify/autofix_lint.sh` (0 errors across 116 files).
  - Tailored vs. Standard Resume PDF Inspection & Selection Architecture (Gate 53):
    - Added cached `/api/pdf/standard` serving the candidate's canonical base resume PDF from `data/resume_profile.json`.
    - Added `/api/pdf/preview/{job_id}?version=tailored` generating on-the-fly preview PDFs for pending jobs.
    - Upgraded `/api/approve/{job_id}` to support `resume_choice: "tailored" | "standard"`, compiling and attaching the user's chosen resume version.
    - Upgraded Command Center UI (`src/ui/templates/index.html` & `src/ui/static/app.js`):
      - Interactive segmented version switcher (`✨ Tailored Version` vs `📄 Standard Base Version`).
      - Real-time text preview switching in Staging Review.
      - Glassmorphic PDF Preview & Comparison modal with tabbed side-by-side inspection (`✨ Tailored PDF` vs `📄 Standard Base PDF`).
      - Smart action buttons updating dynamically based on choice.
    - Verification Gate 53 (`verify/53_test_resume_comparison_and_selection.py`) passing 100%.
    - Codebase linted cleanly via `./verify/autofix_lint.sh` (0 errors across 117 files).
  - PDF Preview Inline Disposition & Download Elimination (Gate 54):
    - Configured `content_disposition_type="inline"` and no-cache headers across `/api/pdf/standard`, `/api/pdf/preview/{job_id}`, and `/api/pdf/{job_id}` in `src/ui/app.py`.
    - Eliminated unintended browser file downloads when previewing PDFs.
    - Added direct "Open in New Tab ↗" external navigation link to the modal header.
    - Added iframe auto-dismiss timeout (1.0s) for `#pdf-spinner` in `src/ui/static/app.js`.
    - Verification Gate 54 (`verify/54_test_pdf_inline_preview_headers.py`) passing 100%.
    - Codebase linted cleanly via `./verify/autofix_lint.sh` (0 errors across 118 files).
  - Oracle Cloud HCM (Akamai) Multi-Stage ATS Autofill Engine (Gate 55):
    - Probed live Akamai career page (`https://fa-extu-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/...`) using browser subagent to analyze multi-stage application flow.
    - Banked `ORACLE_CLOUD_HCM` in `ATSVendorPattern`, `VENDOR_SCHEMAS`, and `classify_ats_pattern` in `src/autofill/vendor_schemas.py`.
    - Implemented multi-stage `_fill_oracle_hcm` in `src/autofill/ats_filler.py`:
      * Cookie consent dismissal (`#onetrust-accept-btn-handler`).
      * Stage 1: Initial Job Overview -> 'Apply Now' click trigger.
      * Stage 2: Email & Legal Disclaimer gate (`#primary-email-0`, legal disclaimer checkbox, 'Next' button).
      * Stage 3: Section 1 form completion: Title pill 'Mr.', First Name, Last Name, Phone Country (+91), Phone Number, Portfolio link, and Resume attachment.
      * Synthetic event dispatch (`input`, `change`, `blur`) for all fields.
    - Added Verification Gate 55 (`verify/55_test_oracle_hcm_autofill_heuristics.py`) validating pattern recognition across 10 vendors, schema banking, and Playwright multi-stage simulation with zero contamination.
    - Verification Gate 55 passing 100%.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 119 files).
  - Workday Standard ATS Vendor Schema & Multi-Stage Application Automation (Gate 56):
    - Probed live JioStar Workday portal (`https://jiostar.wd102.myworkdayjobs.com/JioStar/...`) via browser subagent.
    - Updated `data/profile/candidate_master_data.json` and `MasterPersonalDetails` with `workday_default_password` satisfying all complexity requirements.
    - Expanded `WORKDAY_STANDARD` in `src/autofill/vendor_schemas.py` with comprehensive DOM selectors across all application stages.
    - Implemented multi-stage `_fill_workday` in `src/autofill/ats_filler.py`:
      * Stage 0: Cookie consent dismissal.
      * Stage 1: 'Apply' -> 'Apply Manually' modal traversal.
      * Stage 2: Create Account / Sign-In auto-population with fallback to Sign-In.
      * Stage 2b: 120-second dynamic OTP / Email Verification wait loop with audible chime (`\a`).
      * Stage 3: 'My Information' personal details, address, city, state, postal code, mobile device type, +91 dial code, phone, and source.
      * Stage 4: 'My Experience' tailored resume PDF upload and website links.
    - Added upfront direct routing in `fill_ats_page()` for `WORKDAY_STANDARD`.
    - Created and executed Verification Gate 56 (`verify/56_test_workday_autofill_heuristics.py`) validating pattern recognition across Workday tenants, schema banking, and Playwright multi-stage simulation with 14 fields typed and resume attached.
    - Verification Gate 56 passing 100%.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 120 files).
