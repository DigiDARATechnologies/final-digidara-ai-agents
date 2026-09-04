"""Canonical display formatting for generated and historical explanations."""

import re

from .security import clean_text


STEP_MARKER = re.compile(r"\bStep\s*#?\s*(\d+)\s*(?::|[.)-])\s*", re.IGNORECASE)


def normalize_explanation(value, maximum=3000):
    """Put every embedded ``Step N`` segment on its own canonical line.

    Plain explanations remain a single cleaned paragraph. This function does
    not rewrite reasoning or calculations; it changes only separators and the
    marker's presentation.
    """
    raw=re.sub(r"<[^>]+>","",str(value or "")).replace("\r\n","\n").replace("\r","\n").strip()
    matches=list(STEP_MARKER.finditer(raw))
    if len(matches)<2:
        return clean_text(raw,maximum)

    lines=[]
    intro=clean_text(raw[:matches[0].start()],maximum)
    if intro:lines.append(intro)
    for index,match in enumerate(matches):
        end=matches[index+1].start() if index+1<len(matches) else len(raw)
        body=clean_text(raw[match.end():end],maximum)
        if body:lines.append(f"Step {int(match.group(1))}: {body}")
    return "\n".join(lines)[:maximum]

