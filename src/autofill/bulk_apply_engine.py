"""
Multi-Tab Hybrid Deterministic-Agentic Batch Application Engine (`BulkApplyFastTrackEngine`).

Implements the "Map-Stage-Intervene" Hybrid Pattern:
1. Opens a dedicated browser tab (`context.new_page()`) for each job in a batch wave (default 5 tabs)
   and stamps `window.__agy_job_id = job_id` so jobs NEVER overwrite each other's tab state.
2. Runs a Pre-Flight Cookie & Consent Overlay Buster (`dismiss_overlays`) on every tab to clear
   OneTrust, Cookiebot, TrustArc, GDPR, and modal banners before inspecting or clicking buttons.
3. Deterministically resolves closed jobs (`JOB_UNAVAILABLE` -> purges & closes tab), 1-click portals,
   LinkedIn Easy Apply, and 100%-filled Phase A ATS forms (`APPLIED` -> screenshots, verifies, marks
   applied in SQLite, & closes tab).
4. Leaves complex/multi-step/custom-question tabs OPEN and pre-filled, returning a compact JSON
   handoff digest (`job_id`, `url`, `vendor`, `unmapped_fields`, `visible_buttons`) so the AI Agent
   can intervene on each staged tab in 1 targeted turn with minimal token burn.
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright

from src.autofill.autofill_logger import AutofillLogger
from src.autofill.autofill_verifier import SubmissionVerifier
from src.autofill.batch_form_engine import UniversalBatchFormFiller
from src.autofill.vendor_schemas import classify_ats_pattern, load_candidate_master_data


def ensure_cdp_page_target(cdp_url: str = "http://127.0.0.1:9222") -> None:
    """Ensures at least one browser page target exists on macOS Chrome before connect_over_cdp."""
    try:
        with urllib.request.urlopen(f"{cdp_url}/json/list", timeout=2) as resp:
            targets = json.loads(resp.read().decode("utf-8"))
        page_targets = [t for t in targets if t.get("type") == "page"]
        if not page_targets:
            req = urllib.request.Request(f"{cdp_url}/json/new?about:blank", method="PUT")
            urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass


def ensure_persistent_cdp_browser(
    cdp_url: str = "http://127.0.0.1:9222", dashboard_url: str = "http://127.0.0.1:8000"
) -> None:
    """
    Ensures the persistent headful Chrome session is running on port 9222 using
    native macOS Google Chrome (zero automation flags) so CLI subcommands can
    connect and disconnect cleanly without closing tabs or triggering hCaptcha flags.
    """
    import sys

    from src.browser.cdp_stealth import (
        DEFAULT_STEALTH_DIR,
        MACOS_CHROME_BIN,
        _spawn_native_macos_chrome,
        clean_stale_browser_processes,
        is_cdp_port_open,
    )

    if not is_cdp_port_open(9222):
        clean_stale_browser_processes(DEFAULT_STEALTH_DIR)
        if sys.platform == "darwin" and os.path.exists(MACOS_CHROME_BIN):
            try:
                _spawn_native_macos_chrome(DEFAULT_STEALTH_DIR)
            except Exception:
                pass
        for _ in range(20):
            if is_cdp_port_open(9222):
                break
            time.sleep(0.3)
    ensure_cdp_page_target(cdp_url)


def decode_linkedin_safety_redirect(href: str) -> str:
    """Extracts the destination URL from a LinkedIn `/safety/go/?url=...` anchor."""
    if not href:
        return ""
    if "/safety/go/" in href or "url=" in href:
        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        if qs.get("url"):
            return urllib.parse.unquote(qs["url"][0])
    return href


def resolve_approved_job_pdf(job_id: str, payload: dict[str, Any], approved_dir: str = "data/approved_queue") -> str:
    """Resolves the tailored or standard PDF resume path for an approved job."""
    for key in ("generated_pdf_path", "resume_pdf_path"):
        cand = payload.get(key)
        if cand and os.path.exists(cand):
            return os.path.abspath(cand)

    direct = os.path.join(approved_dir, f"resume_{job_id}.pdf")
    if os.path.exists(direct):
        return os.path.abspath(direct)

    comp = (payload.get("job_details", {}).get("company") or payload.get("company_name") or "").strip()
    num_id = "".join(re.findall(r"\d+", str(job_id)))[:8]
    for pdf_f in glob.glob(os.path.join(approved_dir, "*.pdf")):
        base_f = os.path.basename(pdf_f).lower()
        if (num_id and num_id in base_f) or (comp and comp.lower().split()[0] in base_f):
            return os.path.abspath(pdf_f)

    return ""


async def dismiss_overlays(page: Page) -> list[str]:
    """
    Universal Pre-Flight Cookie, GDPR & Banner Overlay Buster.
    Clicks standard consent accept buttons (OneTrust, Cookiebot, TrustArc, Osano, custom)
    and removes pointer-blocking consent backdrops without touching application modals.
    """
    dismissed: list[str] = []
    try:
        res = await page.evaluate(
            """() => {
                const clicked = [];
                // 1. Known high-confidence vendor selectors (OneTrust, Cookiebot, TrustArc, Osano, Syrenis Cassie)
                const selectors = [
                    '#onetrust-accept-btn-handler',
                    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
                    '#CybotCookiebotDialogBodyButtonAccept',
                    '#truste-consent-button',
                    '.osano-cm-accept-all',
                    'button[data-automation-id="legalNoticeAcceptButton"]',
                    '#cassie_accept_all_pre_banner',
                    '#cassie-widget button[id*="accept" i]',
                    'button#cookie-accept',
                    'button[id*="cookie-accept" i]',
                    'button[id*="accept-cookies" i]',
                    'button[class*="cookie-accept" i]',
                    '.privacyAgreementDialogWrapper-2Q4v3 button',
                    'div[role="dialog"][oktext="OK"] button',
                    '[class*="privacyAgreement"] button'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            el.click();
                            clicked.push(sel);
                        }
                    }
                }

                // 2. Semantic scan inside cookie/consent/privacy containers
                const acceptRe = /^(accept all( cookies)?|allow all( cookies)?|accept cookies|i agree|agree & proceed|agree and proceed|got it|accept|ok, got it)$/i;
                const candidates = Array.from(document.querySelectorAll('button, a[role="button"], input[type="button"]'));
                for (const btn of candidates) {
                    const r = btn.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    const txt = (btn.innerText || btn.value || '').trim();
                    if (!acceptRe.test(txt)) continue;

                    // Verify button or ancestor is related to cookie/consent/banner/gdpr/privacy/cassie
                    let curr = btn;
                    let isOverlay = false;
                    for (let d = 0; d < 6 && curr; d++) {
                        const idCls = ((curr.id || '') + ' ' + (curr.className || '') + ' ' + (curr.getAttribute('aria-label') || '')).toLowerCase();
                        if (/cookie|consent|gdpr|onetrust|cybot|trustarc|privacy|banner|cassie|syrenis/i.test(idCls)) {
                            isOverlay = true;
                            break;
                        }
                        curr = curr.parentElement;
                    }
                    if (isOverlay) {
                        btn.click();
                        clicked.push('text:' + txt);
                    }
                }

                // 3. Remove persistent pointer-blocking cookie overlays if still obstructing
                document.querySelectorAll('#cassie-widget, .syrenis-cookie-widget, .cassie-overlay, .onetrust-pc-dark-filter').forEach(el => {
                    el.style.display = 'none';
                    el.style.pointerEvents = 'none';
                });
                return clicked;
            }"""
        )
        if isinstance(res, list) and res:
            dismissed.extend(res)
            await asyncio.sleep(0.5)
    except Exception:
        pass
    return dismissed


async def stamp_tab_job_id(page: Page, job_id: str) -> None:
    """
    Stamps `window.__agy_job_id` and `window.name` on the tab, binds native CDP dialog auto-accept
    without injecting `add_init_script` into cross-origin CAPTCHA iframes, and attaches the
    Action-Scoped Network Flight Recorder.
    """
    if not job_id:
        return
    try:
        if not getattr(page, "_agy_dialog_bound", False):
            page.on("dialog", lambda d: asyncio.create_task(d.accept()))
            page._agy_dialog_bound = True
        AutofillLogger.get_logger().attach_network_flight_recorder(page)
        await page.evaluate(
            """(jid) => {
                window.__agy_job_id = jid;
                if (!window.name || !window.name.startsWith('agy_job_')) {
                    window.name = 'agy_job_' + jid;
                }
            }""",
            str(job_id),
        )
    except Exception:
        pass


def classify_job_cohort(job: dict[str, Any]) -> tuple[int, str]:
    """
    Classifies an approved job into one of 4 deterministic execution cohorts so fast auto-submitting
    jobs execute first and never get blocked behind multi-step SPAs or login portals:
      - (1, "COHORT_1_FAST_AUTO"): LinkedIn Easy Apply, Greenhouse, Ashby, SmartRecruiters, Hirist, Jobvite, Paylocity
      - (2, "COHORT_2_SPA_AUTO"): Workday, Phenom People, Oracle HCM
      - (3, "COHORT_3_CAPTCHA_PREFILL"): Lever, Keka, BambooHR, Eightfold
      - (4, "COHORT_4_AUTH_PORTAL"): Taleo, iCIMS, Njoyn, Darwinbox, Avature, and custom auth portals
    """
    url = str(job.get("url") or "").lower()
    payload = job.get("payload") or {}
    jd = payload.get("job_details") or {}
    all_urls = " ".join(
        str(x or "")
        for x in (
            url,
            payload.get("apply_url"),
            jd.get("apply_url"),
            payload.get("direct_link"),
            payload.get("ats_provider"),
        )
    ).lower()
    is_easy_apply = bool(payload.get("easy_apply") or jd.get("easy_apply") or "easy_apply" in all_urls)

    if is_easy_apply or any(
        k in all_urls
        for k in (
            "greenhouse.io",
            "gh_jid=",
            "ashbyhq.com",
            "smartrecruiters.com",
            "hirist.tech",
            "hirist.com",
            "jobvite.com",
            "paylocity.com",
        )
    ):
        return 1, "COHORT_1_FAST_AUTO"

    if any(
        k in all_urls
        for k in (
            "myworkdayjobs.com",
            "myworkdaysite.com",
            "workday",
            "phenom",
            "thermofisher.com",
            "oraclecloud.com",
        )
    ):
        return 2, "COHORT_2_SPA_AUTO"

    if any(
        k in all_urls
        for k in (
            "lever.co",
            "keka.com",
            "bamboohr.com",
            "eightfold.ai",
        )
    ):
        return 3, "COHORT_3_CAPTCHA_PREFILL"

    if any(
        k in all_urls
        for k in (
            "taleo.net",
            "icims.com",
            "njoyn.com",
            "darwinbox.in",
            "avature.net",
        )
    ):
        return 4, "COHORT_4_AUTH_PORTAL"

    # Standard LinkedIn /jobs/view/ URLs without explicit external portal indicators default to Cohort 1
    if "linkedin.com/jobs/view/" in url:
        return 1, "COHORT_1_FAST_AUTO"

    return 4, "COHORT_4_AUTH_PORTAL"


def group_jobs_by_cohort(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Annotates each job dict with `cohort_rank` and `cohort_name` and sorts deterministically
    by `(cohort_rank, company, job_id)` so same-vendor and same-cohort jobs run together in waves.
    """
    annotated: list[dict[str, Any]] = []
    for jb in jobs:
        rank, cname = classify_job_cohort(jb)
        item = dict(jb)
        item["cohort_rank"] = rank
        item["cohort_name"] = cname
        annotated.append(item)
    annotated.sort(key=lambda x: (x["cohort_rank"], str(x.get("company", "")).lower(), str(x.get("job_id", ""))))
    return annotated


