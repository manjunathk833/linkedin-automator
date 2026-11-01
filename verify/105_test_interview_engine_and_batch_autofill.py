"""Verification Gate 105: Country Combobox Precision, 2-Phase Batch Form Engine & Interview Router.

Validates:
1. Zero 'British Indian Ocean Territory (+246)' or 'Indiana' contamination across native <select>
   and React-Select comboboxes when selecting 'India' or '+91', plus auto-repair of contaminated controls.
2. UniversalBatchFormFiller 2-Phase 'Extract-Map-BatchExecute' engine (<3s batch fill, strict 60 Days
   notice period, 17 LPA / 27 LPA CTC, and 1-turn custom field batch execution + read-back verification).
3. Direct ATS publish timestamp parsing (`posted_at`), sub-24h LinkedIn sniper URL generation,
   and 3-Tier `InterviewRouter` strategy classification (`TIER_0_POST_AUTHOR`, `TIER_1_SNIPER_APPLY`,
   `TIER_2_REFERRAL_SLA`).
4. 'Low-Key High-Responder' referral candidate scoring (`score_referral_candidate`) — hard-rejecting
   10k+ follower influencers and 'Ex-<Company>' former employees while ranking Post Authors and
   Ex-Dunzo / SJCE Alumni peers at the top.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.batch_form_engine import UniversalBatchFormFiller
from src.autofill.form_mapper import FormFieldMapper
from src.autofill.self_healer import AutofillSelfHealer
from src.ingestion.greenhouse import parse_iso_timestamp
from src.ingestion.workday import parse_workday_posted_on
from src.scraper.job_finder import LinkedInJobFinder
from src.tailor.referral_generator import (
    InterviewRouter,
    ReferralNoteGenerator,
    is_verified_current_employee,
    parse_follower_count,
    score_referral_candidate,
)


async def test_country_and_dial_code_precision() -> None:
    print("🧪 1. Testing Country & Dial Code Combobox Precision (Zero British Indian Ocean Territory)...")
    filler = ATSAssistedFiller(headless=True)
    batch_engine = UniversalBatchFormFiller()

    # Unit-level scorer & exclusion checks
    assert ATSAssistedFiller.is_excluded_territory_option("British Indian Ocean Territory (+246)", "India") is True
    assert ATSAssistedFiller.is_excluded_territory_option("British Indian Ocean Territory (+246)", "+91") is True
    assert ATSAssistedFiller.is_excluded_territory_option("Indiana", "India") is True
    assert ATSAssistedFiller.is_excluded_territory_option("India (+91)", "India") is False
    assert ATSAssistedFiller.is_excluded_territory_option("🇮🇳 India (+91)", "+91") is False

    assert ATSAssistedFiller._score_combobox_option("British Indian Ocean Territory (+246)", "India") == 0
    assert ATSAssistedFiller._score_combobox_option("India (+91)", "India") >= 95
    assert ATSAssistedFiller._score_combobox_option("India", "India") >= 98

    html_fixture = """
    <!DOCTYPE html>
    <html>
    <body>
      <form id="app-form">
        <!-- 1. Native <select> with alphabetical trap (British Indian Ocean Territory at index 0) -->
        <div class="field">
          <label for="native-country">Country / Region *</label>
          <select id="native-country" name="country" required>
            <option value="">Select Country...</option>
            <option value="IO">British Indian Ocean Territory (+246)</option>
            <option value="US-IN">Indiana (US)</option>
            <option value="IN">🇮🇳 India (+91)</option>
          </select>
        </div>

        <!-- 2. React-Select simulated Country Combobox (without dial codes) -->
        <div class="field">
          <label for="rs-country-input">Country of Residence *</label>
          <div class="select__control" id="rs-country-ctrl">
            <div class="select__single-value" id="rs-country-val">British Indian Ocean Territory</div>
            <input id="rs-country-input" class="select__input" role="combobox" type="text" />
          </div>
          <div id="rs-country-menu" style="display:none;">
            <div class="select__option" role="option" data-val="British Indian Ocean Territory">British Indian Ocean Territory</div>
            <div class="select__option" role="option" data-val="India">India</div>
            <div class="select__option" role="option" data-val="Indonesia">Indonesia</div>
          </div>
        </div>

        <!-- 3. Standard fields + Notice Period + CTC + Custom Question -->
        <div class="field">
          <label for="first_name">First Name *</label>
          <input id="first_name" name="first_name" type="text" required />
        </div>
        <div class="field">
          <label for="last_name">Last Name *</label>
          <input id="last_name" name="last_name" type="text" required />
        </div>
        <div class="field">
          <label for="notice_period">Notice Period *</label>
          <input id="notice_period" name="notice_period" type="text" required />
        </div>
        <div class="field">
          <label for="expected_ctc">Expected CTC (LPA) *</label>
          <input id="expected_ctc" name="expected_ctc" type="text" required />
        </div>
        <div class="field">
          <label for="custom_arch_q">Describe your distributed system architecture philosophy *</label>
          <textarea id="custom_arch_q" name="custom_arch_q" required></textarea>
        </div>
      </form>
      <script>
        (() => {
          const rsInput = document.getElementById('rs-country-input');
          const rsMenu = document.getElementById('rs-country-menu');
          const rsVal = document.getElementById('rs-country-val');
          rsInput.addEventListener('click', () => { rsMenu.style.display = 'block'; });
          rsInput.addEventListener('input', () => { rsMenu.style.display = 'block'; });
          document.querySelectorAll('#rs-country-menu .select__option').forEach(opt => {
            opt.addEventListener('click', () => {
              rsVal.innerText = opt.getAttribute('data-val');
              rsMenu.style.display = 'none';
            });
          });
        })();
      </script>
    </body>
    </html>
    """

    async with async_playwright() as pw:
        import json

        from src.autofill.autofill_logger import LEARNED_MAPPINGS_FILE, normalize_field_label_key

        test_key = normalize_field_label_key("Describe your distributed system architecture philosophy *")
        if LEARNED_MAPPINGS_FILE.exists():
            data = json.loads(LEARNED_MAPPINGS_FILE.read_text(encoding="utf-8"))
            if test_key in data.get("mappings", {}):
                del data["mappings"][test_key]
                LEARNED_MAPPINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_fixture)

        # Test native select directly first
        ok_native = await filler._select_react_combobox(page, page.locator("#native-country"), "India")
        assert ok_native is True, "Native select failed to select India"
        selected_val = await page.locator("#native-country").input_value()
        assert selected_val == "IN", f"Expected 'IN' (India), but got '{selected_val}'!"
        print(
            "  ✅ Native <select> selected 'IN' (🇮🇳 India (+91)) and skipped 'British Indian Ocean Territory (+246)'."
        )

        # Now test UniversalBatchFormFiller Phase A (note that #rs-country-val was pre-contaminated with 'British Indian Ocean Territory'!)
        res_a = await batch_engine.inspect_and_autofill_step(page)
        assert res_a["verification"]["verification_passed"] is True, f"Verification failed: {res_a['verification']}"
        rs_committed = (await page.locator("#rs-country-val").inner_text()).strip()
        assert rs_committed == "India", f"Expected auto-repaired 'India', got '{rs_committed}'"
        assert await page.locator("#first_name").input_value() == "Manjunath"
        assert await page.locator("#last_name").input_value() == "H K"
        assert await page.locator("#notice_period").input_value() == "60 Days"
        assert await page.locator("#expected_ctc").input_value() == "27 LPA"
        assert res_a["unmapped_count"] == 1
        unmapped_id = res_a["unmapped_fields"][0]["field_id"]
        print(
            f"  ✅ Phase A batch-filled {res_a['filled_count']} fields in {res_a['elapsed_ms']}ms "
            f"(repaired contaminated country -> 'India', Notice='60 Days', Expected CTC='27 LPA')."
        )

        # Test Phase B: Single-turn custom field batch execution + closed-loop auto-learning
        res_b = await batch_engine.apply_custom_actions(
            page,
            {unmapped_id: "Event-driven contract testing with Playwright, Kafka, and Docker CI sharding."},
        )
        assert res_b["applied_count"] == 1
        assert res_b["learned_count"] == 1
        assert res_b["verification"]["verification_passed"] is True
        assert len(res_b["verification"]["empty_required_fields"]) == 0
        print(f"  ✅ Phase B applied custom field in {res_b['elapsed_ms']}ms and auto-banked 1 learned mapping.")

        # Test Pass 2: Reload fixture and verify Phase A now auto-fills the previously unmapped custom field!
        await page.set_content(html_fixture)
        res_pass2 = await batch_engine.inspect_and_autofill_step(page)
        assert res_pass2["unmapped_count"] == 0, (
            f"Expected 0 unmapped fields on Pass 2 via closed-loop learning, got {res_pass2['unmapped_count']}: {res_pass2['unmapped_fields']}"
        )
        assert (
            await page.locator("#custom_arch_q").input_value()
            == "Event-driven contract testing with Playwright, Kafka, and Docker CI sharding."
        )
        print("  ✅ Pass 2 verified: Closed-loop auto-learning filled custom field in Phase A (0 unmapped fields).")

        # Clean up test-only learned mapping key so production learned_field_mappings.json stays clean
        import json

        from src.autofill.autofill_logger import LEARNED_MAPPINGS_FILE, normalize_field_label_key

        if LEARNED_MAPPINGS_FILE.exists():
            data = json.loads(LEARNED_MAPPINGS_FILE.read_text(encoding="utf-8"))
            mappings = data.get("mappings", {})
            test_key = normalize_field_label_key("Describe your distributed system architecture philosophy *")
            if test_key in mappings:
                del mappings[test_key]
                LEARNED_MAPPINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

        await browser.close()


def test_mapper_and_self_healer_ground_truth() -> None:
    print("🧪 2. Testing FormFieldMapper 60-Day Notice Lock & AutofillSelfHealer Vault Wiring...")
    mapper = FormFieldMapper()
    assert mapper.resolve_field_value("Notice Period") == "60 Days"
    assert mapper.resolve_field_value("Notice Period (in days)", field_type="number") == "60"
    assert mapper.resolve_field_value("Expected CTC") == "27,00,000 INR"
    assert mapper.resolve_field_value("Current CTC") == "17,00,000 INR"

    healer = AutofillSelfHealer()
    assert len(healer.vault_lessons) >= 5, "SelfHealer did not load vault_lessons into memory"
    lesson = healer.find_matching_lesson("ALL_VENDORS", "British Indian Ocean Territory")
    assert lesson is not None, "Expected banked British Indian Ocean Territory lesson in vault"
    print("  ✅ FormFieldMapper ('60 Days') and AutofillSelfHealer vault lookup verified.")


def test_timestamps_sniper_urls_and_interview_router() -> None:
    print("🧪 3. Testing ATS Publish Timestamps, Sub-24h Sniper URLs & 3-Tier InterviewRouter...")
    gh_dt = parse_iso_timestamp("2026-11-01T12:00:00Z")
    assert gh_dt is not None and gh_dt.year == 2026
    wd_dt = parse_workday_posted_on("Posted Today")
    assert wd_dt is not None

    finder = LinkedInJobFinder()
    url_1h = finder.build_search_url(
        keywords="Senior SDET", location="Bengaluru", time_posted="past_1h", sort_by="date"
    )
    assert "f_TPR=r3600" in url_1h and "sortBy=DD" in url_1h
    url_3h = finder.build_search_url(
        keywords="Senior SDET", location="Bengaluru", time_posted="past_3h", sort_by="date"
    )
    assert "f_TPR=r10800" in url_3h

    # Case A: Fresh startup drop (< 2 hours old) -> TIER_1_SNIPER_APPLY
    fresh_startup_job = {
        "company_name": "LinearScale",
        "job_title": "Senior SDET",
        "source": "ashby",
        "is_dream_org": False,
        "posted_at": (datetime.utcnow() - timedelta(hours=1.5)).isoformat(),
        "url": "https://jobs.ashbyhq.com/linearscale/123",
    }
    route_a = InterviewRouter.classify_job_strategy(fresh_startup_job)
    assert route_a["routing_tier"] == "TIER_1_SNIPER_APPLY"
    assert route_a["allow_immediate_apply"] is True
    assert route_a["priority_boost"] == 25

    # Case B: Workday Dream Org -> TIER_2_REFERRAL_SLA (36h hold to preserve referral bonus ownership)
    dream_workday_job = {
        "company_name": "Swiggy",
        "job_title": "Staff SDET",
        "source": "workday",
        "is_dream_org": True,
        "posted_at": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
        "url": "https://swiggy.wd3.myworkdayjobs.com/job/123",
    }
    route_b = InterviewRouter.classify_job_strategy(dream_workday_job)
    assert route_b["routing_tier"] == "TIER_2_REFERRAL_SLA"
    assert route_b["allow_immediate_apply"] is False
    assert route_b["referral_sla_hours"] == 36.0

    # Case C: Job with a matched Hiring Post -> TIER_0_POST_AUTHOR
    matched_posts = [
        {
            "author_name": "Rahul Verma",
            "author_profile_url": "https://www.linkedin.com/in/rahul-verma-sdet/",
            "post_url": "https://www.linkedin.com/posts/rahul-verma_hiring-sdet-activity-123/",
        }
    ]
    route_c = InterviewRouter.classify_job_strategy(fresh_startup_job, matched_posts=matched_posts)
    assert route_c["routing_tier"] == "TIER_0_POST_AUTHOR"
    assert route_c["associated_post_url"] == "https://www.linkedin.com/posts/rahul-verma_hiring-sdet-activity-123/"
    print("  ✅ ATS timestamps, sub-24h Sniper URLs, and 3-Tier InterviewRouter verified.")


def test_low_key_high_responder_referral_scorer() -> None:
    print("🧪 4. Testing 'Low-Key High-Responder' Referral Scorer (Influencer & Ex-Employee Rejection)...")
    assert parse_follower_count("14,200 followers") == 14200
    assert parse_follower_count("12.5K followers") == 12500
    assert parse_follower_count("640 followers") == 640

    # 1. Former employee ('Ex-Swiggy') -> MUST BE REJECTED
    assert is_verified_current_employee("Senior SDET @ Flipkart | Ex-Swiggy", "Swiggy") is False
    ex_emp = score_referral_candidate(
        {
            "name": "Abhishek PR",
            "headline": "Lead QA Engineer | Ex-Swiggy | Automation",
            "profile_url": "https://www.linkedin.com/in/abhishek-pr/",
        },
        target_company="Swiggy",
    )
    assert ex_emp["eligible"] is False
    assert ex_emp["tier"] == "REJECTED_NOT_CURRENT_EMPLOYEE"

    # 2. High-follower Influencer (15k followers / Top Voice) -> MUST BE REJECTED
    influencer = score_referral_candidate(
        {
            "name": "Tech Influencer",
            "headline": "Staff Engineer @ Swiggy | LinkedIn Top Voice | 18K+ followers",
            "followers": "18,400 followers",
            "profile_url": "https://www.linkedin.com/in/tech-influencer/",
        },
        target_company="Swiggy",
    )
    assert influencer["eligible"] is False
    assert influencer["tier"] == "REJECTED_INFLUENCER"

    # 3. Tier S: Someone who posted a hiring update for Swiggy
    post_author = score_referral_candidate(
        {
            "name": "Karthik R",
            "headline": "Engineering Manager - QA @ Swiggy",
            "followers": "920 followers",
            "is_post_author": True,
            "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:739123456/",
            "activity_snippet": "We are hiring Senior SDETs on my team at Swiggy Bengaluru! DM for referral.",
        },
        target_company="Swiggy",
    )
    assert post_author["eligible"] is True
    assert post_author["tier"] == "TIER_S_POST_AUTHOR"
    assert post_author["responder_score"] >= 85

    # 4. Tier A: Shared Ex-Dunzo / SJCE Alumni Peer SDET at Swiggy
    warm_peer = score_referral_candidate(
        {
            "name": "Sandeep M",
            "headline": "Senior SDET at Swiggy | Ex-Dunzo",
            "followers": "540 followers",
            "tenure_months": 8,
        },
        target_company="Swiggy",
    )
    assert warm_peer["eligible"] is True
    assert warm_peer["tier"] == "TIER_A_WARM_PEER_OR_ALUMNI"
    assert warm_peer["responder_score"] >= 80

    # Verify ReferralNoteGenerator pack includes post_acceptance_dm and hiring_posts_content URL
    pack = ReferralNoteGenerator.generate_referral_pack(
        {"company_name": "Swiggy", "job_title": "Staff SDET", "requisition_id": "16779", "location": "Bengaluru"},
        recipient_name="Sandeep",
    )
    assert "hiring_posts_content" in pack["search_urls"]
    assert "ex_dunzo_alumni" in pack["search_urls"]
    assert "post_acceptance_dm" in pack
    assert pack["connection_note_chars"] <= 300
    print(
        f"  ✅ Referral Scorer verified: Ex-Swiggy ({ex_emp['responder_score']}), "
        f"18K Influencer ({influencer['responder_score']}), "
        f"Warm Ex-Dunzo Peer ({warm_peer['responder_score']}), "
        f"Post Author ({post_author['responder_score']})."
    )


async def main() -> None:
    print("\n" + "=" * 70)
    print("🚀 VERIFICATION GATE 105: INTERVIEW ENGINE & BATCH AUTOFILL SUITE")
    print("=" * 70)
    await test_country_and_dial_code_precision()
    test_mapper_and_self_healer_ground_truth()
    test_timestamps_sniper_urls_and_interview_router()
    test_low_key_high_responder_referral_scorer()
    print("\n" + "=" * 70)
    print("🎉 ALL VERIFICATION GATE 105 CHECKS PASSED (100% SUCCESS)!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
