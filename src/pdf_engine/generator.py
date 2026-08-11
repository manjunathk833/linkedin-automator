import asyncio
import os

from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright

from src.resume_store.models import ResumeProfile


class PDFGenerator:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.templates_dir = os.path.join(self.base_dir, "templates")
        self.env = Environment(loader=FileSystemLoader(self.templates_dir))
        self.template = self.env.get_template("resume.html.j2")
        self.css_path = os.path.join(self.templates_dir, "style.css")

    async def generate_pdf_async(self, profile: ResumeProfile, output_path: str):
        """Generates a PDF asynchronously using Playwright."""
        # 1. Render HTML with Jinja2
        rendered_html = self.template.render(profile=profile)

        # Read CSS content to inject it directly
        with open(self.css_path, "r") as f:
            css_content = f.read()

        # Inject CSS into HTML
        html_with_styles = rendered_html.replace(
            '<link rel="stylesheet" href="style.css">', f"<style>\n{css_content}\n</style>"
        )

        # 2. Use Playwright to render the HTML string to PDF
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Load the raw HTML
            await page.set_content(html_with_styles, wait_until="networkidle")

            # Print to PDF
            await page.pdf(
                path=output_path,
                format="A4",
                margin={"top": "15mm", "right": "20mm", "bottom": "15mm", "left": "20mm"},
                print_background=True,
            )

            await browser.close()

        return output_path

    def generate_pdf(self, profile: ResumeProfile, output_path: str):
        """Synchronous wrapper for PDF generation."""
        return asyncio.run(self.generate_pdf_async(profile, output_path))
