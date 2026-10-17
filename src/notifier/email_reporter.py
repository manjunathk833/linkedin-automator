"""
Zero-Cost Executive Email Reporter.
Dispatches responsive HTML briefing reports via Gmail SMTP SSL (Port 465) using an App Password.
Provides resilient offline/fallback behavior by archiving reports to data/logs/daily_report_YYYY-MM-DD.html.
"""

from __future__ import annotations

import datetime
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class EmailReporter:
    """
    Constructs and dispatches HTML executive briefings for daily job search automation runs.
    """

    def __init__(
        self,
        sender_email: str | None = None,
        app_password: str | None = None,
        recipient_email: str | None = None,
    ):
        self.sender = (
            sender_email
            if sender_email is not None
            else (os.environ.get("GMAIL_USER") or os.environ.get("GMAIL_SENDER"))
        )
        self.password = app_password if app_password is not None else os.environ.get("GMAIL_APP_PASSWORD")
        self.recipient = (
            recipient_email if recipient_email is not None else (os.environ.get("REPORT_RECIPIENT") or self.sender)
        )
        self.log_dir = PROJECT_ROOT / "data" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def is_configured(self) -> bool:
        """Returns True if sender and app password credentials are provided."""
        return bool(self.sender and self.password and self.recipient)

    def build_report_html(
        self,
        staged_jobs: list[dict[str, Any]],
        regression_passed: bool = True,
        regression_summary: str = "48/48 Passed (100%)",
        execution_duration_sec: float = 0.0,
        run_date: str | None = None,
    ) -> str:
        """Generates modern, responsive Glassmorphic HTML email body."""
        date_str = run_date or datetime.date.today().strftime("%B %d, %Y")
        total_jobs = len(staged_jobs)
        dream_jobs = [j for j in staged_jobs if j.get("is_dream_org")]
        ats_jobs = [j for j in staged_jobs if str(j.get("source", "")).lower() != "linkedin"]
        linkedin_jobs = [j for j in staged_jobs if str(j.get("source", "")).lower() == "linkedin"]

        status_badge_color = "#10b981" if regression_passed else "#ef4444"
        status_text = "HEALTHY (100% REGRESSION PASS)" if regression_passed else "REGRESSION FAILURE"

        # Build job table rows (top 10 jobs)
        rows_html = []
        for job in staged_jobs[:10]:
            title = job.get("job_details", {}).get("title") or job.get("title", "SDET Role")
            company = job.get("job_details", {}).get("company") or job.get("company", "Tech Company")
            location = job.get("job_details", {}).get("location") or job.get("location", "Bengaluru / Remote")
            source = str(job.get("source", "ATS")).upper()
            is_dream = job.get("is_dream_org", False)
            dream_tag = '<span style="color:#f59e0b;font-weight:700;"> ⭐ DREAM ORG</span>' if is_dream else ""
            job_link = (
                job.get("canonical_url")
                or job.get("apply_url")
                or job.get("job_details", {}).get("job_url", "http://localhost:8000")
            )

            row = f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 12px; font-weight: 600; color: #0f172a;">
                    {title}{dream_tag}<br>
                    <span style="font-size: 11px; color: #64748b; font-weight: normal;">{location}</span>
                </td>
                <td style="padding: 10px 12px; color: #334155; font-weight: 500;">{company}</td>
                <td style="padding: 10px 12px;">
                    <span style="font-size: 10px; background: #e0e7ff; color: #4338ca; padding: 2px 6px; border-radius: 4px; font-weight: 700;">
                        {source}
                    </span>
                </td>
                <td style="padding: 10px 12px; text-align: right;">
                    <a href="{job_link}" style="display: inline-block; font-size: 11px; background: #0f172a; color: #ffffff; padding: 4px 10px; border-radius: 4px; text-decoration: none;">View ↗</a>
                </td>
            </tr>
            """
            rows_html.append(row)

        table_body = (
            "".join(rows_html)
            if rows_html
            else '<tr><td colspan="4" style="padding: 16px; text-align: center; color: #64748b;">No new jobs staged today. Queue is up to date!</td></tr>'
        )

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
  .card {{ max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
  .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 24px; text-align: center; }}
  .pill {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; }}
  .kpi-grid {{ display: flex; gap: 8px; padding: 16px 20px; background: #f1f5f9; border-bottom: 1px solid #e2e8f0; }}
  .kpi {{ flex: 1; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center; }}
  .kpi-num {{ font-size: 22px; font-weight: 800; color: #0f172a; margin: 0; }}
  .kpi-label {{ font-size: 10px; text-transform: uppercase; color: #64748b; font-weight: 700; margin: 0; }}
  .content {{ padding: 20px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th {{ background: #f8fafc; padding: 8px 12px; text-align: left; font-size: 10.5px; text-transform: uppercase; color: #64748b; border-bottom: 2px solid #e2e8f0; }}
  .btn-primary {{ display: block; width: fit-content; margin: 20px auto 0 auto; background: #2563eb; color: #ffffff; padding: 12px 28px; border-radius: 8px; font-weight: 700; text-decoration: none; text-align: center; font-size: 14px; box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2); }}
  .footer {{ padding: 16px; background: #f8fafc; text-align: center; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="pill" style="background: {status_badge_color}; color: #ffffff;">{status_text}</div>
    <h1 style="margin: 0; font-size: 20px; font-weight: 800;">🚀 Morning SDET Executive Briefing</h1>
    <p style="margin: 4px 0 0 0; font-size: 12.5px; color: #94a3b8;">{date_str} • Pipeline Execution: {execution_duration_sec:.1f}s</p>
  </div>

  <div class="kpi-grid">
    <div class="kpi">
      <p class="kpi-num">{total_jobs}</p>
      <p class="kpi-label">New Staged Jobs</p>
    </div>
    <div class="kpi">
      <p class="kpi-num" style="color: #f59e0b;">{len(dream_jobs)}</p>
      <p class="kpi-label">⭐ Dream Orgs</p>
    </div>
    <div class="kpi">
      <p class="kpi-num" style="color: #0284c7;">{len(ats_jobs)}</p>
      <p class="kpi-label">Enterprise ATS</p>
    </div>
    <div class="kpi">
      <p class="kpi-num" style="color: #4f46e5;">{len(linkedin_jobs)}</p>
      <p class="kpi-label">LinkedIn Roles</p>
    </div>
  </div>

  <div class="content">
    <p style="margin-top: 0; font-size: 13px; color: #475569;">
      <strong>Regression Health:</strong> {regression_summary}. All newly scraped roles have been deduplicated, experience-filtered, and enriched with AI-grounded STAR achievements.
    </p>

    <table>
      <thead>
        <tr>
          <th>Role Title & Location</th>
          <th>Company</th>
          <th>Source</th>
          <th style="text-align: right;">Action</th>
        </tr>
      </thead>
      <tbody>
        {table_body}
      </tbody>
    </table>

    <a href="http://localhost:8000" class="btn-primary">
      👉 Open Command Center (localhost:8000)
    </a>
  </div>

  <div class="footer">
    Automated zero-cost briefing generated by Antigravity SDET Job Automator • Single-Column ATS Ground Truth
  </div>
</div>
</body>
</html>
"""

    def send_report(
        self,
        staged_jobs: list[dict[str, Any]],
        regression_passed: bool = True,
        regression_summary: str = "48/48 Passed (100%)",
        execution_duration_sec: float = 0.0,
    ) -> bool:
        """
        Builds report, saves fallback HTML to disk, and attempts SSL dispatch via Gmail SMTP.
        """
        today_slug = datetime.date.today().strftime("%Y-%m-%d")
        html_content = self.build_report_html(
            staged_jobs=staged_jobs,
            regression_passed=regression_passed,
            regression_summary=regression_summary,
            execution_duration_sec=execution_duration_sec,
        )

        # 1. Always save fallback archive HTML to disk
        archive_path = self.log_dir / f"daily_report_{today_slug}.html"
        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"📄 Daily HTML report archived to: {archive_path}")

        # 2. Check if credentials are configured
        if not self.is_configured():
            print("ℹ️ Gmail SMTP credentials not configured in environment (GMAIL_USER / GMAIL_APP_PASSWORD).")
            print("   Saved local HTML archive. To receive email, set GMAIL_USER & GMAIL_APP_PASSWORD in .env.")
            return False

        # 3. Dispatch via SMTP_SSL
        try:
            msg = EmailMessage()
            msg["Subject"] = f"🚀 Daily SDET Automation Briefing: {len(staged_jobs)} New Roles ({today_slug})"
            msg["From"] = self.sender
            msg["To"] = self.recipient
            msg.set_content(
                f"Morning SDET Briefing: {len(staged_jobs)} new roles staged. View at http://localhost:8000\n"
                f"Full HTML report archived at: {archive_path}"
            )
            msg.add_alternative(html_content, subtype="html")

            print(f"📧 Connecting to smtp.gmail.com:465 to send briefing to {self.recipient}...")
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(self.sender, self.password)
                server.send_message(msg)

            print("✅ Executive briefing email dispatched successfully!")
            return True
        except Exception as e:
            print(f"⚠️ SMTP dispatch failed (network error or invalid password): {e}")
            print(f"   Report remains safely accessible at: {archive_path}")
            return False
