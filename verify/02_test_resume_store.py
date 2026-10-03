import json
import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.resume_store.models import ResumeProfile


def test_resume_profile():
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "resume_profile.json")
    print(f"Loading data from {json_path}...")

    with open(json_path, "r") as f:
        data = json.load(f)

    try:
        profile = ResumeProfile(**data)
        print("✅ Pydantic Schema Validation Passed!")
        print(f"   Loaded Profile for: {profile.personal_details.full_name}")
        print(f"   Headline: {profile.personal_details.label}")
        print(f"   Summary length: {len(profile.personal_details.summary or '')} chars")

        # --- Skills query ---
        skill = "Java"
        yoe = profile.get_years_of_experience(skill)
        print(f"\n🔍 Skills Query: '{skill}' -> {yoe} years")
        assert yoe >= 6, f"Expected >= 6, got {yoe}"

        skill_ci = "python"  # case-insensitive test
        yoe_ci = profile.get_years_of_experience(skill_ci)
        assert yoe_ci >= 5, f"Case-insensitive lookup failed: expected >= 5, got {yoe_ci}"
        print(f"🔍 Case-insensitive query '{skill_ci}' -> {yoe_ci} years ✅")

        skill_missing = "Rust"
        yoe_missing = profile.get_years_of_experience(skill_missing)
        assert yoe_missing == 0, f"Expected 0, got {yoe_missing}"
        print(f"🔍 Missing skill '{skill_missing}' -> {yoe_missing} years ✅")

        # --- Education ---
        assert len(profile.education) >= 1, "Expected at least 1 education entry"
        edu = profile.education[0]
        print(f"\n🎓 Education: {edu.study_type} in {edu.area} from {edu.institution}")
        assert "8.02" in (edu.gpa or "")
        print(f"   GPA: {edu.gpa} ✅")

        # --- Projects by tag ---
        java_projects = profile.get_projects_by_tag("Java")
        assert len(java_projects) >= 1, "Expected at least 1 Java project"
        print(f"\n📦 Projects tagged 'Java': {[p.name for p in java_projects]} ✅")

        bdd_projects = profile.get_projects_by_tag("BDD")
        print(f"📦 Projects tagged 'BDD': {[p.name for p in bdd_projects]} ✅")

        # --- Certifications ---
        assert len(profile.certifications) >= 1, "Expected at least 1 certification"
        cert = profile.certifications[0]
        print(f"\n📜 Certification: {cert.name} by {cert.issuer} ✅")

        # --- Awards ---
        assert len(profile.awards) >= 1, "Expected at least 1 award"
        award = profile.awards[0]
        print(f"🏆 Award: {award.title} by {award.awarder} ✅")

        # --- Total experience ---
        total = profile.get_total_experience_years()
        print(f"\n⏱️  Total professional experience: {total} years")
        assert total >= 5.0, f"Expected >= 5.0 years, got {total}"
        print("   Total experience assertion passed ✅")

        # --- Easy Apply answers ---
        ea = profile.easy_apply_answers
        assert ea.authorization_to_work.get("India") is True
        assert ea.sponsorship_needed is False
        assert ea.salary_currency == "INR"
        print("\n📝 Easy Apply Answers:")
        print(f"   India Work Auth: {ea.authorization_to_work.get('India')} ✅")
        print(f"   Salary Currency: {ea.salary_currency} ✅")
        print(f"   Work Preference: {ea.work_preference.value} ✅")
        print(f"   Current Location: {ea.current_location} ✅")

        # --- Languages ---
        assert len(profile.languages) >= 1
        print(f"\n🌍 Languages: {[(l.language, l.fluency.value) for l in profile.languages]} ✅")

        # --- Social Profiles ---
        assert len(profile.personal_details.profiles) >= 2
        print(f"🔗 Social Profiles: {[p.network for p in profile.personal_details.profiles]} ✅")

        # --- Experience count ---
        assert len(profile.experience_history) == 3
        print(f"\n💼 Work Experience entries: {len(profile.experience_history)} ✅")
        for exp in profile.experience_history:
            print(f"   - {exp.role} @ {exp.company} ({len(exp.achievements)} achievements)")

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED — Your resume schema verified!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Schema Validation Failed!\n{e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_resume_profile()
