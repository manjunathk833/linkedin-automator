import json
import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pdf_engine.generator import PDFGenerator
from src.resume_store.models import ResumeProfile


def test_pdf_generation():
    # Load test data
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "resume_profile.json")
    print(f"Loading data from {json_path}...")

    with open(json_path, "r") as f:
        data = json.load(f)

    # Parse via Pydantic
    profile = ResumeProfile(**data)

    # Generate PDF
    output_pdf = os.path.join(os.path.dirname(__file__), "resume_test_output.pdf")
    generator = PDFGenerator()

    print("Generating PDF...")
    generator.generate_pdf(profile, output_pdf)

    if os.path.exists(output_pdf):
        size = os.path.getsize(output_pdf)
        print("✅ PDF generated successfully!")
        print(f"   Path: {output_pdf}")
        print(f"   Size: {size / 1024:.2f} KB")
    else:
        print("❌ PDF generation failed, file not found.")
        sys.exit(1)

    # Validate section sequence in rendered HTML
    rendered_html = generator.template.render(profile=profile)
    idx_sum = rendered_html.find("Professional Summary")
    idx_skills = rendered_html.find("Core Technical Skills")
    idx_exp = rendered_html.find("Experience")
    idx_proj = rendered_html.find("Projects")
    idx_awards = rendered_html.find("Certifications & Awards")
    idx_edu = rendered_html.find("Education")

    assert idx_sum != -1, "Professional Summary section not found"
    assert idx_skills != -1, "Core Technical Skills section not found"
    assert idx_exp != -1, "Experience section not found"
    assert idx_proj != -1, "Projects section not found"
    assert idx_awards != -1, "Certifications & Awards section not found"
    assert idx_edu != -1, "Education section not found"

    assert idx_sum < idx_skills < idx_exp < idx_proj < idx_awards < idx_edu, (
        f"Incorrect section order! Expected Summary -> Skills -> Experience -> Projects -> Awards -> Education, "
        f"got indices: sum={idx_sum}, skills={idx_skills}, exp={idx_exp}, proj={idx_proj}, awards={idx_awards}, edu={idx_edu}"
    )
    print("✅ Verified senior SDET section sequence:")
    print(
        "   1. Professional Summary -> 2. Core Technical Skills -> 3. Experience -> 4. Projects -> 5. Certifications & Awards -> 6. Education (bottom)"
    )


if __name__ == "__main__":
    test_pdf_generation()
