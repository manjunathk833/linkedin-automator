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

