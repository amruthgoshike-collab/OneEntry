"""HTML -> PDF.

Jinja2 templates own all layout; the LLM never produces any of it.

Rendering runs through Playwright's Chromium rather than WeasyPrint: WeasyPrint
needs the GTK/Pango native stack, which does not ship on Windows and fails at
import with `cannot load library 'libgobject-2.0-0'`. Chromium's print-to-PDF
needs no system libraries and honours the same print CSS.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from app.money import format_inr

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["inr"] = format_inr


def render_html(template_name: str, context: dict) -> str:
    return _env.get_template(template_name).render(**context)


def html_to_pdf(html: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            # No external requests to wait for — everything is inlined.
            page.set_content(html, wait_until="load")
            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"},
            )
        finally:
            browser.close()
    return output_path


def render_pdf(template_name: str, context: dict, output_path: Path) -> Path:
    return html_to_pdf(render_html(template_name, context), output_path)
