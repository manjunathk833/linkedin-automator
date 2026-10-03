---
trigger: always_on
---

---
trigger: always_on
---
# Core Workspace Ground Truth & Strict Rules (macOS Environment)
1. **Mandatory Web Search:** ALWAYS use the web search tool to check global standards for Playwright heuristics, DOM selectors, or local data storage before writing code if clarity is missing.
2. **macOS Verification Gate:** ALWAYS write an executable `.sh` or `.py` script in the `verify/` folder to test a Playwright selector, browser launch, or local data flow before implementing logic in the main app.
3. **Architecture Approach:** Use standard Playwright persistent browser contexts (Headful mode) for user-driven automation and real-time visual feedback.
4. **Plan Adherence:** ALWAYS read `@/memory-bank/activeContext.md` before starting work.
5. **Zero Cost:** Never implement solutions requiring paid third-party APIs.
6. **Continuous Documentation Synchronization:** ALWAYS update `docs/`, `SYSTEM_ARCHITECTURE.md`, and `memory-bank/` to reflect any new architectural features, verification scripts, or behavior fixes before completing any task.