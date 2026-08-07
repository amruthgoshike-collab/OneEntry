"""HTML -> PDF.

Jinja2 templates own all layout; the LLM never produces any of it.

Rendering runs through Playwright's Chromium rather than WeasyPrint: WeasyPrint
needs the GTK/Pango native stack, which does not ship on Windows and fails at
import with `cannot load library 'libgobject-2.0-0'`. Chromium's print-to-PDF
needs no system libraries and honours the same print CSS.

Chromium is launched once and kept warm. Starting the Playwright driver and
launching a browser per call measures 0.6-2.6s; reusing a warm browser is
~0.1s, and that difference is what keeps quotation-approval instant.

Playwright's sync API binds its objects to the thread that created them, and
FastAPI serves sync routes from a rotating threadpool — so every render is
funnelled through one long-lived renderer thread over a queue rather than
being called directly.
"""
import atexit
import logging
import queue
import threading
from concurrent.futures import Future
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.money import format_inr

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
RENDER_TIMEOUT_SECONDS = 60

PAGE_OPTIONS = {
    "format": "A4",
    "print_background": True,
    "margin": {"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"},
}

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["inr"] = format_inr

_jobs: queue.Queue = queue.Queue()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()


def render_html(template_name: str, context: dict) -> str:
    return _env.get_template(template_name).render(**context)


def _render_loop() -> None:
    """Owns the browser for the life of the process."""
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch()
    logger.info("PDF renderer ready (Chromium warm)")
    try:
        while True:
            job = _jobs.get()
            if job is None:
                break
            html, output_path, future = job
            try:
                if not browser.is_connected():  # crashed under us
                    browser = playwright.chromium.launch()
                page = browser.new_page()
                try:
                    # Nothing external to fetch — every asset is inlined.
                    page.set_content(html, wait_until="load")
                    page.pdf(path=str(output_path), **PAGE_OPTIONS)
                finally:
                    page.close()
                future.set_result(output_path)
            except Exception as exc:
                future.set_exception(exc)
            finally:
                _jobs.task_done()
    finally:
        browser.close()
        playwright.stop()


def warm_up() -> None:
    """Start the renderer thread so the first real render isn't the slow one."""
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(
                target=_render_loop, name="pdf-renderer", daemon=True
            )
            _worker.start()


@atexit.register
def _shutdown() -> None:
    if _worker is not None and _worker.is_alive():
        _jobs.put(None)
        _worker.join(timeout=5)


def html_to_pdf(html: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    warm_up()
    future: Future = Future()
    _jobs.put((html, output_path, future))
    return future.result(timeout=RENDER_TIMEOUT_SECONDS)


def render_pdf(template_name: str, context: dict, output_path: Path) -> Path:
    return html_to_pdf(render_html(template_name, context), output_path)
