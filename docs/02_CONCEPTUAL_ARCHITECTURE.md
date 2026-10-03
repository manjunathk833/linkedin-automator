# Conceptual Architecture & Design Philosophy

## 1. Core Economics: The Zero-Cost Operational Mandate

Most commercial career automation tools rely on paid third-party proxy networks (BrightData, ScraperAPI), paid CAPTCHA solvers (2Captcha), and paid LLM token subscriptions (OpenAI GPT-4). Over time, these introduce substantial operational costs ($50–$300/month) and risk platform account bans.

This system was engineered with an absolute **Zero-Cost Architectural Mandate**:
1. **Local Apple Silicon Inference:** Leverages local LLMs via Ollama (`qwen2.5:7b-instruct-q4_K_M` or `14b`) utilizing macOS unified memory and Metal GPU hardware acceleration.
2. **Free-Tier Cloud Fallback:** Integrates Google Gemini 2.5 Flash Free Tier (`temperature=0.0`) as a high-speed primary engine with automatic offline fallback to local Ollama.
3. **Keyless ATS Ingestion:** Queries public, unauthenticated JSON endpoints directly exposed by Greenhouse, Lever, and Ashby job boards, eliminating proxy and scraping fees.
4. **Local Hardware Execution:** All relational databases (SQLite), PDF compilers (Typst / Playwright), and web dashboards (FastAPI) execute strictly on the local host. Zero cloud server overhead.

---

## 2. Ingestion Strategy: Dual-Track Discovery

Standard job scrapers rely entirely on LinkedIn DOM crawling, which exposes candidate sessions to rate limits and layout churn. This architecture introduces a **Dual-Track Ingestion Model**:

```
                         ┌────────────────────────────────────────────────────────┐
                         │              DUAL-TRACK INGESTION ENGINE               │
                         └────────────────────────────────────────────────────────┘
                                      │                                 │
                   Track A: Keyless ATS REST APIs          Track B: Stealth LinkedIn Scraper
                                      │                                 │
                   ├── Greenhouse (boards-api.greenhouse.io)├── 4 Channels (Search, Recs,
                   ├── Lever (api.lever.co)                 │   Recruiter Posts, Similar Jobs)
                   └── Ashby (api.ashbyhq.com)              └── Real Chrome Persistent Session
                                      │                                 │
                                      └────────────────┬────────────────┘
                                                       ▼
                                     Unified Pydantic JobListing Model
                                                       │
                                                       ▼
                                        Senior SDET Experience Filter
                                       (4–10 yrs required, BLR / Remote)
```

### Track A: Direct ATS REST Endpoints (High Velocity, Zero Detection Risk)
* Enterprise companies host open career boards on third-party ATS platforms.
* By maintaining an enterprise board registry (`data/config/target_companies.json`), the system dispatches concurrent async HTTP requests (`httpx`) to public REST endpoints.
* **Benefits:** Fetches 200+ clean listings across 37+ tech leaders in <3 seconds without opening a browser, parsing dynamic HTML, or touching LinkedIn.

### Track B: Stealth LinkedIn Scraper (Broad Discovery & Easy Apply Target)
* Scrapes LinkedIn across 4 distinct vectors: Active Boolean Search, Recommended Collection (`/jobs/collections/recommended/`), Recruiter Content Posts (`/search/results/content/`), and Sidebar Similar Jobs.
* **Benefits:** Discovers unlisted openings, startup hiring posts, and jobs with native Easy Apply forms.

---

## 3. Anti-Fabrication Grounding: Defense-in-Depth

