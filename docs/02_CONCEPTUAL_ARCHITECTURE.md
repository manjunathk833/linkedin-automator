# Conceptual Architecture & Design Philosophy

## 1. Core Economics: The Zero-Cost Operational Mandate

Commercial career automation tools rely on paid proxy networks, paid CAPTCHA solvers, and paid LLM API subscriptions (\$50–\$300/month) while risking account bans from datacenter IP addresses.

This platform operates under a strict **Zero-Cost, Residential-First Mandate**:
1. **Rate-Paced Gemini Free Tier + Local Ollama Fallback:** Uses Google Gemini Flash free tier with a deterministic `4.0s` rate pacer, `25s` HTTP socket timeout, and `60s` quota circuit-breaker ([`src/tailor/llm_provider.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/llm_provider.py)), falling back automatically to 100% offline local inference on Apple Silicon via Ollama (`qwen2.5:7b`).
2. **Keyless Enterprise ATS Ingestion:** Queries public, unauthenticated JSON/REST endpoints across **Greenhouse, Lever, Ashby, and Workday Candidate Experience Service (CXS)** for 56+ target enterprises (45 tagged as `is_dream_org`).
3. **Residential macOS `launchd` Daemon + Git Worktree Isolation:** Executes scheduled 8:00 AM IST discovery runs from your local residential IP via an isolated production worktree (`../linkedinjobsearchautomation-prod` on `main`) symlinked to your primary `data/` and `.browser_data/` directories, avoiding GitHub Actions datacenter HTTP 999 blocks.

---

## 2. Tri-Track Discovery & The 3-Tier Interview Generation Engine

Landing Senior SDET interviews in 2026 requires optimizing for **first-applicant velocity** and **high-responder peer referrals** rather than raw application volume.

```text
 ┌───────────────────────────────────────────────────────────────────────────────────┐
 │                         TRI-TRACK INGESTION & DISCOVERY                           │
 └───────────────────────────────────────────────────────────────────────────────────┘
          │                                  │                                 │
 Track 1: Keyless Enterprise ATS    Track 2: 5-Channel LinkedIn       Track 3: Social Hiring Posts
 ├── Greenhouse / Lever / Ashby     ├── Boolean Search & Sniper <24h  ├── EM / QA Lead / Peer Posts
 ├── Workday CXS JSON Engine        ├── Recommended / Top-Applicant   ├── Two-Tier PostClassifier
 └── Real posted_at Timestamps      ├── Still-Hiring & Company Tabs   └── Direct Permalink & Email
          │                                  │                                 │
          └──────────────────────────────────┼─────────────────────────────────┘
                                             ▼
                        3-Tier InterviewRouter (classify_job_strategy)
          ┌──────────────────────────────────┼─────────────────────────────────┐
          ▼                                  ▼                                 ▼
 TIER_0_POST_AUTHOR               TIER_1_SNIPER_APPLY                 TIER_2_REFERRAL_SLA
 (Direct warm outreach to         (<24h fresh drops routed for        (Dream Orgs / Workday held
  hiring post author / email)      immediate first-wave apply)         36h for peer referral first)
```

### Low-Key High-Responder Referral Scorer (`score_referral_candidate`)
Reaching out to LinkedIn influencers (`10k+` followers) or former employees (`"Ex-Swiggy"`) yields `<1%` conversion. Our deterministic referral scorer ([`src/tailor/referral_generator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/referral_generator.py)):
* **Hard-Rejects (`-100`):** Former employees (`is_verified_current_employee` checks `"Ex-<Company>"` / `"Formerly at"`) and high-follower influencers (`>3,000` followers).
* **Prioritizes High-Responders:** Hiring post authors (`+45`), 1st-degree connections with free direct messaging unlocked (`+40`), shared past-employer/college alumni (`Dunzo`, `Value Labs`, `Tata Elxsi`, `SJCE` `+35`), and active mid-to-senior SDET/QA peers (`+25`).

---

## 3. Anti-Fabrication Grounding & Company Boundary Isolation

