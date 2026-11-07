# Operations & Usage Manual

This manual provides the complete operational reference for running, configuring, and maintaining the platform.

---

## 1. System Setup & Prerequisites

* **Operating System:** macOS (Apple Silicon recommended) or Linux (auto-headless fallback supported in CI).
* **Python Runtime:** Python 3.9+ virtual environment (`./venv/bin/python`).
* **Browser:** System Google Chrome (`/Applications/Google Chrome.app`), managed automatically via CDP Port `9222` reuse ([`src/browser/cdp_stealth.py`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/src/browser/cdp_stealth.py)).
* **AI Engine:** Free-tier Google Gemini API Key in `.env` (`GEMINI_API_KEY="..."`) + optional local Ollama (`qwen2.5:7b`).

---

## 2. Primary CLI Command Reference (`main.py`)

| Subcommand | Description | Key Flags / Options |
| :--- | :--- | :--- |
| `python main.py daily` | Runs the comprehensive automated morning workflow: regression gate $\rightarrow$ notes sync $\rightarrow$ 3-track discovery $\rightarrow$ Naukri Resdex touch $\rightarrow$ HTML executive briefing $\rightarrow$ Command Center readiness. | `run` (default)<br/>`audit`: Recent run telemetry.<br/>`diagnose`: Full health check.<br/>`--headless`, `--skip-tests`, `--no-email` |
| `python main.py form-batch` | Runs the 2-Phase `UniversalBatchFormFiller` engine on an active ATS tab or approved job. | `inspect --job-id <id>`: Phase A batch fill + read-back verification + outputs `unmapped_fields` JSON.<br/>`apply --job-id <id> --actions '<json>'`: Phase B 1-turn custom fill + auto-learning. |
| `python main.py referral-scout` | Dynamically scouts verified current employees on LinkedIn over CDP port 9222 and ranks them with `score_referral_candidate`. | `--job-id <id>`: Scout a specific role.<br/>`--limit <n>`: Max leads per company. |
| `python main.py autofill` | Audits ATS autofill events, Phase A benchmark latencies, unmapped field backlogs, and Learning Vault rules. | `--audit`: Prints aggregated telemetry report. |
| `python main.py posts` | Discovers and manages Track 3 LinkedIn social hiring posts from EMs, QA Leads, and recruiters. | `discover`, `list`, `stats`, `--headless` |
| `python main.py search` | Runs unified discovery across Track 1 (Direct ATS: Greenhouse, Lever, Ashby, Workday), Track 2 (LinkedIn Multi-Channel + `<24h` Sniper), and Track 3 (`<24h`/`<72h` Hiring Posts). | `--source [all|ats|linkedin|sniper|portals|posts]`, `--headless`, `--max-jobs` |
| `python main.py dashboard` | Launches the 4-Tab FastAPI Command Center at `http://127.0.0.1:8000`. | `--host 127.0.0.1`, `--port 8000` |
| `python main.py resume` | Validates `Manjunath_HK_Master_Resume.json` and deterministically syncs `resume_profile.json`, `allowed_tools_whitelist.json`, and `master_knowledge_bank.json`. | `sync` (default), `check`, `--dry-run` |
| `python main.py sync` | Translates plain-English notes in `data/candidate_notes.md` into employer-scoped STAR achievements in `data/master_knowledge_bank.json` (skipping `Learning Roadmap` sections). | None |
| `python main.py session` | Inspects or exports portable Playwright authentication cookies (`storage_state.json`). | `status`, `export` |
| `python main.py test` | Executes the Standardized Multi-Tier Regression Suite (70 Tier 1 Core gates). | `--tier [core|autofill|all]`, `--live` |
| `python main.py lint` | Runs Ruff auto-fix linter and formatter across all 174+ Python files in `<1s`. | None |

---

## 3. Configuration Reference

