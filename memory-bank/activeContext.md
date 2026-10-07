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
  - Workday SPA Hydration Barrier, State Machine & Live Sandbox Probing (Gate 56b):
    - Diagnosed race condition where Workday SPA client-side hydration delayed the `[data-automation-id='applyButton']` mounting past instant `domcontentloaded` checks.
    - Implemented `_wait_for_workday_ready()` hydration barrier polling for active page states (`overview`, `modal`, `auth`, `info`).
    - Implemented State Machine transitions with post-condition verification and bounded retries (up to 3 attempts with scroll-into-view).
    - Built bidirectional authentication fallback: handles both Create Account $\rightarrow$ Sign In (if account exists) and Sign In $\rightarrow$ Create Account (if account not found).
    - Built automated diagnostic crash dump (`_capture_workday_diagnostic()`) capturing instant full-page screenshots to `.system_generated/` and logging visible buttons on any transition failure.
    - Created and executed Verification Gate 56b (`verify/56b_test_workday_live_page_autofill.py`): verified live navigation to JioStar Workday portal, hydration detection, Apply button click, modal opening, Apply Manually traversal, and live Auth Gate mounting in 8 seconds.
    - Gates 56 and 56b passing 100%.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 121 files).
  - Workday Autonomous State Machine Engine & Post-Auth Redirection Loop:
    - Diagnosed post-auth redirection behavior where Workday redirects authenticated users back to the Job Overview page (`/job/...`), requiring an authenticated 'Apply' click before entering Stage 3 ('My Information').
    - Refactored `_fill_workday()` from a linear sequence into an autonomous State Machine loop (`while transition_count < 20`) with decoupled DOM state classification (`_detect_workday_state()`).
    - Handled all dynamic transitions across Overview $\rightarrow$ Modal $\rightarrow$ Create Account $\rightarrow$ Sign In $\rightarrow$ Email Verification $\rightarrow$ Post-Auth Redirection Loop $\rightarrow$ Stage 3 ('My Information') $\rightarrow$ Stage 4 ('My Experience') $\rightarrow$ Review Gate.
    - Expanded Verification Gate 56 with Step 6 (`test_workday_post_auth_redirect_and_sign_in_loop`) simulating the full authentication redirect loop, re-entry via authenticated Apply trigger, and seamless form completion.
    - Verification Gate 56 passing 100% across all 6 steps.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 121 files).
  - Structured Diagnostics, Event Logger & Persistent Learning Vault (Gate 57):
    - Diagnosed subtle selector collision where global header navbar "Sign In" link was matched by loose text selectors on the Job Overview page, misclassifying overview as `auth_sign_in` and clicking the navbar instead of form buttons.
    - Implemented strict element scoping: `overview` state strictly prioritized when `applyButton` is visible without password inputs; `auth_sign_in` strictly requires visible password input and `[data-automation-id='signInSubmitButton']`.
    - Created `AutofillLogger` (`src/autofill/autofill_logger.py`) producing structured JSONL audit events (`data/logs/autofill_events.jsonl`), human-readable diagnostic logs (`data/logs/autofill_diagnostics.log`), and automated failure captures with full-page screenshots and structured DOM element dumps in `data/logs/screenshots/`.
    - Established persistent `data/logs/autofill_learning_vault.json` cataloging past automation failures, root causes, and permanent fix rules to prevent repetitive debugging cycles.
    - Created autonomous agent instruction `.agents/agents/autofill_learning_debugger.md`.
    - Added CLI diagnostic command `python main.py autofill audit` displaying recent events, failure screenshots, and all banked lessons.
    - Created and executed Verification Gate 57 (`verify/57_test_autofill_logger_and_learning_vault.py`), passing 100%.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 124 files).
  - Workday Deterministic Dynamic Question Solver & Taxonomy Store (Gate 58):
    - Diagnosed tenant-specific screening questions stopping autofill on Workday Stage 1 ('My Information') and Stage 3 ('Application Questions') (e.g. JioStar prior employment radio group and mandatory Prefix dropdown).
    - Established deterministic taxonomy mapping file `data/profile/workday_field_mappings.json` cataloging regex patterns for prior employment, authorization, sponsorship, nepotism/relatives, conflict of interest, minimum age compliance, non-compete, voluntary disability/veteran/gender disclosures, prefix, device type, and country code.
    - Updated `CandidateMasterData` and `MasterPersonalDetails` (`src/autofill/vendor_schemas.py`) and `data/profile/candidate_master_data.json` to include `"prefix": "Mr."`.
    - Implemented `_resolve_workday_questions()` in `src/autofill/ats_filler.py`: dynamically scans radio groups (`fieldset`, `div[role='radiogroup']`) and custom dropdown comboboxes (`button[aria-haspopup='listbox']`), matching against candidate profile data and deterministic taxonomy rules.
    - Hardened `_select_react_combobox`: guards against calling `.fill()` or `.press("Enter")` on `<button>` elements, clicking the trigger and selecting option from menu listbox.
    - Expanded `_detect_workday_state` to recognize all 5 Workday breadcrumb stages: `info`, `experience`, `questions`, `disclosures`, and `review`.
    - Created and executed Verification Gate 58 (`verify/58_test_workday_dynamic_question_solver.py`), passing 100% across all 4 steps:
      * Step 1: Prior employment radio answered [No], Prefix dropdown selected [Mr.].
      * Step 2: Stage 3 Application Questions answered (Work authorization [Yes], Visa sponsorship [No]).
      * Step 3: Stage 4 Voluntary Disclosures answered (Disability status [No]).
      * Step 4: Multi-stage traversal verified through State Machine up to Review Gate.
    - Full regression suite verified: Gates 56, 57, and 58 passing 100%.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 125 files).
  - Workday Live BEM Schema Precision & Sibling Radio Resolution (Gate 59):
    - Diagnosed live Workday layout from diagnostic dump `autofill_dom_stuck_unknown_1791225819.json`: Stage 1 inputs use BEM IDs (`name--legalName--firstName`, `address--addressLine1`) without `data-automation-id`, causing `_detect_workday_state` to misclassify as `unknown`.
    - Expanded `_detect_workday_state` with dual-tier selectors covering BEM IDs (`legalName--firstName`, `candidateIsPreviousWorker`, `legalName--title`) and `/apply` URL patterns.
    - Updated `_resolve_workday_questions` to scan distinct radio groups by `name`, matching boolean `value="false"`/`"true"` and clicking sibling `<label for="...">`.
    - Fully mapped Stage 1 field locators for BEM IDs: First Name, Last Name, Prefix `Mr.`, Country, Address 1, City, State, Postal Code, Phone Type, Country Code `+91`, and Phone Number.
    - Added `pageFooterNextButton` to advance from 'My Information' to 'My Experience'.
    - Accelerated `_wait_for_workday_ready` to instantly recognize Stage 1 mounting without waiting for hydration timeouts.
    - Banked `LESSON-008` in `autofill_learning_vault.json`.
    - Created and executed Verification Gate 59 (`verify/59_test_workday_live_dom_schema_precision.py`), passing 100% across state detection, sibling radio resolution, full field autofill, and stage advancement.
    - Full regression suite verified: Gates 57, 58, and 59 passing 100%.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 126 files).
  - Human-in-the-Loop Manual Takeover Fallback Mode & Submission Confirmation Detector (Gate 60):
    - Eliminated infinite state cycling on complex enterprise ATS forms (e.g. JioStar Workday) by removing stage exclusions and enforcing a bounded stuck threshold (`state_stuck_count >= 2`).
    - Implemented `_enter_manual_takeover_mode()` in `src/autofill/ats_filler.py`:
      * Emits audible terminal chime (`\a`) to immediately alert user.
      * Prints formatted Candidate Quick-Reference Card in terminal with all personal details, contact info, credential data, and absolute path to tailored PDF resume.
      * Injects non-intrusive floating glassmorphic `#antigravity-copilot-helper` cheat-sheet widget directly into page DOM with candidate details and dismiss button.
      * Launches non-blocking background listener `_monitor_manual_submission()` monitoring for URL and page text confirmation markers (`/application-complete`, `submitted`, `thank-you`, `application submitted`, etc.).
      * Upon user submission, detects confirmation, sounds double chime (`\a\a`), logs `SUBMISSION_CONFIRMED`, and records application status as `APPLIED` in SQLite `ApplicationDatabase`.
    - Implemented dedicated FastAPI endpoint `POST /api/autofill/manual/{job_id}` (`src/ui/app.py`) launching headful Chrome directly with the candidate cheat-sheet widget and tailored resume PDF ready for manual completion.
    - Updated Command Center UI (`src/ui/templates/index.html`, `src/ui/static/app.js`, `src/ui/static/styles.css`): added vibrant amber `🖐️ Manual Apply` buttons on both Staging Review action bar and Approved Applications card grid.
    - Banked `LESSON-010` in `data/logs/autofill_learning_vault.json`.
    - Created and executed Verification Gate 60 (`verify/60_test_manual_takeover_fallback.py`): verified stuck threshold trigger, cheat-sheet DOM injection, background submission detector, and FastAPI endpoint passing 100%.
    - Full regression suite verified: Gates 57, 58, 59, and 60 passing 100%.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 127 files).
  - High-Performance Application Tracking, Multi-Stage Auto-Purge Defense & Tab 3 Dashboard (Gate 61):
    - Added high-performance indexing in SQLite `app_database.db`: `idx_job_applications_status` and `idx_job_applications_applied_at` for ultra-fast (<0.15ms) lookups.
    - Extended `ApplicationDatabase` (`src/storage/database.py`) with `is_job_applied(job_id)`, `get_applied_job_ids()`, `get_all_applications(limit, status)`, `get_application_stats()`, and `delete_application(job_id)`.
    - Added multi-layer auto-purge defense:
      * When retrieving jobs from `/api/jobs` or `/api/pending-jobs` and `/api/approved-jobs` (`src/ui/app.py`), checks `ApplicationDatabase().get_applied_job_ids()`; if any listing on disk was already applied, automatically unlinks/purges the JSON file from the filesystem.
      * In `LinkedInJobFinder.is_duplicate()` (`src/scraper/job_finder.py`): cross-checks `is_job_applied(job_id)` to prevent re-scraping or re-pooling applied jobs.
      * In `LinkedInJobFilter.filter_pending_queue()` (`src/filter/job_filter.py`): discards any staged listing present in `get_applied_job_ids()`.
    - Implemented tracking REST endpoints in `src/ui/app.py`:
      * `POST /api/tracking/mark-applied/{job_id}`: records application to SQLite with status `applied`, purges job from `pending_queue/` and `approved_queue/`, and updates `processed_jobs.json`.
      * `GET /api/tracking/applied`: returns tracked applications in reverse chronological order and aggregated KPIs.
      * `DELETE /api/tracking/{job_id}`: archives/removes application record.
    - Upgraded Command Center UI (`src/ui/templates/index.html`, `src/ui/static/app.js`, `src/ui/static/styles.css`):
      * Added Tab 3 `📊 Applied Tracking` with live count badge synced across tabs.
      * Added `✅ Mark as Applied` button to Staging Review action bar.
      * Added `✅ Applied` quick button to every Ready to Apply card.
      * Built glassmorphic Tab 3 UI featuring KPI stat cards (Total Applied, Applied Today, Active Portals), client-side search/filter bar, applied cards grid, view tailored PDF links, direct job posting links, and archive buttons.
    - Created and executed Verification Gate 61 (`verify/61_test_application_tracking_and_auto_purge.py`), passing 100% across SQLite schema/indexes, auto-purge on retrieval, mark-applied endpoints, tracking view, and scraper defense.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 127 files).
  - User-Driven Applied Trigger Isolation & Complete Approved Queue Temp Purge (Gate 62):
    - Disentangled browser launching from application completion in SQLite:
      * Restricted `ApplicationDatabase.is_job_applied()` and `get_applied_job_ids()` (`src/storage/database.py`) strictly to `status = 'applied'`.
      * Browser launches (`/api/autofill/{job_id}` and `/api/autofill/manual/{job_id}`) record `copilot_launched` and `manual_takeover_opened` audit entries without setting `applied` or triggering auto-purge.
      * Repeated clicks on Copilot or Manual Apply no longer prematurely purge jobs from `data/approved_queue/`.
    - User-Driven Confirmation Gate in Command Center UI:
      * `markApprovedJobApplied()` and `markCurrentJobApplied()` in `src/ui/static/app.js` require explicit confirmation dialog (`"Confirm Submission: Have you submitted your application for <Role> @ <Company>?"`) before firing `POST /api/tracking/mark-applied/{job_id}`.
    - Complete Approved Queue Temp Data Purge & PDF Archiving:
      * When a job is marked applied, the compiled ATS PDF is safely copied/archived into `data/resumes/{pdf_filename}`, updating the DB record.
      * All temp files (`{job_id}.json` and any matching `{job_id}*.pdf` or `token*.pdf`) are completely unlinked from `data/approved_queue/`.
      * Updated `resolve_job_pdf_path()` to search both `data/approved_queue/` and `data/resumes/`, ensuring `/api/pdf/{job_id}` in the Applied Tracking view serves the archived resume without 404 errors.
      * Added `clean_approved_queue_temp_data()` and `POST /api/approved/cleanup` to sweep any orphaned files from `data/approved_queue/`.
    - Created and executed Verification Gate 62 (`verify/62_test_user_driven_applied_and_approved_purge.py`), passing 100% across browser launch isolation, repeat click safety, user confirmation trigger, temp file purge, and resume archiving.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 129 files).
  - Unified Job Search Architecture & Cross-Source Applied Reseed Defense (Gate 63):
    - Confirmed and hardened cross-source applied defense in SQLite `ApplicationDatabase` (`src/storage/database.py`):
      * Added `is_company_role_applied(company_name, job_title)` providing normalized, case-insensitive, whitespace-trimmed duplicate protection.
      * Added `get_applied_composite_hashes()` returning md5 hashes for all applied roles.
    - Upgraded `ATSDiscoveryCoordinator` (`src/ingestion/ats_discovery.py`):
      * Integrated pre-ingestion duplicate and reseed checks (`is_duplicate`) querying SQLite (`is_job_applied`, `is_company_role_applied`), `processed_jobs.json`, and physical queues.
      * Integrated AI resume tailoring directly into ATS ingestion via `ResumeTailorer(use_ai=self.use_ai)`.
      * Automatically registers newly discovered enterprise jobs into `processed_jobs.json` with composite hashes.
    - Enhanced `LinkedInJobFinder.is_duplicate()` (`src/scraper/job_finder.py`):
      * Checks `ApplicationDatabase().is_company_role_applied(company, title)` so LinkedIn never reseeds a role already applied via Greenhouse/Lever/Ashby.
      * Added `--headless` support via `discovery_config.get("headless", False)`.
    - Hardened `LinkedInJobFilter` (`src/filter/job_filter.py`):
      * Dynamically resolves `easy_apply_only` setting from `config.yaml` (defaulting to False).
      * Successfully retains `LINKEDIN_EXTERNAL` and `ATS_*` (`ATS_GREENHOUSE`, `ATS_LEVER`, `ATS_ASHBY`) listings in pending queue.
    - Unified Orchestration in `JobSearchPipelineRunner.run_search_stage()` (`src/pipeline/runner.py`):
      * Multi-track discovery coordinating Track 1 (Direct Keyless ATS REST) and Track 2 (LinkedIn Multi-Channel Stealth) in a single unified execution.
      * Supports source selection (`all`, `linkedin`, `ats`) and headless execution for CI/CD / daily scheduled runs.
    - Added CLI flags in `main.py`: `python main.py search [--source all|linkedin|ats] [--headless]` and `python main.py run [--source all|linkedin|ats] [--headless]`.
    - Added REST endpoint `POST /api/discovery/run` in `src/ui/app.py` for one-click background execution from web dashboard or CI pipelines.
    - Updated `config.yaml` with unified `discovery.source: "all"` and `discovery.headless: false`.
    - Created and executed Verification Gate 63 (`verify/63_test_unified_job_search.py`), passing 100% across SQLite checks, ATS pre-ingestion guard, cross-platform deduplication, multi-source retention, runner orchestration, and API response.
    - Codebase linted cleanly via `python main.py lint` (0 errors across 130 files).
  - Source Badge Attribution, Metadata Normalization & Cross-Platform Dashboard Precision (Gate 64):
    - Diagnosed source display bug: `job_finder.py` omitted `"source": "linkedin"`, causing LinkedIn listings to fall back to generic `"ATS"` in `src/ui/app.py` and display flat `"ATS APPLICATION"` badges in the UI.
    - Updated `LinkedInJobFinder` (`src/scraper/job_finder.py`) to explicitly set `"source": "linkedin"` across recruiter posts and standard card extraction.
    - Implemented `normalize_job_source_metadata()` in `src/ui/app.py`: retro-normalizes authentic platform source and application type across older and newly discovered jobs on disk (`linkedin`, `greenhouse`, `lever`, `ashby`, `workday`).
    - Integrated `normalize_job_source_metadata` across `/api/pending-jobs`, `/api/approved-jobs`, `/api/tracking/applied`, `autofill_job`, `launch_manual_takeover`, and `mark_job_applied`.
    - Upgraded SQLite tracking database `data/app_database.db`: migrated 14 historical records previously tagged as generic `manual`/`manual_takeover` to authentic platform tags (`linkedin: 20`, `greenhouse: 18`, `workday: 1`, `lever: 1`, `ashby: 1`).
    - Implemented `formatSourceBadge(source, appType)` helper in `src/ui/static/app.js`:
      * ⚡ `LinkedIn Easy Apply` (Royal Blue `.badge-linkedin-easy`)
      * 🌐 `LinkedIn External` (Electric Indigo `.badge-linkedin-ext`)
      * 🟢 `Greenhouse ATS` (Emerald Green `.badge-greenhouse`)
      * 🐬 `Lever ATS` (Purple `.badge-lever`)
      * 🟣 `Ashby ATS` (Cyan `.badge-ashby`)
      * 🟠 `Workday ATS` (Amber Orange `.badge-workday`)
      * 💼 `Direct ATS` (Slate Gray `.badge-generic-ats`)
    - Upgraded badge rendering across all 3 tabs: Tab 1 Staging Review (`#job-source-badge`), Tab 2 Ready to Apply cards, and Tab 3 Applied Tracking rows + real-time search filtering.
    - Created and executed Verification Gate 64 (`verify/64_test_source_badge_accuracy.py`), passing 100% across normalizer heuristics, API attribution, SQLite migration, and front-end CSS/JS contracts.
    - Regression verified across Gates 61, 62, 63, and 64 (100% pass).
    - Codebase linted cleanly via `python main.py lint` (0 errors across 131 files).