In Senior SDET technical loops, resume inflation or cross-company tool contamination causes immediate rejection. The system enforces a **Three-Layer Grounding Gate** ([`src/llm/validator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/llm/validator.py), [`src/tailor/knowledge_translator.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/tailor/knowledge_translator.py)):
1. **Master Knowledge Bank & Standard Resume Grounding:** All STAR bullets originate from [`data/master_knowledge_bank.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/master_knowledge_bank.json) and [`data/resume_profile.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/resume_profile.json).
2. **Strict Company Boundary Isolation (Gates 51, 52 & 65):**
   * Historical employer blocks (`Value Labs`, `Dunzo`, `Tata Elxsi`) are locked to their authentic toolchains (`Java`, `Selenium`, `REST Assured`, `Python`, `Appium`, `Ekam`, `BDD`).
   * Whitelisted modern distributed test architecture skills (`playwright`, `typescript`, `docker`, `kubernetes`, `kafka`, `wiremock`, `pact`) are strictly confined to the **`Technical Projects` / `Personal`** boundary and can never leak into past employer histories.
   * Unverified tools (`cypress`, `golang`, `rust`, `tosca`, `webdriverio`) are deterministically stripped.

---

## 4. High-Speed 2-Phase `Extract-Map-BatchExecute` Autofill & Continuous Telemetry

Traditional browser agents take 3–5 minutes per job because they run 15–20 sequential LLM vision/DOM turns per form. Our **2-Phase Batch Engine** ([`src/autofill/batch_form_engine.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/batch_form_engine.py)) achieves **10–15+ applications/hour**:

1. **Phase A (`form-batch inspect` — `<6s`, Zero LLM Turns):**
   * Injects stable `data-agy-id` attributes across all form controls in a single DOM pass.
   * Deterministically maps and batch-fills 80–90% of fields using `candidate_master_data.json`, `workday_field_mappings.json`, and `learned_field_mappings.json` (`Notice Period: 60 Days`, `Current CTC: 17 LPA`, `Expected CTC: 27 LPA`).
   * **Zero Territory Contamination:** Enforces `TERRITORY_EXCLUSIONS` (blocking `"British Indian Ocean Territory (+246)"` and `"Indiana"`), `:not(.iti__country)` option scoping, 4-tier exact-first scoring (`+91`), and mandatory post-selection DOM read-back verification (`_verify_combobox_selection`).
   * Outputs compact JSON containing **only** `unmapped_fields`.
2. **Phase B (`form-batch apply` — 1 Single Turn + Closed-Loop Auto-Learning):**
   * Resolves all remaining custom fields in a single batch call and automatically banks the question + answer into `data/logs/learned_field_mappings.json` so Phase A auto-fills that question on all future applications with zero LLM turns.
3. **2-Layer Continuous Improvement Telemetry:**
   * Layer 1 (Inline Python): Streams per-page speed and coverage metrics to `data/logs/autofill_benchmarks.jsonl` and unmapped questions to `data/logs/unmapped_fields_backlog.jsonl`.
   * Layer 2 (`autofill_learning_debugger`): Audits `python main.py autofill --audit` and promotes recurring questions (`count >= 2`) into permanent rules.

---

## 5. Seamless CDP Reuse, Safety Governor & HTTP 412 Submission Verification

1. **Seamless CDP Port 9222 Session Reuse (Gate 81):** [`src/browser/cdp_stealth.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/cdp_stealth.py) detects if headful Chrome is already listening on port `9222` (`is_cdp_port_open(9222)`) and attaches via `connect_over_cdp`, opening a new tab without profile lock collisions (`SingletonLock`) or browser restarts.
2. **Configurable Safety Rate Governor (Gate 42):** Enforces a configurable daily ceiling (`default: 200/day` in `config.yaml`) backed by SQLite.
3. **Log-Grounded Submission Verification Gate (Gate 80 — HTTP 412):** `POST /api/tracking/mark-applied/{job_id}` is protected by [`SubmissionVerifier`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/autofill_verifier.py), which rejects unconfirmed calls with `HTTP 412 Precondition Failed` unless a recent `SUBMISSION_CONFIRMED` event in `autofill_events.jsonl` and a visual confirmation screenshot in `data/logs/screenshots/` exist.
