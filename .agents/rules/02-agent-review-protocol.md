---
trigger: always_on
---
# Mandatory Tri-Agent Auto-Invocation Protocol (Critic Architect, Vision & ATS Debugger)

For EVERY user prompt and proposed code modification, the agent MUST automatically evaluate the request through three mandatory quality lenses:

## 1. Vision Alignment Lens (`vision`)
Before planning or executing changes, verify alignment against our core North Star:
- [ ] **Zero Cost:** Requires 0 paid third-party APIs (uses Ollama or Gemini Free Tier).
- [ ] **Senior SDET Precision:** Tailored for Senior SDET / QA Lead (5+ yrs, Bengaluru / Remote India).
- [ ] **Human-in-the-Loop:** Preserves local Dashboard UI (`localhost:8000`) review gate.
- [ ] **No Scope Creep:** Rejects unnecessary feature bloat that strays from core job search & application ROI.

## 2. Critic Architect Quality Lens (`critic_architect`)
Before modifying code or running commands, audit technical soundness:
- [ ] **DOM & Selector Resilience:** Playwright selectors must be robust against LinkedIn layout variations.
- [ ] **Decoupled State Management:** Metadata extraction must occur before page navigation to prevent stale handles.
- [ ] **Verification Gate:** Verification script in `verify/` must validate browser/parser logic.
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

