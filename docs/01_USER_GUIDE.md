# To the User: The Plain-English System Guide & Copilot Manual

> **Welcome!** If you want to understand how this system works, how it maximizes **interviews** (not just blind applications), how to use it every day, and how to customize it without getting buried in technical jargon, this document was written specifically for you.
>
> 🚀 **Quick Reference:** For day-to-day commands, daemon checks, and troubleshooting, see the [Production Operations & Daily Workflow Guide](PRODUCTION_OPERATIONS_GUIDE.md).

---

## 1. What is This System in Plain English?

Think of this software as your **Personal Senior SDET Interview Generation & Application Engine**.

Applying to 100+ jobs manually is exhausting—and applying blindly to 3-week-old postings rarely lands interviews. This system is engineered around two goals: **getting you to the front of the recruiter queue** (via `<24h` first-applicant sniping and low-key employee referrals) and **eliminating repetitive form-filling** (10–15+ applications/hour):

1. **3-Track Discovery Radar:** It scans **56+ Enterprise Career Portals** (Workday, Greenhouse, Lever, Ashby), **5 LinkedIn Job Channels** (including `<24h` fresh drops and company job tabs), and **Organic Hiring Posts** written by Engineering Managers and SDET peers.
2. **3-Tier Interview Routing (`InterviewRouter`):** Every discovered job is automatically classified into the highest-converting path:
   * **`TIER_0_POST_AUTHOR`:** Direct warm outreach to the hiring manager or engineer who posted about the role.
   * **`TIER_1_SNIPER_APPLY`:** Fresh `<24h` postings routed for immediate application so you land in the first 25 resumes reviewed.
   * **`TIER_2_REFERRAL_SLA`:** Dream Enterprise / Workday roles held for a **36-hour referral outreach window** (so an internal employee can refer you *before* your email is locked in their ATS), using our **Low-Key High-Responder Scorer** that rejects `>3,000` follower LinkedIn influencers and `"Ex-<Company>"` former employees in favor of 1st-degree connections and shared-alumni (`Dunzo`, `Value Labs`, `Tata Elxsi`, `SJCE`) peers.
3. **Strict "Lie Detector" & Company Boundary Lock:** It tailors your resume using your real achievements (`data/master_knowledge_bank.json`). Modern architecture tools (`Playwright`, `TypeScript`, `Docker`, `Kubernetes`, `Kafka`, `Pact`, `WireMock`) are strictly scoped to your `Technical Projects` boundary and **never** leak into your historical employer blocks (`Value Labs`, `Dunzo`, `Tata Elxsi`). Unverified tools (`Cypress`, `Golang`) are 100% blocked.
4. **4-Tab Local Command Center (`http://localhost:8000`):** Review staged jobs, compare Base vs. Tailored PDFs side-by-side, generate 1-click referral notes, inspect social hiring leads, and track your applied history.
5. **High-Speed 2-Phase Batch Autofill (`/apply` & `form-batch`):** Populates 80–90% of standard and screening fields in `<5 seconds` (strictly enforcing `60 Days` notice period, `17 LPA` current CTC, `27 LPA` expected CTC, and `India (+91)` while blocking `"British Indian Ocean Territory (+246)"`), auto-learns any new custom questions you answer, and verifies submission screenshots before marking a job applied (HTTP 412 guard).

---

## 2. The End-to-End Lifecycle

```text
[Candidate Notes & Profile] ──> [3-Track Discovery: ATS + LinkedIn Sniper + Social Posts]
                                                   │
                                                   ▼
                                [Senior SDET & Jurisdiction Filter]
                                (5–12 yrs exp, Bengaluru / India Remote / Global 44ADA)
                                                   │
                                                   ▼
                                [Grounded STAR Tailoring + Boundary Gate]
                                                   │
                                                   ▼
                                [3-Tier InterviewRouter Classification]
                                ├── TIER_0: Hiring Post Author Outreach
                                ├── TIER_1: <24h First-Applicant Sniper Apply
                                └── TIER_2: 36h Dream Org Low-Key Referral Hold
                                                   │
                                                   ▼
                                [4-Tab Command Center (localhost:8000)]
                                                   │
                                                   ▼
                                [2-Phase Batch Autofill (/apply & form-batch)]
                                                   │
                                                   ▼
                                [HTTP 412 Screenshot & Log Verification Gate]
                                                   │
                                                   ▼
                                [Tracked in SQLite + Queue Auto-Purged]
```

