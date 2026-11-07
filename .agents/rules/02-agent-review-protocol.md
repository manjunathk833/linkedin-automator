---
trigger: always_on
---
# Subagent Delegation & Domain Invariants Protocol

## 1. Just-In-Time (JIT) Subagent Delegation
To prevent context rot and instruction bloat in the primary conversation, delegate heavy or specialized workflows to isolated subagents via `invoke_subagent` (using `Model: "inherit"` unless specified otherwise):
- **`research` (Built-in Read-Only Subagent):** Spawn for broad codebase surveys, multi-file audits, or documentation exploration that would clutter the main context window.
- **`autofill_learning_debugger` (`.agents/agents/autofill_learning_debugger.md`):** Spawn or follow when diagnosing ATS form failures, inspecting `autofill_dom_*.json` dumps, auditing `unmapped_fields_backlog.jsonl` (`python main.py autofill --audit`), or banking lessons into `data/logs/autofill_learning_vault.json`.
- **`dry_run_agent` (`.agents/agents/dry_run_agent.md`):** Spawn or follow during Phase N post-implementation verification to validate end-to-end data flow, SQLite state, and live UI rendering on `http://127.0.0.1:8000`.
- **`apply_agent` (`.agents/agents/apply_agent.md` & `.agents/skills/apply/SKILL.md`):** Activate when draining `data/approved_queue/` via `/apply`.

## 2. Non-Negotiable Domain & Engineering Invariants
1. **Candidate Profile & Evidence-Gated Employment Boundary Isolation:**
   - Ground all tailoring and form filling strictly in `Manjunath_HK_Master_Resume.json` (and the derived `data/resume_profile.json`, `data/master_knowledge_bank.json`, `data/profile/allowed_tools_whitelist.json`) plus `data/profile/candidate_master_data.json` (`Notice Period: 60 Days`, `Current CTC: 17 LPA`, `Expected CTC: 27 LPA`, `6.8 YOE`).
   - A tool may appear in a tailored bullet only within the employer or project boundary where the master resume contains evidence for it (`tool_evidence` in `allowed_tools_whitelist.json`). Tools listed in `learning_roadmap` (`typescript`, `wiremock`, `pact`, `deepeval`, `ragas`, `promptfoo`, `garak`, etc.) and `disallowed_hallucinations` (`cypress`, `golang`, `rust`, etc.) are blocked across all boundaries. A roadmap tool graduates to `allowed_tools` automatically once added to the master resume with an experience or project bullet and synced via `python main.py resume sync`.
2. **3-Tier Interview Routing (`InterviewRouter`):**
   - Route jobs into `TIER_0_POST_AUTHOR` (direct hiring post outreach), `TIER_1_SNIPER_APPLY` (`<24h` fresh postings for rapid application), or `TIER_2_REFERRAL_SLA` (Dream Enterprises / Workday roles held for a 36-hour low-key peer/alumni referral outreach window before cold applying).
   - Referral scoring (`score_referral_candidate`) must reject `>3,000` follower influencers and `"Ex-<Company>"` former employees.
3. **ATS Form & Combobox Precision:**
   - Never use loose `div:has(label:has-text(...))` ancestor selectors that collapse onto `#first_name` or `#country`.
   - Enforce `TERRITORY_EXCLUSIONS` (blocking `"British Indian Ocean Territory (+246)"` and `"Indiana"`), prioritize `+91` dial code matching, filter out `.select__menu-notice` loading spinners, dispatch synthetic React events (`input`, `change`, `blur`), and verify combobox selections via DOM read-back.
4. **Log-Grounded Submission Verification Gate (HTTP 412):**
   - Transitioning a job to `applied` in SQLite (`/api/tracking/mark-applied/{job_id}`) strictly requires a verified `SUBMISSION_CONFIRMED` event in `data/logs/autofill_events.jsonl` and a confirmation screenshot in `data/logs/screenshots/`.