async def find_tab_for_job(context: BrowserContext, job_id: str) -> Page | None:
    """Finds an existing open tab stamped for `job_id` (`window.__agy_job_id` or `window.name`)."""
    if not job_id:
        return None
    target_jid = str(job_id).strip()
    for pg in reversed(context.pages):
        try:
            if pg.is_closed():
                continue
            matched = await pg.evaluate(
                """(jid) => {
                    return window.__agy_job_id === jid || window.name === ('agy_job_' + jid);
                }""",
                target_jid,
            )
            if matched:
                return pg
        except Exception:  # noqa: S112
            continue
    return None


async def extract_visible_buttons(page: Page, limit: int = 10) -> list[str]:
    """Returns a deduplicated list of visible button/action texts on the current page for Agentic triage."""
    try:
        btns = await page.evaluate(
            """(maxItems) => {
                const seen = new Set();
                const out = [];
                const els = Array.from(document.querySelectorAll('button, a[role="button"], input[type="submit"], input[type="button"], a.postings-btn'));
                for (const el of els) {
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    const txt = (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
                    if (!txt || txt.length > 50) continue;
                    const low = txt.toLowerCase();
                    if (seen.has(low)) continue;
                    seen.add(low);
                    out.push(txt);
                    if (out.length >= maxItems) break;
                }
                return out;
            }""",
            limit,
        )
        return btns if isinstance(btns, list) else []
    except Exception:
        return []


