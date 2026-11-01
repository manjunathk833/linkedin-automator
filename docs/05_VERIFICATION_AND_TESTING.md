# Verification Suite & Testing Standards

Per Workspace Rule #2 and Rule #8, every browser interaction, DOM selector, LLM translation, data schema, and API endpoint must be verified via an executable script in `verify/` and pass the Standardized Multi-Tier Regression Runner (`100%` pass rate required before any commit or PR).

---

## 1. Standardized Multi-Tier Regression Runner (`verify/run_regressions.py`)

Execute the standardized test suite via `main.py`:

```bash
# Run Tier 1 Core Regression Suite (62 self-contained tests in ~60s — Mandatory before every commit/PR):
./venv/bin/python main.py test --tier core

# Run Tier 2 Playwright Autofill Simulation Suite (18 vendor form simulation gates):
./venv/bin/python main.py test --tier autofill

# Run All Tiers (Core + Autofill):
./venv/bin/python main.py test --tier all

# Run Ruff Linter & Formatter (0 errors required across 174+ files):
./venv/bin/python main.py lint
```

* **CI/CD Portability:** When `data/profile/candidate_master_data.json` is absent (e.g., on GitHub Actions Ubuntu runners where candidate PII is gitignored), `verify/synthetic_mock_fixtures.py` automatically deploys deterministic mock fixtures, and `src/browser/cdp_stealth.py` auto-switches to headless mode when `$DISPLAY` is unset.

---

## 2. Master Verification Gate Catalog (Gates 01 to 105)

### Gates 01–62: Foundation, Ingestion, Grounding, Vendor Schemas & Queue Governance
| Gate | Script Path | Subsystem Verified | Status |
| :---: | :--- | :--- | :---: |
| **01–06** | `verify/01` to `06_audit_resume_accuracy.py` | Playwright launch, `ResumeProfile` Pydantic schema, FastAPI approval gate, CDP connect, PDF engine, and canonical resume accuracy | **PASSED** |
| **07–21** | `verify/07` to `21_test_description_and_diff.py` | Multi-step Easy Apply, Boolean query optimization, 4-channel scraper, pagination guards, status sync, and visual diff badging | **PASSED** |
| **23–33** | `verify/23` to `33_test_resume_and_knowledge_regeneration.py` | STAR notes translation, deterministic fabrication detector, local Ollama client, keyless Greenhouse/Lever/Ashby ingestion, Typst PDF compiler, and SQLite governor | **PASSED** |
| **34–45** | `verify/34` to `45_test_staging_job_metadata_enrichment.py` | Dashboard data flow, type coercion, live queue status, inline PDF preview, static cache busting, multi-tab popup switching, standardized vendor schemas, 200/day governor, React-Select comboboxes, and `Manjunath_HK_*` PDF naming | **PASSED** |
| **46–54** | `verify/46` to `54_test_pdf_inline_preview_headers.py` | Okta, Databricks, and Coinbase custom Greenhouse schemas, LinkedIn External ATS pivot, Gemini rate pacer & 60s cooldown circuit-breaker, cross-company boundary isolation, zero-contamination queue audit, and side-by-side PDF comparison | **PASSED** |
| **55–62** | `verify/55` to `62_test_user_driven_applied_and_approved_purge.py` | Oracle Cloud HCM, Workday Standard & BEM DOM precision, `AutofillLogger` & Learning Vault (`autofill_learning_vault.json`), manual takeover cheat-sheet, SQLite indexing, and user-driven applied queue auto-purge | **PASSED** |

