# Knowledge Base & Architecture Hub

Welcome to the central documentation suite for the **Local-First Career Automation & Assisted Application Copilot**.

This repository is an autonomous, anti-detection hardened job search and assisted application system specifically tailored for **Senior SDET / Lead QA Automation Engineers** (5+ years experience threshold, Bengaluru onsite/hybrid and India Remote focus).

---

## Documentation Directory

The documentation is organized into clear functional layers:

| Document | Category | Purpose | Target Audience |
| :--- | :--- | :--- | :--- |
| **[01_USER_GUIDE.md](01_USER_GUIDE.md)** | **Special: "To the User"** | Intuitive, plain-English walkthrough of the entire end-to-end lifecycle. Explains how the system works without dense jargon, how to use it daily, and exactly how to critique/customize it for your personal career preferences. | Candidate / End User |
| **[02_CONCEPTUAL_ARCHITECTURE.md](02_CONCEPTUAL_ARCHITECTURE.md)** | **Conceptual** | The foundational philosophy: Zero-cost economics, Dual-track ingestion (Public ATS + Stealth LinkedIn), Deterministic anti-fabrication grounding, and anti-detection threat modeling. | System Designers & Architects |
| **[03_TECHNICAL_SPECIFICATION.md](03_TECHNICAL_SPECIFICATION.md)** | **Architectural** | Deep technical breakdown of all 10 core modules, Pydantic schemas, SQLite relational database schema, Bézier kinematics formulas, and DOM locators. | Core Engineers & SDET Leads |
| **[04_USAGE_AND_OPERATIONS.md](04_USAGE_AND_OPERATIONS.md)** | **Operations & Usage** | Comprehensive CLI command reference (`main.py`, `run_ingestion.py`), configuration guide (`config.yaml`, `target_companies.json`), and daily workflow execution playbooks. | Operators & Daily Users |
| **[05_VERIFICATION_AND_TESTING.md](05_VERIFICATION_AND_TESTING.md)** | **Quality Assurance** | Catalog of all 32 standalone verification scripts in `verify/`, test assertions, and Ruff linter formatting standards. | QA Architects & Contributors |

---

## System Quick Reference

```
job-copilot/
├── docs/                        # Complete Knowledge Base (Architecture, Guides, Ops)
├── data/
│   ├── config/                  # Target company ATS board slugs & search filters
│   ├── profile/                 # Candidate authentic profile & allowed tools whitelist
│   ├── resumes/                 # Generated ATS-compliant single-column PDF resumes
│   └── app_database.db          # SQLite application audit log & daily submission counters
├── src/
│   ├── browser/                 # CDP stealth context & cubic Bézier input kinematics
│   ├── ingestion/               # Keyless REST collectors (Greenhouse, Lever, Ashby)
│   ├── scraper/                 # Stealth LinkedIn multi-channel scraper
│   ├── tailor/                  # AI resume tailoring & candidate notes translator
│   ├── llm/                     # Local Ollama client & deterministic verification gate
│   ├── compiler/                # Typst single-column ATS PDF generator
│   ├── filter/                  # Senior SDET experience & policy filters
│   ├── autofill/                # Assisted LinkedIn & ATS form fillers with pause hook
│   ├── storage/                 # Normalized Pydantic models & SQLite connection manager
│   ├── ui/                      # Local FastAPI Approval Gate dashboard (localhost:8000)
│   └── pipeline/                # One-shot unified pipeline orchestrator
├── scripts/                     # Seed company registry & direct ATS ingestion runners
├── verify/                      # 32 standalone verification scripts covering all modules
└── main.py                      # Subcommand CLI entrypoint (run, search, sync, filter, dashboard, apply, login, lint)
```
