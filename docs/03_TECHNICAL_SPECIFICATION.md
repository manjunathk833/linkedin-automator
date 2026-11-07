# Technical Specification & Module Architecture

This document provides code-level engineering specifications for all core subsystems of the platform.

---

## 1. System Module Catalog

```text
src/
├── browser/      # Module 2: CDP port 9222 reuse, stealth context, session manager & Bézier kinematics
├── ingestion/    # Module 3: Keyless REST collectors (Greenhouse, Lever, Ashby, Workday CXS) & filters
├── scraper/      # Module 4: 5-Channel LinkedIn discovery scraper & sub-24h First-Applicant Sniper
├── posts/        # Module 5: Track 3 Social Hiring Posts tracker, 2-tier classifier & outreach composer
├── tailor/       # Module 6: Grounded STAR tailorer, 3-Tier InterviewRouter & Referral Scorer
├── llm/          # Module 7: Deterministic ResumeVerificationGate & company boundary isolation
├── compiler/     # Module 8: Typst & Playwright single-column ATS PDF compiler
├── filter/       # Module 9: Experience (5–12 yrs), India/Global Remote & jurisdiction policy filter
├── autofill/     # Module 10: UniversalBatchFormFiller, vendor schemas, self-healer & HTTP 412 verifier
├── notifier/     # Module 11: DailyRunLogger & Gmail SMTP SSL Executive Briefing reporter
├── storage/      # Module 12: Pydantic models & 5-table SQLite persistence manager
├── ui/           # Module 13: 4-Tab FastAPI Command Center (http://127.0.0.1:8000)
└── pipeline/     # Module 1: Unified & Daily Pipeline orchestrators
```

---

## 2. Module-by-Module Technical Breakdown

### Module 1: CLI Entrypoint & Pipeline Orchestration
* **Source:** [`main.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/main.py), [`src/pipeline/runner.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/pipeline/runner.py), [`src/pipeline/daily_runner.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/pipeline/daily_runner.py)
* **Primary Subcommands:**
  * `python main.py daily [run|audit|diagnose]`: Orchestrates regression health check $\rightarrow$ notes sync $\rightarrow$ 3-track discovery $\rightarrow$ Naukri Resdex pinger $\rightarrow$ HTML executive email briefing $\rightarrow$ Command Center readiness.
  * `python main.py form-batch [inspect|apply] --job-id <id>`: Executes Phase A (`inspect`: single-pass DOM extraction, deterministic batch fill, read-back verification) and Phase B (`apply`: 1-turn custom field batch execution + closed-loop learning).
  * `python main.py referral-scout [--job-id <id>]`: Dynamically scouts verified current employees on LinkedIn over CDP port 9222 and scores them via `score_referral_candidate`.
  * `python main.py posts [discover|list|stats]`: Runs Track 3 hiring posts discovery and analytics.
  * `python main.py autofill [--audit]`: Aggregates telemetry from `autofill_benchmarks.jsonl`, `unmapped_fields_backlog.jsonl`, and `autofill_learning_vault.json`.
  * `python main.py test [--tier core|autofill|all]`: Runs the Standardized Multi-Tier Regression Suite (62 Core gates).
  * `python main.py lint`: Runs Ruff auto-fix linter and formatter across 174+ files.

---

### Module 2: Browser Context, CDP Reuse & Kinematics
* **Source:** [`src/browser/cdp_stealth.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/cdp_stealth.py), [`src/browser/session_manager.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/session_manager.py), [`src/browser/kinematics.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/kinematics.py)
* **Seamless CDP Fast-Path (Gate 81):** `is_cdp_port_open(9222)` checks `127.0.0.1:9222` and `localhost:9222`; if open, `_connect_existing_cdp` attaches via `connect_over_cdp` and opens a new tab without profile lock collisions. Automatically falls back to headless mode on Linux CI when `$DISPLAY` is unset, and uses a deterministic isolated fallback profile if `.browser_data` is locked across sandbox boundaries (`EPERM`).
* **Kinematics:** Cubic Bézier cursor trajectories ($B(t) = (1-t)^3 P_0 + 3(1-t)^2 t P_1 + 3(1-t) t^2 P_2 + t^3 P_3$) and log-normal keystroke intervals.

---

