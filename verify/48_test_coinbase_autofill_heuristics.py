"""Verification script for Gate 48: Coinbase Custom Greenhouse Autofill Heuristics & Live Form Autofill.

Validates:
1. Canonical ATS URL resolution mapping Coinbase career URLs directly to Greenhouse embed portal.
2. ATS Vendor Pattern classification for Coinbase custom domain and embed URLs.
3. Vendor schema registry structure for COINBASE_CUSTOM_GREENHOUSE.
4. Live Playwright autofill on the Coinbase position (8054055) asserting zero cross-field collisions.
"""

from __future__ import annotations

import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller, resolve_canonical_ats_url
from src.autofill.vendor_schemas import (
    ATSVendorPattern,
    classify_ats_pattern,
    get_vendor_schema,
    load_candidate_master_data,
)

TARGET_COINBASE_WRAPPER = "https://www.coinbase.com/en-in/careers/positions/8054055?gh_jid=8054055"
TARGET_COINBASE_STANDARD = "https://www.coinbase.com/careers/positions/8054055?gh_jid=8054055"
TARGET_COINBASE_NO_GH = "https://www.coinbase.com/careers/positions/8054055"
EXPECTED_CANONICAL = "https://job-boards.greenhouse.io/embed/job_app?token=8054055&for=coinbase&gh_jid=8054055"


def test_coinbase_canonical_resolution():
    print("\n🧪 Step 1: Testing Coinbase Canonical ATS URL Resolution...")

    res_1 = resolve_canonical_ats_url(TARGET_COINBASE_WRAPPER, company="Coinbase")
    assert res_1 == EXPECTED_CANONICAL, f"Expected {EXPECTED_CANONICAL}, got {res_1}"
    print(f"   ✅ Localized wrapper resolved: {res_1}")

    res_2 = resolve_canonical_ats_url(TARGET_COINBASE_STANDARD, company="Coinbase")
    assert res_2 == EXPECTED_CANONICAL, f"Expected {EXPECTED_CANONICAL}, got {res_2}"
    print(f"   ✅ Standard wrapper resolved: {res_2}")

    res_3 = resolve_canonical_ats_url(TARGET_COINBASE_NO_GH, company="Coinbase")
    assert res_3 == EXPECTED_CANONICAL, f"Expected {EXPECTED_CANONICAL}, got {res_3}"
    print(f"   ✅ Direct position URL resolved: {res_3}")


def test_coinbase_pattern_classification():
    print("\n🧪 Step 2: Testing Coinbase Pattern Classification...")

    p_wrapper = classify_ats_pattern(TARGET_COINBASE_WRAPPER)
    assert p_wrapper == ATSVendorPattern.COINBASE_CUSTOM_GREENHOUSE, (
        f"Expected COINBASE_CUSTOM_GREENHOUSE, got {p_wrapper}"
    )
    print(f"   ✅ Wrapper classified as: {p_wrapper}")

    p_embed = classify_ats_pattern(EXPECTED_CANONICAL)
    assert p_embed == ATSVendorPattern.COINBASE_CUSTOM_GREENHOUSE, f"Expected COINBASE_CUSTOM_GREENHOUSE, got {p_embed}"
    print(f"   ✅ Canonical embed classified as: {p_embed}")


def test_coinbase_vendor_schema():
    print("\n🧪 Step 3: Auditing Coinbase Vendor Schema in Registry...")

    schema = get_vendor_schema(ATSVendorPattern.COINBASE_CUSTOM_GREENHOUSE)
    assert schema, "Coinbase vendor schema not found in registry"
    assert schema["vendor_name"] == "Coinbase Custom Greenhouse"
    selectors = schema.get("selectors", {})
    assert "first_name" in selectors
    assert "last_name" in selectors
    assert "email" in selectors
    assert "phone" in selectors
    assert "location" in selectors
    assert "phone_country" in selectors
    assert "resume" in selectors
    print("   ✅ Schema selectors and fingerprints verified.")


