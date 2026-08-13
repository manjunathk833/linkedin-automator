from __future__ import annotations

import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="User Approval Gate")

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

    jobs = []
    if os.path.exists(PENDING_DIR):
        for filename in os.listdir(PENDING_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(PENDING_DIR, filename)
                try:
                    with open(file_path, "r") as f:
                        raw_payload = json.load(f)
                        diff_payload = compute_resume_diff(raw_payload, master_profile)
                        jobs.append(diff_payload)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    return {"jobs": jobs}


@app.post("/api/approve/{job_id}")
async def approve_job(job_id: str, payload: dict):
    from src.pdf_engine.generator import PDFGenerator
    from src.resume_store.models import ResumeProfile

    approved_path = os.path.join(APPROVED_DIR, f"{job_id}.json")
    try:
        if "tailored_resume" in payload:
            print(f"Generating PDF for job {job_id}...")

            ea = payload["tailored_resume"].get("easy_apply_answers", {})
            if isinstance(ea, dict):
                for int_field in ["salary_expectations_min", "salary_expectations_max"]:
                    if ea.get(int_field) == "":
                        ea[int_field] = None

            profile = ResumeProfile(**payload["tailored_resume"])
            generator = PDFGenerator()
            pdf_filename = f"{job_id}_resume.pdf"
            pdf_path = os.path.join(APPROVED_DIR, pdf_filename)

            await generator.generate_pdf_async(profile, pdf_path)

            payload["generated_pdf_path"] = pdf_path
            print(f"PDF generated at {pdf_path}")

        with open(approved_path, "w") as f:
            json.dump(payload, f, indent=2)

        return {
            "status": "success",
            "message": f"Job {job_id} approved and saved.",
            "path": approved_path,
            "pdf_path": payload.get("generated_pdf_path"),
        }
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reject/{job_id}")
async def reject_job(job_id: str):
    return {"status": "success", "message": f"Job {job_id} rejected."}
