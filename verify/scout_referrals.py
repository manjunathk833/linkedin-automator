import asyncio
import json
import re

from playwright.async_api import async_playwright

from src.tailor.referral_generator import ReferralNoteGenerator


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = context.pages[0]

        targets = [
            {
                "company": "Apple",
                "role": "Software Development Engineer in Test, Retail CS&E",
                "req_id": "4477572600",
                "job_url": "https://www.linkedin.com/jobs/view/4477572600/",
                "search_url": "https://www.linkedin.com/search/results/people/?keywords=%22Apple%22%20(%22Quality%20Engineering%22%20OR%20%22SDET%22%20OR%20%22Engineering%20Manager%22)%20Bengaluru&origin=GLOBAL_SEARCH_HEADER",
            },
            {
                "company": "Swiggy",
                "role": "Sr. Software Development Engineer in Test",
                "req_id": "4481865334",
                "job_url": "https://www.linkedin.com/jobs/view/4481865334/",
                "search_url": "https://www.linkedin.com/search/results/people/?keywords=%22Swiggy%22%20(%22QA%22%20OR%20%22SDET%22%20OR%20%22Engineering%20Manager%22)%20Bengaluru&origin=GLOBAL_SEARCH_HEADER",
            },
            {
                "company": "Zscaler",
                "role": "Principal Software Development Engineer - QA + Networking",
                "req_id": "5271592007",
                "job_url": "https://job-boards.greenhouse.io/zscaler/jobs/5271592007",
                "search_url": "https://www.linkedin.com/search/results/people/?keywords=%22Zscaler%22%20(%22Director%22%20OR%20%22Engineering%20Manager%22%20OR%20%22Principal%20SDET%22%20OR%20%22QA%22)%20Bengaluru&origin=GLOBAL_SEARCH_HEADER",
            },
        ]

        recon_data = {}

        for t in targets:
            print(f"=== Scouting {t['company']} ===")
            await page.goto(t["search_url"], wait_until="domcontentloaded")
            await asyncio.sleep(4)

            # Scroll down to ensure all cards load
            await page.evaluate("() => window.scrollTo(0, 1000)")
            await asyncio.sleep(2)

            raw_cards = await page.evaluate("""() => {
                const anchors = Array.from(document.querySelectorAll('a[href*="/in/"]'));
                return anchors.map(a => {
                    const text = a.innerText.trim();
                    const href = a.href.split('?')[0];
                    return { text, href };
                });
            }""")

            leads = []
            seen_urls = set()
            for item in raw_cards:
                href = item["href"]
                text = item["text"]
                if not href or href in seen_urls:
                    continue
                if any(x in href for x in ["/jobs/", "/company/", "search/results"]):
                    continue
                if "entity history" in text.lower():
                    continue

                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                name_line = lines[0]
                clean_name = re.sub(
                    r"[\s•·]+(1st|2nd|3rd\+?|\d+(?:st|nd|rd|th)?)$", "", name_line, flags=re.IGNORECASE
                ).strip()
                if (
                    not clean_name
                    or "LinkedIn Member" in clean_name
                    or len(clean_name) < 3
                    or clean_name in ["Connect", "Message", "Follow"]
                ):
                    continue

                idx = 1
                if idx < len(lines) and re.match(r"^[•·]?\s*(?:1st|2nd|3rd\+?)$", lines[idx]):
                    idx += 1
                headline = lines[idx] if idx < len(lines) else ""
                idx += 1

                if not headline or headline in ["Connect", "Message", "Follow"]:
                    continue

                # Find location & mutuals
                location = ""
                mutuals = ""
                for line in lines[idx:]:
                    if any(
                        k in line.lower()
                        for k in ["india", "bengaluru", "bangalore", "area", "mumbai", "delhi", "karnataka"]
                    ) and not any(k in line.lower() for k in ["mutual", "connection"]):
                        location = line
                    elif "mutual connection" in line.lower():
                        mutuals = line

                # Prioritize leads working at or relevant to the target company
                # or have strong mutual connection counts
                seen_urls.add(href)

                # Generate tailored connection note (<300 chars) and InMail pitch (<1000 chars)
                payload = {
                    "company_name": t["company"],
                    "job_title": t["role"],
                    "requisition_id": t["req_id"],
                    "job_url": t["job_url"],
                }
                first_name = clean_name.split()[0]
                note_300 = ReferralNoteGenerator.generate_connection_note(
                    payload, recipient_name=first_name, max_chars=300
                )
                pitch_1000 = ReferralNoteGenerator.generate_inmail_pitch(
                    payload, recipient_name=first_name, max_chars=1000
                )

                leads.append(
                    {
                        "name": clean_name,
                        "first_name": first_name,
                        "url": href,
                        "headline": headline,
                        "location": location,
                        "mutuals": mutuals,
                        "connection_note": note_300,
                        "inmail_pitch": pitch_1000,
                    }
                )

            print(f"Discovered {len(leads)} high-signal leads for {t['company']}")
            recon_data[t["company"]] = {
                "target_role": t["role"],
                "target_req_id": t["req_id"],
                "job_url": t["job_url"],
                "leads": leads[:5],
            }

        # Write to JSON report
        out_file = "data/logs/referral_reconnaissance.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(recon_data, f, indent=2)
        print(f"\nSaved structured referral reconnaissance pack to {out_file}!")


if __name__ == "__main__":
    asyncio.run(main())