async def test_live_coinbase_autofill():
    print("\n🧪 Step 4: Testing Live Coinbase Greenhouse Autofill...")

    master_data = load_candidate_master_data()
    print(f"   👤 Candidate: {master_data.personal.full_name} ({master_data.personal.email})")

    # Sample resume PDF
    resumes_dir = os.path.join(PROJECT_ROOT, "data", "approved_queue")
    sample_pdf = None
    if os.path.exists(resumes_dir):
        for f in os.listdir(resumes_dir):
            if f.endswith(".pdf"):
                sample_pdf = os.path.join(resumes_dir, f)
                break

    if not sample_pdf or not os.path.exists(sample_pdf):
        sample_pdf = os.path.join(PROJECT_ROOT, "data", "test_resume.pdf")
        with open(sample_pdf, "wb") as f:
            f.write(b"%PDF-1.4 Mock resume content for Gate 48 verification")

    print(f"   📎 Resume path: {sample_pdf}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        filler = ATSAssistedFiller(master_data=master_data)
        result = await filler.fill_ats_page(page, TARGET_COINBASE_WRAPPER, resume_pdf_path=sample_pdf)

        print("\n" + "=" * 65)
        print(f"📊 Results: {result['fields_filled']} fields pre-filled | Resume attached: {result['resume_attached']}")
        print(f"📊 Status: {result['status']} | Active URL: {result['url']}")
        print("=" * 65)

        assert result["status"] == "ready_for_review", f"Expected ready_for_review, got {result['status']}"
        assert result["fields_filled"] >= 15, f"Expected at least 15 fields filled, got {result['fields_filled']}"
        assert result["resume_attached"] is True, "Resume was not attached"

        # Field assertions on active form page (tab switched or navigated)
        active_page = context.pages[-1]
        fn_val = await active_page.locator("input#first_name").input_value()
        ln_val = await active_page.locator("input#last_name").input_value()
        em_val = await active_page.locator("input#email").input_value()
        ph_val = await active_page.locator("input#phone").input_value()

        comp_val_0 = await active_page.locator("input#company-name-0").input_value()
        title_val_0 = await active_page.locator("input#title-0").input_value()
        comp_val_1 = await active_page.locator("input#company-name-1").input_value()
        comp_val_2 = await active_page.locator("input#company-name-2").input_value()

        print(f"   • First Name: '{fn_val}'")
        print(f"   • Last Name:  '{ln_val}'")
        print(f"   • Email:      '{em_val}'")
        print(f"   • Phone:      '{ph_val}'")
        print(f"   • Job 0 (Current): '{comp_val_0}' ({title_val_0})")
        print(f"   • Job 1: '{comp_val_1}'")
        print(f"   • Job 2: '{comp_val_2}'")

        assert fn_val == master_data.personal.first_name, f"Expected {master_data.personal.first_name}, got {fn_val}"
        assert ln_val == master_data.personal.last_name, f"Expected {master_data.personal.last_name}, got {ln_val}"
        clean_phone = master_data.personal.phone.replace("+91", "").strip()
        assert ph_val in (master_data.personal.phone, clean_phone), (
            f"Expected {master_data.personal.phone} or {clean_phone}, got {ph_val}"
        )
        assert comp_val_0 == "Value Labs", f"Expected Value Labs, got {comp_val_0}"
        assert comp_val_1 == "Dunzo", f"Expected Dunzo, got {comp_val_1}"
        assert comp_val_2 == "Tata Elxsi", f"Expected Tata Elxsi, got {comp_val_2}"

        await browser.close()


def main():
    print("=" * 65)
    print("  Testing Gate 48: Coinbase Custom Greenhouse Autofill Heuristics")
    print("=" * 65)

    test_coinbase_canonical_resolution()
    test_coinbase_pattern_classification()
    test_coinbase_vendor_schema()
    asyncio.run(test_live_coinbase_autofill())

    print("\n✅ GATE 48 COINBASE VERIFICATION PASSED SUCCESSFULLY!\n")


if __name__ == "__main__":
    main()
