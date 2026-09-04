"""Best-effort "does the page actually render" evidence for a static
HTML/CSS/JS capstone submission — the counterpart to judge0_client.py for
projects that have no server-side process to execute at all. A static page
can't be handed to Judge0 (there's nothing to run headlessly on stdin/stdout),
so this loads it in a real headless browser instead and reports what
happened: whether it loaded, and any console errors — the same class of
"ground truth, not self-reported" evidence Python/Node submissions get from
actual execution.

Best-effort only, same as judge0_client.py: a missing Playwright install or a
launch failure means "no execution evidence" for this submission, never a
submission failure — see app/graph/nodes.py's code_execution_node."""
from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from app import config

logger = logging.getLogger("capstone.execution")


class BrowserCheckUnavailable(Exception):
    pass


def _is_safe_member(name: str) -> bool:
    if name.startswith("/") or name.startswith("\\"):
        return False
    if ":" in name:
        return False
    return ".." not in PurePosixPath(name).parts


def run_html_submission(zip_path: str, entry_point: str) -> dict:
    """Extracts the submitted zip to a throwaway temp directory (so relative
    `<link>`/`<script>`/`<img>` references resolve like they would for a real
    reviewer opening the file) and loads `entry_point` in headless Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserCheckUnavailable("Playwright is not installed.") from exc

    tmp_dir = tempfile.mkdtemp(prefix="capstone_html_")
    try:
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for info in zf.infolist():
                    if info.is_dir() or not _is_safe_member(info.filename):
                        continue
                    if PurePosixPath(info.filename).parts and PurePosixPath(info.filename).parts[0] in config.ZIP_IGNORE_DIR_NAMES:
                        continue
                    dest = Path(tmp_dir) / info.filename
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(dest, "wb") as out:
                        out.write(src.read())
        except (zipfile.BadZipFile, OSError) as exc:
            raise BrowserCheckUnavailable(f"Could not re-extract the zip for rendering: {exc}") from exc

        entry_path = Path(tmp_dir) / entry_point
        if not entry_path.exists():
            raise BrowserCheckUnavailable(f"Entry point {entry_point!r} was not found after extraction.")

        console_errors: list[str] = []
        page_errors: list[str] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    page = browser.new_page()
                    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
                    page.goto(entry_path.as_uri(), timeout=config.BROWSER_CHECK_TIMEOUT_MS)
                    page.wait_for_timeout(500)  # let async scripts/fetches settle
                    title = page.title()
                    body_text = (page.inner_text("body") or "")[:2000]
                    loaded = True
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001 — any Playwright/launch failure is "no evidence", not a crash
            logger.warning("Headless browser check failed: %s", exc)
            raise BrowserCheckUnavailable(str(exc)) from exc

        return {
            "available": True,
            "completed": True,
            "kind": "browser",
            "entry_point": entry_point,
            "status": "Loaded" if loaded else "Failed to load",
            "page_title": title,
            "console_errors": console_errors[:20],
            "page_errors": page_errors[:20],
            "rendered_text_snippet": body_text,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
