"""
Dynamic Outreach Message Composer for LinkedIn Hiring Posts.
Generates personalized, high-converting connection request notes (≤300 chars),
InMail pitches (≤1000 chars), and direct email drafts tailored to
Engineers, Hiring Managers, and Recruiters citing their exact post.
"""

from __future__ import annotations

from typing import Any

PORTFOLIO_URL = "manjunathhk.netlify.app/"


class PostOutreachComposer:
    """
    Crafts customized outreach communications for discovered LinkedIn hiring posts.
    """

    def generate_connection_note(self, post_data: dict[str, Any]) -> str:
        """
        Generates a personalized connection request note strictly ≤ 300 characters.
        Adapts dynamically based on whether author is an Engineer, Leader, or Recruiter.
        """
        raw_name = post_data.get("author_name", "there").strip()
        first_name = raw_name.split()[0] if raw_name else "there"
        # Sanitize name
        if len(first_name) > 15 or not first_name.isalpha():
            first_name = "there"

        company = post_data.get("company_name", "").strip()
        role_category = post_data.get("author_role_category", "ENGINEER")
        job_codes = post_data.get("extracted_job_codes", [])
        job_code_str = f" (Req: {job_codes[0]})" if job_codes else ""

        # Differentiated angle based on author persona
        if role_category == "ENGINEER":
            # Peer-to-peer engineering referral angle
            if company and company != "Tech Enterprise":
                hook = f"Saw your post on {company} SDET referrals{job_code_str}."
            else:
                hook = f"Saw your post on SDET referrals{job_code_str}."
        elif role_category == "LEADER":
            # Engineering manager / lead angle
            if company and company != "Tech Enterprise":
                hook = f"Saw you're expanding your SDET team at {company}{job_code_str}."
            else:
                hook = f"Saw you're hiring for your SDET team{job_code_str}."
        elif role_category == "RECRUITER":
            # Recruiter / TA angle
            if company and company != "Tech Enterprise":
                hook = f"Saw the {company} SDET role you posted{job_code_str}."
            else:
                hook = f"Saw the open SDET role you posted{job_code_str}."
        else:
            # General peer referral angle
            if company and company != "Tech Enterprise":
                hook = f"Saw your post on {company} openings{job_code_str}."
            else:
                hook = f"Saw your post on open team roles{job_code_str}."

        pitch = "I bring ~7 YOE in Playwright, TypeScript & API contract testing."
        ask = f"Portfolio: {PORTFOLIO_URL} - would love to connect!"

        full_note = f"Hi {first_name}, {hook} {pitch} {ask}".strip()

        # Strict character ceiling governor (300 chars)
        if len(full_note) <= 300:
            return full_note

        # Condensed fallback if needed
        condensed = f"Hi {first_name}, {hook} SDET (~7 YOE) in Playwright, TypeScript & API testing. Portfolio: {PORTFOLIO_URL} - would love to connect!"
        if len(condensed) <= 300:
            return condensed

        return f"Hi {first_name}, saw your SDET hiring post! SDET (~7 YOE) in Playwright & TypeScript. Portfolio: {PORTFOLIO_URL} - would love to connect!"[
            :300
        ]

    def generate_inmail_pitch(self, post_data: dict[str, Any]) -> str:
        """
        Generates an InMail or direct message pitch strictly ≤ 1000 characters.
        """
        raw_name = post_data.get("author_name", "there").strip()
        first_name = raw_name.split()[0] if raw_name else "there"
        company = post_data.get("company_name", "your team")
        job_codes = post_data.get("extracted_job_codes", [])
        job_ref = f" (Ref: {job_codes[0]})" if job_codes else ""

        pitch = (
            f"Hi {first_name},\n\n"
            f"I came across your LinkedIn post regarding the open SDET / QA role at {company}{job_ref} and wanted to reach out directly.\n\n"
            f"I am a Senior SDET / Automation Lead with ~7 years of experience specializing in resilient, high-speed test architecture:\n"
            f"• Playwright & TypeScript: Distributed end-to-end suites with parallelized shard execution.\n"
            f"• Microservice & API Testing: Contract testing with Pact and WireMock stubbing.\n"
            f"• Event-Driven Validation: Kafka event stream assertions and Docker containerized pipelines.\n\n"
            f"You can review my test engineering architecture and projects on my portfolio: https://{PORTFOLIO_URL}\n\n"
            f"If your team is still reviewing profiles, I'd welcome the opportunity to share my resume and discuss how I can contribute to {company}'s quality goals.\n\n"
            f"Best regards,\n"
            f"Manjunath H K\n"
            f"Senior SDET | Bengaluru / Remote"
        )

        return pitch[:1000]

    def generate_email_draft(self, post_data: dict[str, Any], recipient_email: str) -> dict[str, str]:
        """
        Generates a direct email subject and body for posts containing contact emails.
        """
        raw_name = post_data.get("author_name", "Hiring Team").strip()
        first_name = raw_name.split()[0] if raw_name else "Hiring Team"
        company = post_data.get("company_name", "your team")
        job_codes = post_data.get("extracted_job_codes", [])
        code_str = f" - Job Code {job_codes[0]}" if job_codes else ""

        subject = f"Application: Senior SDET / QA Automation Lead - Manjunath H K{code_str}"
        body = (
            f"Dear {first_name},\n\n"
            f"I hope this note finds you well.\n\n"
            f"I am writing in response to your recent LinkedIn update regarding the Senior SDET / QA opening at {company}.\n\n"
            f"With approximately 7 years of test engineering experience, I specialize in designing robust automation frameworks using Playwright, TypeScript, and Java. My core focus has been scalable microservice contract testing, Kafka event validation, and CI/CD test sharding.\n\n"
            f"Portfolio: https://{PORTFOLIO_URL}\n"
            f"LinkedIn: https://www.linkedin.com/in/manjunath-h-k-ab30b1146/\n\n"
            f"I have attached my resume for your review and would love to connect for a quick conversation.\n\n"
            f"Thank you for your time and consideration.\n\n"
            f"Sincerely,\n"
            f"Manjunath H K\n"
            f"Bengaluru, India"
        )

        return {
            "to": recipient_email,
            "subject": subject,
            "body": body,
        }