A critical failure mode of AI-generated resumes is **hallucination**—inventing tools, metrics, or technologies to forcibly match job keywords. In technical engineering roles (specifically Senior SDET), claiming unverified tools (e.g. claiming Playwright or Kubernetes when the candidate's authentic history is Selenium and REST Assured) causes instant rejection during technical interviews.

The system prevents fabrication via a **Three-Tier Defense-in-Depth Architecture**:

```
[Raw Job Description] + [Authentic Candidate Vault]
                     │
                     ▼
  Level 1: Prompt Grounding (temperature = 0.0)
  Strict STAR instructions + Negative few-shot rules
                     │
                     ▼
  Level 2: Deterministic Verification Gate (Code Layer)
  Inspects tokens against allowed_tools_whitelist.json
  Purges/Substitutes 100% of unverified tools
                     │
                     ▼
  Level 3: Human Approval Gate (FastAPI Dashboard)
  Visual diff highlighting ✨ Tailored vs Base achievements
  Candidate reviews and verifies before autofill trigger
```

* **Level 1 (Prompt Level):** Uses deterministic generation (`temperature=0.0`) and structured output schemas (`TailoredBulletsResponse`) that explicitly forbid introducing tools absent from the master knowledge bank.
* **Level 2 (Deterministic Code Gate):** The output passes through `ResumeVerificationGate` ([src/llm/validator.py](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/llm/validator.py)). The gate parses the candidate's authentic whitelist ([data/profile/allowed_tools_whitelist.json](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/profile/allowed_tools_whitelist.json)). Any unauthorized tool (e.g. Cypress, Golang, Kubernetes) is automatically stripped or substituted with its authentic equivalent (Selenium, Python, Docker) before PDF generation.
* **Level 3 (Human Review Gate):** No application ever proceeds to submission without candidate review on the local FastAPI web dashboard.

---

## 4. Anti-Detection Hardening & Humanized Kinematics

Modern anti-bot systems (Cloudflare Bot Management, Datadome, LinkedIn Security) evaluate browser behavior across three layers:
1. **TLS & Session Fingerprinting:** Headless browsers generate unnatural TLS client hellos and lack authentic cookies.
   * *Mitigation:* We use a **headful persistent Google Chrome context** pointing to the candidate's authentic user profile (`.browser_data/`). Authentic session cookies, WebGL fingerprints, and browser storage are naturally preserved.
2. **CDP Leaks (`Runtime.enable` Traps):** Anti-bot scripts detect standard Playwright automations via Chrome DevTools Protocol artifacts (`navigator.webdriver == true`, leaked console inspection handlers).
   * *Mitigation:* [src/browser/cdp_stealth.py](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/cdp_stealth.py) strips `navigator.webdriver`, mocks authentic `window.chrome.runtime` and `loadTimes`, emulates authentic macOS Chrome plugins, and supports drop-in replacement with `rebrowser-playwright`.
3. **Kinematics & Behavioral Biometrics:** Bot detection monitors mouse trajectories and keystroke cadences. Instant coordinate jumps and linear movements trigger immediate security challenges.
   * *Mitigation:* [src/browser/kinematics.py](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/kinematics.py) generates natural non-linear mouse paths using **cubic Bézier curves** with randomized control point offsets and micro-tremor noise:
     $$B(t) = (1-t)^3 P_0 + 3(1-t)^2 t P_1 + 3(1-t) t^2 P_2 + t^3 P_3, \quad t \in [0, 1]$$
   * Keystrokes are generated using **log-normal randomized delay distributions** ($40–240$ ms per character) with thinking pauses after spaces and punctuation.

---

## 5. Governance & Safety Limits: The Rolling 24-Hour Quota

To ensure complete platform terms compliance and prevent aggressive automation that could damage candidate profile trust:
* **Assisted Autofill (HITL):** The system replaces unattended botting with an **assisted copilot**. The browser pre-fills known fields, attaches the tailored PDF, and **halts at the final "Review your application" modal**. Control is intentionally yielded back to the candidate, who clicks the final "Submit" button.
* **Daily Budget Governor:** An automated rate limiter ([src/autofill/governor.py](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/governor.py)) tracks applications in a local SQLite database ([data/app_database.db](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/app_database.db)) and enforces a strict cap of **$\le 15$ applications per 24 hours**. Once the budget is exhausted, the autofill trigger locks with HTTP 429 until midnight.

---

## 6. Multi-Tab Event Model & Dynamic Portal Switching

Enterprise career sites (e.g. Coinbase, Lever, Greenhouse client boards) frequently launch the actual job application form in a separate tab or popup window via `<a target="_blank">` or JavaScript `window.open()`.
* **Context-Level Page Interception:** Rather than remaining trapped in the original landing page handle, [src/autofill/ats_filler.py](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/autofill/ats_filler.py) registers a temporary `"page"` event listener on the active `BrowserContext`.
* **Automatic Tab Hand-off:** When the `Apply` trigger spawns a popup or new tab, the copilot immediately captures the new `Page` reference, awaits `domcontentloaded`, and calls `bring_to_front()` to ensure physical visibility on macOS.
* **Recursive Target Evaluation:** The copilot dynamically checks the newly focused tab for nested ATS iframes or secondary trigger buttons before executing kinematics-driven field population.

