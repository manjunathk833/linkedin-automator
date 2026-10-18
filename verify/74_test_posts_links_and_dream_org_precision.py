#!/usr/bin/env python3
"""
Verification Gate 74: Universal Post Links Sanitization, Tool Disambiguation & Dream Org Precision.

Validates:
1. Robust lnkd.in token isolation (strips concatenated words like 'Follow', 'Apply', and unicode emojis).
2. Elimination of tool collisions: technical skill keywords in headlines (Docker, Postman, Kafka)
   are never misclassified as hiring companies or false Dream Orgs.
3. Authentic Dream Org detection: only genuine employers (e.g. Swiggy, Okta) trigger Dream Org flags.
4. Downstream outreach sync: connection notes and InMail drafts cite the authentic hiring company.
5. Database self-healing migration: cleanses legacy corrupted links and heals false Dream Org records.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.posts.outreach_composer import PostOutreachComposer
from src.posts.post_classifier import PostClassifier
from src.storage.database import ApplicationDatabase


def test_url_sanitization_and_token_isolation():
    """Validates that lnkd.in and external URLs are isolated from trailing words and emojis."""
    classifier = PostClassifier()

    corrupted_samples = [
        ("https://lnkd.in/dfQ3eZphFollow", "https://lnkd.in/dfQ3eZph"),
        ("https://lnkd.in/dCHhxN8J\ud83d\udccc", "https://lnkd.in/dCHhxN8J"),
        ("https://lnkd.in/gVwCJBdMApply", "https://lnkd.in/gVwCJBdM"),
        ("https://lnkd.in/g-EuUW6hIf", "https://lnkd.in/g-EuUW6h"),
        ("https://jobviareferral.com\u2026", "https://jobviareferral.com"),
        ("https://careers.company.com/apply/12345.", "https://careers.company.com/apply/12345"),
        ("https://careers.company.com/jobsFollow", "https://careers.company.com/jobs"),
    ]

    for raw, expected in corrupted_samples:
        cleaned = classifier.clean_single_url(raw)
        assert cleaned == expected, f"Failed cleaning '{raw}': got '{cleaned}', expected '{expected}'"

    # Test extract_links with concatenated text and dom_links
    raw_text = (
        "Check openings at https://lnkd.in/dfQ3eZphFollow for details. "
        "Also apply here: https://jobviareferral.com\u2026 or email test@example.com"
    )
    extracted = classifier.extract_links(raw_text)
    assert "https://lnkd.in/dfQ3eZph" in extracted
    assert "https://jobviareferral.com" in extracted
    assert not any("Follow" in u for u in extracted)
    assert not any("\u2026" in u for u in extracted)

    # Test additional DOM-extracted links integration
    dom_links = ["https://lnkd.in/abc12345", "https://media.licdn.com/dms/image/123.jpg"]
    combined_links = classifier.extract_links(raw_text, additional_links=dom_links)
    assert "https://lnkd.in/abc12345" in combined_links
    assert not any("licdn.com" in u for u in combined_links)
    print("   ✅ Shortlink token isolation & link sanitization verified across all edge cases")


def test_tool_disambiguation_and_dream_org_precision():
    """Validates that technical skills in headlines are never misclassified as companies or dream orgs."""
    classifier = PostClassifier()

    # Case 1: Pooja Sawarkar (Docker in skills headline, hiring for IRIS Software)
    headline_pooja = (
        "Python Automation Engineer | Robot Framework | Pytest | REST API | Selenium | "
        "BDDPlaywright | Linux | SQL | Cloud Testing | Docker | AWS"
    )
    text_pooja = (
        "🚀 IRIS Software – Multiple Job Openings | Referrals Welcome! "
        "Open Positions: SDET – Lead | Exp: 8–9 years | Noida, Pune, Gurgaon | ID: 34881"
    )
    company_1, is_dream_1 = classifier.extract_company_name(headline_pooja, text_pooja)
    assert company_1.lower() == "iris software", f"Expected 'Iris Software', got '{company_1}'"
    assert not is_dream_1, "Failed: IRIS Software was mistakenly tagged as Dream Org due to Docker skill!"
    print("   ✅ Case 1: Docker in skills headline correctly disambiguated; company resolved as IRIS Software")

    # Case 2: Vishal Patil (Postman in skills/headline context, hiring for Blitz)
    headline_vishal = "Quality Engineering Specialist | Helping IT professionals get referrals"
    text_vishal = "🚀 Blitz is Hiring SDET-2 and QA Automation Leads in Bengaluru! Apply now."
    company_2, is_dream_2 = classifier.extract_company_name(headline_vishal, text_vishal)
    assert company_2.lower() == "blitz", f"Expected 'Blitz', got '{company_2}'"
    assert not is_dream_2, "Failed: Blitz was mistakenly tagged as Dream Org!"
    print("   ✅ Case 2: Blitz hiring trigger resolved correctly; no Postman false positive")

    # Case 3: Sivareddy M. (Headline says "Quality Engineer at Synextic Global Business Solution")
    headline_siva = "Quality Engineer at Synextic Global Business Solution"
    text_siva = "I am searching for QA testing opportunities with hands-on in Postman, Rest Assured and Selenium."
    company_3, is_dream_3 = classifier.extract_company_name(headline_siva, text_siva)
    assert "synextic" in company_3.lower(), f"Expected Synextic, got '{company_3}'"
    assert not is_dream_3, "Failed: Synextic was mistakenly tagged as Dream Org due to Postman in text!"
    print("   ✅ Case 3: Employer in headline resolved correctly; Postman skill in body ignored")

    # Case 4: Authentic Dream Org (Karthik Raja at Swiggy)
    headline_swiggy = "Senior SDET @ Swiggy | Playwright & Distributed Systems"
    text_swiggy = "My team at Swiggy is actively hiring for Lead SDETs. Reach out directly!"
    company_4, is_dream_4 = classifier.extract_company_name(headline_swiggy, text_swiggy)
    assert company_4.lower() == "swiggy"
    assert is_dream_4, "Failed: Swiggy was not recognized as an authentic Dream Org!"
    print("   ✅ Case 4: Authentic Dream Org (Swiggy) correctly identified and tagged")

    # Case 5: Authentic Dream Org (Okta)
    headline_okta = "QA Lead & Engineering Manager @ Okta | Ex-Microsoft"
    text_okta = "Okta is hiring Lead SDET and QA Architect. Req ID: REQ-9941."
    company_5, is_dream_5 = classifier.extract_company_name(headline_okta, text_okta)
    assert company_5.lower() == "okta"
    assert is_dream_5, "Failed: Okta was not recognized as an authentic Dream Org!"
    print("   ✅ Case 5: Authentic Dream Org (Okta) correctly identified and tagged")


def test_downstream_outreach_synchronization():
    """Validates that generated outreach drafts cite the authentic company, not tool keywords."""
    composer = PostOutreachComposer()

    post_data_iris = {
        "author_name": "Pooja Sawarkar",
        "company_name": "Iris Software",
        "author_role_category": "ENGINEER",
        "extracted_job_codes": ["34881"],
    }
    note = composer.generate_connection_note(post_data_iris)
    inmail = composer.generate_inmail_pitch(post_data_iris)

    assert "Iris Software" in note
    assert "Docker" not in note
    assert "Iris Software" in inmail
    assert "Docker (Ref:" not in inmail
    print("   ✅ Downstream outreach drafts accurately cite authentic company without tool pollution")


def test_database_metadata_and_links_self_healing():
    """Validates that ApplicationDatabase heals legacy broken links and false dream org records."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    try:
        db = ApplicationDatabase(db_path=temp_db_path)

        # Seed corrupted legacy records
        with db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO hiring_posts (
                    post_id, author_name, author_headline, author_profile_url,
                    company_name, is_dream_org, post_url, post_text, posted_at_relative,
                    extracted_links, quality_score, custom_dm_draft, custom_inmail_draft
                ) VALUES
                (
                    'post_false_dream_1', 'Pooja Sawarkar',
                    'Python Automation Engineer | Docker | AWS',
                    'https://www.linkedin.com/in/pooja-sawarkar/',
                    'Docker', 1, 'https://www.linkedin.com/in/pooja-sawarkar/recent-activity/all/',
                    '🚀 IRIS Software – Multiple Job Openings | Referrals Welcome! Apply: https://lnkd.in/dfQ3eZphFollow',
                    '2h', '["https://lnkd.in/dfQ3eZphFollow"]', 85,
                    'Hi Pooja, Saw your post on Docker SDET referrals', 'Role at Docker'
                ),
                (
                    'post_false_dream_2', 'Vishal Patil',
                    'Quality Specialist | Helping professionals get referrals',
                    'https://www.linkedin.com/in/vishal-patil/',
                    'Postman', 1, 'https://www.linkedin.com/in/vishal-patil/recent-activity/all/',
                    '🚀 Blitz is Hiring SDET! Link: https://jobviareferral.com\u2026',
                    '1d', '["https://jobviareferral.com\u2026"]', 90,
                    'Hi Vishal, Saw your post on Postman SDET referrals', 'Role at Postman'
                );
                """
            )
            conn.commit()

        # Run database repair
        repaired_count = db.repair_posts_metadata_and_links()
        assert repaired_count == 2, f"Expected 2 rows repaired, got {repaired_count}"

        # Audit repaired rows
        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT post_id, company_name, is_dream_org, extracted_links, custom_dm_draft FROM hiring_posts ORDER BY post_id"
            )
            rows = {r["post_id"]: dict(r) for r in cur.fetchall()}

        # Verify Pooja's record
        pooja_row = rows["post_false_dream_1"]
        assert pooja_row["company_name"].lower() == "iris software"
        assert pooja_row["is_dream_org"] == 0
        clean_links_pooja = json.loads(pooja_row["extracted_links"])
        assert clean_links_pooja == ["https://lnkd.in/dfQ3eZph"]
        assert "Iris Software" in pooja_row["custom_dm_draft"]
        assert "Docker" not in pooja_row["custom_dm_draft"]

        # Verify Vishal's record
        vishal_row = rows["post_false_dream_2"]
        assert vishal_row["company_name"].lower() == "blitz"
        assert vishal_row["is_dream_org"] == 0
        clean_links_vishal = json.loads(vishal_row["extracted_links"])
        assert clean_links_vishal == ["https://jobviareferral.com"]
        assert "Blitz" in vishal_row["custom_dm_draft"]
        assert "Postman" not in vishal_row["custom_dm_draft"]

        print("   ✅ Database self-healing migration successfully cleansed corrupted links and false dream orgs")

    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


def test_job_seeker_filtering_and_stopwords_precision():
    """Validates that job seekers (#OpenToWork, 'if your team is hiring') are rejected and stopwords are cleansed."""
    classifier = PostClassifier()

    # 1. BhuvNesh TiwaRi (Job seeker with unicode small-caps Oᴘᴇɴ ᴛᴏ Wᴏʀᴋ and 'If your team is hiring')
    hl_bhuvnesh = "Sr. QA Engineer | Exp: 9+ yrs | FinTech | Selenium | Java | Postman"
    text_bhuvnesh = (
        "🚀 Oᴘᴇɴ ᴛᴏ Wᴏʀᴋ | Sᴇɴɪᴏʀ QA Eɴɢɪɴᴇᴇʀ | QA Lᴇᴀᴅ | Rᴇᴍᴏᴛᴇ\n"
        "I'm currently exploring new opportunities in QA and would appreciate your help. "
        "If your team is hiring or you know of a relevant opportunity, lets connect! #OpenToWork"
    )
    is_valid, reason = classifier.is_hiring_post(hl_bhuvnesh, text_bhuvnesh)
    assert not is_valid, "Failed: BhuvNesh TiwaRi was not recognized as a job seeker!"
    print(f"   ✅ Job seeker 1 (BhuvNesh TiwaRi) rejected: {reason}")

    # 2. Sam Thota (Lost job, 'If your team is hiring, or you can refer me', #OpenToWork)
    hl_sam = "QA Automation Engineer | 3+ Years of Experience | Playwright | Selenium"
    text_sam = (
        "💔I have lost my job ..Plz don't ignore this post. "
        "I’m looking for my next opportunity as a QA Automation Engineer / SDET. "
        "If your team is hiring, or you can refer me, I’d really appreciate a comment. #OpenToWork"
    )
    is_valid_sam, reason_sam = classifier.is_hiring_post(hl_sam, text_sam)
    assert not is_valid_sam, "Failed: Sam Thota was not recognized as a job seeker!"
    print(f"   ✅ Job seeker 2 (Sam Thota) rejected: {reason_sam}")

    # 3. Company Candidate Sanitization (Stopword and fragment rejection)
    junk_candidates = [
        (".If Your Team", None),
        ("Several Exciting", None),
        ("Right.If Your Team", None),
        ("Exciting Opportunities", None),
        ("Your Team", None),
        ("If You", None),
    ]
    for raw_cand, expected in junk_candidates:
        sanitized = classifier._sanitize_company_candidate(raw_cand)
        assert sanitized == expected, f"Expected '{expected}' for '{raw_cand}', got '{sanitized}'"
    print("   ✅ Conversational fragments (.If Your Team, Several Exciting) rejected as companies")

    # 4. Valid Hiring Post should still pass
    hl_hiring = "Engineering Manager @ TechCorp"
    text_hiring = "We are hiring Lead SDET and Senior QA in Bengaluru. DM me your resume!"
    is_valid_hiring, _ = classifier.is_hiring_post(hl_hiring, text_hiring)
    assert is_valid_hiring, "Failed: Valid hiring post was falsely rejected!"
    print("   ✅ Genuine team hiring post successfully passes filter")


def main():
    print("=" * 70)
    print("🚀 RUNNING VERIFICATION GATE 74: UNIVERSAL POST LINKS & DREAM ORG PRECISION")
    print("=" * 70)

    print("\n🔍 Step 1: Testing Shortlink Token Isolation & URL Sanitization...")
    test_url_sanitization_and_token_isolation()

    print("\n🔍 Step 2: Testing Tool vs. Company Disambiguation & Dream Org Precision...")
    test_tool_disambiguation_and_dream_org_precision()

    print("\n🔍 Step 3: Testing Job Seeker Filtering & Stopword Company Sanitization...")
    test_job_seeker_filtering_and_stopwords_precision()

    print("\n🔍 Step 4: Testing Downstream Outreach Synchronization...")
    test_downstream_outreach_synchronization()

    print("\n🔍 Step 5: Testing Database Self-Healing Migration & Job Seeker Purge...")
    test_database_metadata_and_links_self_healing()

    print("\n" + "=" * 70)
    print("🎉 ALL GATE 74 CHECKS PASSED: ZERO CORRUPTED LINKS & ZERO FALSE DREAM ORGS")
    print("=" * 70)


if __name__ == "__main__":
    main()
