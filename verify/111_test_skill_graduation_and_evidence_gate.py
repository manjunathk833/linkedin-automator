"""
Verification Gate 111: Evidence-Gated Skill Graduation & Boundary Enforcement.

Uses temporary synthetic files only (safe in CI, never touches real candidate data):
1. A learning-roadmap tool (TypeScript) is blocked everywhere while it has no master-resume evidence.
2. Adding a project that uses it to the master resume + re-running the sync graduates it automatically
   (moved from learning_roadmap to allowed_tools, evidence recorded).
3. Boundary evidence: a tool evidenced only at employer A is rejected in employer B bullets.
4. Learning-roadmap sections in candidate notes are never synced by the knowledge translator.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.master_sync import run_sync
from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector


def _master() -> dict:
    def ul(items):
        return "<ul>" + "".join(f"<li><p>{i}</p></li>" for i in items) + "</ul>"

    return {
        "basics": {
            "name": "Test Candidate",
            "headline": "Senior SDET",
            "email": "test@example.com",
            "phone": "+91 9000000000",
            "location": "Bengaluru, India",
            "website": {"url": "https://example.dev/", "label": "example.dev"},
            "customFields": [{"id": "g", "text": "github.com/test", "link": "https://github.com/test"}],
        },
        "summary": {"hidden": False, "content": "<p>Senior SDET with 7 years of experience.</p>"},
        "sections": {
            "experience": {
                "hidden": False,
                "items": [
                    {
                        "id": "e1",
                        "hidden": False,
                        "company": "Alpha Corp",
                        "position": "Senior SDET",
                        "dates": {"start": "2023-06", "end": None, "present": True},
                        "description": ul(
                            [
                                "Built Java REST Assured suites and ran them in Docker containers via Jenkins.",
                                "Monitored Kafka event logs with Kibana to triage service failures.",
                            ]
                        ),
                        "roles": [],
                    },
                    {
                        "id": "e2",
                        "hidden": False,
                        "company": "Beta Labs",
                        "position": "QA Engineer",
                        "dates": {"start": "2019-12", "end": "2023-05", "present": False},
                        "description": ul(["Automated mobile sanity suites in Python with Appium."]),
                        "roles": [],
                    },
                ],
            },
            "projects": {"hidden": False, "items": []},
            "skills": {
                "hidden": False,
                "items": [
                    {
                        "id": "s1",
                        "hidden": False,
                        "name": "Tools",
                        "keywords": [
                            "Java",
                            "Python",
                            "REST Assured",
                            "Docker",
                            "Kafka",
                            "Kibana",
                            "Appium",
                            "Jenkins",
                        ],
                    }
                ],
            },
            "education": {
                "hidden": False,
                "items": [
                    {
                        "id": "ed",
                        "hidden": False,
                        "school": "College",
                        "degree": "B.E. Computer Science",
                        "grade": "8.0",
                        "dates": {"start": "2015-08", "end": "2019-03"},
                    }
                ],
            },
            "certifications": {"hidden": False, "items": []},
            "awards": {"hidden": False, "items": []},
        },
    }


def _paths(tmp: str) -> dict:
    return {
        "master_path": os.path.join(tmp, "master.json"),
        "profile_path": os.path.join(tmp, "resume_profile.json"),
        "whitelist_path": os.path.join(tmp, "whitelist.json"),
        "bank_path": os.path.join(tmp, "bank.json"),
        "notes_path": os.path.join(tmp, "notes.md"),
        "candidate_master_data_path": os.path.join(tmp, "candidate_master_data.json"),
    }


def _write(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f)


def _detector(p: dict) -> FabricationDetector:
    with open(p["profile_path"], encoding="utf-8") as f:
        profile = ResumeProfile(**json.load(f))
    with open(p["bank_path"], encoding="utf-8") as f:
        bank = json.load(f)
    return FabricationDetector(profile, bank, whitelist_path=p["whitelist_path"])


def test_graduation_and_boundaries():
    with tempfile.TemporaryDirectory() as tmp:
        p = _paths(tmp)
        _write(p["master_path"], _master())
        _write(
            p["whitelist_path"], {"learning_roadmap": ["typescript", "pact"], "disallowed_hallucinations": ["cypress"]}
        )
        _write(p["notes_path"], "## Alpha Corp\n- Built Java suites.\n")

        # 1. Roadmap tool blocked before graduation
        report = run_sync(**p)
        assert "typescript" in report["roadmap_blocked"]
        det = _detector(p)
        assert "typescript" not in det.allowed_tools
        assert not det.check_bullet("Built a Playwright framework in TypeScript.")["is_valid"]
        print("✅ Roadmap tool 'typescript' blocked before graduation.")

        # 3. Boundary evidence: Docker evidenced at Alpha Corp only
        assert det.check_company_contamination("Alpha Corp", "Ran Docker containers in CI.")["is_clean"]
        beta = det.check_company_contamination("Beta Labs", "Ran Docker containers in CI.")
        assert not beta["is_clean"], "Docker has no evidence at Beta Labs and must be rejected there"
        assert det.check_company_contamination("Beta Labs", "Automated mobile sanity suites in Python.")["is_clean"]
        print(f"✅ Boundary evidence enforced: {beta['violating_companies']}")

        # 2. Graduation: add a project using TypeScript to the master resume and re-sync
        master = copy.deepcopy(_master())
        master["sections"]["projects"]["items"].append(
            {
                "id": "p1",
                "hidden": False,
                "name": "Playwright TS Framework (Personal)",
                "description": "<p>Built a parallel Playwright framework in TypeScript. Stack: TypeScript, Docker.</p>",
            }
        )
        master["sections"]["skills"]["items"][0]["keywords"].append("TypeScript")
        _write(p["master_path"], master)
        report2 = run_sync(**p)
        assert "typescript" in report2["graduated"], f"Expected graduation, got {report2['graduated']}"
        with open(p["whitelist_path"], encoding="utf-8") as f:
            reg = json.load(f)
        assert "typescript" in reg["allowed_tools"] and "typescript" not in reg["learning_roadmap"]
        assert any(b.startswith("project:") for b in reg["tool_evidence"]["typescript"])
        assert "pact" in reg["learning_roadmap"], "Un-built roadmap tools must stay blocked"
        assert _detector(p).check_bullet("Built a framework in TypeScript.")["is_valid"]
        print("✅ 'typescript' graduated automatically after being added to the master resume; 'pact' still blocked.")


def test_roadmap_notes_never_synced():
    from src.tailor.knowledge_translator import KnowledgeBankTranslator

    notes = (
        "## Alpha Corp (2023 – Present)\n- Built Java REST Assured suites with Docker.\n"
        "## Learning Roadmap & Parked Projects (NOT FOR RESUME)\n### Roadmap\n"
        "- Built Pact contract tests with WireMock.\n"
    )
    translator = KnowledgeBankTranslator(use_ai=False)
    pairs = translator.extract_sectioned_bullets(notes)
    assert pairs == [("Alpha Corp", "Built Java REST Assured suites with Docker.")], pairs
    print("✅ Learning-roadmap notes (incl. nested sub-headings) are excluded; employer label from heading.")


if __name__ == "__main__":
    test_graduation_and_boundaries()
    test_roadmap_notes_never_synced()
    print("\n🎉 Gate 111 passed.")
