"""Phase 3: screenshot-based structure troubleshooting.

When the deterministic checker (app/ingestion/structure_check.py) finds a
required folder/file missing, a confused student can attach a screenshot of
their file explorer, their extracted zip, or their IDE's file tree -- this
module sends that image to a vision-capable LLM call alongside the exact
list of what's missing, and gets back concrete, screenshot-grounded guidance
instead of the student having to guess what the earlier error meant.
"""
from __future__ import annotations

import base64

from app.graph import prompts
from app.llm.client import call_json


def analyze_structure_screenshot(
    image_bytes: bytes, mime_type: str, missing_items: list[dict], matched_items: list[dict]
) -> dict:
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    return call_json(
        system=prompts.screenshot_structure_prompt(missing_items, matched_items),
        user="Look at the attached screenshot and answer now.",
        image_data_url=data_url,
        temperature=0.1,
    )
