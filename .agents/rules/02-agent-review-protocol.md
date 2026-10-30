---
trigger: always_on
---
# Mandatory Multi-Agent Auto-Invocation Protocol (Critic Architect, Vision, ATS Debugger, Dry Run Agent & Apply Agent)

For EVERY user prompt and proposed code modification, the agent MUST automatically evaluate the request through four mandatory quality lenses:

## 1. Vision Alignment Lens (`vision`)
Before planning or executing changes, verify alignment against our core North Star:
- [ ] **Zero Cost:** Requires 0 paid third-party APIs (uses Ollama or Gemini Free Tier).
- [ ] **Senior SDET & Architecture Precision:** Tailored for Senior SDET / Lead Automation Architect (5+ yrs, Bengaluru / Remote India / Global Remote contractor, ₹25–35+ LPA band).
- [ ] **Tiered Dual-Funnel Routing:** High-speed copilot autofill for growth startups vs. cold autofill lock + referral outreach for Dream Enterprises.
- [ ] **Human-in-the-Loop:** Preserves local Dashboard UI (`localhost:8000`) review gate.
- [ ] **No Scope Creep:** Rejects unnecessary feature bloat that strays from core job search & application ROI.

## 2. Critic Architect Quality Lens (`critic_architect`)
Before modifying code or running commands, audit technical soundness:
- [ ] **DOM & Selector Resilience:** Playwright selectors must be robust against LinkedIn layout variations.
- [ ] **Tool Whitelist & Boundary Governance:** Whitelisted tools (`playwright`, `typescript`, `docker`, `kubernetes`, `kafka`, `wiremock`, `pact`) must be grounded in candidate notes; unverified tools (`cypress`, `golang`, etc.) remain blocked.
- [ ] **Employment Boundary Isolation:** Independent architecture bullets must be scoped strictly to `Technical Projects` without leaking into Value Labs, Dunzo, or Tata Elxsi.
- [ ] **Decoupled State Management:** Metadata extraction must occur before page navigation to prevent stale handles.
- [ ] **Verification Gate & Regression Suite:** Verification script in `verify/` must validate browser/parser logic, and the full core regression suite must pass 100% (`python main.py test --tier core`).
- [ ] **Clean Code & Linting:** Code must pass `python main.py lint` with 0 linter errors.
- [ ] **ATS Vendor Schema Banking:** Discovered custom or org-branded URLs during debugging must be cataloged in `src/autofill/vendor_schemas.py` and classified on navigation.
- [ ] **Documentation Sync:** Architecture changes, endpoints, and verification tests must be synced to `docs/` and `SYSTEM_ARCHITECTURE.md`.

## 3. ATS Autofill Debugger & Form Precision Lens (`ats_autofill_debugger`)
When debugging, fixing, or adding ATS vendor autofill logic, enforce precision safeguards:
- [ ] **Exact Element Scoping:** Reject broad `div:has(...)` queries that could match root container `div`s and overwrite top-level inputs (e.g. First Name or Country).
- [ ] **Combobox Loading Notice Filter:** Ensure combobox locators filter out `.select__menu-notice` to avoid clicking transient loading spinners.
- [ ] **Dial Code (+91) Prioritization:** Ensure phone country selectors prioritize exact dial code matches over partial string matches to prevent territory collisions (e.g. +246).
- [ ] **Synthetic Event Dispatch:** Ensure text inputs dispatch `input`, `change`, and `blur` events so React/form state registers them and clears red validation outlines.
- [ ] **Live Zero-Contamination Assertions:** Ensure verification scripts assert exact values for every individual field and combobox control text without cross-field contamination.

