---
trigger: always_on
---
# Mandatory Dual-Agent Auto-Invocation Protocol (Critic Architect & Vision)

For EVERY user prompt and proposed code modification, the agent MUST automatically evaluate the request through two mandatory quality lenses:

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
- [ ] **Documentation Sync:** Architecture changes, endpoints, and verification tests must be synced to `docs/` and `SYSTEM_ARCHITECTURE.md`.