### Gates 63–105: Career Transition Sprints, Social Posts, Self-Healing, CDP Reuse & Interview Engine
| Gate | Script Path | Subsystem Verified | Status |
| :---: | :--- | :--- | :---: |
| **63** | `verify/63_test_unified_job_search.py` | Unified search coordinator pooling Direct ATS + LinkedIn channels with cross-source deduplication | **PASSED** |
| **64** | `verify/64_test_source_badge_accuracy.py` | Accurate source badge resolution (`Greenhouse`, `Lever`, `Ashby`, `Workday`, `LinkedIn`) in UI | **PASSED** |
| **65** | `verify/65_test_sprint1_stack_and_inbound.py` | Modern SDET tool whitelist (`Playwright`, `TypeScript`, `Docker`, `K8s`, `Kafka`, `Pact`, `WireMock`), `Technical Projects` boundary isolation, and Naukri pinger | **PASSED** |
| **66** | `verify/66_test_sprint2_workday_cxs_and_dream_orgs.py` | Keyless Workday CXS REST collector, 56-company registry (45 Dream Orgs), and SQLite `tracked_requisitions` SHA-256 change detection | **PASSED** |
| **67** | `verify/67_test_sprint2_enhanced_filtering_and_workday.py` | Centralized `is_sdet_title` and `is_india_or_remote_location` filters + multi-term Workday India search | **PASSED** |
| **68** | `verify/68_test_sprint3_dual_funnel_and_referral_generator.py` | Dual-funnel routing, `ReferralNoteGenerator` ($\le 300$-char notes, $\le 1000$-char InMails), and isolated SQLite `referral_outreach` lifecycle | **PASSED** |
| **69** | `verify/69_test_sprint4_global_remote_and_compliance.py` | Global remote heuristics, US-only jurisdiction exclusions, Section 44ADA / W-8BEN / GST LUT guides, and concurrency-safe SDET coding patterns | **PASSED** |
| **70** | `verify/70_test_session_and_email_reporter.py` | `SessionManager` cookie export, `EmailReporter` HTML briefing & archive fallback, and `DailyRunLogger` diagnostics | **PASSED** |
| **71** | `verify/71_test_referral_reconnaissance_pivot_and_job_links.py` | Parameterized LinkedIn People search links, clean job URL weaving, and dynamic recipient greeting reactivity | **PASSED** |
| **72** | `verify/72_test_hiring_posts_tracker_and_classifier.py` | Track 3 `HiringPostTracker`, two-tier `PostClassifier`, `PostOutreachComposer`, SQLite `hiring_posts`, and Tab 4 UI | **PASSED** |
| **73** | `verify/73_test_post_url_extraction_and_repair.py` | Multi-tier LinkedIn post permalink extraction, React Fiber SDUI inspection, and `repair_invalid_post_urls` migration | **PASSED** |
| **74** | `verify/74_test_posts_links_and_dream_org_precision.py` | Direct ATS career link extraction from posts, `mailto:` recruiter triggers, and word-boundary Dream Org matching | **PASSED** |
| **75** | `verify/75_test_post_formatting_and_permalink_resilience.py` | Post paragraph preservation, UI noise stripping, and permalink fallback resilience | **PASSED** |
| **76** | `verify/76_test_posts_optimization_and_deduplication.py` | Fast early-break post pagination, 5-query rotation, and cross-session SHA-256 post deduplication | **PASSED** |
| **77** | `verify/77_test_daily_pipeline_comprehensive_wiring.py` | End-to-end `DailyPipelineRunner` wiring across Track 1, Track 2, Track 3, Naukri Resdex touch, and morning HTML briefing | **PASSED** |
| **79** | `verify/79_test_autofill_logging_and_self_healing.py` | `AutofillLogger` atomic JSONL streaming, `AutofillSelfHealer` 5 remediation recipes, and `HIRIST_TECH_STANDARD` schema | **PASSED** |
| **80** | `verify/80_test_submission_verifier_and_guardrails.py` | `SubmissionVerifier` log-audit gate, `HTTP 412 Precondition Failed` protection on `/api/tracking/mark-applied/{job_id}`, and `force=true` override | **PASSED** |
| **81** | `verify/81_test_stealth_browser_cdp_reuse.py` | Seamless Chrome CDP Port `9222` session reuse, anti-collision fallback, and headless Linux CI compatibility | **PASSED** |
| **103** | `verify/103_test_expanded_collections_and_keywords.py` | Multi-collection discovery (`recommended`, `top-applicant`, `still-hiring`) and expanded Senior SDET boolean syntax | **PASSED** |
| **104** | `verify/104_test_search_sort_and_company_discovery.py` | Configurable relevance vs. date sorting (`sort_by: "relevance"`) and Channel 5 Company Jobs Tab scraper (`scrape_company_jobs`) | **PASSED** |
| **105** | `verify/105_test_interview_engine_and_batch_autofill.py` | Zero-contamination country/dial-code combobox scorer (`TERRITORY_EXCLUSIONS`, `+91`), `UniversalBatchFormFiller` Phase A & Phase B closed-loop learning, 60-Day Notice Lock, ATS publish timestamps, 3-Tier `InterviewRouter`, and Low-Key Referral Scorer | **PASSED** |
| **106** | `verify/106_test_portal_sniper_and_ci_auto_ingest.py` | Extended Collectors (`SmartRecruiters`, `Rippling`, `Workable`, `Recruitee`), `OrgResearcher` 107-org watchlist audit, `PortalSniperEngine` `<24h` delta & seen-ledger filter, and `CISyncIngestor` + `/api/ci-sync` onboarding | **PASSED** |
