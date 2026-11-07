"""
Instahyre Curated Product & AI Startup Ingestion Collector.
Discovers and extracts curated SDET, AI QA, and Playwright roles from instahyre.com,
normalizing them into standardized JobListing objects for the application queue.
Supports authenticated candidate opportunity extraction via persistent browser session,
real JSON-LD <=3-day datePosted freshness verification, and curated skill feed parsing.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import re
from datetime import datetime
from typing import Any

import httpx

from src.browser.cdp_stealth import DEFAULT_STEALTH_DIR
from src.ingestion.filters import is_india_or_remote_location, is_sdet_title
from src.storage.models import JobListing

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def clean_html_text(raw_html: str) -> str:
    """Strips HTML tags, decodes entities, and collapses whitespace."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class InstahyreCollector:
    """Collector for instahyre.com curated tech feeds and candidate opportunities."""

    BASE_URL = "https://www.instahyre.com"
    CURATED_SLUGS = (
        "playwright-jobs-in-bangalore",
        "remote-playwright-jobs",
        "remote-automation-testing-jobs",
        "sdet-jobs-in-bangalore",
    )

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def parse_job_payload(self, item: dict[str, Any], filter_sdet: bool = True) -> JobListing | None:
        """Parses a structured JSON job object from Instahyre internal feeds or API responses."""
        raw_id = str(item.get("id") or item.get("job_id") or "")
        if not raw_id:
            return None

        title = str(item.get("title") or item.get("job_title") or item.get("position") or "").strip()
        if not title:
            return None

        if filter_sdet and not is_sdet_title(title):
            return None

        company = str(
            item.get("company_name")
            or item.get("company")
            or item.get("employer_name")
            or "Instahyre Verified Employer"
        ).strip()

        location = str(item.get("location") or item.get("city") or "Bengaluru, India").strip()
        if filter_sdet and not is_india_or_remote_location(location):
            return None

        is_remote = bool(
            re.search(r"\bremote\b", location, re.IGNORECASE)
            or re.search(r"\bremote\b", title, re.IGNORECASE)
            or item.get("is_remote")
        )

        job_url = str(item.get("url") or item.get("job_url") or f"{self.BASE_URL}/job-{raw_id}")
        if not job_url.startswith("http"):
            job_url = f"{self.BASE_URL}/{job_url.lstrip('/')}"

        desc_raw = str(item.get("description") or item.get("job_description") or "")
        desc_clean = clean_html_text(desc_raw) or f"{title} opportunity at {company}. High-impact QA Automation role."

        salary = str(item.get("salary") or item.get("compensation") or "")

        return JobListing(
            id=f"instahyre_{raw_id}",
            source="instahyre",
            company_name=company,
            job_title=title,
            location=location,
            is_remote=is_remote,
            is_dream_org=False,
            job_description_raw=desc_raw or desc_clean,
            job_description_clean=desc_clean,
            url=job_url,
            salary_range=salary or None,
            discovered_at=datetime.utcnow(),
            status="pending",
        )

    def parse_html_page(self, html_text: str, filter_sdet: bool = True) -> list[JobListing]:
        """Extracts job cards from server-rendered HTML or embedded script JSON."""
        listings: list[JobListing] = []
        if not html_text:
            return listings

        for s in re.findall(
            r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html_text, re.DOTALL
        ):
            try:
                data = json.loads(s)
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if it.get("@type") == "JobPosting":
                        jid = str(it.get("identifier", {}).get("value") or hash(it.get("title", "")) % 100000)
                        hiring_org = it.get("hiringOrganization", {})
                        comp = hiring_org.get("name") if isinstance(hiring_org, dict) else str(hiring_org)
                        raw_payload = {
                            "id": jid,
                            "title": it.get("title"),
                            "company_name": comp,
                            "location": it.get("jobLocation", {})
                            .get("address", {})
                            .get("addressLocality", "Bengaluru"),
                            "description": it.get("description"),
                            "url": it.get("url"),
                        }
                        listing = self.parse_job_payload(raw_payload, filter_sdet=filter_sdet)
                        if listing:
                            listings.append(listing)
            except Exception:
                pass

        if not listings:
            card_regex = re.compile(
                r"<div[^>]*class=[\"'][^\"']*(?:opportunity-row|job-card)[^\"']*[\"'][^>]*>(.*?)</div>\s*</div>",
                re.DOTALL | re.IGNORECASE,
            )
            for m in card_regex.finditer(html_text):
                block = m.group(1)
                title_m = re.search(r"<span[^>]*class=[\"'][^\"']*position[^\"']*[\"'][^>]*>([^<]+)</span>", block)
                comp_m = re.search(r"<span[^>]*class=[\"'][^\"']*company-name[^\"']*[\"'][^>]*>([^<]+)</span>", block)
                link_m = re.search(r"href=[\"'](/job-[^\"']+)[\"']", block)

                if title_m and comp_m:
                    title = title_m.group(1).strip()
                    comp = comp_m.group(1).strip()
                    href = link_m.group(1).strip() if link_m else "/job-instahyre"
                    jid_m = re.search(r"/job-(\d+)", href)
                    jid = jid_m.group(1) if jid_m else "instahyre"

                    raw_payload = {
                        "id": jid,
                        "title": title,
                        "company_name": comp,
                        "location": "Bengaluru, India",
                        "url": f"{self.BASE_URL}{href}",
                    }
                    listing = self.parse_job_payload(raw_payload, filter_sdet=filter_sdet)
                    if listing:
                        listings.append(listing)

        return listings

    async def fetch_opportunities_via_browser(
        self,
        headless: bool = True,
        limit: int = 30,
        filter_sdet: bool = True,
        max_age_days: float = 3.0,
    ) -> list[JobListing]:
        """
        Extracts pre-matched opportunities from https://www.instahyre.com/candidate/opportunities/
        using persistent stealth browser session (bypassing Cloudflare Turnstile).
        Strictly verifies authentic Schema.org JSON-LD datePosted on each requisition
        and enforces <= max_age_days (default: 3 days), eliminating historical stale mandates.
        """
        listings: list[JobListing] = []
        if not os.path.exists(DEFAULT_STEALTH_DIR):
            return listings

        now = datetime.utcnow()

        self.last_status = "OK"
        try:
            from playwright.async_api import async_playwright

            from src.browser.cdp_stealth import (
                ensure_cdp_page_target,
                is_cdp_port_open,
                launch_stealth_browser,
            )

            async with async_playwright() as p:
                owns_context = False
                ctx = None
                if is_cdp_port_open(9222):
                    ensure_cdp_page_target(9222)
                    browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=10000)
                    ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
                else:
                    ctx = await launch_stealth_browser(p, headless=headless)
                    owns_context = True

                page = await ctx.new_page()
                try:
                    await page.goto(
                        f"{self.BASE_URL}/candidate/opportunities/?matching=true",
                        timeout=25000,
                        wait_until="domcontentloaded",
                    )
                    await asyncio.sleep(2.5)

                    raw_opps = await page.evaluate(
                        """() => {
                            const el = (
                                document.querySelector('[ng-controller="candidateOpportunitiesCtrl"]') ||
                                document.querySelector('.employer-block') ||
                                document.querySelector('.employer-row') ||
                                document.querySelector('[ng-controller]')
                            );
                            if (!el || !window.angular) return [];
                            const scope = window.angular.element(el).scope();
                            if (!scope) return [];
                            const opps = scope.opportunities || scope._opportunities_cached || scope.opps || [];
                            return opps.map(o => ({
                                id: String(o.id || (o.job && o.job.id) || ''),
                                job_id: String(o.job_id || (o.job && o.job.id) || ''),
                                title: o.job ? (o.job.title || o.job.candidate_title || '') : '',
                                company: o.employer ? (o.employer.company_name || '') : '',
                                location: o.job ? (o.job.locations || 'Bengaluru') : 'Bengaluru',
                                skills: o.job ? (o.job.keywords || o.job.skills || []) : [],
                                summary: o.employer ? (o.employer.instahyre_note || o.employer.summary || '') : '',
                                opportunity_url: o.job ? (o.job.opportunity_url || '') : '',
                            }));
                        }"""
                    )

                    # Sort by numeric job_id descending so the newest requisitions are inspected first
                    raw_opps.sort(
                        key=lambda x: int(x.get("job_id") or 0) if str(x.get("job_id") or "").isdigit() else 0,
                        reverse=True,
                    )

                    stale_streak = 0
                    for o in raw_opps:
                        jid = o.get("job_id") or o.get("id")
                        title = o.get("title") or ""
                        company = o.get("company") or "Instahyre Verified Employer"
                        location = o.get("location") or "Bengaluru, India"
                        opp_path = o.get("opportunity_url") or f"/job-{jid}"
                        if not jid or not title:
                            continue

                        if filter_sdet and not is_sdet_title(title):
                            continue

                        canonical_url = f"{self.BASE_URL}{opp_path}" if opp_path.startswith("/") else opp_path

                        # STRICT DATE AUDIT: Inspect Schema.org JSON-LD datePosted on the actual job page
                        posted_dt = None
                        try:
                            await page.goto(canonical_url, timeout=12000, wait_until="domcontentloaded")
                            date_str = await page.evaluate(
                                """() => {
                                    const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
                                    for (const s of scripts) {
                                        try {
                                            const d = JSON.parse(s.innerText);
                                            if (d.datePosted) return d.datePosted;
                                        } catch(e) {}
                                    }
                                    return null;
                                }"""
                            )
                            if date_str:
                                dt = datetime.fromisoformat(date_str)
                                age_days = (now - dt).total_seconds() / 86400.0
                                if age_days > max_age_days:
                                    # Stale historical mandate (>max_age_days) — REJECT
                                    stale_streak += 1
                                    if stale_streak >= 3:
                                        break
                                    continue
                                stale_streak = 0
                                posted_dt = dt
                            else:
                                # If datePosted cannot be verified on Instahyre, discard to prevent false positives
                                continue
                        except Exception as date_err:
                            _ = date_err
                            continue

                        if not posted_dt:
                            continue

                        skills_text = ", ".join(o.get("skills", []))
                        summary_text = o.get("summary", "")
                        desc = f"{title} at {company} in {location}. Skills: {skills_text}. {summary_text}".strip()

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
                            posted_at=posted_dt,
                            discovered_at=now,
                            status="pending",
                        )
                        listings.append(listing)
                        if len(listings) >= limit:
                            break

                finally:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    if owns_context and ctx:
                        try:
                            await ctx.close()
                        except Exception:
                            pass
        except Exception as e:
            self.last_status = f"ERROR: {e}"
            print(f"⚠️ InstahyreCollector browser opportunity extraction warning: {e}")

        return listings

    async def fetch_feed_jobs(
        self,
        slug: str,
        filter_sdet: bool = True,
        max_age_days: float = 3.0,
    ) -> list[JobListing]:
        """
        Fetches jobs from a specific curated skill slug on Instahyre.
        Falls back to authenticated opportunity extraction with <=3-day freshness check.
        """
        clean_slug = slug.strip("/ ")
        url = f"{self.BASE_URL}/{clean_slug}/"
        results: list[JobListing] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    results = self.parse_html_page(resp.text, filter_sdet=filter_sdet)
        except Exception:
            pass

        if not results:
            try:
                results = await self.fetch_opportunities_via_browser(
                    headless=True, limit=25, filter_sdet=filter_sdet, max_age_days=max_age_days
                )
            except Exception as e:
                print(f"⚠️ InstahyreCollector browser fallback warning: {e}")

        return results

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        """Fetches jobs for a target company slug on Instahyre."""
        url = f"{self.BASE_URL}/company/{slug}/"
        results: list[JobListing] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    items = self.parse_html_page(resp.text, filter_sdet=filter_sdet)
                    for it in items:
                        it.company_name = company_name
                    results.extend(items)
        except Exception as e:
            print(f"⚠️ InstahyreCollector board warning for {company_name} ({slug}): {e}")

        return results
