---
trigger: always_on
---
# Mandatory Quad-Agent Auto-Invocation Protocol (Critic Architect, Vision, ATS Debugger & Dry Run Agent)

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

## 4. Autonomous Dry Run & Live Browser Validation Lens (`dry_run_agent`)
After code changes or bug fixes are applied, evaluate against the dry run mandate:
- [ ] **Persistent Browser Session Readiness:** Ensure stored session state (`.browser_data/`, `SessionManager`) and local FastAPI server (`http://127.0.0.1:8000`) are verified.
- [ ] **Human-in-the-Loop Takeover (Zero Premature Exit):** If authentication, 2FA, or CAPTCHA is encountered, execution must NEVER terminate prematurely. Prompt the user, pause interactively, refresh session, and seamlessly resume.
- [ ] **Live Browser Traversal & Dynamic Reactivity:** Verify staging review, version toggling, referral reconnaissance, dynamic note reactivity, character limits, and assisted copilot flows in real browser execution.
- [ ] **Autonomous Self-Healing Loop:** If regressions, broken selectors, or overflow issues are found, diagnose via `autofill_learning_vault.json`, immediately patch in `src/`, and re-verify.
- [ ] **Implementation Report Emitted:** Deliver a structured health report upon completion before raising a Pull Request to `main`.

