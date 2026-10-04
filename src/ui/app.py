from __future__ import annotations

import json
import os
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="User Approval Gate")


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "data"))
PENDING_DIR = os.path.join(DATA_DIR, "pending_queue")
APPROVED_DIR = os.path.join(DATA_DIR, "approved_queue")
RESUMES_DIR = os.path.join(DATA_DIR, "resumes")
MASTER_PROFILE_PATH = os.path.join(DATA_DIR, "resume_profile.json")
CANDIDATE_DATA_PATH = os.path.join(DATA_DIR, "profile", "candidate_master_data.json")
STANDARD_PDF_PATH = os.path.join(RESUMES_DIR, "Manjunath_HK_Standard_Resume.pdf")

os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(APPROVED_DIR, exist_ok=True)
os.makedirs(RESUMES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


async def get_or_create_standard_pdf() -> str:
    """Compiles and caches the candidate's canonical base resume PDF."""
    from src.pdf_engine.generator import PDFGenerator
    from src.resume_store.models import ResumeProfile

    need_generate = False
    if (
        not os.path.exists(STANDARD_PDF_PATH)
        or os.path.exists(MASTER_PROFILE_PATH)
        and (os.path.getmtime(MASTER_PROFILE_PATH) > os.path.getmtime(STANDARD_PDF_PATH))
    ):
        need_generate = True

    if need_generate:
        with open(MASTER_PROFILE_PATH, "r", encoding="utf-8") as f:
            std_data = json.load(f)
        profile = ResumeProfile(**std_data)
        generator = PDFGenerator()
        await generator.generate_pdf_async(profile, STANDARD_PDF_PATH)

    return STANDARD_PDF_PATH


def get_candidate_name_slug(payload: dict | None = None) -> str:
    """Extracts a clean, professional candidate name slug (e.g., 'Manjunath_HK')."""
    if payload:
        name = payload.get("tailored_resume", {}).get("personal_details", {}).get("full_name")
        if name and name.strip():
            parts = name.strip().split()
            if len(parts) > 1:
                first = re.sub(r"[^a-zA-Z0-9]", "", parts[0])
                rest = "".join(re.sub(r"[^a-zA-Z0-9]", "", p) for p in parts[1:])
                return f"{first}_{rest}"
            return re.sub(r"[^a-zA-Z0-9]", "", name)

    if os.path.exists(CANDIDATE_DATA_PATH):
        try:
            with open(CANDIDATE_DATA_PATH, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            personal = cdata.get("personal", {})
            first = personal.get("first_name", "").strip()
            last = personal.get("last_name", "").strip()
            if first and last:
                clean_first = re.sub(r"[^a-zA-Z0-9]", "", first)
                clean_last = re.sub(r"[^a-zA-Z0-9]", "", last)
                return f"{clean_first}_{clean_last}"
            full = personal.get("full_name", "").strip()
            if full:
                parts = full.split()
                if len(parts) > 1:
                    first = re.sub(r"[^a-zA-Z0-9]", "", parts[0])
                    rest = "".join(re.sub(r"[^a-zA-Z0-9]", "", p) for p in parts[1:])
                    return f"{first}_{rest}"
                return re.sub(r"[^a-zA-Z0-9]", "", full)
        except Exception:
            pass

    return "Manjunath_HK"


def extract_company_slug(job_id: str, payload: dict | None = None) -> str:
    """Extracts a clean company name slug (e.g. 'Coinbase', 'Zapier', 'Spotify')."""
    if payload:
        comp = payload.get("job_details", {}).get("company", "").strip()
        if comp and comp.lower() not in ("unknown", "unknown company"):
            clean = re.sub(r"[^a-zA-Z0-9]+", "_", comp).strip("_")
            return clean

    tokens = job_id.split("_")
    if len(tokens) >= 3 and tokens[0].lower() in ("greenhouse", "lever", "ashby", "workday"):
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", tokens[1]).strip("_")
        return clean.capitalize()
    return "Company"


def extract_job_token(job_id: str) -> str:
    """Extracts a clean, short job token (e.g. '8095207' or first 8 chars of uuid)."""
    tokens = job_id.split("_")
    raw_token = tokens[-1] if tokens else job_id
    clean = re.sub(r"[^a-zA-Z0-9]", "", raw_token)
    if len(clean) > 8:
        return clean[:8]
    return clean or "ref"


def generate_professional_resume_filename(job_id: str, payload: dict | None = None) -> str:
    """Generates standard recruiter-friendly resume filename e.g. Manjunath_HK_Coinbase_8095207_Resume.pdf."""
    cand = get_candidate_name_slug(payload)
    comp = extract_company_slug(job_id, payload)
    tok = extract_job_token(job_id)
    return f"{cand}_{comp}_{tok}_Resume.pdf"


def resolve_job_pdf_path(job_id: str, payload: dict | None = None) -> tuple[str, str]:
    """
    Resolves the actual PDF path and display filename on disk for a job.
    Supports both professional candidate-named resumes and legacy {job_id}_resume.pdf.
    Returns (pdf_path, pdf_filename).
    """
    # 1. If payload contains an existing generated_pdf_path that exists on disk, use it
    if payload and payload.get("generated_pdf_path"):
        gen_path = payload["generated_pdf_path"]
        if os.path.exists(gen_path):
            return gen_path, os.path.basename(gen_path)

    # 2. Check if approved JSON file has generated_pdf_path
    approved_json = os.path.join(APPROVED_DIR, f"{job_id}.json")
    if os.path.exists(approved_json):
        try:
            with open(approved_json, "r", encoding="utf-8") as f:
                saved_payload = json.load(f)
            saved_pdf = saved_payload.get("generated_pdf_path")
            if saved_pdf and os.path.exists(saved_pdf):
                return saved_pdf, os.path.basename(saved_pdf)
        except Exception:
            pass

    # 3. Check for modern candidate-named resume file in APPROVED_DIR
    target_filename = generate_professional_resume_filename(job_id, payload)
    target_path = os.path.join(APPROVED_DIR, target_filename)
    if os.path.exists(target_path):
        return target_path, target_filename

    # 4. Check for pattern match in APPROVED_DIR using the job token
    token = extract_job_token(job_id)
    if os.path.exists(APPROVED_DIR):
        for fname in os.listdir(APPROVED_DIR):
            if fname.endswith(".pdf") and token in fname:
                found_path = os.path.join(APPROVED_DIR, fname)
                return found_path, fname

    # 5. Fallback to legacy path for backward compatibility
    legacy_filename = f"{job_id}_resume.pdf"
    legacy_path = os.path.join(APPROVED_DIR, legacy_filename)
    return legacy_path, legacy_filename


def extract_job_experience(text: str) -> str:
    """Extracts required experience in years (e.g. '5+ years' or '6–8 years')."""
    if not text:
        return "Not specified"
    context_keywords = [
        "exp",
        "experience",
        "testing",
        "sdet",
        "automation",
        "background",
        "working",
        "quality",
        "qa",
        "relevant",
        "required",
        "preferred",
        "qualification",
    ]
    years = []
    for m in re.finditer(r"(\d+)(?:\s*(?:\+|-\s*(\d+)|to\s*(\d+)))?\s*years?", text, re.IGNORECASE):
        start_idx = max(0, m.start() - 40)
        end_idx = min(len(text), m.end() + 40)
        snippet = text[start_idx:end_idx].lower()

        if any(kw in snippet for kw in context_keywords):
            val1 = int(m.group(1))
            val2 = int(m.group(2) or m.group(3)) if (m.group(2) or m.group(3)) else None
            if 0 < val1 < 30:
                if val2 and 0 < val2 < 30:
                    years.append(f"{min(val1, val2)}–{max(val1, val2)} years")
                else:
                    years.append(f"{val1}+ years")

    if years:
        return years[0]
    return "Not specified"


def classify_job_location(location: str, description: str = "") -> dict:
    """Classifies job location to detect US-only or non-India geographic restrictions vs India eligibility."""
    loc_clean = (location or "").strip()
    loc_lower = loc_clean.lower()
    desc_lower = description.lower() if description else ""

    # 1. India / Bengaluru check
    india_terms = [
        "bengaluru",
        "bangalore",
        "india",
        "karnataka",
        "mumbai",
        "delhi",
        "gurgaon",
        "hyderabad",
        "pune",
        "chennai",
    ]
    if any(term in loc_lower for term in india_terms):
        return {
            "location_text": loc_clean or "Bengaluru, India",
            "is_us_only": False,
            "is_india": True,
            "badge_type": "success",
            "badge_label": "🇮🇳 Bengaluru / India Eligible",
        }

    # 2. Explicit US-Only / North America / Non-India check
    us_terms = [
        "usa",
        "united states",
        "u.s.",
        "remote - usa",
        "remote - us",
        "us remote",
        "usa remote",
        "san francisco",
        "new york",
        "seattle",
        "austin",
        "chicago",
        "california",
        "texas",
        "washington",
        "ny",
        "ca",
        "canada",
        "toronto",
        "vancouver",
        "uk",
        "united kingdom",
        "london",
        "europe",
        "emea",
    ]
    is_us = any(re.search(rf"\b{re.escape(term)}\b", loc_lower) for term in us_terms)

    # Check description for US-only restrictions if location is ambiguous
    if not is_us and (
        "only open to candidates in the us" in desc_lower
        or "must be located in the united states" in desc_lower
        or "authorized to work in the us without sponsorship" in desc_lower
    ):
        is_us = True

    if is_us:
        return {
            "location_text": loc_clean or "US / Non-India Location",
            "is_us_only": True,
            "is_india": False,
            "badge_type": "warning",
            "badge_label": "⚠️ US / Non-India Location",
        }

    # 3. Global / Worldwide Remote
    if "worldwide" in loc_lower or "anywhere" in loc_lower or "global" in loc_lower:
        return {
            "location_text": loc_clean or "Worldwide Remote",
            "is_us_only": False,
            "is_india": True,
            "badge_type": "info",
            "badge_label": "🌐 Worldwide Remote Eligible",
        }

    # Default Remote or unverified location
    if "remote" in loc_lower:
        return {
            "location_text": loc_clean,
            "is_us_only": False,
            "is_india": False,
            "badge_type": "neutral",
            "badge_label": "📍 Remote (Check Eligibility)",
        }

    return {
        "location_text": loc_clean or "Not specified",
        "is_us_only": False,
        "is_india": False,
        "badge_type": "neutral",
        "badge_label": f"📍 {loc_clean}" if loc_clean else "📍 Location Not Specified",
    }


def extract_salary_estimate(job_details: dict) -> str:
    """Extracts salary range from job details or description text."""
    if not isinstance(job_details, dict):
        return "Competitive"
    if job_details.get("salary_range"):
        return str(job_details["salary_range"])

    desc = job_details.get("description") or job_details.get("requirements") or ""
    m = re.search(
        r"(\$\s*[\d,]+(?:\s*[kK])?\s*(?:—|-|to)\s*\$\s*[\d,]+(?:\s*[kK])?(?:\s*(?:USD|CAD))?)",
        desc,
    )
    if m:
        return m.group(1).strip()
    m_inr = re.search(
        r"((?:₹|INR)\s*[\d,]+(?:\s*(?:L|LPA))?\s*(?:—|-|to)\s*(?:₹|INR)?\s*[\d,]+(?:\s*(?:L|LPA))?)",
        desc,
    )
    if m_inr:
        return m_inr.group(1).strip()

    return "Competitive"


def compute_resume_diff(payload: dict, master_profile: dict) -> dict:
    """Injects is_tailored diff flags into payload experience history achievements."""
    master_exp_map = {}
    for m_exp in master_profile.get("experience_history", []):
        company_norm = m_exp.get("company", "").strip().lower()
        role_norm = m_exp.get("role", "").strip().lower()
        master_exp_map[(company_norm, role_norm)] = m_exp.get("achievements", [])

    tailored_resume = payload.get("tailored_resume", {})
    for exp in tailored_resume.get("experience_history", []):
        c_norm = exp.get("company", "").strip().lower()
        r_norm = exp.get("role", "").strip().lower()

        base_bullets = []
        for (m_c, _m_r), bullets in master_exp_map.items():
            if m_c in c_norm or c_norm in m_c or r_norm in _m_r or _m_r in r_norm:
                base_bullets = bullets
                break

        achievements = exp.get("achievements", [])
        diff_bullets = []
        for idx, ach in enumerate(achievements):
            is_tailored = ach not in base_bullets
            diff_bullets.append({"text": ach, "is_tailored": is_tailored})
        exp["achievements_diff"] = diff_bullets

    return payload


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/pending-jobs")
async def get_pending_jobs():
    master_profile = {}
    if os.path.exists(MASTER_PROFILE_PATH):
        try:
            with open(MASTER_PROFILE_PATH, "r") as f:
                master_profile = json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading master profile: {e}")

    # Lazy-init tailorer only if needed
    _tailorer = None

    def get_tailorer():
        nonlocal _tailorer
        if _tailorer is None:
            from src.tailor.resume_tailorer import ResumeTailorer

            _tailorer = ResumeTailorer(use_ai=False)
        return _tailorer

    jobs = []
    if os.path.exists(PENDING_DIR):
        for filename in os.listdir(PENDING_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(PENDING_DIR, filename)
                try:
                    with open(file_path, "r") as f:
                        raw_payload = json.load(f)

                    # On-demand tailoring fallback: if tailored_resume is missing, tailor now
                    if "tailored_resume" not in raw_payload:
                        jd = raw_payload.get("job_details", {})
                        # Ensure requirements text exists for keyword matching
                        if not jd.get("requirements") and jd.get("description"):
                            clean = re.sub(r"<[^>]+>", " ", jd["description"])
                            clean = (
                                clean.replace("&amp;", "&")
                                .replace("&nbsp;", " ")
                                .replace("&lt;", "<")
                                .replace("&gt;", ">")
                            )
                            clean = re.sub(r"\s+", " ", clean).strip()
                            jd["requirements"] = clean[:2000]

                        tailorer = get_tailorer()
                        raw_payload = tailorer.tailor_job_payload(raw_payload)

                        # Persist back so we don't re-tailor on every refresh
                        with open(file_path, "w") as fw:
                            json.dump(raw_payload, fw, indent=2)

                    diff_payload = compute_resume_diff(raw_payload, master_profile)

                    # Enrich metadata for upfront review
                    jd = raw_payload.get("job_details", {})
                    req_text = jd.get("requirements") or jd.get("description") or ""

                    diff_payload["experience_required"] = extract_job_experience(req_text)
                    diff_payload["location_info"] = classify_job_location(
                        jd.get("location", ""), jd.get("description", "")
                    )
                    diff_payload["salary_estimate"] = extract_salary_estimate(jd)
                    diff_payload["direct_link"] = raw_payload.get("url") or raw_payload.get("job_url") or ""
                    diff_payload["source_platform"] = raw_payload.get("source", "ATS").upper()
                    diff_payload["standard_resume"] = master_profile
                    diff_payload["standard_pdf_url"] = "/api/pdf/standard"
                    diff_payload["preview_pdf_url"] = f"/api/pdf/preview/{raw_payload.get('job_id')}"

                    jobs.append(diff_payload)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")

    approved_count = 0
    if os.path.exists(APPROVED_DIR):
        approved_count = len(
            [f for f in os.listdir(APPROVED_DIR) if f.endswith(".json") and not f.endswith("_resume.json")]
        )
    return {"jobs": jobs, "approved_count": approved_count}


def coerce_easy_apply_answers(ea: dict) -> dict:
    """Gracefully coerces easy apply form field inputs to expected types."""
    if not isinstance(ea, dict):
        return {}
    res = dict(ea)

    # Int fields (salary bounds)
    for int_field in ["salary_expectations_min", "salary_expectations_max"]:
        val = res.get(int_field)
        if val is None or val == "":
            res[int_field] = None
        else:
            try:
                res[int_field] = int(val)
            except (ValueError, TypeError):
                res[int_field] = None

    # Non-nullable string fields
    for str_field in ["notice_period", "current_location", "salary_currency"]:
        val = res.get(str_field)
        if val is None:
            res[str_field] = ""
        else:
            res[str_field] = str(val).strip()

    # Nullable string fields
    for opt_str_field in [
        "start_date_available",
        "clearance_level",
        "highest_education_level",
        "gender",
        "race_ethnicity",
        "veteran_status",
        "disability_status",
        "cover_letter_default",
    ]:
        val = res.get(opt_str_field)
        if val is not None:
            val_str = str(val).strip()
            res[opt_str_field] = val_str if val_str != "" else None

    # Boolean fields
    for bool_field in ["sponsorship_needed", "willing_to_relocate"]:
        val = res.get(bool_field)
        if isinstance(val, str):
            res[bool_field] = val.lower() in ("true", "1", "yes")
        elif val is not None:
            res[bool_field] = bool(val)

    # Work preference enum
    from src.resume_store.models import WorkPreference

    wp = res.get("work_preference")
    if isinstance(wp, str):
        try:
            res["work_preference"] = WorkPreference(wp.lower())
        except ValueError:
            res["work_preference"] = WorkPreference.FLEXIBLE

    return res


@app.post("/api/approve/{job_id}")
async def approve_job(job_id: str, payload: dict):
    from src.pdf_engine.generator import PDFGenerator
    from src.resume_store.models import ResumeProfile

    approved_path = os.path.join(APPROVED_DIR, f"{job_id}.json")
    try:
        resume_choice = payload.get("resume_choice", "tailored").lower()
        if resume_choice not in ["tailored", "standard"]:
            resume_choice = "tailored"

        print(f"Approving job {job_id} using '{resume_choice}' resume...")

        generator = PDFGenerator()
        pdf_filename = generate_professional_resume_filename(job_id, payload)
        pdf_path = os.path.join(APPROVED_DIR, pdf_filename)

        if resume_choice == "standard":
            with open(MASTER_PROFILE_PATH, "r", encoding="utf-8") as f:
                std_data = json.load(f)
            profile = ResumeProfile(**std_data)
            payload["chosen_resume_version"] = "standard"
            payload["approved_resume"] = std_data
        else:
            tailored_resume = payload.get("tailored_resume", {})
            if "easy_apply_answers" in tailored_resume:
                tailored_resume["easy_apply_answers"] = coerce_easy_apply_answers(tailored_resume["easy_apply_answers"])
            profile = ResumeProfile(**tailored_resume)
            payload["chosen_resume_version"] = "tailored"
            payload["approved_resume"] = tailored_resume

        await generator.generate_pdf_async(profile, pdf_path)
        payload["generated_pdf_path"] = pdf_path
        print(f"PDF generated at {pdf_path} (version: {payload['chosen_resume_version']})")

        with open(approved_path, "w") as f:
            json.dump(payload, f, indent=2)

        # Cleanly remove from pending queue once approved
        pending_path = os.path.join(PENDING_DIR, f"{job_id}.json")
        if os.path.exists(pending_path):
            os.remove(pending_path)

        return {
            "status": "success",
            "message": f"Job {job_id} approved with {payload['chosen_resume_version']} resume.",
            "path": approved_path,
            "pdf_path": payload.get("generated_pdf_path"),
            "chosen_resume_version": payload.get("chosen_resume_version", "tailored"),
        }
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/reject/{job_id}")
async def reject_job(job_id: str):
    pending_path = os.path.join(PENDING_DIR, f"{job_id}.json")
    if os.path.exists(pending_path):
        os.remove(pending_path)
    return {"status": "success", "message": f"Job {job_id} rejected."}


@app.post("/api/autofill/{job_id}")
async def autofill_job(job_id: str):
    from src.autofill.ats_filler import ATSAssistedFiller
    from src.autofill.governor import ApplicationGovernor
    from src.autofill.linkedin_filler import LinkedInAssistedFiller
    from src.storage.database import ApplicationDatabase

    # Enforce daily budget governor (≤200 applications/day)
    governor = ApplicationGovernor()
    budget = governor.check_budget()
    if not budget["allowed"]:
        raise HTTPException(status_code=429, detail=budget["message"])

    pending_file = os.path.join(PENDING_DIR, f"{job_id}.json")
    approved_file = os.path.join(APPROVED_DIR, f"{job_id}.json")
    target_file = pending_file if os.path.exists(pending_file) else approved_file

    if not os.path.exists(target_file):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found in queues")

    with open(target_file, "r", encoding="utf-8") as f:
        job_data = json.load(f)

    job_url = job_data.get("url") or job_data.get("job_url") or f"https://www.linkedin.com/jobs/view/{job_id}/"
    app_type = job_data.get("application_type", "EASY_APPLY")
    pdf_path, _ = resolve_job_pdf_path(job_id, job_data)

    company_name = job_data.get("job_details", {}).get("company", "")
    external_url = job_data.get("job_details", {}).get("external_url")

    # Routing logic:
    # 1. Direct external ATS link or ATS application type
    if ("ATS" in str(app_type) and "LINKEDIN" not in str(app_type)) or any(
        ats in job_url.lower() for ats in ["greenhouse", "lever", "ashby", "myworkdayjobs", "coinbase", "databricks"]
    ):
        ats_filler = ATSAssistedFiller(headless=False)
        result = await ats_filler.autofill_ats_application(job_url, pdf_path, company=company_name)
    # 2. LinkedIn External Apply (navigates to LinkedIn, clicks external apply, captures ATS popup)
    elif app_type == "LINKEDIN_EXTERNAL" or (app_type != "EASY_APPLY" and "linkedin.com" in job_url.lower()):
        ats_filler = ATSAssistedFiller(headless=False)
        if external_url and external_url.startswith("http"):
            result = await ats_filler.autofill_ats_application(external_url, pdf_path, company=company_name)
        else:
            result = await ats_filler.autofill_linkedin_external(job_url, pdf_path, company=company_name)
    # 3. LinkedIn Easy Apply
    else:
        li_filler = LinkedInAssistedFiller(headless=False)
        result = await li_filler.autofill_easy_apply(job_url, pdf_path)

    # Record application audit event
    if result.get("status") in ("ready_for_review", "applied", "success"):
        db = ApplicationDatabase()
        job_details = job_data.get("job_details", {})
        db.record_application(
            job_id=job_id,
            source=job_data.get("source", "linkedin"),
            company_name=job_details.get("company", "Unknown"),
            job_title=job_details.get("title", "Unknown"),
            job_url=job_url,
            resume_path=pdf_path or "",
            tailored_data=job_data.get("tailored_resume", {}),
            status="assisted_autofilled",
        )

    fields_n = result.get("fields_filled", 0)
    resume_ok = result.get("resume_attached", False)
    attach_str = "with PDF resume attached" if resume_ok else ""
    return {
        "status": "success",
        "result": result,
        "remaining_today": budget["remaining"] - 1,
        "message": f"Copilot active for {company_name or job_id}: {fields_n} fields pre-filled {attach_str}. Review in Chrome.",
    }


@app.get("/api/approved-jobs")
async def get_approved_jobs():
    from src.autofill.governor import ApplicationGovernor

    governor = ApplicationGovernor()
    budget = governor.check_budget()
    budget["used_today"] = budget.get("current_count", 0)

    approved_jobs = []
    if os.path.exists(APPROVED_DIR):
        files = [f for f in os.listdir(APPROVED_DIR) if f.endswith(".json") and not f.endswith("_resume.json")]
        # Sort by file mtime descending (most recently approved first)
        files.sort(key=lambda f: os.path.getmtime(os.path.join(APPROVED_DIR, f)), reverse=True)

        for filename in files:
            file_path = os.path.join(APPROVED_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                job_id = payload.get("job_id", filename.replace(".json", ""))
                jd = payload.get("job_details", {})
                pdf_path, pdf_filename = resolve_job_pdf_path(job_id, payload)

                approved_jobs.append(
                    {
                        "job_id": job_id,
                        "company": jd.get("company", "Unknown Company"),
                        "title": jd.get("title", "Unknown Role"),
                        "location": jd.get("location", "Not specified"),
                        "source": payload.get("source", "ATS"),
                        "application_type": payload.get("application_type", "ATS"),
                        "job_url": payload.get("url") or payload.get("job_url", ""),
                        "matched_keywords": payload.get("matched_keywords", []),
                        "has_pdf": os.path.exists(pdf_path),
                        "pdf_filename": pdf_filename,
                        "approved_at": os.path.getmtime(file_path),
                    }
                )
            except Exception as e:
                print(f"Error reading approved job {filename}: {e}")

    return {
        "jobs": approved_jobs,
        "total_approved": len(approved_jobs),
        "budget": budget,
    }


@app.get("/api/pdf/standard")
async def get_standard_pdf():
    """Serves the compiled Standard Base Resume PDF from candidate canonical profile."""
    pdf_path = await get_or_create_standard_pdf()
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Standard resume PDF could not be generated")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename="Manjunath_HK_Standard_Resume.pdf",
    )


@app.get("/api/pdf/preview/{job_id}")
async def get_preview_pdf(job_id: str, version: str = "tailored"):
    """Generates and serves a live preview PDF (tailored or standard) for a job."""
    if version.lower() == "standard":
        return await get_standard_pdf()

    # Look for job payload in pending_queue first, then approved_queue
    pending_file = os.path.join(PENDING_DIR, f"{job_id}.json")
    approved_file = os.path.join(APPROVED_DIR, f"{job_id}.json")
    target_file = pending_file if os.path.exists(pending_file) else approved_file

    if not os.path.exists(target_file):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found for preview")

    with open(target_file, "r", encoding="utf-8") as f:
        job_data = json.load(f)

    tailored_resume = job_data.get("tailored_resume")
    if not tailored_resume:
        raise HTTPException(status_code=400, detail="Tailored resume not found in job payload")

    from src.pdf_engine.generator import PDFGenerator
    from src.resume_store.models import ResumeProfile

    preview_path = os.path.join(RESUMES_DIR, f"preview_{job_id}_tailored.pdf")

    # Re-generate if not cached or if job file was updated
    need_gen = not os.path.exists(preview_path) or (os.path.getmtime(target_file) > os.path.getmtime(preview_path))
    if need_gen:
        t_copy = dict(tailored_resume)
        if "easy_apply_answers" in t_copy:
            t_copy["easy_apply_answers"] = coerce_easy_apply_answers(t_copy["easy_apply_answers"])
        profile = ResumeProfile(**t_copy)
        generator = PDFGenerator()
        await generator.generate_pdf_async(profile, preview_path)

    return FileResponse(
        path=preview_path,
        media_type="application/pdf",
        filename=f"Manjunath_HK_Preview_{job_id}_Tailored_Resume.pdf",
    )


@app.get("/api/pdf/{job_id}")
async def get_job_pdf(job_id: str):
    pdf_path, pdf_filename = resolve_job_pdf_path(job_id)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Resume PDF not found for this job")

    tokens = pdf_filename.split("_")
    if len(tokens) >= 5 and tokens[-1].lower() == "resume.pdf":
        download_name = f"{tokens[0]}_{tokens[1]}_{tokens[2]}_Resume.pdf"
    else:
        download_name = pdf_filename

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_name,
    )


@app.delete("/api/approved/{job_id}")
async def delete_approved_job(job_id: str):
    json_path = os.path.join(APPROVED_DIR, f"{job_id}.json")
    pdf_path, _ = resolve_job_pdf_path(job_id)

    deleted = False
    if os.path.exists(json_path):
        os.remove(json_path)
        deleted = True
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    legacy_pdf = os.path.join(APPROVED_DIR, f"{job_id}_resume.pdf")
    if os.path.exists(legacy_pdf):
        os.remove(legacy_pdf)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found in approved queue")

    return {"status": "success", "message": f"Job {job_id} removed from approved queue."}