### Module 3 & 4: Tri-Track Ingestion & Sub-24h Sniper Discovery
* **Source:** [`src/ingestion/greenhouse.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/greenhouse.py), [`src/ingestion/lever.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/lever.py), [`src/ingestion/ashby.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/ashby.py), [`src/ingestion/workday.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/workday.py), [`src/ingestion/filters.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/ingestion/filters.py), [`src/scraper/job_finder.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/scraper/job_finder.py)
* **Publish Timestamp Extraction:** Extracts authentic `posted_at` datetimes across Greenhouse (`updated_at` / `first_published`), Lever (`createdAt` epoch ms), Ashby (`publishedAt`), and Workday (`postedOn` relative parser).
* **5-Channel LinkedIn Scraper + Sniper Mode:** Iterates Boolean Keyword Search (configurable `sort_by: "relevance"` or `"date"` and sub-24h sniper windows `past_1h` `r3600`, `past_3h` `r10800`, `past_6h` `r21600`, `past_24h` `r86400`), Multi-Collection Feeds (`recommended`, `top-applicant`, `still-hiring`), Recruiter Posts, Similar Jobs, and Company Jobs Tabs (`/company/{slug}/jobs/`).

---

### Module 5 & 6: 3-Tier `InterviewRouter`, Referral Scorer & Grounded Tailoring
* **Source:** [`src/tailor/referral_generator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/referral_generator.py), [`src/tailor/resume_tailorer.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/resume_tailorer.py), [`src/tailor/llm_provider.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/llm_provider.py), [`src/posts/post_tracker.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/posts/post_tracker.py)
* **`InterviewRouter.classify_job_strategy`:** Routes jobs into `TIER_0_POST_AUTHOR` (matching hiring post), `TIER_1_SNIPER_APPLY` (`<24h` fresh non-Workday postings), or `TIER_2_REFERRAL_SLA` (36-hour hold for Dream Enterprises / Workday roles with `referral_sla_deadline` metadata).
* **`score_referral_candidate` & `is_verified_current_employee`:** Rejects `>3,000` follower influencers (`-100`) and `"Ex-<Company>"` former employees (`-100`); boosts 1st-degree connections (`+40`), post authors (`+45`), shared alumni (`Dunzo`, `Value Labs`, `Tata Elxsi`, `SJCE` `+35`), and SDET ICs (`+25`).
* **LLM Rate Pacer & Timeout Protection:** `genai.Client(http_options=types.HttpOptions(timeout=25000))` with a `4.0s` request pacer and `60s` model cooldown circuit-breaker.

---

### Module 7 & 8: Master Resume Sync, Evidence-Gated Verification Gate & ATS PDF Compiler
* **Source:** [`src/resume_store/master_resume.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/resume_store/master_resume.py), [`src/resume_store/master_sync.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/resume_store/master_sync.py), [`src/llm/validator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/llm/validator.py), [`src/tailor/fabrication_detector.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/fabrication_detector.py), [`src/tailor/knowledge_translator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/knowledge_translator.py), [`src/pdf_engine/generator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/pdf_engine/generator.py)
* **Master Resume Source of Truth (`python main.py resume [sync|check]`):** Parses `Manjunath_HK_Master_Resume.json` (`rxresu.me` schema) and deterministically generates `data/resume_profile.json`, `data/profile/allowed_tools_whitelist.json` (with `allowed_tools`, per-boundary `tool_evidence`, `learning_roadmap`, and `disallowed_hallucinations`), and `data/master_knowledge_bank.json`.
* **Evidence-Gated Whitelist & Boundary Isolation:** Allows a tool in a tailored bullet strictly within the employer or project boundary where `tool_evidence` confirms authentic usage (e.g. `docker` in ValueLabs & Dunzo, `kubernetes` in Dunzo, `dynatrace` and `kafka` event-log monitoring in ValueLabs, `appium` in Tata Elxsi). Blocks all `learning_roadmap` tools (`typescript`, `wiremock`, `pact`, `deepeval`, `ragas`, `promptfoo`, `garak`, etc.) and `disallowed_hallucinations` (`cypress`, `golang`, `rust`, etc.) across all boundaries until evidenced in the master resume and graduated via `python main.py resume sync`.
* **ATS-Hardened PDF Compilation:** Compiles single-column PDFs (`Manjunath_HK_<Company>_<Token>_Resume.pdf` and `data/profile/Manjunath_HK_Resume.pdf`) with font ligatures disabled (`font-variant-ligatures: none`), plain-text visible profile URLs, stacked promotion roles without unsafe arrow glyphs, and `Content-Disposition: inline` preview support.

---

