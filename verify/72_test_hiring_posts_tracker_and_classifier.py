#!/usr/bin/env python3
"""
Verification Gate 72: LinkedIn Hiring Posts Tracker, Multi-Persona Classifier,
and Outreach Composer Engine (Track 3).

Validates:
1. Inclusivity of Engineer, Leader, Peer, and Recruiter personas without dropping valid posts.
2. Anti-noise rejection of Job Seekers (#OpenToWork), EdTech spam, and promotion posts.
3. Information extraction: emails, external URLs, and requisition/job codes.
4. Character-budgeted outreach generation: Connection Notes (<=300 chars) & InMail (<=1000 chars).
5. SQLite schema persistence, status workflows, and KPI metrics aggregation.
"""

from __future__ import annotations

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


def test_post_classifier_multi_persona():
    """Validates that Engineers, Leads, Peers, and Recruiters are all welcomed and accurately classified."""
    classifier = PostClassifier()

    # 1. Engineer Hiring Post (Often uses "actively looking for SDET" or "looking for my squad")
    engineer_post = {
        "author_name": "Karthik Raja",
        "author_headline": "Senior SDET @ Swiggy | Playwright & Distributed Systems",
        "post_text": "I am actively looking for a Senior SDET with 5+ years experience in Playwright and Java for my team at Swiggy. If you're open to work, DM me your resume!",
        "posted_at_relative": "2h",
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7182910293/",
    }
    processed_eng = classifier.process_raw_post(engineer_post)
    assert processed_eng is not None, "Failed: Engineer hiring post was mistakenly rejected!"
    assert processed_eng["author_role_category"] == "ENGINEER", (
        f"Expected ENGINEER, got {processed_eng['author_role_category']}"
    )
    assert processed_eng["company_name"] == "Swiggy", f"Expected Swiggy, got {processed_eng['company_name']}"
    print("   ✅ Engineer hiring post accepted and classified as ENGINEER")

    # 2. Engineering Leader / QA Lead Post (Mentions layoffs to offer help, expanding squad)
    leader_post = {
        "author_name": "Siddharth Rao",
        "author_headline": "QA Lead & Engineering Manager @ Okta | Ex-Microsoft",
        "post_text": "Anyone impacted by recent layoffs? Our QA automation team at Okta is expanding. Openings for Lead SDET and QA Architect. Req ID: REQ-9941. Reach out to me directly or email siddharth@okta.com",
        "posted_at_relative": "1d",
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7182910400/",
    }
    processed_lead = classifier.process_raw_post(leader_post)
    assert processed_lead is not None, "Failed: Leader hiring post was mistakenly rejected!"
    assert processed_lead["author_role_category"] == "LEADER", (
        f"Expected LEADER, got {processed_lead['author_role_category']}"
    )
    assert processed_lead["company_name"] == "Okta", f"Expected Okta, got {processed_lead['company_name']}"
    assert "siddharth@okta.com" in processed_lead["extracted_emails"], "Failed to extract email from leader post"
    assert "REQ-9941" in processed_lead["extracted_job_codes"], "Failed to extract job code REQ-9941"
    print("   ✅ Engineering Leader post accepted, classified as LEADER, email and Req ID extracted")

    # 3. Peer Referral Post (Non-QA employee offering team referrals)
    peer_post = {
        "author_name": "Ananya Sen",
        "author_headline": "Senior Product Manager @ Dunzo",
        "post_text": "Dunzo is actively hiring! Referrals open for SDET-2 and QA Automation Engineer in Bengaluru. Send your CV to me on LinkedIn or at ananya.sen@dunzo.in",
        "posted_at_relative": "3h",
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7182910555/",
    }
    processed_peer = classifier.process_raw_post(peer_post)
    assert processed_peer is not None, "Failed: Peer referral post was mistakenly rejected!"
    assert processed_peer["author_role_category"] == "PEER", (
        f"Expected PEER, got {processed_peer['author_role_category']}"
    )
    assert "ananya.sen@dunzo.in" in processed_peer["extracted_emails"]
    print("   ✅ Peer referral post accepted and classified as PEER")

    # 4. Recruiter / TA Partner Post
    recruiter_post = {
        "author_name": "Pooja Malhotra",
        "author_headline": "Talent Acquisition Specialist @ Angel One | Tech Hiring",
        "post_text": "We are hiring Senior SDETs (₹25-32 LPA band) for Angel One in Bengaluru. Must have 5+ yrs in API and UI test automation. Apply directly: https://careers.angelone.in/jobs/8291 or email pooja.m@angelone.in. Job Code: AO-TEST-44",
        "posted_at_relative": "4h",
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7182910777/",
    }
    processed_recruiter = classifier.process_raw_post(recruiter_post)
    assert processed_recruiter is not None, "Failed: Recruiter hiring post was mistakenly rejected!"
    assert processed_recruiter["author_role_category"] == "RECRUITER", (
        f"Expected RECRUITER, got {processed_recruiter['author_role_category']}"
    )
    assert "pooja.m@angelone.in" in processed_recruiter["extracted_emails"]
    assert "AO-TEST-44" in processed_recruiter["extracted_job_codes"]
    assert any("careers.angelone.in" in u for u in processed_recruiter["extracted_links"])
    print("   ✅ Recruiter post accepted and classified as RECRUITER")


