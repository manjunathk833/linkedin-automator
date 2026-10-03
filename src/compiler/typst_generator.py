"""
ATS-Compliant Single-Column Resume Compiler.
Generates parameterized Typst markup and compiles into data/resumes/{company}_{job_id}_{role_slug}.pdf.
Provides seamless fallback to HTML/WeasyPrint if Typst CLI is not installed on host.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any

from src.pdf_engine.generator import PDFGenerator

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_RESUME_DIR = os.path.join(PROJECT_ROOT, "data", "resumes")
TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "resume_template.typ")


def sanitize_filename(name: str) -> str:
    """Removes special characters for safe filesystem naming."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "_", clean)


class TypstResumeCompiler:
    """
    Compiles tailored candidate profiles into structured, single-column ATS PDFs.
    """

    def __init__(self, output_dir: str = DEFAULT_RESUME_DIR):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.typst_bin = shutil.which("typst")
        self.pdf_engine = PDFGenerator()

    def generate_typst_markup(self, profile: dict[str, Any]) -> str:
        """Renders raw Typst document string from candidate profile dictionary."""
        p_details = profile.get("personal_details", {})
        full_name = p_details.get("full_name", "Candidate")
        label = p_details.get("label", "Senior SDET")
        email = p_details.get("email", "")
        phone = p_details.get("phone", "")
        location = p_details.get("location", "")
        summary = p_details.get("summary", "")

        # Format experience blocks
        exp_entries: list[str] = []
        for exp in profile.get("experience_history", []):
            role = exp.get("role", "")
            comp = exp.get("company", "")
            s_date = exp.get("start_date", "")
            e_date = exp.get("end_date") or "Present"

            bullets: list[str] = []
            for b in exp.get("achievements", []):
                clean_b = b.replace("\\", "\\\\").replace('"', '\\"').replace("[", "\\[").replace("]", "\\]")
                bullets.append(f"  - {clean_b}")

            bullet_text = "\n".join(bullets)
            exp_markup = f"""
*#text(weight: "bold")[{role}]* --- #text(fill: rgb("#334155"))[{comp}] #h(1fr) #text(size: 8pt, fill: rgb("#64748b"))[{s_date} - {e_date}]
{bullet_text}
"""
            exp_entries.append(exp_markup)

        all_exp_markup = "\n".join(exp_entries)

        # Technical skills block
        skills = profile.get("skills", [])
        skills_str = (
            ", ".join(s.get("name", "") for s in skills)
            if skills
            else "Java, Python, REST Assured, Selenium, TestNG, Jenkins, Docker"
        )

        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = f.read()

        rendered = template.replace("#FULL_NAME", f'"{full_name}"')
        rendered = rendered.replace("#LABEL", f'"{label}"')
        rendered = rendered.replace("#EMAIL", f'"{email}"')
        rendered = rendered.replace("#PHONE", f'"{phone}"')
        rendered = rendered.replace("#LOCATION", f'"{location}"')
        rendered = rendered.replace("#SUMMARY_TEXT", f'"{summary}"')
        rendered = rendered.replace("#EXPERIENCE_BLOCKS", all_exp_markup)
        rendered = rendered.replace("#SKILLS_BLOCK", f'"{skills_str}"')

        return rendered

    def compile(
        self,
        profile: dict[str, Any],
        company: str,
        job_id: str,
        role_title: str,
    ) -> str:
        """
        Compiles tailored resume into data/resumes/{company}_{job_id}_{role_slug}.pdf.
        """
        comp_slug = sanitize_filename(company)
        clean_id = sanitize_filename(job_id)
        role_slug = sanitize_filename(role_title)

        cand_name = "Manjunath_HK"
        if isinstance(profile, dict):
            p_det = profile.get("personal_details", {})
            full_name = p_det.get("full_name") or p_det.get("name")
            if full_name:
                parts = full_name.strip().split()
                if len(parts) > 1:
                    first = re.sub(r"[^a-zA-Z0-9]", "", parts[0])
                    rest = "".join(re.sub(r"[^a-zA-Z0-9]", "", p) for p in parts[1:])
                    cand_name = f"{first}_{rest}"
                else:
                    cand_name = re.sub(r"[^a-zA-Z0-9]", "", full_name)

        filename = f"{cand_name}_{comp_slug}_{clean_id}_{role_slug}.pdf"
        output_pdf = os.path.join(self.output_dir, filename)

        if self.typst_bin:
            # 1. Primary Typst Compilation
            temp_typ = os.path.join(self.output_dir, f"{comp_slug}_{clean_id}.typ")
            markup = self.generate_typst_markup(profile)
            with open(temp_typ, "w", encoding="utf-8") as f:
                f.write(markup)

            try:
                subprocess.run(
                    [self.typst_bin, "compile", temp_typ, output_pdf],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                print(f"📄 Typst compiled PDF generated at: {output_pdf}")
                return output_pdf
            except Exception as e:
                print(f"⚠️ Typst CLI error: {e}. Falling back to HTML engine...")
            finally:
                if os.path.exists(temp_typ):
                    os.remove(temp_typ)

        # 2. Resilient Fallback: HTML/Playwright Engine
        from src.resume_store.models import ResumeProfile

        profile_obj = ResumeProfile(**profile) if isinstance(profile, dict) else profile
        return self.pdf_engine.generate_pdf(profile_obj, output_pdf)