### Module 10: 2-Phase Batch Autofill, Self-Healer & HTTP 412 Verifier
* **Source:** [`src/autofill/batch_form_engine.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/batch_form_engine.py), [`src/autofill/ats_filler.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/ats_filler.py), [`src/autofill/vendor_schemas.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/vendor_schemas.py), [`src/autofill/autofill_verifier.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/autofill_verifier.py), [`src/autofill/autofill_logger.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/autofill_logger.py)
* **`UniversalBatchFormFiller`:**
  * `extract_form_schema(page)`: Tags inputs/selects/comboboxes with `data-agy-id`, resolving hidden React-Select inputs via parent `.select__control`.
  * `execute_batch_fill(page, resume_path)`: Deterministically fills fields (`60 Days` notice, `17 LPA` current CTC, `27 LPA` expected CTC, `India (+91)`), enforces `TERRITORY_EXCLUSIONS` (blocking `"British Indian Ocean Territory (+246)"` and `"Indiana"`), verifies filled values via `verify_filled_fields`, and logs telemetry to `autofill_benchmarks.jsonl` and `unmapped_fields_backlog.jsonl`.
  * `apply_custom_actions(page, actions, unmapped_fields)`: Executes Phase B actions in 1 call and banks learned mappings into `data/logs/learned_field_mappings.json`.
* **`SubmissionVerifier` (HTTP 412 Gate):** Audits `data/logs/autofill_events.jsonl` for a verified `SUBMISSION_CONFIRMED` event and confirms screenshot existence in `data/logs/screenshots/` before allowing `/api/tracking/mark-applied/{job_id}`.

---

## 3. SQLite Relational Database Schema (`data/app_database.db`)

Managed by [`src/storage/database.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/storage/database.py) across 5 indexed tables:
1. **`job_applications`:** Tracks `id`, `source`, `company_name`, `job_title`, `job_url`, `resume_path`, `tailored_data_json`, `screening_qa_json`, `applied_at`, and `status` (`pending` | `approved` | `applied` | `rejected`).
2. **`daily_submission_limits`:** Tracks daily application counts against the configurable safety governor ceiling (`default: 200/day`).
3. **`tracked_requisitions`:** Stores SHA-256 content hashes of direct ATS requisitions (`NEW` $\rightarrow$ `ACTIVE` $\rightarrow$ `UPDATED`).
4. **`referral_outreach`:** Tracks referral outreach packs (`job_id`, `company`, `requisition_id`, `connection_note`, `inmail_pitch`, `status`: `GENERATED` $\rightarrow$ `SENT` $\rightarrow$ `CONNECTED` $\rightarrow$ `REFERRED`).
5. **`hiring_posts`:** Stores Track 3 social hiring posts (`post_id`, `author_name`, `author_headline`, `author_persona`, `company`, `post_text`, `post_url`, `extracted_emails`, `extracted_links`, `confidence_score`, `status`).
6. **Discovery Freshness, Sniper `<24h` Split, Track 3 SDUI Timestamp/US-W2 Guard & Repost-Saturation Guards (`src/ingestion/filters.py`, `src/scraper/job_finder.py`, `src/posts/post_tracker.py`, `src/posts/post_classifier.py`, `src/ingestion/hirist.py`):** Enforces `is_linkedin_posting_fresh_and_unsaturated(max_days=1, is_sniper_24h=True)` on LinkedIn's `sniper_fresh_24h` channel vs `max_days=3` (`<=72h`) on all other LinkedIn channels (rejecting `>3d`/week/month cards from `recommended` collections and rejecting recycled `Reposted` listings that already have `Over 100 people clicked apply`), parses SDUI concatenated post timestamps (`"Testing6d •"`) via `extract_relative_timestamp_from_card_text()`, rejects unverified `"recent"` placeholders and overseas US W2 staffing posts in Track 3, blocks hardware/industrial/PLC/FPGA/Typst titles in `NEGATIVE_TITLE_REGEX`, and requires verified employer metadata in `HiristCollector.fetch_sitemap_jobs()`.
7. **1,067-Org Watchlist, 3x/Day Sniper Sync & Deep Funnel Analytics Engine (`data/config/target_companies.json`, `scripts/com.linkedin.automator.daily.plist`, `src/storage/database.py`, `src/ui/templates/index.html`, `src/ui/static/app.js`):** Polls `1,067` verified active enterprise career boards (`2,425` catalog entries) 3x/day via Cloud CI (`07:30`, `13:30`, `19:30 IST`) paired with 3x/day local `launchd` sync runs (`08:00`, `14:15`, `20:00 IST`), and powers the Tab 3 **Analytics, Interview Turnover & Strategic Inference Engine** (`_enrich_application_row()`, `get_funnel_metrics()`) tracking interviewed organizations, posted-to-applied speed latency (`<6h`, `6-24h`, `24-72h`, `>72h`), most sought-out SDET/AI-QA topics, and portfolio value inferences.
