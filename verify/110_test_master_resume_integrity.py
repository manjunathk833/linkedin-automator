"""
Verification Gate 110: Master Resume (Reactive Resume JSON) Integrity & ATS Readiness.

1. The integrity checker flags every known ATS/authenticity defect on a synthetic bad resume
   (hidden URLs, unsafe glyphs incl. arrows/ligatures, duplicate bullets, roadmap tools, missing sections).
2. The checker passes a synthetic clean resume (runs in CI where private data is gitignored).
3. When the private master resume exists locally, it must pass with zero issues.
"""

from __future__ import annotations

import copy
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.master_resume import (
    MASTER_RESUME_PATH,
    check_integrity,
    extract_boundary_texts,
    load_master_resume,
)

ROADMAP = ["typescript", "wiremock", "pact"]


def _clean_resume() -> dict:
    return {
        "basics": {
            "name": "Test Candidate",
            "headline": "Senior SDET | API & UI Automation",
            "email": "test@example.com",
            "phone": "+91 9000000000",
            "location": "Bengaluru, India",
            "website": {"url": "https://example.dev/", "label": "example.dev"},
            "customFields": [
                {"id": "a", "icon": "github-logo", "text": "github.com/test", "link": "https://github.com/test"}
            ],
        },
        "summary": {"hidden": False, "content": "<p>Senior SDET with 7 years of API automation experience.</p>"},
        "sections": {
            "experience": {
                "hidden": False,
                "items": [
                    {
                        "id": "e1",
                        "hidden": False,
                        "company": "Acme",
                        "position": "",
                        "dates": {"start": "2019-12", "end": "2022-08", "present": False},
                        "description": "<ul><li><p>Built a REST Assured framework covering 1,500+ API tests.</p></li>"
                        "<li><p>Monitored Kafka event logs alongside Kibana to triage failures.</p></li></ul>",
                        "roles": [
                            {"id": "r1", "position": "Senior Engineer, QA", "period": "Jul 2021 – Aug 2022"},
                            {"id": "r2", "position": "Engineer, QA", "period": "Dec 2019 – Jul 2021"},
                        ],
                    }
                ],
            },
            "projects": {
                "hidden": False,
                "items": [
                    {
                        "id": "p1",
                        "hidden": False,
                        "name": "Program X",
                        "description": "<p>600+ API tests for linking bookings across services.</p>",
                    }
                ],
            },
            "skills": {
                "hidden": False,
                "items": [{"id": "s1", "hidden": False, "name": "Languages", "keywords": ["Java", "Python"]}],
            },
            "education": {"hidden": False, "items": [{"id": "ed1", "hidden": False, "school": "College"}]},
        },
    }


def test_clean_resume_passes():
    issues = check_integrity(_clean_resume(), roadmap=ROADMAP)
    assert issues == [], f"Clean synthetic resume should pass, got: {issues}"
    boundaries = {b for b, _ in extract_boundary_texts(_clean_resume())}
    assert {"Acme", "project:Program X", "skills", "summary"} <= boundaries
    print("✅ Clean synthetic resume passes integrity checks; boundaries extracted correctly.")


def test_defects_are_flagged():
    bad = copy.deepcopy(_clean_resume())
    bad["basics"]["customFields"][0]["text"] = "GitHub"  # hidden URL
    bad["basics"]["website"]["label"] = "Portfolio"  # hidden URL
    exp = bad["sections"]["experience"]["items"][0]
    exp["roles"][0]["position"] = "Engineer -> Senior Engineer, QA"  # ascii arrow
    exp["description"] += (
        "<ul><li><p>Automated ~50% of the sanity suite with Playwright and TypeScript workﬂows.</p></li></ul>"
    )
    # duplicate bullet in a project
    bad["sections"]["projects"]["items"][0]["description"] = (
        "<p>Built a REST Assured framework covering 1,500+ API tests.</p>"
    )
    bad["sections"]["education"]["items"] = []

    issues = "\n".join(check_integrity(bad, roadmap=ROADMAP))
    expected = [
        "Profile link 'GitHub' hides its URL",
        "Website label hides its URL",
        "ascii arrow",
        "tilde",
        "fl ligature",
        "Duplicate text",
        "Learning-roadmap tool 'typescript'",
        "Section 'education'",
    ]
    for marker in expected:
        assert marker in issues, f"Expected integrity issue containing '{marker}'.\nGot:\n{issues}"
    print(f"✅ All {len(expected)} defect classes flagged by the integrity checker.")


def test_private_master_resume_is_clean():
    data = load_master_resume()
    if data is None:
        print(f"ℹ️ {os.path.basename(MASTER_RESUME_PATH)} not present (clean CI clone). Skipping private check.")
        return
    issues = check_integrity(data)
    assert issues == [], "Master resume integrity issues:\n - " + "\n - ".join(issues)
    print("✅ Private master resume passes all ATS & authenticity integrity checks.")


if __name__ == "__main__":
    test_clean_resume_passes()
    test_defects_are_flagged()
    test_private_master_resume_is_clean()
    print("\n🎉 Gate 110 passed.")
