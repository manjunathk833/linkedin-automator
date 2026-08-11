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


if __name__ == "__main__":
    test_pdf_generation()