### The 4 Tabs of Your Command Center (`http://localhost:8000`)
* **📋 Tab 1 — Staging Review:** Inspect fresh matches with `⭐ Dream Org` badges, side-by-side Base vs. Tailored PDF preview, `🤝 Generate Referral Note` modal, and 1-click **Approve** or **Reject**.
* **🚀 Tab 2 — Ready to Apply:** View approved jobs with compiled `Manjunath_HK_<Company>_<ID>_Resume.pdf` files. Trigger `🚀 Launch Copilot` from the UI or type **`/apply`** in Antigravity chat to batch-process the queue.
* **📊 Tab 3 — Applied Tracking:** Your permanent SQLite audit ledger (`66+` applications tracked) with direct job links and permanent re-seed protection.
* **📢 Tab 4 — Posts & Leads:** Organic LinkedIn posts from Engineering Managers, QA Leads, and recruiters actively hiring SDETs, complete with 1-click connection notes ($\le 300$ chars), InMail pitches ($\le 1000$ chars), and `mailto:` triggers.

---

## 3. Your Daily Commands

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Check morning daemon & system health
python main.py daily audit
python main.py daily diagnose

# 3. Launch Command Center UI (http://localhost:8000)
python main.py dashboard

# 4. Scout verified low-key referral leads for approved Dream Org roles
python main.py referral-scout

# 5. Run 2-Phase High-Speed Batch Form Inspection / Fill on an open ATS tab
python main.py form-batch inspect --job-id <job_id>
python main.py form-batch apply --job-id <job_id> --actions '{"agy_field_8": "Yes"}'

# 6. Audit autofill telemetry benchmarks & recurring unmapped questions
python main.py autofill --audit
```

*(Or simply type **`/apply`** in the Antigravity chat window after approving jobs in the Command Center!)*

---

## 4. How to Customize the System

1. **Candidate Ground Truth (`Notice Period: 60 Days`, `17 LPA` / `27 LPA`, Contact Info):**
   * Edit [`data/profile/candidate_master_data.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/profile/candidate_master_data.json) (gitignored for privacy) and [`data/resume_profile.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/resume_profile.json).
2. **Search Keywords, Sort Mode & Sub-24h Sniper Window:**
   * Edit [`config.yaml`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/config.yaml) (`time_posted: "past_24h"` or `"past_week"`, `sort_by: "relevance"`, `recommendation_collections`).
3. **Allowed Tools Whitelist & Hallucination Blocks:**
   * Edit [`data/profile/allowed_tools_whitelist.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/profile/allowed_tools_whitelist.json).
4. **Target Enterprises & Dream Org Tags (56+ Companies):**
   * Edit [`data/config/target_companies.json`](file:///Users/yeshwinmanjunath/development/linkedinjobsearchautomation/data/config/target_companies.json).

---

## 5. Account Safety & Anti-Detection FAQ

* **Q: Will LinkedIn ban my account?**
  * **A: No.** It attaches seamlessly over CDP Port `9222` to your real macOS Google Chrome session (`.browser_data/`), preserving authentic cookies, TLS fingerprints, and humanized Bézier mouse movements.
* **Q: Can a job be falsely marked as "Applied" if submission failed?**
  * **A: Never.** `POST /api/tracking/mark-applied/{job_id}` is guarded by `SubmissionVerifier` (Gate 80), which returns `HTTP 412 Precondition Failed` unless a verified `SUBMISSION_CONFIRMED` event and confirmation screenshot exist in `data/logs/screenshots/`.
* **Q: How much does this cost to run?**
  * **A: Exactly \$0.00.** It uses rate-paced Google Gemini Flash free tier (`4.0s` pacer + `25s` socket timeout + `60s` cooldown circuit breaker) with automatic offline fallback to local Ollama (`qwen2.5:7b`), plus free Gmail SMTP SSL for morning executive briefings.
