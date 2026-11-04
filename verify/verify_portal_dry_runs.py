#!/usr/bin/env python3
"""
Verification Script for Hirist & Instahyre Authenticated Live Extraction
Tests Playwright selectors, data normalization, and <3-day time filters.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta

from playwright.async_api import async_playwright

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.browser.cdp_stealth import DEFAULT_STEALTH_DIR, launch_stealth_browser
from src.ingestion.filters import is_sdet_title
from src.storage.models import JobListing

INSTAHYRE_LEDGER_PATH = os.path.join(PROJECT_ROOT, "data", "logs", "instahyre_seen_ledger.json")


def parse_relative_age_days(text: str) -> float | None:
    """
    Parses relative age strings: 'Posted today', 'Posted 1 day ago', 'Posted 2 days ago',
    'Posted 3 weeks ago', 'Posted 1 month ago', '2 hours ago'.
    Returns the age in days as float, or None if no match.
    """
    if not text:
        return None
    t = text.lower()
    if "today" in t or "just now" in t or "hour" in t or "minute" in t:
        return 0.0
    m_day = re.search(r"(\d+)\s+day", t)
    if m_day:
        return float(m_day.group(1))
    m_week = re.search(r"(\d+)\s+week", t)
    if m_week:
        return float(m_week.group(1)) * 7.0
    m_month = re.search(r"(\d+)\s+month", t)
    if m_month:
        return float(m_month.group(1)) * 30.0
    return None


async def verify_hirist_feed_freshness(max_age_days: float = 3.0) -> list[JobListing]:
    """Extracts live jobs from Hirist /jobfeed enforcing max_age_days <= 3."""
    listings: list[JobListing] = []
    print(f"Testing Hirist /jobfeed extraction with <={max_age_days}d freshness filter...")
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            DEFAULT_STEALTH_DIR,
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        page = await ctx.new_page()
        try:
            await page.goto("https://www.hirist.tech/jobfeed", timeout=25000, wait_until="domcontentloaded")
            await asyncio.sleep(2.5)

            raw_cards = await page.eval_on_selector_all(
                ".joblist-card-v2",
                """els => els.map(el => {
                    const link = el.querySelector('a[href*="/j/"]');
                    const href = link ? link.getAttribute('href') : '';
                    const fullText = el.innerText.trim();
                    const lines = fullText.split('\\n').map(l => l.trim()).filter(Boolean);
                    const title = lines[0] || '';
                    return { href, title, lines, fullText };
                })""",
            )

            for c in raw_cards:
                href = c.get("href") or ""
                lines = c.get("lines") or []
                raw_title = c.get("title") or ""
                if not href or not raw_title:
                    continue

                company = "Hirist Enterprise"
                clean_title = raw_title
                if " - " in raw_title:
                    parts = raw_title.split(" - ", 1)
                    company = parts[0].strip()
                    clean_title = parts[1].strip()

                if not (is_sdet_title(raw_title) or is_sdet_title(clean_title)):
                    continue

                # Freshness Check (<= 3.0 days)
                posted_line = next((l for l in lines if "posted" in l.lower()), "")
                age_days = parse_relative_age_days(posted_line)
                if age_days is not None and age_days > max_age_days:
                    # Drop stale jobs (>3d)
                    continue

                posted_dt = datetime.utcnow() - timedelta(days=age_days) if age_days is not None else datetime.utcnow()

                id_match = re.search(r"-(\d+)", href)
                raw_id = id_match.group(1) if id_match else re.sub(r"\D", "", href)

                salary = None
                location = "Bengaluru, India"
                for l in lines[1:5]:
                    if "LPA" in l or "₹" in l:
                        salary = l
                    elif any(
                        city in l
                        for city in ("Bangalore", "Bengaluru", "Hyderabad", "Pune", "Remote", "Noida", "Mumbai")
                    ):
                        location = l

                canonical_url = f"https://www.hirist.tech{href.split('?')[0]}"
                listing = JobListing(
                    id=f"hirist_{raw_id}",
                    source="hirist",
                    company_name=company,
                    job_title=clean_title,
                    location=location,
                    is_remote="remote" in location.lower(),
                    is_dream_org=False,
                    job_description_raw=c.get("fullText", ""),
                    job_description_clean=c.get("fullText", ""),
                    url=canonical_url,
                    salary_range=salary,
                    posted_at=posted_dt,
                    discovered_at=datetime.utcnow(),
                    status="pending",
                )
                listings.append(listing)
        finally:
            await ctx.close()

    print(f"✅ Hirist /jobfeed successfully extracted {len(listings)} FRESH (<=3d) SDET listings.")
    return listings


async def verify_instahyre_feed_freshness(max_age_days: float = 3.0) -> list[JobListing]:
    """Extracts live jobs from Instahyre /candidate/opportunities/ enforcing ledger freshness."""
    listings: list[JobListing] = []
    print(f"Testing Instahyre extraction with <={max_age_days}d ledger freshness...")

    os.makedirs(os.path.dirname(INSTAHYRE_LEDGER_PATH), exist_ok=True)
    ledger: dict[str, dict[str, str]] = {}
    if os.path.exists(INSTAHYRE_LEDGER_PATH):
        try:
            with open(INSTAHYRE_LEDGER_PATH, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception:
            ledger = {}

    p, ctx, page = await launch_stealth_browser(headless=False)
    now = datetime.utcnow()
    try:
        await page.goto(
            "https://www.instahyre.com/candidate/opportunities/?matching=true",
            timeout=25000,
            wait_until="domcontentloaded",
        )
        await asyncio.sleep(2.5)

        raw_opps = await page.evaluate(
            """() => {
                const el = document.querySelector('.employer-row') || document.querySelector('[ng-controller]');
                if (!el || !window.angular) return [];
                const scope = window.angular.element(el).scope();
                if (!scope) return [];
                const opps = scope.opportunities || scope.opps || [];
                return opps.map(o => ({
                    id: String(o.id || (o.job && o.job.id) || ''),
                    job_id: String(o.job_id || (o.job && o.job.id) || ''),
                    title: o.job ? o.job.title : '',
                    company: o.employer ? o.employer.company_name : '',
                    location: o.job ? (o.job.locations || 'Bengaluru') : 'Bengaluru',
                    skills: o.job ? (o.job.skills || []) : [],
                    summary: o.employer ? (o.employer.summary || '') : '',
                }));
            }"""
        )

        for o in raw_opps:
            jid = o.get("job_id") or o.get("id")
            title = o.get("title") or ""
            company = o.get("company") or "Instahyre Verified Employer"
            location = o.get("location") or "Bengaluru, India"
            if not jid or not title:
                continue

            if not is_sdet_title(title):
                continue

            # Check ledger freshness
            record = ledger.get(jid)
            if record:
                first_seen_str = record.get("first_seen_at")
                if first_seen_str:
                    try:
                        first_seen_dt = datetime.fromisoformat(first_seen_str)
                        age_days = (now - first_seen_dt).total_seconds() / 86400.0
                        if age_days > max_age_days:
                            continue  # Drop jobs seen more than 3 days ago
                    except Exception:
                        pass
            else:
                ledger[jid] = {
                    "first_seen_at": now.isoformat(),
                    "title": title,
                    "company": company,
                }

            canonical_url = f"https://www.instahyre.com/job-{jid}"
            desc = f"{title} at {company} in {location}. Skills: {', '.join(o.get('skills', []))}. {o.get('summary', '')}".strip()

            listing = JobListing(
                id=f"instahyre_{jid}",
                source="instahyre",
                company_name=company,
                job_title=title,
                location=location,
                is_remote="remote" in location.lower(),
                is_dream_org=False,
                job_description_raw=desc,
                job_description_clean=desc,
                url=canonical_url,
                posted_at=now,
                discovered_at=now,
                status="pending",
            )
            listings.append(listing)

        # Save updated ledger
        with open(INSTAHYRE_LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)

    finally:
        await ctx.close()
        await p.stop()

    print(f"✅ Instahyre successfully extracted {len(listings)} FRESH (<=3d) SDET listings.")
    return listings


async def main():
    print("=" * 65)
    print("PORTAL FRESHNESS VERIFICATION GATE (<3 DAYS TIME FILTER)")
    print("=" * 65)
    h_jobs = await verify_hirist_feed_freshness(max_age_days=3.0)
    for j in h_jobs[:5]:
        print(
            f"  [Hirist Fresh] {j.company_name} | {j.job_title} | Posted: {j.posted_at.strftime('%Y-%m-%d')} | {j.url}"
        )

    i_jobs = await verify_instahyre_feed_freshness(max_age_days=3.0)
    for j in i_jobs[:5]:
        print(
            f"  [Instahyre Fresh] {j.company_name} | {j.job_title} | Discovered: {j.discovered_at.strftime('%Y-%m-%d')} | {j.url}"
        )

    print("\nFRESHNESS AUDIT SUMMARY:")
    print(f"Total Hirist Fresh SDET jobs (<=3d):    {len(h_jobs)}")
    print(f"Total Instahyre Fresh SDET jobs (<=3d): {len(i_jobs)}")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