## 4. Autonomous Dry Run & Universal Flow Verification Lens (`dry_run_agent`)
Before proposing plans and after code changes or bug fixes are applied, evaluate against the universal dry run verification mandate:
- [ ] **Mandatory Plan Phase Check:** Verify that the proposed implementation plan explicitly includes a dedicated phase for Post-Implementation Dry Run & System Flow Verification prior to requesting approval.
- [ ] **Universal End-to-End Flow Verification (Zero Superficial Passes):** Dry runs must NEVER settle for superficial checks (such as merely checking if a function ran without throwing an error, checking if a list is non-empty, or counting saved rows). Whenever ANY code change, parser tweak, business logic update, database migration, or UI component is modified, the dry run MUST exhaustively verify the entire operational flow end-to-end across every stage:
  - **1. Input & Data Integrity:** Verify extracted or generated values (e.g., links, IDs, contact details, dates) are syntactically valid, free of concatenation artifacts or emoji pollution, and reachable/resolvable.
  - **2. Semantic & Classification Fidelity:** Rigorously audit tags, badges, statuses, and classifications against false positives, heuristic edge cases, and domain keyword collisions (e.g., tech skills colliding with company names).
  - **3. Downstream Persistence & API Fidelity:** Verify that changes correctly propagate into storage/database persistence and are accurately served by REST endpoints without schema drift.
  - **4. Live Dynamic UI & Interaction Verification:** In the local Command Center UI (`http://127.0.0.1:8000`), verify complete visual rendering, interactive state transitions, modals, filters, tabs, and button actions.
  - **5. Action Execution & Edge-Case Resilience:** Ensure downstream actions (e.g., opening links, copying notes, autofilling forms) perform seamlessly without breaking or hitting 404s.
- [ ] **Persistent Browser Session Readiness:** Ensure stored session state (`.browser_data/`, `SessionManager`) and local FastAPI server (`http://127.0.0.1:8000`) are active and verified. Safe process lifecycle management prevents duplicate Chrome process collisions.
- [ ] **Anti-Looping & Diagnostic Lock (Max 2 Attempts):** Enforce strict anti-looping safeguards. If any action fails twice, immediately halt, dump DOM diagnostics, diagnose root cause, and either patch or escalate. Never repeat identical failed operations 3+ times.
- [ ] **Human-in-the-Loop Takeover (Zero Premature Exit):** If authentication, 2FA, or CAPTCHA is encountered, execution must NEVER terminate prematurely. Prompt the user, pause interactively, refresh session, and seamlessly resume.
- [ ] **Autonomous Self-Healing Loop:** If regressions, broken selectors, or overflow issues are found, diagnose via `autofill_learning_vault.json`, immediately patch in `src/`, and re-verify.
- [ ] **Mandatory Post-Implementation Dry Run Execution:** An exhaustive live, headful dry run is strictly mandatory after EVERY implementation cycle. No task or PR may be completed without running the active system flow live, observing real output seeds, validating database state, and confirming that the UI reflects the updates.
- [ ] **Standardized Regression & Lint Gate:** Core regression suite passes 100% (55+ tests) and linter reports 0 errors across all files.
- [ ] **Implementation Report Emitted:** Deliver a structured health report upon completion before raising a Pull Request to `main`.

## 5. Autonomous Apply Agent Lens (`apply_agent`)
When reviewing, testing, or executing job application workflows:
- [ ] **Approved Queue Verification:** Checks and loads job payloads from `data/approved_queue/` with matching tailored PDF resumes.
- [ ] **Data Bank Grounding & Zero Hallucination:** Ensures 100% data grounding in `candidate_master_data.json` (Notice Period: 60 Days, Expected CTC: 27 LPA, Current CTC: 17 LPA), `resume_profile.json`, and `workday_field_mappings.json`. Inlines exact values into browser subagent prompts to strictly prevent hallucination.
- [ ] **Repeatable Form Container Expansion:** Expands repeatable sections (`+ Add Experience Details`, `+ Add Education Details`) to populate all historical positions (Value Labs, Dunzo, Tata Elxsi) and SJCE degree, and supplies `NA` for negative referral disclosures.
- [ ] **Strict Fail-Fast Policy (Zero Over-Exploration):** If a job is 404, closed, or unavailable, strictly forbids searching Google or external career portals; immediately logs `UNAVAILABLE`, purges from queue, and advances to the next job.
- [ ] **High Autonomy & Targeted HITL:** Executes independently across jobs without interrupting for known candidate values; halts and invokes `ask_question` strictly for unmapped salary expectations, novel questions, or CAPTCHA/2FA.
- [ ] **Step Budget Enforcement:** Enforces maximum 20 browser actions per job.
- [ ] **Post-Apply Audit:** Ensures applications are registered in SQLite `ApplicationDatabase`, resumes archived to `data/resumes/`, and payloads purged from `data/approved_queue/`.
