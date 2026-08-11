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

os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(APPROVED_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/pending-jobs")
async def get_pending_jobs():
    jobs = []
    if os.path.exists(PENDING_DIR):
        for filename in os.listdir(PENDING_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(PENDING_DIR, filename)
                try:
                    with open(file_path, "r") as f:
                        jobs.append(json.load(f))
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    return {"jobs": jobs}


@app.post("/api/approve/{job_id}")
async def approve_job(job_id: str, payload: dict):
    from src.pdf_engine.generator import PDFGenerator
    from src.resume_store.models import ResumeProfile

    approved_path = os.path.join(APPROVED_DIR, f"{job_id}.json")
    try:
        # Generate the PDF
        if "tailored_resume" in payload:
            print(f"Generating PDF for job {job_id}...")

            # Sanitize numeric fields in easy_apply_answers (empty string -> None)
            ea = payload["tailored_resume"].get("easy_apply_answers", {})
            if isinstance(ea, dict):
                for int_field in ["salary_expectations_min", "salary_expectations_max"]:
                    if ea.get(int_field) == "":
                        ea[int_field] = None

            profile = ResumeProfile(**payload["tailored_resume"])
            generator = PDFGenerator()
            pdf_filename = f"{job_id}_resume.pdf"
            pdf_path = os.path.join(APPROVED_DIR, pdf_filename)

            # Use async method directly since FastAPI is running an event loop
            await generator.generate_pdf_async(profile, pdf_path)

            # Link the PDF path in the payload for Playwright to use later
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
