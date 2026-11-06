"""
Verification Gate: Multi-Tab Hybrid Bulk Apply Engine (`src/autofill/bulk_apply_engine.py`).

Tests:
1. `decode_linkedin_safety_redirect` extracts clean external ATS URLs from `/safety/go/?url=...`.
2. `list_queue_batch` respects `batch_size`, `ignore_tiers`, and `--respect-tiers` (`TIER_2_REFERRAL_SLA`).
3. `purge_unavailable_job` removes stale `.json` and `.pdf` files from a temporary approved queue directory.
4. Multi-tab non-overwriting isolation (`stamp_tab_job_id`, `find_tab_for_job`) ensures 3 jobs open in 3 separate tabs without overwriting each other.
5. `dismiss_overlays` clears synthetic OneTrust / Cookiebot / GDPR consent banners blocking buttons.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.autofill.autofill_logger import AutofillLogger
from src.autofill.bulk_apply_engine import (
    BulkApplyFastTrackEngine,
    classify_job_cohort,
    decode_linkedin_safety_redirect,
    dismiss_overlays,
    find_tab_for_job,
    group_jobs_by_cohort,
    resolve_approved_job_pdf,
    stamp_tab_job_id,
)
from src.browser.cdp_stealth import STEALTH_EVASION_JS


def test_cohort_grouping() -> None:
    jobs = [
        {"job_id": "400", "company": "Siemens", "url": "https://jobs.siemens.com/avature.net/123", "payload": {}},
        {"job_id": "300", "company": "Neuron7", "url": "https://jobs.lever.co/neuron7/abc/apply", "payload": {}},
        {"job_id": "200", "company": "ABB", "url": "https://abb.wd3.myworkdayjobs.com/External/job/1", "payload": {}},
        {"job_id": "100", "company": "Airbnb", "url": "https://boards.greenhouse.io/airbnb/jobs/1", "payload": {}},
    ]
    assert classify_job_cohort(jobs[0]) == (4, "COHORT_4_AUTH_PORTAL")
    assert classify_job_cohort(jobs[1]) == (3, "COHORT_3_CAPTCHA_PREFILL")
    assert classify_job_cohort(jobs[2]) == (2, "COHORT_2_SPA_AUTO")
    assert classify_job_cohort(jobs[3]) == (1, "COHORT_1_FAST_AUTO")

    grouped = group_jobs_by_cohort(jobs)
    assert [j["job_id"] for j in grouped] == ["100", "200", "300", "400"], f"Unexpected order: {grouped}"


def test_decode_safety_redirect() -> None:
    raw = "https://www.linkedin.com/safety/go/?url=https%3A%2F%2Fjobs.lever.co%2Fneuron7%2Ffe2e1697-e326-410b-9a2b-9f8ad338bba5"
    decoded = decode_linkedin_safety_redirect(raw)
    assert decoded == "https://jobs.lever.co/neuron7/fe2e1697-e326-410b-9a2b-9f8ad338bba5", f"Got: {decoded}"
    assert decode_linkedin_safety_redirect("https://boards.greenhouse.io/airbnb/jobs/123") == (
        "https://boards.greenhouse.io/airbnb/jobs/123"
    )


def test_list_queue_batch_and_purge() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        j1 = {
            "job_id": "111111",
            "routing_tier": "TIER_1_SNIPER_APPLY",
            "job_details": {"company": "AlphaCorp", "title": "Senior SDET"},
        }
        j2 = {
            "job_id": "222222",
            "routing_tier": "TIER_2_REFERRAL_SLA",
            "job_details": {"company": "DreamCorp", "title": "Lead QA Automation"},
        }
        with open(os.path.join(tmpdir, "111111.json"), "w", encoding="utf-8") as f:
            json.dump(j1, f)
        with open(os.path.join(tmpdir, "Manjunath_HK_AlphaCorp_111111_Resume.pdf"), "w", encoding="utf-8") as f:
            f.write("%PDF-1.4 dummy")
        with open(os.path.join(tmpdir, "222222.json"), "w", encoding="utf-8") as f:
            json.dump(j2, f)

        engine = BulkApplyFastTrackEngine(approved_dir=tmpdir)

        # 1. With ignore_tiers=True, both jobs are returned
        batch_all = engine.list_queue_batch(batch_size=10, ignore_tiers=True)
        assert len(batch_all) == 2, f"Expected 2 jobs, got {len(batch_all)}"

        # 2. With ignore_tiers=False, TIER_2_REFERRAL_SLA is held back
        batch_filtered = engine.list_queue_batch(batch_size=10, ignore_tiers=False)
        assert len(batch_filtered) == 1
        assert batch_filtered[0]["job_id"] == "111111"

        # 3. Verify PDF resolution
        pdf_resolved = resolve_approved_job_pdf("111111", j1, approved_dir=tmpdir)
        assert pdf_resolved.endswith("Manjunath_HK_AlphaCorp_111111_Resume.pdf")

        # 4. Verify purge_unavailable_job removes both JSON and PDF
        engine.purge_unavailable_job("111111", "AlphaCorp", "No longer accepting applications")
        assert not os.path.exists(os.path.join(tmpdir, "111111.json"))
        assert not os.path.exists(os.path.join(tmpdir, "Manjunath_HK_AlphaCorp_111111_Resume.pdf"))


async def test_multi_tab_isolation_and_overlay_buster() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # Open 3 separate tabs for 3 different jobs and verify zero tab overwriting
        tabs = {}
        for jid, company in [("job_101", "Alpha"), ("job_102", "Beta"), ("job_103", "Gamma")]:
            pg = await context.new_page()
            await pg.set_content(
                f"""
                <html><body>
                    <h1>{company} Career Portal</h1>
                    <div id="onetrust-banner-sdk" class="cookie-banner">
                        <button id="onetrust-accept-btn-handler" onclick="document.getElementById('onetrust-banner-sdk').style.display='none'">Accept All Cookies</button>
                    </div>
                    <div class="gdpr-privacy-modal" id="gdpr-box">
                        <button onclick="document.getElementById('gdpr-box').remove()">Agree & Proceed</button>
                    </div>
                    <div class="privacyAgreementDialogWrapper-2Q4v3" id="ef-box">
                        <button onclick="document.getElementById('ef-box').remove()">OK</button>
                    </div>
                    <input id="cntryFields.localFirstName" value="Manjunath" />
                    <input id="phoneWidget.countryPhoneCode" value="IND_91" />
                    <input id="Contact_Information_phone" type="tel" value="+917337813770" />
                </body></html>
                """
            )
            await stamp_tab_job_id(pg, jid)
            tabs[jid] = pg

        # Verify all 3 tabs coexist independently and can be looked up by job_id
        for jid, company in [("job_101", "Alpha"), ("job_102", "Beta"), ("job_103", "Gamma")]:
            found_pg = await find_tab_for_job(context, jid)
            assert found_pg is not None, f"Tab for {jid} not found!"
            h1_txt = await found_pg.locator("h1").inner_text()
            assert company in h1_txt, f"Tab overwrite detected! Expected {company}, got {h1_txt}"

            # Test overlay buster & post-resume-parse sanitizer on each tab
            clicked = await dismiss_overlays(found_pg)
            assert "#onetrust-accept-btn-handler" in clicked, f"OneTrust not dismissed: {clicked}"
            assert ".privacyAgreementDialogWrapper-2Q4v3 button" in clicked, (
                f"Eightfold dialog not dismissed: {clicked}"
            )
            assert any("Agree & Proceed" in c for c in clicked), f"GDPR modal not dismissed: {clicked}"

            eng = BulkApplyFastTrackEngine()
            await eng._sanitize_post_resume_parse(found_pg)
            local_fn = await found_pg.locator("input[id='cntryFields.localFirstName']").input_value()
            assert local_fn == "", f"Expected cleared localFirstName, got {local_fn!r}"
            clean_ph = await found_pg.locator("#Contact_Information_phone").input_value()
            assert clean_ph == "7337813770", f"Expected stripped +91 phone, got {clean_ph!r}"

        # Verify Action-Scoped Flight Recorder & hCaptcha-safe STEALTH_EVASION_JS
        test_pg = tabs["job_101"]
        await test_pg.evaluate(STEALTH_EVASION_JS)
        has_own_wd = await test_pg.evaluate(
            "() => Object.getOwnPropertyDescriptor(navigator, 'webdriver') !== undefined"
        )
        assert not has_own_wd, "STEALTH_EVASION_JS must NEVER define an own-property 'webdriver' on navigator instance!"

        snap = await AutofillLogger.get_logger().record_flight_snapshot(
            page=test_pg,
            job_id="job_101",
            company="Alpha",
            vendor="EIGHTFOLD_AI",
            status="NEEDS_AGENT",
            reason="Unit test flight snapshot",
        )
        assert snap["job_id"] == "job_101"
        assert snap["visible_controls_count"] >= 2
        assert len(json.dumps(snap)) < 15000, "Flight snapshot must remain compact (<15 KB)!"

        await browser.close()


if __name__ == "__main__":
    test_decode_safety_redirect()
    test_cohort_grouping()
    test_list_queue_batch_and_purge()
    asyncio.run(test_multi_tab_isolation_and_overlay_buster())
    print("✅ PASS: Multi-Tab BulkApplyFastTrackEngine, Cohort Grouping & Flight Recorder checks succeeded.")
