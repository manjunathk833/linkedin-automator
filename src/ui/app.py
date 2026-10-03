from __future__ import annotations

import json
import os

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
MASTER_PROFILE_PATH = os.path.join(DATA_DIR, "resume_profile.json")

os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(APPROVED_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


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
                            import re

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
        if "tailored_resume" in payload:
            print(f"Generating PDF for job {job_id}...")

            if "easy_apply_answers" in payload["tailored_resume"]:
                payload["tailored_resume"]["easy_apply_answers"] = coerce_easy_apply_answers(
                    payload["tailored_resume"]["easy_apply_answers"]
                )

            profile = ResumeProfile(**payload["tailored_resume"])
            generator = PDFGenerator()
            pdf_filename = f"{job_id}_resume.pdf"
            pdf_path = os.path.join(APPROVED_DIR, pdf_filename)

            await generator.generate_pdf_async(profile, pdf_path)

            payload["generated_pdf_path"] = pdf_path
            print(f"PDF generated at {pdf_path}")

        with open(approved_path, "w") as f:
            json.dump(payload, f, indent=2)

        # Cleanly remove from pending queue once approved
        pending_path = os.path.join(PENDING_DIR, f"{job_id}.json")
        if os.path.exists(pending_path):
            os.remove(pending_path)

        return {
            "status": "success",
            "message": f"Job {job_id} approved and saved.",
            "path": approved_path,
            "pdf_path": payload.get("generated_pdf_path"),
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
    pdf_path = job_data.get("generated_pdf_path") or os.path.join(APPROVED_DIR, f"{job_id}_resume.pdf")

    company_name = job_data.get("job_details", {}).get("company", "")
    if "ATS" in str(app_type) or "greenhouse" in job_url or "lever" in job_url or "ashby" in job_url:
        ats_filler = ATSAssistedFiller(headless=False)
        result = await ats_filler.autofill_ats_application(job_url, pdf_path, company=company_name)
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
                pdf_path = payload.get("generated_pdf_path") or os.path.join(APPROVED_DIR, f"{job_id}_resume.pdf")

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
                        "pdf_filename": f"{job_id}_resume.pdf",
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


@app.get("/api/pdf/{job_id}")
async def get_job_pdf(job_id: str):
    pdf_path = os.path.join(APPROVED_DIR, f"{job_id}_resume.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Resume PDF not found for this job")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{job_id}_resume.pdf",
    )


@app.delete("/api/approved/{job_id}")
async def delete_approved_job(job_id: str):
    json_path = os.path.join(APPROVED_DIR, f"{job_id}.json")
    pdf_path = os.path.join(APPROVED_DIR, f"{job_id}_resume.pdf")

    deleted = False
    if os.path.exists(json_path):
        os.remove(json_path)
        deleted = True
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found in approved queue")

    return {"status": "success", "message": f"Job {job_id} removed from approved queue."}