### `config.yaml` (Discovery, Sniper Windows & Rate Pacer)
```yaml
search_profiles:
  - keywords: '"Senior SDET" OR "Sr. SDET" OR "Lead QA" OR "Staff SDET" OR "SDET II"'
    location: "Bengaluru, Karnataka, India"
    distance: 25
    time_posted: "past_week" # Supports Sniper filters: past_1h, past_3h, past_6h, past_24h, past_week
    sort_by: "relevance"     # Options: relevance | date
    easy_apply_only: false
    recommendation_collections: ["recommended", "top-applicant", "still-hiring"]

llm:
  provider: "hybrid"
  primary_model: "models/gemini-flash-lite-latest"
  temperature: 0.0

safety_governor:
  daily_limit: 200
```

### `data/profile/allowed_tools_whitelist.json` (Evidence-Gated Whitelist & Learning Roadmap)
Generated deterministically via `python main.py resume sync` from `Manjunath_HK_Master_Resume.json`:
```json
{
  "allowed_tools": [
    "java", "python", "javascript", "sql",
    "selenium", "playwright", "appium", "rest assured", "ekam",
    "docker", "kubernetes", "k8s", "kafka", "dynatrace", "kibana",
    "testng", "pytest", "cucumber", "bdd", "jenkins", "harness", "teamcity", "github actions", "git"
  ],
  "learning_roadmap": [
    "typescript", "wiremock", "pact", "deepeval", "ragas", "promptfoo", "garak", "pyrit", "langsmith", "langfuse"
  ],
  "disallowed_hallucinations": [
    "cypress", "golang", "go", "rust", "ruby", "c#", ".net", "tosca", "katalon", "webdriverio"
  ]
}
```
*(Note: Each tool in `allowed_tools` is mapped in `tool_evidence` to the exact employer or project boundaries where the master resume evidences it. Tools in `learning_roadmap` are blocked everywhere until added to `Manjunath_HK_Master_Resume.json` with an experience/project bullet and synced via `python main.py resume sync`).*

---

## 4. Operational Playbooks

### Playbook A: High-Speed Batch Application Run (`/apply` — 10–15+ Apps/Hr)
1. Open `http://localhost:8000` (`Tab 1: 📋 Staging Review`) and click **Approve** on desired roles.
2. For `⭐ Dream Org` / `TIER_2_REFERRAL_SLA` roles, run `python main.py referral-scout` (or click `🤝 Generate Referral Note` in the UI) to message a verified low-key peer or shared-alumni SDET first.
3. In Antigravity chat, type **`/apply`**.
4. The agent reuses your open Chrome session over CDP Port `9222`, executes `form-batch inspect` (filling 80–90% of fields in `<6s` with `60 Days` notice, `17/27 LPA`, and `+91` dial code priority), resolves any custom questions in 1 turn via `form-batch apply` (auto-banking them into `learned_field_mappings.json`), verifies the submission screenshot (`HTTP 412` gate), and marks the job `applied` in SQLite.

### Playbook B: Continuous Improvement Telemetry Audit
After a batch application session, review performance metrics and promote any recurring custom questions:
```bash
./venv/bin/python main.py autofill --audit
```

---

## 5. Troubleshooting & FAQ

* **Issue: Browser Profile Collision (`Opening in existing browser session`)**
  * *How it is handled automatically:* Do **not** run `pkill -f "Google Chrome"` (which would close your personal browser). `src/browser/cdp_stealth.py` automatically detects active Chrome on CDP Port `9222` and attaches via `connect_over_cdp`. If `.browser_data/` has a stale lock from a killed process, remove `.browser_data/Singleton*` locks while keeping Chrome open.
* **Issue: `HTTP 412 Precondition Failed` when marking a job applied**
  * *Explanation:* `SubmissionVerifier` blocked a premature `mark-applied` call because no `SUBMISSION_CONFIRMED` event or confirmation screenshot was found in `data/logs/screenshots/`. Complete the submission in Chrome first (or pass `?force=true` for manual human overrides).