def test_post_classifier_noise_filtering():
    """Validates strict filtering of job seekers, EdTech sales, and promotions."""
    classifier = PostClassifier()

    # 1. Job Seeker with #OpenToWork
    job_seeker = {
        "author_name": "Ramesh Kumar",
        "author_headline": "SDET | 5 YOE | #OpenToWork | Looking for immediate opportunities",
        "post_text": "I was impacted by recent layoffs and am actively looking for an SDET role. Please refer me to any open positions in Bangalore. Connect with me!",
    }
    assert classifier.process_raw_post(job_seeker) is None, "Failed: Job seeker #OpenToWork was not filtered!"
    print("   ✅ Job seeker #OpenToWork filtered out successfully")

    # 2. First-person job seeker without headline badge
    job_seeker_first_person = {
        "author_name": "Aakash Verma",
        "author_headline": "QA Engineer at Legacy Corp",
        "post_text": "I am looking for a job as an SDET in Bengaluru. Please refer me or help connect with recruiters. Immediate joiner.",
    }
    assert classifier.process_raw_post(job_seeker_first_person) is None, (
        "Failed: First-person job seeker was not filtered!"
    )
    print("   ✅ First-person job seeker filtered out successfully")

    # 3. Commercial EdTech course spam
    edtech_spam = {
        "author_name": "Automation Academy",
        "author_headline": "Leading SDET Training Institute",
        "post_text": "Become a Full Stack SDET in 12 weeks with 100% placement guarantee! Enroll now for our weekend batch starting Saturday. Register here for free demo class.",
    }
    assert classifier.process_raw_post(edtech_spam) is None, "Failed: EdTech commercial spam was not filtered!"
    print("   ✅ EdTech commercial spam filtered out successfully")

    # 4. Promotion celebration without hiring
    promo_post = {
        "author_name": "Neha Joshi",
        "author_headline": "Senior QA Engineer",
        "post_text": "Thrilled to share my promotion to Lead SDET! Grateful to my manager and colleagues for 4 amazing years at Google.",
    }
    assert classifier.process_raw_post(promo_post) is None, "Failed: Promotion celebration post was not filtered!"
    print("   ✅ Promotion celebration filtered out successfully")


def test_outreach_composer_limits_and_personas():
    """Validates character ceilings and persona-tailored outreach generation."""
    composer = PostOutreachComposer()

    # Engineer lead
    eng_post = {
        "author_name": "Karthik Raja",
        "author_headline": "Senior SDET @ Swiggy",
        "author_role_category": "ENGINEER",
        "company_name": "Swiggy",
        "extracted_job_codes": ["SWIG-901"],
    }
    note_eng = composer.generate_connection_note(eng_post)
    assert len(note_eng) <= 300, f"Connection note exceeded 300 chars: {len(note_eng)}"
    assert "Hi Karthik" in note_eng
    assert "Swiggy SDET referrals" in note_eng
    assert "manjunathhk.netlify.app/" in note_eng
    print(f"   ✅ Engineer connection note generated ({len(note_eng)}/300 chars)")

    # Leader lead
    leader_post = {
        "author_name": "Siddharth Rao",
        "author_headline": "Engineering Manager",
        "author_role_category": "LEADER",
        "company_name": "Okta",
        "extracted_job_codes": [],
    }
    note_lead = composer.generate_connection_note(leader_post)
    assert len(note_lead) <= 300, f"Connection note exceeded 300 chars: {len(note_lead)}"
    assert "expanding your SDET team at Okta" in note_lead
    print(f"   ✅ Leader connection note generated ({len(note_lead)}/300 chars)")

    # InMail pitch
    inmail = composer.generate_inmail_pitch(leader_post)
    assert len(inmail) <= 1000, f"InMail pitch exceeded 1000 chars: {len(inmail)}"
    assert "Playwright" in inmail
    assert "WireMock" in inmail
    print(f"   ✅ InMail pitch generated ({len(inmail)}/1000 chars)")

    # Email draft
    email = composer.generate_email_draft(leader_post, "siddharth@okta.com")
    assert email["to"] == "siddharth@okta.com"
    assert "Senior SDET" in email["subject"]
    assert len(email["body"]) > 50
    print("   ✅ Email draft generated with structured subject and body")


