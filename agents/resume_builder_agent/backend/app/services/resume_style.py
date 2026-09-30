"""Candidate-chosen style for the resume PDF: font family, text size and line
spacing, applied on top of whichever template is selected.

Every template builds its text styles through ReportLab's ParagraphStyle,
which render_reportlab_resume_pdf passes to it. Swapping in the subclass from
styled_paragraph_style() applies the choice everywhere at once -- the font is
replaced (keeping bold/italic), sizes and line heights are scaled -- so no
template's own layout code changes, and "template default" leaves the PDF
exactly as it was.

Beyond ReportLab's built-in Helvetica and Times, four free fonts ship in
app/assets/fonts (SIL Open Font License; licence files alongside): Carlito
(metric-compatible with Calibri), Lato, Open Sans and Liberation Serif
(metric-compatible with Times New Roman).
"""
from __future__ import annotations

import threading
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
TEMPLATE_DEFAULT = "template"

# id -> label, and either built-in ReportLab names or the TTF file stem.
FONT_FAMILIES = {
    TEMPLATE_DEFAULT: {"label": "Template default"},
    "carlito": {"label": "Carlito (Calibri style)", "file": "Carlito", "kind": "sans"},
    "helvetica": {
        "label": "Helvetica (Arial style)",
        "kind": "sans",
        "builtin": {"regular": "Helvetica", "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique", "bold_italic": "Helvetica-BoldOblique"},
    },
    "lato": {"label": "Lato", "file": "Lato", "kind": "sans"},
    "open-sans": {"label": "Open Sans", "file": "OpenSans", "kind": "sans"},
    "times": {
        "label": "Times (classic serif)",
        "kind": "serif",
        "builtin": {"regular": "Times-Roman", "bold": "Times-Bold", "italic": "Times-Italic", "bold_italic": "Times-BoldItalic"},
    },
    "liberation-serif": {"label": "Liberation Serif (Times New Roman style)", "file": "LiberationSerif", "kind": "serif"},
}
FONT_SCALES = {0.9: "90% (smaller)", 0.95: "95%", 1.0: "100% (template size)", 1.05: "105%", 1.1: "110%", 1.15: "115%", 1.2: "120% (larger)"}
LINE_SPACINGS = {0.9: "Compact", 1.0: "Standard", 1.15: "Relaxed", 1.3: "Spacious"}
DEFAULT_STYLE = {"font_family": TEMPLATE_DEFAULT, "font_scale": 1.0, "line_spacing": 1.0}

_VARIANTS = {"regular": "Regular", "bold": "Bold", "italic": "Italic", "bold_italic": "BoldItalic"}
_registered: dict[str, dict[str, str]] = {}
_lock = threading.Lock()


def style_options() -> dict:
    """What the editor offers, in display order."""
    return {
        "font_families": [{"id": key, "label": value["label"]} for key, value in FONT_FAMILIES.items()],
        "font_scales": [{"value": key, "label": label} for key, label in FONT_SCALES.items()],
        "line_spacings": [{"value": key, "label": label} for key, label in LINE_SPACINGS.items()],
        "default": dict(DEFAULT_STYLE),
    }


def _closest(value, allowed) -> float:
    return min(allowed, key=lambda option: abs(option - float(value)))


def normalize_style(raw, strict: bool = False) -> dict:
    """A complete, valid style. With strict=True an unknown value is an error
    (for a candidate's own choice); otherwise it falls back to the default."""
    if not isinstance(raw, dict):
        if strict and raw is not None:
            raise ValueError("style_settings must be an object")
        return dict(DEFAULT_STYLE)
    style = dict(DEFAULT_STYLE)
    family = raw.get("font_family", TEMPLATE_DEFAULT)
    if family in FONT_FAMILIES:
        style["font_family"] = family
    elif strict:
        raise ValueError(f"Unknown font_family. Use one of: {', '.join(FONT_FAMILIES)}.")
    for key, allowed in (("font_scale", FONT_SCALES), ("line_spacing", LINE_SPACINGS)):
        if key not in raw or raw[key] is None:
            continue
        try:
            style[key] = _closest(raw[key], allowed)
        except (TypeError, ValueError):
            if strict:
                raise ValueError(f"{key} must be a number")
    return style


def is_default(style: dict | None) -> bool:
    return normalize_style(style) == DEFAULT_STYLE


def _family_fonts(family_id: str) -> dict[str, str] | None:
    """ReportLab font names for regular/bold/italic/bold_italic, registering
    bundled TTF files on first use."""
    family = FONT_FAMILIES.get(family_id)
    if not family or family_id == TEMPLATE_DEFAULT:
        return None
    if "builtin" in family:
        return family["builtin"]
    with _lock:
        if family_id not in _registered:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib.fonts import addMapping

            stem = family["file"]
            names = {}
            for variant, suffix in _VARIANTS.items():
                name = stem if variant == "regular" else f"{stem}-{suffix}"
                pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / f"{stem}-{suffix}.ttf")))
                names[variant] = name
            # Inline <b>/<i> markup inside a paragraph picks the right face.
            addMapping(names["regular"], 0, 0, names["regular"])
            addMapping(names["regular"], 1, 0, names["bold"])
            addMapping(names["regular"], 0, 1, names["italic"])
            addMapping(names["regular"], 1, 1, names["bold_italic"])
            _registered[family_id] = names
    return _registered[family_id]


def _variant_of(font_name: str) -> str:
    name = font_name or "Helvetica"
    bold = "Bold" in name
    italic = "Italic" in name or "Oblique" in name
    return "bold_italic" if bold and italic else "bold" if bold else "italic" if italic else "regular"


def styled_paragraph_style(base_cls, style: dict | None):
    """ParagraphStyle, or a drop-in constructor applying `style` to every
    style a template creates. It returns genuine ParagraphStyle objects
    (ReportLab requires a parent to be of the same class). Sizes are scaled
    once: a style inheriting from one that was already scaled keeps the
    inherited value."""
    style = normalize_style(style)
    if style == DEFAULT_STYLE:
        return base_cls
    fonts = _family_fonts(style["font_family"])
    scale = style["font_scale"]
    spacing = style["line_spacing"]

    def styled(name, parent=None, **kw):
        created = base_cls(name, parent, **kw)
        inherited_scaled = getattr(parent, "_digidara_styled", False)
        if fonts:
            created.fontName = fonts[_variant_of(created.fontName)]
        if "fontSize" in kw or not inherited_scaled:
            created.fontSize = round(created.fontSize * scale, 2)
        if "leading" in kw or not inherited_scaled:
            created.leading = round(created.leading * scale * spacing, 2)
        created._digidara_styled = True
        return created

    return styled
