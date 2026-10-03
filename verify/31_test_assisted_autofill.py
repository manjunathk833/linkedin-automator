"""
Verification script for Sprint 4: Dashboard-Triggered Assisted Autofill Copilot.
Tests form field mapping heuristics, candidate response resolution,
and assisted filler initialization.
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.form_mapper import FormFieldMapper
from src.autofill.linkedin_filler import LinkedInAssistedFiller
from src.ui.app import app


def test_form_mapper_heuristics():
    print("==================================================")
    print("  Testing Sprint 4: Form Field Mapping Heuristics")
    print("==================================================")

    mapper = FormFieldMapper()
    contact = mapper.get_contact_info()
    assert contact["first_name"] == "Manjunath", f"Unexpected first name: {contact['first_name']}"
    assert "manjunathhk833@gmail.com" in contact["email"], f"Unexpected email: {contact['email']}"
    print(f"👤 Candidate Contact Verified: {contact['full_name']} ({contact['email']})")

    # Test label resolution
    test_cases = [
        ("First Name", "Manjunath"),
        ("Family Name", "H K"),
        ("Email Address", "manjunathhk833@gmail.com"),
        ("Mobile Phone Number", "+917337813770"),
        ("LinkedIn Profile URL", contact["linkedin"]),
        ("GitHub Repository", contact["github"]),
        ("Total Years of Experience in QA", "6"),
        ("Years of Core Java experience", "6"),
        ("Selenium WebDriver automation experience (years)", "4"),
        ("Are you legally authorized to work in India?", "Yes"),
        ("Will you now or in the future require visa sponsorship?", "No"),
    ]

    print("\n🔍 Testing field resolution across standard application questions:")
    for label, expected in test_cases:
        resolved = mapper.resolve_field_value(label)
        assert resolved == expected, f"Failed for '{label}': expected '{expected}', got '{resolved}'"
        print(f"   • Label: '{label}' -> Resolved: '{resolved}' ✅")

    print("\n✅ All form field heuristic mappings passed!")


def test_fillers_initialization():
    print("\n==================================================")
    print("  Testing Assisted Filler Module Initializers")
    print("==================================================")

    li_filler = LinkedInAssistedFiller(headless=True)
    ats_filler = ATSAssistedFiller(headless=True)

    assert hasattr(li_filler, "autofill_easy_apply"), "LinkedIn filler missing autofill_easy_apply"
    assert hasattr(ats_filler, "autofill_ats_application"), "ATS filler missing autofill_ats_application"
    print("✅ LinkedInAssistedFiller and ATSAssistedFiller initialized successfully.")


def test_dashboard_autofill_route():
    print("\n==================================================")
    print("  Testing Dashboard Autofill FastAPI Endpoint")
    print("==================================================")

    client = TestClient(app)
    # Test unknown job ID returns 404 cleanly
    resp = client.post("/api/autofill/non_existent_job_12345")
    assert resp.status_code == 404, f"Expected 404 for missing job, got {resp.status_code}"
    print("✅ /api/autofill/{job_id} correctly returned 404 for non-existent job.")


def main():
    test_form_mapper_heuristics()
    test_fillers_initialization()
    test_dashboard_autofill_route()
    print("\n" + "=" * 50)
    print("✅ VERIFICATION SCRIPT 31 (ASSISTED AUTOFILL) PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    main()
