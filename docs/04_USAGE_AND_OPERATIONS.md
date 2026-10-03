# Operations & Usage Manual

This manual provides an exhaustive operational reference for running, configuring, and operating the application copilot.

---

## 1. System Setup & Prerequisites

### Requirements
* **Operating System:** macOS (Apple Silicon M-series recommended) or Linux.
* **Python Runtime:** Python 3.9+ virtual environment.
* **Browser:** System Google Chrome installed (`/Applications/Google Chrome.app`).
* **AI Engine:**
  * Free Tier: Google Gemini API Key in `.env` (`GEMINI_API_KEY="..."`).
  * Local Offline (Optional): Ollama host (`brew install ollama && ollama serve`).

### Installation
```bash
# 1. Clone repository
git clone https://github.com/manjunathk833/linkedin-automator.git
cd linkedin-automator

# 2. Initialize virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Install Playwright browser dependencies
python -m playwright install chrome

# 4. Configure environment variables
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY
```

---

## 2. Command Reference

### Primary CLI Commands (`main.py`)

| Subcommand | Description | Flags / Options |
| :--- | :--- | :--- |
| `python main.py run` | Executes full one-shot automated pipeline: syncs notes $\rightarrow$ searches jobs $\rightarrow$ filters experience $\rightarrow$ launches dashboard. | `--skip-sync`: Skips notes translation.<br/>`--no-dashboard`: Runs discovery without launching UI. |
| `python main.py dashboard` | Launches the local FastAPI approval gate web interface at `http://127.0.0.1:8000`. | `--host`: Bind host (default: `127.0.0.1`).<br/>`--port`: Port number (default: `8000`). |
| `python main.py search` | Runs multi-channel LinkedIn scraper and generates tailored resume payloads into `data/pending_queue/`. | `--max-jobs`: Max jobs per channel profile. |
| `python main.py sync` | Translates plain text notes in `data/candidate_notes.md` into structured STAR achievements in `data/master_knowledge_bank.json`. | None |
| `python main.py filter` | Scans `data/pending_queue/`, purges underqualified (<4 yrs) or overqualified (>10 yrs) listings, and updates `data/processed_jobs.json`. | None |
| `python main.py apply` | Executes Easy Apply automation on approved jobs in `data/approved_queue/`. | `--dry-run`: (Default: True) Fills forms and halts.<br/>`--no-dry-run`: Live submission. |
| `python main.py login` | Launches persistent headful Chrome to log into LinkedIn manually. Session cookies are automatically saved to `.browser_data/`. | None |
| `python main.py lint` | Runs Ruff auto-fix linter and code formatter across all workspace files in <1 second. | None |

### Direct ATS Scripts (`scripts/`)

```bash
# Seed or refresh the target company registry (37+ enterprises)
python scripts/seed_companies.py

# Ingest fresh jobs from public Greenhouse, Lever, and Ashby boards
python scripts/run_ingestion.py

# Ingest and automatically queue jobs into data/pending_queue for dashboard review
python scripts/run_ingestion.py --queue
```

---

## 3. Configuration Reference

### `config.yaml` (Search Filters & Channels)
```yaml
search_profiles:
  - keywords: '"Senior SDET" OR "Lead QA" OR "Staff SDET"'
    location: "Bengaluru, Karnataka, India"
    work_types: ["remote", "hybrid"]
    experience_levels: [4] # Mid-Senior level
    max_jobs: 25

browser:
  headless: false
  slow_mo: 150
  profile_dir: ".browser_data"

ai_tailor:
  provider: "hybrid" # Options: gemini | ollama | hybrid
  model_name: "gemini-2.5-flash"
  temperature: 0.0
```

### `data/config/target_companies.json` (Direct ATS Registry)
Stores enterprise slugs for direct keyless REST ingestion:
```json
[
  {
    "name": "Stripe",
    "ats_provider": "greenhouse",
    "slug": "stripe",
    "domain": "stripe.com"
  },
  {
    "name": "Docker",
    "ats_provider": "lever",
    "slug": "docker",
    "domain": "docker.com"
  },
  {
    "name": "Linear",
    "ats_provider": "ashby",
    "slug": "linear",
    "domain": "linear.app"
  }
]
```

### `data/profile/allowed_tools_whitelist.json` (Integrity Whitelist)
Controls the deterministic verification gate:
```json
{
  "allowed_tools": [
    "java", "python", "rest assured", "selenium", "testng",
    "cucumber", "jenkins", "docker", "gcp", "azure devops"
  ],
  "disallowed_hallucinations": [
    "playwright", "cypress", "kubernetes", "golang"
  ]
}
```

---

## 4. Operational Playbooks

### Playbook A: Daily Morning Application Run
1. Ingest fresh ATS roles:
   ```bash
   python scripts/run_ingestion.py --queue
   ```
2. Open the approval dashboard:
   ```bash
   python main.py dashboard
   ```
3. Open `http://localhost:8000`:
   * **Staging Review (`📋 Staging Review`):** Review incoming candidate matches. Inspect tailored bullets, edit screening questions, and click **"Move to Approved Queue"** (or **"Approve All"**). Single-column ATS PDFs are automatically generated into `data/resumes/`.
   * **Ready to Apply (`🚀 Ready to Apply`):** Filter jobs by keyword, click **"View PDF"** to preview the compiled ATS resume in an inline modal, and click **"🚀 Launch Copilot"** on preferred jobs.
4. When the browser launches, the copilot automatically handles multi-tab/popup transitions, pre-fills candidate inputs, attaches the PDF resume, and pauses at the review modal. Verify fields and click **Submit**.

### Playbook B: Adding a New Career Achievement
1. Open `data/candidate_notes.md` and append your achievement:
   ```markdown
   * Reduced API regression execution runtime from 3 hours to 35 minutes by implementing parallel REST Assured execution threads with TestNG.
   ```
2. Synchronize your knowledge vault:
   ```bash
   python main.py sync
   ```
3. The new STAR achievement is now permanently available for resume tailoring.

---

## 5. Troubleshooting & FAQ

* **Issue: `Chrome is already running with remote debugging port`**
  * *Fix:* Close existing Chrome windows launched by the scraper or kill background instances:
    ```bash
    pkill -f "Google Chrome"
    ```
* **Issue: `Daily budget reached (15/15)`**
  * *Explanation:* To protect your account health, the rate governor locks autofill triggers after 15 applications per 24 hours. The counter automatically resets at midnight. To adjust the limit, change `DEFAULT_DAILY_LIMIT` in `src/autofill/governor.py`.
* **Issue: `Gemini API 429 Too Many Requests`**
  * *Fix:* The system automatically falls back to local Ollama (`qwen2.5:7b`). If Ollama is not running, start it via `ollama serve &` or wait 60 seconds for Gemini rate limits to clear.
