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
1. **Candidate Profile & Employment Boundary Isolation:**
   - Ground all tailoring and form filling strictly in `data/profile/candidate_master_data.json`, `data/resume_profile.json`, and `data/master_knowledge_bank.json` (`Notice Period: 60 Days`, `Current CTC: 17 LPA`, `Expected CTC: 27 LPA`, `6.8 YOE`).
   - Whitelisted modern architecture tools (`playwright`, `typescript`, `docker`, `kubernetes`, `kafka`, `wiremock`, `pact`) must remain scoped strictly to `Technical Projects` / `Personal` boundaries and NEVER leak into historical employer blocks (`Value Labs`, `Dunzo`, `Tata Elxsi`). Unverified tools (`cypress`, `golang`, etc.) remain strictly blocked.
2. **3-Tier Interview Routing (`InterviewRouter`):**
   - Route jobs into `TIER_0_POST_AUTHOR` (direct hiring post outreach), `TIER_1_SNIPER_APPLY` (`<24h` fresh postings for rapid application), or `TIER_2_REFERRAL_SLA` (Dream Enterprises / Workday roles held for a 36-hour low-key peer/alumni referral outreach window before cold applying).
   - Referral scoring (`score_referral_candidate`) must reject `>3,000` follower influencers and `"Ex-<Company>"` former employees.
3. **ATS Form & Combobox Precision:**
   - Never use loose `div:has(label:has-text(...))` ancestor selectors that collapse onto `#first_name` or `#country`.
   - Enforce `TERRITORY_EXCLUSIONS` (blocking `"British Indian Ocean Territory (+246)"` and `"Indiana"`), prioritize `+91` dial code matching, filter out `.select__menu-notice` loading spinners, dispatch synthetic React events (`input`, `change`, `blur`), and verify combobox selections via DOM read-back.
4. **Log-Grounded Submission Verification Gate (HTTP 412):**
   - Transitioning a job to `applied` in SQLite (`/api/tracking/mark-applied/{job_id}`) strictly requires a verified `SUBMISSION_CONFIRMED` event in `data/logs/autofill_events.jsonl` and a confirmation screenshot in `data/logs/screenshots/`.