class BulkApplyFastTrackEngine:
    """High-velocity multi-tab batch application orchestrator with agentic handoff."""

    CLOSED_JOB_MARKERS: tuple[str, ...] = (
        "no longer accepting applications",
        "this job is no longer available",
        "job you are looking for is no longer open",
        "either does not exist or is no longer open",
        "the requested job could not be found",
        "page not found",
        "this position has been filled",
        "job posting has expired",
        "the page you are looking for doesn't exist",
        "the page you are looking for does not exist",
        "job doesn't exist",
        "position is no longer available",
    )

    CONFIRMATION_MARKERS: tuple[str, ...] = (
        "thank you for applying",
        "application has been received",
        "application has been submitted",
        "your application was sent",
        "application sent",
        "application submitted",
        "we have received your application",
        "thanks for applying",
    )

    AUTH_GATE_MARKERS: tuple[str, ...] = (
        "sign in to apply",
        "create an account",
        "verify you are human",
        "enter verification code",
        "one-time password",
    )

    def __init__(
        self,
        cdp_url: str = "http://127.0.0.1:9222",
        dashboard_url: str = "http://127.0.0.1:8000",
        approved_dir: str = "data/approved_queue",
    ) -> None:
        self.cdp_url = cdp_url
        self.dashboard_url = dashboard_url.rstrip("/")
        self.approved_dir = approved_dir
        self.logger = AutofillLogger.get_logger()
        self.master_data = load_candidate_master_data()
        self.filler = UniversalBatchFormFiller(master_data=self.master_data)

    def list_queue_batch(
        self,
        batch_size: int = 5,
        ignore_tiers: bool = True,
        job_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Loads the next batch of approved job payloads from `data/approved_queue/`."""
        if not os.path.exists(self.approved_dir):
            return []

        files = [
            os.path.join(self.approved_dir, f)
            for f in os.listdir(self.approved_dir)
            if f.endswith(".json") and not f.endswith("_resume.json")
        ]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)

        selected: list[dict[str, Any]] = []
        target_set = {str(x).strip() for x in (job_ids or []) if str(x).strip()}

        for fpath in files:
            jid = os.path.basename(fpath).replace(".json", "")
            if target_set and jid not in target_set:
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as fp:
                    payload = json.load(fp)
            except Exception:  # noqa: S112
                continue

            if not ignore_tiers:
                tier = str(payload.get("routing_tier") or payload.get("routing_strategy", {}).get("tier") or "")
                if "TIER_2_REFERRAL_SLA" in tier:
                    continue

            jd = payload.get("job_details", {})
            company = (jd.get("company") or payload.get("company_name") or "Unknown").strip()
            title = (jd.get("title") or payload.get("job_title") or "Senior SDET").strip()
            url = (
                payload.get("apply_url")
                or jd.get("apply_url")
                or payload.get("url")
                or payload.get("job_url")
                or jd.get("url")
                or f"https://www.linkedin.com/jobs/view/{jid}/"
            )
            pdf_path = resolve_approved_job_pdf(jid, payload, self.approved_dir)

            selected.append(
                {
                    "job_id": jid,
                    "company": company,
                    "title": title,
                    "url": url,
                    "pdf_path": pdf_path,
                    "file_path": fpath,
                    "payload": payload,
                }
            )

        grouped = group_jobs_by_cohort(selected)
        return grouped[:batch_size]

    def purge_unavailable_job(self, job_id: str, company: str, reason: str, url: str = "") -> None:
        """Logs `JOB_UNAVAILABLE` and purges stale JSON + PDF from `data/approved_queue/`."""
        self.logger.log(
            event_type="JOB_UNAVAILABLE",
            message=f"Job unavailable/closed for {company} ({job_id}): {reason}",
            url=url,
            details={"job_id": job_id, "company": company, "reason": reason},
        )
        json_path = os.path.join(self.approved_dir, f"{job_id}.json")
        if os.path.exists(json_path):
            try:
                os.remove(json_path)
            except Exception:
                pass

        num_id = "".join(re.findall(r"\d+", str(job_id)))[:8]
        for fname in os.listdir(self.approved_dir):
            if fname.endswith(".pdf") and (job_id in fname or (num_id and len(num_id) >= 5 and num_id in fname)):
                try:
                    os.remove(os.path.join(self.approved_dir, fname))
                except Exception:
                    pass

        try:
            from src.scraper.job_finder import LinkedInJobFinder

            LinkedInJobFinder().mark_job_processed(job_id=job_id, company=company, title="", status="JOB_UNAVAILABLE")
        except Exception:
            pass

    async def verify_and_mark_applied(
        self,
        page: Page,
        job_id: str,
        company: str,
        marker_type: str,
        marker_text: str,
    ) -> dict[str, Any]:
        """Captures visual confirmation screenshot, logs `SUBMISSION_CONFIRMED`, and calls `/api/tracking/mark-applied`."""
        screenshots_dir = Path("data/logs/screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        snap_path = str((screenshots_dir / f"submission_{job_id}.png").resolve())
        try:
            await page.screenshot(path=snap_path, full_page=False)
        except Exception:
            pass

        await SubmissionVerifier.record_submission_confirmed(
            job_id=job_id,
            company=company,
            page=page,
            marker_type=marker_type,
            marker_text=marker_text,
            screenshot_path=snap_path if os.path.exists(snap_path) else None,
        )

        verif = SubmissionVerifier.verify_submission(job_id)
        if not verif.get("verified"):
            return {"verified": False, "error": verif.get("reason", "Verification failed")}

        mark_url = f"{self.dashboard_url}/api/tracking/mark-applied/{job_id}"
        try:
            req = urllib.request.Request(mark_url, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
            return {"verified": True, "mark_applied": resp_data, "screenshot": snap_path}
        except Exception as e:
            return {"verified": True, "mark_applied_error": str(e), "screenshot": snap_path}

    async def _is_page_closed_or_unavailable(self, page: Page) -> str | None:
        """Checks if the current page (or embedded iCIMS content iframe) indicates a closed or unavailable job."""
        try:
            body_text = (await page.locator("body").inner_text(timeout=3000)).lower()
        except Exception:
            body_text = ""

        try:
            icims_fr = page.frame(name="icims_content_iframe")
            if icims_fr:
                fr_text = (await icims_fr.locator("body").inner_text(timeout=2500)).lower()
                body_text = f"{body_text}\n{fr_text}"
        except Exception:
            pass

        if not body_text:
            return None

        for marker in self.CLOSED_JOB_MARKERS:
            if marker in body_text:
                return marker
        return None

    async def _detect_linkedin_top_card_action(self, page: Page) -> dict[str, str]:
        """Inspects a LinkedIn `/jobs/view/{id}/` page (SDUI + legacy) to classify the primary Apply button."""
        info = await page.evaluate(
            """() => {
                const bodyTxt = (document.body ? document.body.innerText : '').toLowerCase();
                if (bodyTxt.includes('no longer accepting applications')) {
                    return {type: 'CLOSED', reason: 'No longer accepting applications'};
                }
                if (bodyTxt.includes('application submitted') || bodyTxt.includes('applied ')) {
                    const badges = Array.from(document.querySelectorAll('span, div, p')).filter(
                        el => /^applied(\\s+\\d+.*)?$/i.test((el.innerText || '').trim())
                    );
                    if (badges.length > 0 && !document.querySelector('a[aria-label*="Apply"], button[aria-label*="Apply"]')) {
                        return {type: 'ALREADY_APPLIED', reason: 'Already applied on LinkedIn'};
                    }
                }

                const candidates = Array.from(document.querySelectorAll('button, a'));
                for (const el of candidates) {
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    const txt = (el.innerText || '').trim();
                    const aria = (el.getAttribute('aria-label') || '').trim();
                    const href = (el.getAttribute('href') || '').trim();
                    if (href.includes('/jobs/search-results/') || txt.includes('\\n')) continue;

                    if (/easy apply/i.test(txt) || /easy apply/i.test(aria)) {
                        return {type: 'EASY_APPLY', text: txt, aria: aria, href: href};
                    }
                }

                for (const el of candidates) {
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    const txt = (el.innerText || '').trim();
                    const aria = (el.getAttribute('aria-label') || '').trim();
                    const href = (el.getAttribute('href') || '').trim();
                    if (href.includes('/jobs/search-results/') || txt.includes('\\n')) continue;

                    if (
                        /apply on company website/i.test(aria) ||
                        (href.includes('/safety/go/') && (/apply/i.test(txt) || /apply/i.test(aria))) ||
                        (/^apply$/i.test(txt) && (el.tagName === 'A' || el.tagName === 'BUTTON'))
                    ) {
                        return {type: 'EXTERNAL_APPLY', text: txt, aria: aria, href: href};
                    }
                }

                return {type: 'UNKNOWN'};
            }"""
        )
        return info or {"type": "UNKNOWN"}

    async def _execute_linkedin_easy_apply(
        self,
        page: Page,
        job: dict[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Clicks Easy Apply on the job's dedicated tab and steps through the modal."""
        jid = job["job_id"]
        company = job["company"]
        pdf_path = job["pdf_path"]

        await dismiss_overlays(page)
        btn = page.locator(
            "button.jobs-apply-button, a[aria-label*='Easy Apply'], button[aria-label*='Easy Apply'], "
            "button:has-text('Easy Apply'), a:has-text('Easy Apply')"
        ).first
        if await btn.count() == 0:
            return {
                "status": "NEEDS_AGENT",
                "job_id": jid,
                "company": company,
                "url": page.url,
                "reason": "Easy Apply button not clickable",
                "tab_kept_open": True,
            }

        await btn.click()
        await asyncio.sleep(1.8)
        await stamp_tab_job_id(page, jid)

        modal = page.locator("div[role='dialog'], .jobs-easy-apply-modal").first
        has_legacy_modal = await modal.count() > 0 and await modal.is_visible()
        has_sdui_modal = await page.evaluate(
            """() => {
                const btns = Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null);
                return btns.some(b => ['Next', 'Review', 'Submit application'].includes(b.innerText.trim()));
            }"""
        )
        if not has_legacy_modal and not has_sdui_modal:
            return {
                "status": "NEEDS_AGENT",
                "job_id": jid,
                "company": company,
                "url": page.url,
                "reason": "Easy Apply modal did not open",
                "tab_kept_open": True,
            }

        for step in range(1, 10):
            await asyncio.sleep(0.8)
            step_res = await self.filler.inspect_and_autofill_step(page, resume_pdf_path=pdf_path or None)

            # SDUI & Legacy LinkedIn Easy Apply field normalization (phone digits, radio <label for=id>, selects)
            await page.evaluate(
                """() => {
                    const setVal = (el, val) => {
                        const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                        const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
                        if (setter) setter.call(el, val);
                        else el.value = val;
                        el.dispatchEvent(new Event("input", {bubbles: true}));
                        el.dispatchEvent(new Event("change", {bubbles: true}));
                        el.dispatchEvent(new Event("blur", {bubbles: true}));
                    };
                    const inputs = Array.from(document.querySelectorAll("input, select, textarea")).filter(el => el.offsetParent !== null);
                    for (const el of inputs) {
                        if (el.placeholder === "Describe the job you want" || (el.value && el.value.includes("Software"))) continue;
                        const lbl = ((el.labels && el.labels[0] ? el.labels[0].innerText : "") || el.getAttribute("aria-label") || (el.closest("fieldset") ? el.closest("fieldset").innerText : "") || (el.parentElement ? el.parentElement.innerText : "")).toLowerCase();
                        if (el.tagName === "INPUT" && (el.type === "text" || el.type === "tel" || el.type === "number")) {
                            if ((lbl.includes("mobile phone") || lbl.includes("phone number")) && (el.value.startsWith("+91") || !el.value)) {
                                setVal(el, "7337813770");
                            } else if (lbl.includes("middle name") && el.value === "Manjunath H K") {
                                setVal(el, "");
                            } else if ((lbl.includes("how many years") || lbl.includes("years of") || lbl.includes("experience")) && (isNaN(Number(el.value)) || !el.value)) {
                                setVal(el, (lbl.includes("playwright") || lbl.includes("ai") || lbl.includes("llm") || lbl.includes("red team")) ? "2" : "6");
                            }
                        } else if (el.tagName === "SELECT") {
                            const opts = Array.from(el.options);
                            const yesOpt = opts.find(o => o.text.trim().toLowerCase() === "yes");
                            const noOpt = opts.find(o => o.text.trim().toLowerCase() === "no");
                            if (lbl.includes("sponsor") || lbl.includes("visa") || lbl.includes("know anyone") || lbl.includes("currently working at")) {
                                if (noOpt && el.value !== noOpt.value) {
                                    el.value = noOpt.value;
                                    el.dispatchEvent(new Event("change", {bubbles: true}));
                                }
                            } else if (!el.value || el.value.includes("Select") || el.selectedIndex <= 0) {
                                if (yesOpt) el.value = yesOpt.value;
                                else if (opts.length > 1) el.value = opts[1].value;
                                el.dispatchEvent(new Event("change", {bubbles: true}));
                            }
                        }
                    }
                    const rgs = document.querySelectorAll("[role=radiogroup], fieldset");
                    for (const rg of rgs) {
                        const rs = Array.from(rg.querySelectorAll("input[type=radio]"));
                        if (rs.length > 0 && !rs.some(r => r.checked)) {
                            const txt = rg.innerText.toLowerCase();
                            const wantNo = txt.includes("sponsor") || txt.includes("visa") || txt.includes("relocat");
                            const target = wantNo && rs.length > 1 ? rs[1] : rs[0];
                            const lbl = document.querySelector(`label[for="${target.id}"]`);
                            if (lbl) lbl.click();
                            else target.click();
                        }
                    }
                }"""
            )

            scope = modal if has_legacy_modal else page
            submit_btn = scope.locator(
                "button:has-text('Submit application'), button[aria-label*='Submit application']"
            ).first
            if await submit_btn.count() > 0 and await submit_btn.is_visible():
                if dry_run:
                    return {
                        "status": "DRY_RUN_READY",
                        "job_id": jid,
                        "company": company,
                        "mode": "EASY_APPLY",
                        "steps": step,
                        "tab_kept_open": True,
                    }
                await submit_btn.click()
                await asyncio.sleep(3.0)
                verif_res = await self.verify_and_mark_applied(
                    page=page,
                    job_id=jid,
                    company=company,
                    marker_type="linkedin_easy_apply_modal",
                    marker_text="Application sent",
                )
                return {
                    "status": "APPLIED" if verif_res.get("verified") else "SUBMITTED_UNVERIFIED",
                    "job_id": jid,
                    "company": company,
                    "mode": "EASY_APPLY",
                    "verification": verif_res,
                    "tab_kept_open": not verif_res.get("verified"),
                }

            review_btn = scope.locator("button:has-text('Review'), button[aria-label*='Review']").first
            next_btn = scope.locator("button:has-text('Next'), button[aria-label*='Continue to next step']").first

            if await review_btn.count() > 0 and await review_btn.is_visible():
                await review_btn.click()
                await asyncio.sleep(1.2)
            elif await next_btn.count() > 0 and await next_btn.is_visible():
                await next_btn.click()
                await asyncio.sleep(1.2)
            else:
                return {
                    "status": "NEEDS_AGENT",
                    "job_id": jid,
                    "company": company,
                    "mode": "EASY_APPLY",
                    "url": page.url,
                    "unmapped_fields": step_res.get("unmapped_fields", []),
                    "empty_required_fields": step_res.get("verification", {}).get("empty_required_fields", []),
                    "visible_buttons": await extract_visible_buttons(page),
                    "tab_kept_open": True,
                }

        return {
            "status": "NEEDS_AGENT",
            "job_id": jid,
            "company": company,
            "mode": "EASY_APPLY",
            "url": page.url,
            "reason": "Max modal steps (9) reached without Submit button",
            "visible_buttons": await extract_visible_buttons(page),
            "tab_kept_open": True,
        }

    async def _execute_external_or_direct_ats(
        self,
        page: Page,
        target_url: str,
        job: dict[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Navigates the job's dedicated tab to `target_url`, dismisses cookie/GDPR overlays,
        exposes the ATS form, runs Phase A batch fill, and either auto-submits or leaves the tab
        open and pre-filled for 1-turn Agentic intervention.
        """
        jid = job["job_id"]
        company = job["company"]
        pdf_path = job["pdf_path"]

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=22000)
            await asyncio.sleep(2.2)
        except Exception as e:
            await stamp_tab_job_id(page, jid)
            return {
                "status": "NAVIGATION_ERROR",
                "job_id": jid,
                "company": company,
                "url": target_url,
                "reason": str(e)[:200],
                "tab_kept_open": True,
            }

        await stamp_tab_job_id(page, jid)
        overlays_cleared = await dismiss_overlays(page)
        curr_url = page.url

        closed_reason = await self._is_page_closed_or_unavailable(page)
        if closed_reason:
            self.purge_unavailable_job(jid, company, closed_reason, url=curr_url)
            return {
                "status": "JOB_UNAVAILABLE",
                "job_id": jid,
                "company": company,
                "url": curr_url,
                "reason": closed_reason,
                "tab_kept_open": False,
            }

        pattern = str(classify_ats_pattern(curr_url))
        try:
            from src.ingestion.org_researcher import OrgResearcher

            OrgResearcher().extract_and_bank_ats_url(curr_url, company_name=company, save=True)
        except Exception:
            pass

        # 1. Handle Greenhouse wrapper pages (?gh_jid=...) or embedded Greenhouse iframes
        gh_match = re.search(r"gh_jid=(\d+)", curr_url)
        if gh_match and "job-boards.greenhouse.io/embed/job_app" not in curr_url:
            token = gh_match.group(1)
            slug = re.sub(r"[^a-z0-9]", "", company.lower().split()[0]) if company else ""
            iframe_src = await page.evaluate(
                """() => {
                    const f = document.querySelector("iframe[src*='greenhouse.io/embed/job_app']");
                    return f ? f.src : '';
                }"""
            )
            embed_url = iframe_src or (
                f"https://job-boards.greenhouse.io/embed/job_app?for={slug}&token={token}" if slug else ""
            )
            if embed_url:
                try:
                    await page.goto(embed_url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2.0)
                    await stamp_tab_job_id(page, jid)
                    await dismiss_overlays(page)
                    curr_url = page.url
                except Exception:
                    pass

        # 2. Handle Lever overview pages (/jobs.lever.co/<comp>/<uuid> -> /apply)
        if "jobs.lever.co/" in curr_url and not curr_url.rstrip("/").endswith("/apply"):
            apply_url = curr_url.split("?")[0].rstrip("/") + "/apply"
            try:
                await page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2.0)
                await stamp_tab_job_id(page, jid)
                await dismiss_overlays(page)
                curr_url = page.url
            except Exception:
                pass

        # 3. Check if an "Apply" / "Apply Now" button needs to be clicked to expose the form
        vis_inputs = await page.evaluate(
            """() => {
                const els = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="search"]), select, textarea'));
                return els.filter(e => {
                    const r = e.getBoundingClientRect();
                    const idCls = ((e.id || '') + ' ' + (e.name || '') + ' ' + (e.placeholder || '')).toLowerCase();
                    if (/search|keyword|cookie/i.test(idCls)) return false;
                    return r.width > 0 && r.height > 0;
                }).length;
            }"""
        )
        if vis_inputs < 2:
            apply_trigger = page.locator(
                "a:has-text('Apply for this job'), button:has-text('Apply for this job'), "
                "a:has-text('Apply Now'), button:has-text('Apply Now'), "
                "button#apply-button, a.postings-btn, [data-qa='apply-button'], "
                "button[data-automation-id='adventureButton'], a[data-automation-id='adventureButton'], "
                "button:has-text('Apply'), a:has-text('Apply')"
            ).first
            if await apply_trigger.count() > 0:
                try:
                    if await apply_trigger.is_visible(timeout=2000):
                        # Listen strictly for popups opened by THIS page (never context-wide across workers)
                        opened_popups: list[Page] = []

                        def _on_pop(new_p: Page) -> None:
                            opened_popups.append(new_p)

                        page.on("popup", _on_pop)
                        try:
                            await apply_trigger.click(timeout=4000)
                            await asyncio.sleep(2.5)
                        finally:
                            try:
                                page.remove_listener("popup", _on_pop)
                            except Exception:
                                pass

                        if opened_popups:
                            pop = opened_popups[0]
                            try:
                                await pop.wait_for_load_state("domcontentloaded", timeout=12000)
                            except Exception:
                                pass
                            pop_url = pop.url
                            await pop.close()
                            if pop_url and pop_url != "about:blank":
                                await page.goto(pop_url, wait_until="domcontentloaded", timeout=20000)
                                await asyncio.sleep(2.0)

                        await stamp_tab_job_id(page, jid)
                        await dismiss_overlays(page)
                        curr_url = page.url
                except Exception:
                    pass

        # Re-check if clicking Apply mounted a Greenhouse embed iframe
        iframe_src2 = await page.evaluate(
            """() => {
                const f = document.querySelector("iframe[src*='greenhouse.io/embed/job_app']");
                return f ? f.src : '';
            }"""
        )
        if iframe_src2 and "job-boards.greenhouse.io/embed/job_app" not in curr_url:
            try:
                await page.goto(iframe_src2, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2.0)
                await stamp_tab_job_id(page, jid)
                await dismiss_overlays(page)
                curr_url = page.url
            except Exception:
                pass

        # Re-check if the redirected ATS page or iCIMS iframe reports the job is closed
        closed_after_redirect = await self._is_page_closed_or_unavailable(page)
        if closed_after_redirect:
            self.purge_unavailable_job(jid, company, closed_after_redirect, url=curr_url)
            return {
                "status": "JOB_UNAVAILABLE",
                "job_id": jid,
                "company": company,
                "url": curr_url,
                "reason": closed_after_redirect,
                "tab_kept_open": False,
            }

        # Handle iCIMS email entry step inside `icims_content_iframe` or main frame automatically
        if "icims.com/" in curr_url.lower() or page.frame(name="icims_content_iframe") is not None:
            try:
                icims_target: Any = page.frame(name="icims_content_iframe") or page
                icims_email = icims_target.locator("input#email, input[name='css_email'], input[type='email']").first
                if await icims_email.count() > 0 and await icims_email.is_visible():
                    await icims_email.fill(self.master_data.personal.email)
                    cb = icims_target.locator("input[type='checkbox']").first
                    if await cb.count() > 0 and await cb.is_visible() and not await cb.is_checked():
                        await cb.check(force=True)
                    nxt = icims_target.locator(
                        "input#enterEmailSubmitButton, button#enterEmailSubmitButton, input[type='submit'][value*='Next' i], button:has-text('Next')"
                    ).first
                    if await nxt.count() > 0 and await nxt.is_visible():
                        await nxt.click()
                        await asyncio.sleep(2.5)
                        curr_url = page.url
            except Exception:
                pass

        # Handle Siemens Avature ApplicationMethods interstitial (`Self-complete`)
        if "applicationmethods" in curr_url.lower():
            try:
                self_comp = page.locator("a:has-text('Self-complete'), button:has-text('Self-complete')").first
                if await self_comp.count() > 0 and await self_comp.is_visible():
                    await self_comp.click()
                    await asyncio.sleep(2.5)
                    curr_url = page.url
            except Exception:
                pass

        # Handle Oracle Taleo Guest Apply & Privacy Agreement (`✔ I have read`) and Darwinbox Shadow DOM
        if "taleo.net" in curr_url.lower() or "darwinbox.in" in curr_url.lower():
            await self._advance_taleo_and_darwinbox(page, pdf_path or "")
            curr_url = page.url

        # Check if 1-click portal (like Hirist) already confirmed submission after clicking Apply
        body_lower = (await page.locator("body").inner_text(timeout=3000)).lower()
        for c_marker in self.CONFIRMATION_MARKERS:
            if c_marker in body_lower:
                verif_res = await self.verify_and_mark_applied(
                    page=page,
                    job_id=jid,
                    company=company,
                    marker_type="url_and_dom",
                    marker_text=c_marker,
                )
                return {
                    "status": "APPLIED" if verif_res.get("verified") else "SUBMITTED_UNVERIFIED",
                    "job_id": jid,
                    "company": company,
                    "vendor": pattern,
                    "url": curr_url,
                    "verification": verif_res,
                    "tab_kept_open": not verif_res.get("verified"),
                }

        # 3b. Delegate Workday multi-step SPA directly to ATSAssistedFiller._fill_workday state machine
        if (
            "myworkdayjobs.com" in curr_url.lower()
            or "myworkdaysite.com" in curr_url.lower()
            or pattern == "WORKDAY_STANDARD"
        ):
            try:
                from src.autofill.ats_filler import ATSAssistedFiller

                wd_filler = ATSAssistedFiller()
                await wd_filler._fill_workday(
                    page,
                    pdf_path or "",
                    job_id=jid,
                    company=company,
                    auto_submit=not dry_run,
                    fast_park_on_verify=True,
                )
                await stamp_tab_job_id(page, jid)
                wd_url = page.url
                wd_body = (await page.locator("body").inner_text(timeout=3000)).lower()
                wd_confirmed = ""
                if "/completed/application" in wd_url.lower() or "/jobtasks/completed" in wd_url.lower():
                    wd_confirmed = f"URL: {wd_url}"
                else:
                    for c_marker in self.CONFIRMATION_MARKERS:
                        if c_marker in wd_body:
                            wd_confirmed = c_marker
                            break

                if wd_confirmed:
                    verif_res = await self.verify_and_mark_applied(
                        page=page,
                        job_id=jid,
                        company=company,
                        marker_type="workday_completed",
                        marker_text=wd_confirmed,
                    )
                    return {
                        "status": "APPLIED" if verif_res.get("verified") else "SUBMITTED_UNVERIFIED",
                        "job_id": jid,
                        "company": company,
                        "vendor": "WORKDAY_STANDARD",
                        "url": wd_url,
                        "verification": verif_res,
                        "tab_kept_open": not verif_res.get("verified"),
                    }

                is_verify_gate = (
                    "verify your email" in wd_body
                    or "verification link" in wd_body
                    or await page.locator("input[type='password']:visible").count() > 0
                )
                return {
                    "status": "NEEDS_AUTH_OR_HITL" if is_verify_gate else "NEEDS_AGENT",
                    "job_id": jid,
                    "company": company,
                    "title": job["title"],
                    "vendor": "WORKDAY_STANDARD",
                    "url": wd_url,
                    "visible_buttons": await extract_visible_buttons(page),
                    "reason": "Workday verification/auth gate"
                    if is_verify_gate
                    else "Workday paused for review/custom step",
                    "tab_kept_open": True,
                }
            except Exception as wd_err:
                self.logger.log(
                    event_type="WORKDAY_DELEGATION_WARNING",
                    message=f"Workday state machine fallback for {company} ({jid}): {wd_err}",
                    vendor="WORKDAY_STANDARD",
                    url=curr_url,
                )

        # 3c. Delegate Lever (`jobs.lever.co`) to `_fill_lever_humanized` (Invisible hCaptcha + retrieveLocations.js safe)
        if "jobs.lever.co" in curr_url.lower() or pattern == "LEVER_STANDARD":
            return await self._fill_lever_humanized(page, pdf_path or "", job)

        # Check if portal requires login / account creation / CAPTCHA
        has_password = await page.locator("input[type='password']:visible").count() > 0
        if has_password or any(m in body_lower for m in self.AUTH_GATE_MARKERS):
            return {
                "status": "NEEDS_AUTH_OR_HITL",
                "job_id": jid,
                "company": company,
                "title": job["title"],
                "vendor": pattern,
                "url": curr_url,
                "overlays_dismissed": overlays_cleared,
                "visible_buttons": await extract_visible_buttons(page),
                "reason": "Portal requires login/account creation or verification gate",
                "tab_kept_open": True,
            }

        # 4. Execute Phase A `UniversalBatchFormFiller.inspect_and_autofill_step`
        inspect_res = await self.filler.inspect_and_autofill_step(page, resume_pdf_path=pdf_path or None)
        await stamp_tab_job_id(page, jid)
        await self._sanitize_post_resume_parse(page)
        filled_cnt = inspect_res.get("filled_count", 0)
        resume_ok = inspect_res.get("resume_attached", False)
        verif_block = inspect_res.get("verification", {})
        empty_req = verif_block.get("empty_required_fields", [])
        unmapped = inspect_res.get("unmapped_fields", [])

        real_empty_req = [f for f in empty_req if f.get("label", "").strip().lower() not in ("", "select...", "phone")]

        # Auto-submit ONLY if Phase A filled >=3 genuine candidate fields (or attached a resume) AND zero required fields remain empty
        if (filled_cnt >= 3 or resume_ok) and len(real_empty_req) == 0:
            submit_btn = page.locator(
                "button#btn-submit, button:has-text('Submit application'), button:has-text('Submit Application'), "
                "form button[type='submit']:not([data-ph-at-id*='send']):not([aria-label*='email this job' i]):not([aria-label*='search' i])"
            ).first
            if await submit_btn.count() > 0 and await submit_btn.is_visible():
                if dry_run:
                    return {
                        "status": "DRY_RUN_READY",
                        "job_id": jid,
                        "company": company,
                        "vendor": inspect_res.get("vendor", pattern),
                        "url": curr_url,
                        "filled_count": filled_cnt,
                        "resume_attached": resume_ok,
                        "tab_kept_open": True,
                    }
                try:
                    await submit_btn.click(timeout=5000)
                    await asyncio.sleep(4.5)
                    post_url = page.url
                    post_body = (await page.locator("body").inner_text(timeout=3000)).lower()
                    confirmed_marker = ""
                    if (
                        "confirmation" in post_url.lower()
                        or "applied" in post_url.lower()
                        or "thanks" in post_url.lower()
                    ):
                        confirmed_marker = f"URL: {post_url}"
                    else:
                        for c_marker in self.CONFIRMATION_MARKERS:
                            if c_marker in post_body:
                                confirmed_marker = c_marker
                                break

                    if confirmed_marker:
                        verif_res = await self.verify_and_mark_applied(
                            page=page,
                            job_id=jid,
                            company=company,
                            marker_type="url_and_dom",
                            marker_text=confirmed_marker,
                        )
                        return {
                            "status": "APPLIED" if verif_res.get("verified") else "SUBMITTED_UNVERIFIED",
                            "job_id": jid,
                            "company": company,
                            "vendor": inspect_res.get("vendor", pattern),
                            "url": post_url,
                            "filled_count": filled_cnt,
                            "verification": verif_res,
                            "tab_kept_open": not verif_res.get("verified"),
                        }
                except Exception:
                    pass

        # Leave tab OPEN and pre-filled for 1-turn Agentic intervention
        return {
            "status": "NEEDS_AGENT",
            "job_id": jid,
            "company": company,
            "title": job["title"],
            "vendor": inspect_res.get("vendor", pattern),
            "url": curr_url,
            "overlays_dismissed": overlays_cleared,
            "filled_count": filled_cnt,
            "resume_attached": resume_ok,
            "empty_required_fields": real_empty_req,
            "unmapped_fields": [u for u in unmapped if u.get("label", "").strip().lower() not in ("", "select...")][
                :15
            ],
            "visible_buttons": await extract_visible_buttons(page),
            "tab_kept_open": True,
        }

    async def _fill_lever_humanized(
        self,
        page: Page,
        pdf_path: str,
        job: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Humanized Lever (`jobs.lever.co`) filler engineered specifically for Lever's
        `parseResume.js`, `retrieveLocations.js`, and Invisible hCaptcha (`secure-api.js`):
        1. Uploads the tailored PDF into `#resume-upload-input` first and waits for `/parseResume`
           to natively populate `name`, `email`, `phone`, `org`, `location`, `#selected-location`,
           and `input[name=resumeStorageId]`.
        2. Emits genuine mouse movements and keystroke events on custom card questions so
           Invisible hCaptcha records natural human interaction telemetry.
        3. Preserves `#selected-location` (`{"name":"Bengaluru, Bengaluru Urban, Karnataka, IND"}`)
           while keeping `.dropdown-container` `display: none` so `retrieveLocations.js`'s blur
           listener never wipes `#location-input`.
        4. Never auto-clicks `#btn-submit` while CDP is attached, leaving the tab ready for a
           single human click with 0 active CDP debuggers.
        """
        jid = job["job_id"]
        company = job["company"]
        filled_cnt = 0
        resume_ok = False

        # 1. Human mouse movement across viewport to seed Invisible hCaptcha behavioral buffer
        try:
            await page.mouse.move(220, 320, steps=12)
            await page.mouse.move(480, 520, steps=15)
        except Exception:
            pass

        # 2. Upload resume first and wait for Lever's /parseResume XHR to populate resumeStorageId & selectedLocation
        if pdf_path and os.path.exists(pdf_path):
            try:
                file_in = page.locator("input#resume-upload-input, input[type='file'][name='resume']").first
                if await file_in.count() > 0:
                    await file_in.set_input_files(os.path.abspath(pdf_path))
                    resume_ok = True
                    filled_cnt += 1
                    for _ in range(18):
                        storage_id = await page.evaluate(
                            "() => (document.querySelector('input[name=resumeStorageId]') || {}).value || ''"
                        )
                        if storage_id:
                            break
                        await asyncio.sleep(0.25)
            except Exception:
                pass

        # 3. Fill any standard fields not populated by /parseResume using real keystrokes
        p = self.master_data.personal
        std_pairs = [
            ("input[name='name']", p.full_name),
            ("input[name='email']", p.email),
            ("input[name='phone']", p.phone),
            ("input[name='org']", self.master_data.current_employment.company),
            ("input[name='urls[LinkedIn]']", self.master_data.profiles.linkedin),
            ("input[name='urls[GitHub]']", self.master_data.profiles.github),
            ("input[name='urls[Portfolio]']", self.master_data.profiles.portfolio),
        ]
        for sel, val in std_pairs:
            if not val:
                continue
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    cur_v = (await el.input_value()).strip()
                    if not cur_v:
                        await el.click()
                        await page.keyboard.type(str(val), delay=18)
                        filled_cnt += 1
                    else:
                        filled_cnt += 1
            except Exception:
                pass

        # 4. Ensure Lever #location-input and #selected-location are populated via /searchLocations or safe fallback
        try:
            await page.evaluate(
                """() => {
                    const dc = document.querySelector('.dropdown-container');
                    if (dc) dc.style.display = 'none';
                    const loc = document.getElementById('location-input');
                    const selLoc = document.getElementById('selected-location');
                    if (loc && !loc.value) {
                        loc.value = 'Bengaluru, Bengaluru Urban, Karnataka, IND';
                    }
                    if (selLoc && !selLoc.value) {
                        selLoc.value = JSON.stringify({
                            name: 'Bengaluru, Bengaluru Urban, Karnataka, IND',
                            id: 'f9fb0ff8176b132b009ff9e9235fb567'
                        });
                    }
                }"""
            )
            filled_cnt += 1
        except Exception:
            pass

        # 5. Fill custom Lever card questions (`li.application-question.custom-question`) with real mouse/keyboard events
        try:
            q_items = await page.locator(
                "li.application-question.custom-question, li.application-question:has([name^='cards['])"
            ).all()
            for q_li in q_items:
                lbl_txt = (await q_li.inner_text()).lower()
                radios = await q_li.locator("input[type='radio']").all()
                if radios:
                    want_no = any(k in lbl_txt for k in ("sponsor", "visa", "relocat", "non-compete"))
                    target_val = "No" if want_no else "Yes"
                    for r_el in radios:
                        r_val = (await r_el.get_attribute("value") or "").strip()
                        if r_val.lower() == target_val.lower():
                            await r_el.click()
                            filled_cnt += 1
                            break
                    continue

                txt_in = q_li.locator("input[type='text'], input[type='number'], textarea").first
                if await txt_in.count() > 0 and await txt_in.is_visible():
                    cur_v = (await txt_in.input_value()).strip()
                    ans = ""
                    if "notice" in lbl_txt:
                        ans = "60"
                    elif "expected" in lbl_txt and (
                        "ctc" in lbl_txt or "salary" in lbl_txt or "compensation" in lbl_txt
                    ):
                        ans = "27 LPA"
                    elif "current" in lbl_txt and (
                        "ctc" in lbl_txt or "salary" in lbl_txt or "compensation" in lbl_txt
                    ):
                        ans = "17 LPA"
                    elif "current" in lbl_txt and ("org" in lbl_txt or "company" in lbl_txt or "employer" in lbl_txt):
                        ans = "Value Labs"
                    elif "current location" in lbl_txt or ("location" in lbl_txt and "what is your" in lbl_txt):
                        ans = "Bengaluru, Karnataka, India"
                    elif "designed and implemented" in lbl_txt or "framework from scratch" in lbl_txt:
                        ans = "Yes, designed and implemented scalable UI, API, and Mobile test automation frameworks from scratch using Java, Python, Playwright, Selenium, RestAssured, and Appium."
                    elif "built and deployed" in lbl_txt or "ai/ml or llm" in lbl_txt:
                        ans = "Yes, built and validated AI-driven test automation and LLM evaluation workflows."
                    elif "llm technologies" in lbl_txt or "prompt engineering" in lbl_txt or "rag" in lbl_txt:
                        ans = "Hands-on experience with prompt engineering, LLM evaluation, RAG-based test generation, and AI agent validation workflows."
                    elif "cloud platforms" in lbl_txt:
                        ans = "AWS, Docker, Kubernetes, and LLM API integrations."
                    elif "ci/cd" in lbl_txt:
                        ans = "Jenkins, GitHub Actions, GitLab CI, Docker, and Kubernetes."
                    elif "year" in lbl_txt or "experience" in lbl_txt:
                        ans = "6.8"
                    elif "why" in lbl_txt:
                        ans = f"Excited to architect scalable AI test automation and quality engineering systems at {company}."
                    if ans and (not cur_v or (cur_v == "6.8" and len(ans) > 10)):
                        await txt_in.click()
                        await txt_in.fill("")
                        await page.keyboard.type(ans, delay=14)
                        filled_cnt += 1
                    elif cur_v:
                        filled_cnt += 1

            # Pronoun checkbox: select He/him if present
            he_cb = page.locator("input[name='pronouns'][value='He/him']").first
            if await he_cb.count() > 0 and await he_cb.is_visible() and not await he_cb.is_checked():
                await he_cb.click()
                filled_cnt += 1
        except Exception:
            pass

        # Scroll down to SUBMIT APPLICATION button so user sees it immediately
        try:
            await page.mouse.move(520, 680, steps=15)
            sub_btn = page.locator("#btn-submit").first
            if await sub_btn.count() > 0:
                await sub_btn.scroll_into_view_if_needed()
        except Exception:
            pass

        return {
            "status": "NEEDS_AGENT",
            "job_id": jid,
            "company": company,
            "title": job["title"],
            "vendor": "LEVER_STANDARD",
            "url": page.url,
            "filled_count": filled_cnt,
            "resume_attached": resume_ok,
            "empty_required_fields": [],
            "unmapped_fields": [],
            "visible_buttons": ["SUBMIT APPLICATION"],
            "reason": "Lever Invisible hCaptcha ready for 1-click user submit (CDP detached)",
            "tab_kept_open": True,
        }

    async def _advance_taleo_and_darwinbox(self, page: Page, pdf_path: str = "") -> int:
        """
        Advances Oracle Taleo (`taleo.net`) through `Apply as Guest` and Privacy Agreement
        (`input#dialogTemplate-dialogForm-StatementBeforeAuthentificationContent-ContinueButton`,
        `value='✔ I have read'`), and pierces Darwinbox (`darwinbox.in`) `<dbx-textinput>`
        Shadow DOM controls to populate candidate email/password/registration fields.
        """
        filled = 0
        p = self.master_data.personal
        default_pwd = (
            os.getenv("WORKDAY_DEFAULT_PASSWORD")
            or getattr(p, "workday_default_password", None)
            or "CandidateMockSecret123!"
        )
        url_low = page.url.lower()

        if "taleo.net" in url_low:
            for _step in range(6):
                progressed = False
                try:
                    guest_btn = page.locator(
                        "a:has-text('Apply as Guest'), input[value*='Apply as Guest' i], button:has-text('Apply as Guest')"
                    ).first
                    if await guest_btn.count() > 0 and await guest_btn.is_visible():
                        await guest_btn.click()
                        await asyncio.sleep(2.5)
                        filled += 1
                        progressed = True
                except Exception:
                    pass

                try:
                    taleo_continue = page.locator(
                        "input[id*='StatementBeforeAuthentificationContent-ContinueButton'], "
                        "input[value*='I have read' i], input[value*='I Accept' i], button:has-text('I have read')"
                    ).first
                    if await taleo_continue.count() > 0 and await taleo_continue.is_visible():
                        await taleo_continue.click()
                        await asyncio.sleep(3.5)
                        filled += 1
                        progressed = True
                except Exception:
                    pass

                try:
                    taleo_em = page.locator(
                        "input#dialogTemplate-dialogForm-email, input[id*='dialogForm-email']"
                    ).first
                    if await taleo_em.count() > 0 and await taleo_em.is_visible():
                        await taleo_em.fill(p.email)
                        filled += 1
                        cont2 = page.locator(
                            "input[value='Continue'][type='button'], input[value='Continue'][type='submit'], input[id*='ContinueButton']:not([value*='Cancel'])"
                        ).first
                        if await cont2.count() > 0 and await cont2.is_visible():
                            await cont2.click()
                            await asyncio.sleep(4.0)
                            filled += 1
                            progressed = True
                except Exception:
                    pass

                if pdf_path and os.path.exists(pdf_path):
                    try:
                        cv_now_radio = page.locator("input[type='radio'][value='2']").first
                        if await cv_now_radio.count() > 0 and await cv_now_radio.is_visible():
                            await cv_now_radio.click(force=True)
                            await asyncio.sleep(0.8)
                        f_in = page.locator("input[type='file']").first
                        if await f_in.count() > 0:
                            await f_in.set_input_files(os.path.abspath(pdf_path))
                            filled += 1
                            await asyncio.sleep(2.5)
                            nxt_taleo = page.locator(
                                "input[id*='saveContinueCmd'], input[value*='Save and Continue' i], a:has-text('Save and Continue'), button:has-text('Save and Continue')"
                            ).first
                            if await nxt_taleo.count() > 0 and await nxt_taleo.is_visible():
                                await nxt_taleo.click()
                                await asyncio.sleep(5.0)
                                progressed = True
                    except Exception:
                        pass

                # Run Phase A batch form filler on any mounted Taleo form step and click Save and Continue / Submit
                try:
                    t_res = await self.filler.inspect_and_autofill_step(page, resume_pdf_path=pdf_path or None)
                    t_filled = int(t_res.get("filled_count", 0))
                    # Fill Taleo Cellular Number and Title select if present
                    cell_in = page.locator("input[id*='MobilePhone' i], label:has-text('Cellular') + input").first
                    if await cell_in.count() == 0:
                        cell_in = page.get_by_label("Cellular Number", exact=False).first
                    if await cell_in.count() > 0 and await cell_in.is_visible():
                        cur_cell = (await cell_in.input_value()).strip()
                        if not cur_cell:
                            await cell_in.fill("7337813770")
                            t_filled += 1
                    title_sel = page.locator("select[id*='Title' i], select[name*='Title' i]").first
                    if await title_sel.count() > 0:
                        try:
                            await title_sel.select_option(label="Mr.")
                            t_filled += 1
                        except Exception:
                            try:
                                await title_sel.select_option(label="Mr")
                                t_filled += 1
                            except Exception:
                                pass
                    if t_filled > 0:
                        filled += t_filled
                        # Do not auto-advance if a sensitive government ID field (like PAN Card) is empty and required
                        pan_empty = await page.evaluate(
                            """() => {
                                const lbls = Array.from(document.querySelectorAll('label'));
                                for (const l of lbls) {
                                    if (/pan card/i.test(l.innerText || '')) {
                                        const inp = l.htmlFor ? document.getElementById(l.htmlFor) : null;
                                        if (inp && !inp.value) return true;
                                    }
                                }
                                return false;
                            }"""
                        )
                        if pan_empty:
                            break
                        sub_or_nxt = page.locator(
                            "input[value='Submit'][type='button'], input[value='Submit'][type='submit'], "
                            "input[value*='Save and Continue' i], a:has-text('Save and Continue'), a:has-text('Submit')"
                        ).first
                        if await sub_or_nxt.count() > 0 and await sub_or_nxt.is_visible():
                            await sub_or_nxt.click()
                            await asyncio.sleep(4.5)
                            progressed = True
                except Exception:
                    pass

                if not progressed:
                    break

        if "darwinbox.in" in url_low:
            try:
                if "/auth/login" in page.url.lower():
                    em_in = page.locator(
                        "input[placeholder*='email' i], input[type='email'], dbx-textinput input[type='text']"
                    ).first
                    if await em_in.count() > 0 and await em_in.is_visible():
                        await em_in.fill(p.email)
                        filled += 1

                    pw_in = page.locator("input[placeholder*='password' i], input[type='password']").first
                    if await pw_in.count() > 0 and await pw_in.is_visible():
                        await pw_in.fill(default_pwd)
                        filled += 1

                    sign_in_btn = page.locator(
                        "button.action-btn:has-text('Sign In'), button:has-text('Sign In')"
                    ).first
                    if await sign_in_btn.count() > 0 and await sign_in_btn.is_visible():
                        await sign_in_btn.click()
                        await asyncio.sleep(2.5)

                net_errs = list(getattr(page, "_agy_net_errors", []))
                acc_missing = any("does not exist" in str(e.get("response_preview", "")).lower() for e in net_errs)
                if acc_missing or "/auth/login" in page.url.lower():
                    sign_up_el = page.locator("text='Sign Up'").first
                    if await sign_up_el.count() > 0 and await sign_up_el.is_visible():
                        await sign_up_el.click()
                        await asyncio.sleep(2.5)

                # Pre-fill Darwinbox Sign Up / Registration Shadow DOM inputs if present
                for ph, val in [
                    ("first name", p.first_name),
                    ("last name", p.last_name),
                    ("full name", p.full_name),
                    ("name", p.full_name),
                    ("email", p.email),
                    ("mobile", "7337813770"),
                    ("phone", "7337813770"),
                    ("contact", "7337813770"),
                    ("password", default_pwd),
                ]:
                    inps = await page.locator(f"input[placeholder*='{ph}' i]").all()
                    for inp in inps:
                        if await inp.is_visible():
                            await inp.fill(str(val))
                            filled += 1

                terms_cb = page.locator("input[name='terms'], input[type='checkbox']").first
                if await terms_cb.count() > 0 and await terms_cb.is_visible() and not await terms_cb.is_checked():
                    try:
                        await terms_cb.check(force=True)
                    except Exception:
                        await terms_cb.click(force=True)
                    filled += 1
            except Exception:
                pass

        return filled

    async def _sanitize_post_resume_parse(self, page: Page) -> None:
        """
        Normalizes fields that enterprise resume parsers (Phenom People, Eightfold.ai, Darwinbox)
        overwrite or corrupt after resume upload:
        - Clears non-required `cntryFields.local*` fields so partial local-name pair validation does not fail.
        - Strips `+91` prefix from phone inputs when a dedicated country phone code dropdown/combobox exists.
        - Sanitizes `experienceData` textareas so special punctuation (`–`, `;`, `%`) does not fail regex gates.
        """
        try:
            await dismiss_overlays(page)
            await page.evaluate(
                """() => {
                    for (const id of ["cntryFields.localFirstName", "cntryFields.localPrimary", "cntryFields.localLastName"]) {
                        const el = document.getElementById(id);
                        if (el && !el.required && el.getAttribute("aria-required") !== "true" && el.value) {
                            el.value = "";
                            el.dispatchEvent(new Event("input", {bubbles: true}));
                            el.dispatchEvent(new Event("change", {bubbles: true}));
                        }
                    }
                    const hasPhoneCode = !!(
                        document.getElementById("phoneWidget.countryPhoneCode") ||
                        document.getElementById("input-5") ||
                        document.querySelector("select[id*='PhoneCode' i], input[aria-label*='Country code' i]")
                    );
                    if (hasPhoneCode) {
                        document.querySelectorAll("input[id*='phone' i], input[type='tel']").forEach(ph => {
                            if (ph.value && ph.value.startsWith("+91")) {
                                ph.value = ph.value.replace(/^\\+91\\s*/, "");
                                ph.dispatchEvent(new Event("input", {bubbles: true}));
                                ph.dispatchEvent(new Event("change", {bubbles: true}));
                            }
                        });
                    }
                    document.querySelectorAll("textarea[id*='experienceData']").forEach(ta => {
                        if (ta.value && /[–;%•]/.test(ta.value)) {
                            ta.value = "Led QA and test automation frameworks using Java Python Playwright and REST APIs";
                            ta.dispatchEvent(new Event("input", {bubbles: true}));
                            ta.dispatchEvent(new Event("change", {bubbles: true}));
                        }
                    });
                    // Restore Lever #location-input & #selected-location WITHOUT dispatching input+blur
                    // (which triggers retrieveLocations.js blur handler to wipe both fields!)
                    const locInput = document.getElementById("location-input");
                    if (locInput && !locInput.value) {
                        const dc = document.querySelector(".dropdown-container");
                        if (dc) dc.style.display = "none";
                        locInput.value = "Bengaluru, Bengaluru Urban, Karnataka, IND";
                        const selLoc = document.getElementById("selected-location");
                        if (selLoc && !selLoc.value) {
                            selLoc.value = JSON.stringify({
                                name: "Bengaluru, Bengaluru Urban, Karnataka, IND",
                                id: "f9fb0ff8176b132b009ff9e9235fb567"
                            });
                        }
                    }
                }"""
            )
        except Exception:
            pass

    async def _process_single_job_tab(
        self,
        context: BrowserContext,
        job: dict[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Processes a single job in its dedicated stamped tab (`window.__agy_job_id`)."""
        jid = job["job_id"]
        company = job["company"]
        url = job["url"]

        job_page = await find_tab_for_job(context, jid)
        if job_page is None:
            try:
                job_page = await context.new_page()
            except Exception:
                ensure_cdp_page_target(self.cdp_url)
                await asyncio.sleep(0.5)
                job_page = await context.new_page()
        await stamp_tab_job_id(job_page, jid)

        res: dict[str, Any]
        if "linkedin.com/jobs/view/" in url.lower():
            try:
                await job_page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2.2)
                await stamp_tab_job_id(job_page, jid)
                await dismiss_overlays(job_page)
            except Exception as nav_err:
                return {
                    "status": "NAVIGATION_ERROR",
                    "job_id": jid,
                    "company": company,
                    "url": url,
                    "reason": str(nav_err)[:200],
                    "tab_kept_open": True,
                }

            li_action = await self._detect_linkedin_top_card_action(job_page)
            act_type = li_action.get("type", "UNKNOWN")

            if act_type == "CLOSED":
                self.purge_unavailable_job(jid, company, li_action.get("reason", "Closed"), url=url)
                try:
                    if len(context.pages) > 1:
                        await job_page.close()
                except Exception:
                    pass
                return {
                    "status": "JOB_UNAVAILABLE",
                    "job_id": jid,
                    "company": company,
                    "url": url,
                    "reason": li_action.get("reason", "Closed"),
                    "tab_kept_open": False,
                }

            if act_type == "EASY_APPLY":
                res = await self._execute_linkedin_easy_apply(job_page, job, dry_run=dry_run)
            elif act_type == "EXTERNAL_APPLY":
                raw_href = li_action.get("href", "")
                dest_url = decode_linkedin_safety_redirect(raw_href)
                if dest_url and dest_url.startswith("http") and "linkedin.com" not in dest_url.lower():
                    res = await self._execute_external_or_direct_ats(job_page, dest_url, job, dry_run=dry_run)
                else:
                    opened: list[Page] = []

                    def _on_page(new_p: Page, _bucket: list[Page] = opened) -> None:
                        _bucket.append(new_p)

                    context.on("page", _on_page)
                    try:
                        btn = job_page.locator(
                            "a[aria-label*='Apply on company website'], button[aria-label*='Apply on company website'], "
                            "a:has-text('Apply'), button:has-text('Apply')"
                        ).first
                        await btn.click(timeout=4000)
                        for _ in range(25):
                            if opened:
                                break
                            await asyncio.sleep(0.1)
                    except Exception:
                        pass
                    finally:
                        try:
                            context.remove_listener("page", _on_page)
                        except Exception:
                            pass

                    if opened:
                        ext_tab = opened[0]
                        try:
                            await ext_tab.wait_for_load_state("domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                        ext_url = ext_tab.url
                        await ext_tab.close()
                        if ext_url and ext_url != "about:blank":
                            res = await self._execute_external_or_direct_ats(job_page, ext_url, job, dry_run=dry_run)
                        else:
                            res = {
                                "status": "NEEDS_AGENT",
                                "job_id": jid,
                                "company": company,
                                "url": job_page.url,
                                "reason": "External tab URL was blank",
                                "tab_kept_open": True,
                            }
                    else:
                        res = {
                            "status": "NEEDS_AGENT",
                            "job_id": jid,
                            "company": company,
                            "url": job_page.url,
                            "reason": "External apply click did not open destination URL",
                            "visible_buttons": await extract_visible_buttons(job_page),
                            "tab_kept_open": True,
                        }
            else:
                res = {
                    "status": "NEEDS_AGENT",
                    "job_id": jid,
                    "company": company,
                    "url": job_page.url,
                    "detected_action": li_action,
                    "visible_buttons": await extract_visible_buttons(job_page),
                    "tab_kept_open": True,
                }
        else:
            res = await self._execute_external_or_direct_ats(job_page, url, job, dry_run=dry_run)

        res["cohort_name"] = job.get("cohort_name", "COHORT_1_FAST_AUTO")

        # Record Action-Scoped Flight Recorder snapshot on any non-APPLIED / non-JOB_UNAVAILABLE outcome
        if res.get("status") not in ("APPLIED", "JOB_UNAVAILABLE", "DRY_RUN_READY"):
            try:
                await self.logger.record_flight_snapshot(
                    page=job_page,
                    job_id=jid,
                    company=company,
                    vendor=str(res.get("vendor") or res.get("mode") or "GENERIC"),
                    status=str(res.get("status", "NEEDS_AGENT")),
                    reason=str(res.get("reason") or ""),
                    extra={
                        "cohort": job.get("cohort_name", ""),
                        "empty_required_count": len(res.get("empty_required_fields", [])),
                        "unmapped_count": len(res.get("unmapped_fields", [])),
                    },
                )
                res["flight_record_logged"] = True
            except Exception:
                res["flight_record_logged"] = False

        if not res.get("tab_kept_open", True):
            try:
                if len(context.pages) > 1 and not job_page.is_closed():
                    await job_page.close()
            except Exception:
                pass

        return res

    async def execute_batch(
        self,
        batch_size: int = 5,
        ignore_tiers: bool = True,
        dry_run: bool = False,
        job_ids: list[str] | None = None,
        concurrency: int = 5,
        max_open_tabs: int = 5,
    ) -> dict[str, Any]:
        """
        Stages `batch_size` jobs in cohort order (strictly capped at `max_open_tabs=5` per wave)
        in SEPARATE dedicated tabs (`context.new_page()`), auto-completes & closes clean/unavailable
        tabs, and leaves complex tabs open and pre-filled with Flight Recorder telemetry.
        """
        t0 = time.perf_counter()
        effective_batch = min(max(1, batch_size), max(1, max_open_tabs)) if not job_ids else max(1, batch_size)
        effective_concurrency = min(max(1, concurrency), max(1, max_open_tabs), 5)
        batch_jobs = self.list_queue_batch(batch_size=effective_batch, ignore_tiers=ignore_tiers, job_ids=job_ids)

        if not batch_jobs:
            return {
                "batch_size": 0,
                "max_open_tabs": max_open_tabs,
                "elapsed_sec": 0.0,
                "applied_count": 0,
                "unavailable_purged_count": 0,
                "staged_open_tabs_count": 0,
                "results": [],
            }

        ensure_persistent_cdp_browser(self.cdp_url, self.dashboard_url)
        sem = asyncio.Semaphore(effective_concurrency)

        p = await async_playwright().start()
        self._pw = p
        try:
            browser = await p.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()

            async def _worker(job_item: dict[str, Any]) -> dict[str, Any]:
                async with sem:
                    try:
                        return await self._process_single_job_tab(context, job_item, dry_run=dry_run)
                    except Exception as exc:
                        return {
                            "status": "NEEDS_AGENT",
                            "job_id": job_item.get("job_id", ""),
                            "company": job_item.get("company", ""),
                            "url": job_item.get("url", ""),
                            "error": str(exc),
                            "tab_kept_open": True,
                        }

            # Process in waves of at most `max_open_tabs` (default 5)
            results: list[dict[str, Any]] = []
            wave_size = max(1, min(max_open_tabs, 5))
            for i in range(0, len(batch_jobs), wave_size):
                wave = batch_jobs[i : i + wave_size]
                wave_res = list(await asyncio.gather(*(_worker(jb) for jb in wave)))
                results.extend(wave_res)
        finally:
            try:
                await p.stop()
            except Exception:
                pass
            self._pw = None

        elapsed = round(time.perf_counter() - t0, 2)
        summary = {
            "batch_size": len(batch_jobs),
            "max_open_tabs": wave_size,
            "elapsed_sec": elapsed,
            "applied_count": sum(1 for r in results if r.get("status") == "APPLIED"),
            "unavailable_purged_count": sum(1 for r in results if r.get("status") == "JOB_UNAVAILABLE"),
            "staged_open_tabs_count": sum(1 for r in results if r.get("tab_kept_open")),
            "results": results,
        }
        return summary

    async def resume_open_tabs(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Inspects all currently open tabs in the persistent Chrome session (`--resume-tabs`),
        matches each tab to its approved queue job (via `window.__agy_job_id`, `window.name`,
        or URL/company slug), and deterministically completes signed-in Workday, Taleo, Lever,
        and ATS tabs without launching new tabs.
        """
        t0 = time.perf_counter()
        all_queued = self.list_queue_batch(batch_size=200, ignore_tiers=True)
        by_id = {jb["job_id"]: jb for jb in all_queued}

        ensure_persistent_cdp_browser(self.cdp_url, self.dashboard_url)
        p = await async_playwright().start()
        self._pw = p
        resumed_results: list[dict[str, Any]] = []
        try:
            browser = await p.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()

            for pg in list(context.pages):
                try:
                    if pg.is_closed():
                        continue
                    cur_url = pg.url or ""
                    if not cur_url or cur_url.startswith(
                        ("about:blank", "chrome://", "http://127.0.0.1:8000", "http://localhost:8000")
                    ):
                        continue

                    stamped_id = await pg.evaluate(
                        """() => {
                            if (window.__agy_job_id) return String(window.__agy_job_id);
                            if (window.name && window.name.startsWith('agy_job_')) return window.name.replace('agy_job_', '');
                            return '';
                        }"""
                    )
                    matched_job = by_id.get(stamped_id) if stamped_id else None
                    if not matched_job:
                        low_u = cur_url.lower()
                        for jb in all_queued:
                            comp_slug = (
                                re.sub(r"[^a-z0-9]", "", jb["company"].lower().split()[0]) if jb["company"] else ""
                            )
                            if (jb["job_id"] in low_u) or (comp_slug and len(comp_slug) >= 3 and comp_slug in low_u):
                                matched_job = jb
                                break

                    if not matched_job:
                        continue

                    jid = matched_job["job_id"]
                    company = matched_job["company"]
                    pdf_path = matched_job["pdf_path"]
                    await stamp_tab_job_id(pg, jid)
                    await dismiss_overlays(pg)

                    body_lower = (await pg.locator("body").inner_text(timeout=3000)).lower()
                    confirmed_marker = ""
                    if "/completed/application" in cur_url.lower() or "/jobtasks/completed" in cur_url.lower():
                        confirmed_marker = f"URL: {cur_url}"
                    else:
                        for c_marker in self.CONFIRMATION_MARKERS:
                            if c_marker in body_lower:
                                confirmed_marker = c_marker
                                break

                    if confirmed_marker:
                        verif_res = await self.verify_and_mark_applied(
                            page=pg,
                            job_id=jid,
                            company=company,
                            marker_type="resume_tabs_confirmed",
                            marker_text=confirmed_marker,
                        )
                        if verif_res.get("verified") and len(context.pages) > 1:
                            await pg.close()
                        resumed_results.append(
                            {
                                "status": "APPLIED" if verif_res.get("verified") else "SUBMITTED_UNVERIFIED",
                                "job_id": jid,
                                "company": company,
                                "url": cur_url,
                            }
                        )
                        continue

                    if "myworkdayjobs.com" in cur_url.lower() or "myworkdaysite.com" in cur_url.lower():
                        from src.autofill.ats_filler import ATSAssistedFiller

                        await ATSAssistedFiller()._fill_workday(
                            pg,
                            pdf_path or "",
                            job_id=jid,
                            company=company,
                            auto_submit=not dry_run,
                            fast_park_on_verify=True,
                        )
                        post_url = pg.url
                        post_body = (await pg.locator("body").inner_text(timeout=3000)).lower()
                        if "/completed/application" in post_url.lower() or any(
                            m in post_body for m in self.CONFIRMATION_MARKERS
                        ):
                            verif_res = await self.verify_and_mark_applied(
                                page=pg,
                                job_id=jid,
                                company=company,
                                marker_type="workday_resume_completed",
                                marker_text=f"URL: {post_url}",
                            )
                            if verif_res.get("verified") and len(context.pages) > 1:
                                await pg.close()
                            resumed_results.append(
                                {
                                    "status": "APPLIED" if verif_res.get("verified") else "SUBMITTED_UNVERIFIED",
                                    "job_id": jid,
                                    "company": company,
                                    "vendor": "WORKDAY_STANDARD",
                                    "url": post_url,
                                }
                            )
                        else:
                            await self.logger.record_flight_snapshot(
                                pg,
                                jid,
                                company,
                                "WORKDAY_STANDARD",
                                "NEEDS_AGENT",
                                reason="Resumed Workday tab incomplete",
                            )
                            resumed_results.append(
                                {
                                    "status": "NEEDS_AGENT",
                                    "job_id": jid,
                                    "company": company,
                                    "vendor": "WORKDAY_STANDARD",
                                    "url": post_url,
                                }
                            )
                    elif "jobs.lever.co" in cur_url.lower():
                        lever_res = await self._fill_lever_humanized(pg, pdf_path or "", matched_job)
                        await self._sanitize_post_resume_parse(pg)
                        await self.logger.record_flight_snapshot(
                            pg,
                            jid,
                            company,
                            "LEVER_STANDARD",
                            "RESUMED_PREFILLED",
                            reason="Resumed Lever tab humanized prefill",
                        )
                        resumed_results.append(
                            {
                                "status": "RESUMED_PREFILLED",
                                "job_id": jid,
                                "company": company,
                                "vendor": "LEVER_STANDARD",
                                "filled_count": lever_res.get("filled_count", 0),
                                "url": pg.url,
                            }
                        )
                    else:
                        closed_reason = await self._is_page_closed_or_unavailable(pg)
                        if closed_reason:
                            self.purge_unavailable_job(jid, company, closed_reason, url=cur_url)
                            if len(context.pages) > 1:
                                await pg.close()
                            resumed_results.append(
                                {
                                    "status": "JOB_UNAVAILABLE",
                                    "job_id": jid,
                                    "company": company,
                                    "url": cur_url,
                                    "reason": closed_reason,
                                }
                            )
                            continue

                        if "icims.com/" in pg.url.lower() or pg.frame(name="icims_content_iframe") is not None:
                            try:
                                icims_target: Any = pg.frame(name="icims_content_iframe") or pg
                                icims_email = icims_target.locator(
                                    "input#email, input[name='css_email'], input[type='email']"
                                ).first
                                if await icims_email.count() > 0 and await icims_email.is_visible():
                                    await icims_email.fill(self.master_data.personal.email)
                                    cb = icims_target.locator("input[type='checkbox']").first
                                    if await cb.count() > 0 and await cb.is_visible() and not await cb.is_checked():
                                        await cb.check(force=True)
                                    nxt = icims_target.locator(
                                        "input#enterEmailSubmitButton, button#enterEmailSubmitButton, input[type='submit'][value*='Next' i], button:has-text('Next')"
                                    ).first
                                    if await nxt.count() > 0 and await nxt.is_visible():
                                        await nxt.click()
                                        await asyncio.sleep(2.5)
                            except Exception:
                                pass
                        if "applicationmethods" in pg.url.lower():
                            try:
                                self_comp = pg.locator(
                                    "a:has-text('Self-complete'), button:has-text('Self-complete')"
                                ).first
                                if await self_comp.count() > 0 and await self_comp.is_visible():
                                    await self_comp.click()
                                    await asyncio.sleep(2.5)
                            except Exception:
                                pass
                        td_filled = 0
                        if "taleo.net" in pg.url.lower() or "darwinbox.in" in pg.url.lower():
                            td_filled = await self._advance_taleo_and_darwinbox(pg, pdf_path or "")
                        fill_target: Any = pg.frame(name="icims_content_iframe") or pg
                        step_res = await self.filler.inspect_and_autofill_step(
                            fill_target, resume_pdf_path=pdf_path or None
                        )
                        await self._sanitize_post_resume_parse(pg)
                        total_filled = int(step_res.get("filled_count", 0)) + td_filled
                        await self.logger.record_flight_snapshot(
                            pg,
                            jid,
                            company,
                            str(step_res.get("vendor", "GENERIC")),
                            "RESUMED_PREFILLED",
                            reason="Resumed open tab prefilled",
                        )
                        resumed_results.append(
                            {
                                "status": "RESUMED_PREFILLED",
                                "job_id": jid,
                                "company": company,
                                "vendor": step_res.get("vendor", "GENERIC"),
                                "filled_count": total_filled,
                                "url": pg.url,
                            }
                        )
                except Exception as e:
                    resumed_results.append({"status": "ERROR", "error": str(e)[:200]})
        finally:
            try:
                await p.stop()
            except Exception:
                pass
            self._pw = None

        return {
            "resumed_tabs_count": len(resumed_results),
            "applied_count": sum(1 for r in resumed_results if r.get("status") == "APPLIED"),
            "elapsed_sec": round(time.perf_counter() - t0, 2),
            "results": resumed_results,
        }
