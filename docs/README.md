# Knowledge Base & Architecture Hub

Welcome to the central documentation suite for the **Local-First Career Automation, Interview Generation Engine & Assisted Application Copilot**.

This repository is an autonomous, anti-detection hardened job discovery, referral reconnaissance, and high-speed 2-phase batch application system specifically tailored for **Senior SDET / Lead QA Automation Architects** (5+ years experience threshold, Bengaluru onsite/hybrid, India Remote, and Global Remote contractor focus targeting the ₹25–35+ LPA band).

---

## Documentation Directory

The documentation is organized into clear functional layers:

| Document | Category | Purpose | Target Audience |
| :--- | :--- | :--- | :--- |
| **[01_USER_GUIDE.md](01_USER_GUIDE.md)** | **Special: "To the User"** | Intuitive, plain-English walkthrough of the entire end-to-end lifecycle, 3-Tier Interview Engine, `/apply` runbook, and how to customize it for your personal career preferences. | Candidate / End User |
| **[PRODUCTION_OPERATIONS_GUIDE.md](PRODUCTION_OPERATIONS_GUIDE.md)** | **Daily Operations** | Plain-English daily cheatsheet for monitoring the 8:00 AM daemon, auditing telemetry, using the 4-Tab Command Center, running `form-batch` & `referral-scout`, and deploying PR fixes. | Candidate / Daily Operator |
| **[02_CONCEPTUAL_ARCHITECTURE.md](02_CONCEPTUAL_ARCHITECTURE.md)** | **Conceptual** | The foundational philosophy: Zero-cost economics, 3-Track Ingestion (Direct ATS + Stealth LinkedIn Sniper + Social Hiring Posts), 3-Tier `InterviewRouter`, Low-Key Referral Scorer, and 2-Phase Batch Autofill. | System Designers & Architects |
| **[03_TECHNICAL_SPECIFICATION.md](03_TECHNICAL_SPECIFICATION.md)** | **Architectural** | Deep technical breakdown of all core modules, Pydantic schemas, 5-table SQLite relational database schema, Bézier kinematics, `UniversalBatchFormFiller`, and HTTP 412 submission verification. | Core Engineers & SDET Leads |
| **[04_USAGE_AND_OPERATIONS.md](04_USAGE_AND_OPERATIONS.md)** | **Operations & Usage** | Comprehensive CLI command reference (`main.py` subcommands including `form-batch`, `referral-scout`, `daily`, `posts`, `test`), configuration guide, and operational playbooks. | Operators & Daily Users |
| **[05_VERIFICATION_AND_TESTING.md](05_VERIFICATION_AND_TESTING.md)** | **Quality Assurance** | Catalog of the Standardized Multi-Tier Regression Runner (`python main.py test --tier core`, 62 Core gates + 18 Autofill simulations) and Ruff linter standards. | QA Architects & Contributors |
| **[SYSTEM_CAPABILITIES_EVALUATION.md](SYSTEM_CAPABILITIES_EVALUATION.md)** | **System Evaluation** | Comprehensive audit of all end-to-end capabilities, telemetry pipelines, and funnel metrics. | Architects & Operators |
| **[RESEARCH_1000_ORG_CI_PORTAL_SNIPER.md](RESEARCH_1000_ORG_CI_PORTAL_SNIPER.md)** | **Next-Phase Architecture** | Blueprint for the Explicit 1,000-Org Watchlist, GitHub CI `<24h` Delta Scanner, and Cloud-to-Local SQLite/Dashboard Auto-Ingest. | System Designers & Operators |

---

## System Quick Reference

```text
linkedinjobsearchautomation/
├── .agents/                     # Streamlined Agentic Customization OS (-64% token footprint)
│   ├── rules/                   # 3 Always-On Rules (00-core, 01-planning, 02-domain-invariants)
│   ├── skills/apply/SKILL.md    # On-Command /apply 6-step autonomous application runbook
│   ├── agents/                  # 3 JIT Subagents (apply_agent, autofill_learning_debugger, dry_run_agent)
│   └── hooks.json               # Post-edit verification & documentation sync reminder
├── docs/                        # Complete Knowledge Base (Architecture, Guides, Tax, Interview Prep)
├── data/
│   ├── config/                  # 56+ target enterprises (45 Dream Orgs) & ATS board slugs
│   ├── profile/                 # Candidate master data (gitignored), tools whitelist & Workday mappings
│   ├── logs/                    # 2-Layer Telemetry (benchmarks, unmapped backlog, learning vault, events)
│   ├── resumes/                 # Compiled single-column ATS PDF resumes
│   └── app_database.db          # SQLite database (applications, requisitions, referrals, hiring posts)
├── src/
│   ├── browser/                 # CDP port 9222 reuse, stealth context & cubic Bézier kinematics
│   ├── ingestion/               # Keyless REST collectors (Greenhouse, Lever, Ashby, Workday CXS)
│   ├── scraper/                 # 5-Channel Stealth LinkedIn scraper + sub-24h First-Applicant Sniper
│   ├── posts/                   # Track 3 Social Hiring Posts & Recruiter/Lead lead tracker
│   ├── tailor/                  # Grounded STAR tailoring, 3-Tier InterviewRouter & Referral Scorer
│   ├── llm/                     # Deterministic ResumeVerificationGate & company boundary isolation
│   ├── compiler/                # Typst & HTML/Playwright single-column ATS PDF generator
│   ├── filter/                  # Senior SDET experience (5–12 yrs), India/Global Remote & jurisdiction filter
│   ├── autofill/                # 2-Phase UniversalBatchFormFiller, ATS/LinkedIn copilot & HTTP 412 verifier
│   ├── notifier/                # DailyRunLogger & Zero-Cost Gmail SMTP Executive Briefing reporter
│   ├── storage/                 # Normalized Pydantic models & 5-table SQLite connection manager
│   ├── ui/                      # 4-Tab FastAPI Command Center (http://localhost:8000)
│   └── pipeline/                # Unified & Daily Pipeline orchestrators
├── scripts/                     # Daily launchd runner, Naukri Resdex pinger & ATS ingestion scripts
├── verify/                      # Standardized Regression Runner (62 Tier 1 Core + 18 Tier 2 Autofill gates)
└── main.py                      # Unified CLI (run, search, daily, form-batch, referral-scout, posts, test, lint)
```