def test_database_hiring_posts_crud():
    """Validates SQLite schema, CRUD operations, status transitions, and stats."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db = ApplicationDatabase(db_path=db_path)

        post_data = {
            "post_id": "post_unit_test_001",
            "author_name": "Rohit Verma",
            "author_headline": "Lead SDET @ Flipkart",
            "author_profile_url": "https://linkedin.com/in/rohit-verma",
            "company_name": "Flipkart",
            "is_dream_org": True,
            "post_url": "https://linkedin.com/feed/update/urn:li:activity:99999",
            "post_text": "We are hiring SDET-2 and SDET-3 for Flipkart supply chain tech. Send resumes to rohit@flipkart.com",
            "posted_at_relative": "1h",
            "extracted_emails": ["rohit@flipkart.com"],
            "extracted_links": ["https://flipkart.careers/sdet"],
            "extracted_job_codes": ["FK-9921"],
            "author_role_category": "LEADER",
            "quality_score": 95,
            "outreach_status": "NEW",
            "custom_dm_draft": "Hi Rohit, saw your post on SDET team expansion at Flipkart.",
            "custom_inmail_draft": "Hi Rohit, I am a Senior SDET with ~7 YOE.",
        }

        # 1. Save post
        assert not db.is_hiring_post_saved(post_data["post_id"])
        db.save_hiring_post(post_data)
        assert db.is_hiring_post_saved(post_data["post_id"])
        print("   ✅ Database save and existence check verified")

        # 2. Query posts
        posts = db.get_hiring_posts(limit=10)
        assert len(posts) == 1
        fetched = posts[0]
        assert fetched["post_id"] == "post_unit_test_001"
        assert fetched["company_name"] == "Flipkart"
        assert fetched["is_dream_org"] is True
        assert fetched["extracted_emails"] == ["rohit@flipkart.com"]
        assert fetched["quality_score"] == 95
        print("   ✅ Database retrieval and JSON column deserialization verified")

        # 3. Update status
        db.update_hiring_post_status("post_unit_test_001", "CONTACTED")
        updated = db.get_hiring_posts(limit=1)[0]
        assert updated["outreach_status"] == "CONTACTED"
        print("   ✅ Status transition NEW -> CONTACTED verified")

        # 4. Check stats
        stats = db.get_hiring_posts_stats()
        assert stats["total_posts"] == 1
        assert stats["contacted"] == 1
        assert stats["dream_orgs"] == 1
        assert stats["leader_posts"] == 1
        print("   ✅ Aggregated stats verified")

        # 5. Delete post
        db.delete_hiring_post("post_unit_test_001")
        assert not db.is_hiring_post_saved("post_unit_test_001")
        assert len(db.get_hiring_posts()) == 0
        print("   ✅ Deletion/dismissal verified")
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def main():
    print("=" * 70)
    print("  VERIFY GATE 72: LINKEDIN HIRING POSTS TRACKER & MULTI-PERSONA ENGINE")
    print("=" * 70)

    print("\n🔍 1. Testing Multi-Persona Inclusivity (Engineers, Leads, Peers, HR)...")
    test_post_classifier_multi_persona()

    print("\n🛡️ 2. Testing Anti-Noise Filtering (Job Seekers, EdTech, Promotions)...")
    test_post_classifier_noise_filtering()

    print("\n✍️ 3. Testing Outreach Generator & Character Budgets (<=300, <=1000 chars)...")
    test_outreach_composer_limits_and_personas()

    print("\n💾 4. Testing SQLite Database CRUD, Status Transitions & Metrics...")
    test_database_hiring_posts_crud()

    print("\n" + "=" * 70)
    print("🎉 GATE 72 PASSED: LinkedIn Hiring Posts Tracker & Classifier Fully Verified!")
    print("=" * 70)


if __name__ == "__main__":
    main()
