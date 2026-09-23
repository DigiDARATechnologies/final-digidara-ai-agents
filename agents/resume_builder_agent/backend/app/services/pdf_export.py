from html import escape
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import urlparse

from app.template_catalog import LEGACY_TEMPLATE_ALIASES, VALID_TEMPLATE_IDS

VALID_TEMPLATES = VALID_TEMPLATE_IDS | set(LEGACY_TEMPLATE_ALIASES)
# Shared presentation contract. Both the browser preview and ReportLab export
# consume these values so alignment and visual hierarchy cannot silently drift.
TEMPLATE_STYLE_SPECS = {
    "ats-standard": {"accent": "#1f2937", "header_alignment": "left", "section_alignment": "left", "layout": "single-column"},
    "steady-form": {"accent": "#26323f", "header_alignment": "center", "section_alignment": "left", "layout": "single-column"},
    "classic-serif": {"accent": "#111111", "header_alignment": "center", "section_alignment": "left", "layout": "single-column"},
    "mercury-flow": {"accent": "#5f655f", "header_alignment": "center", "section_alignment": "left", "layout": "single-column"},
    "slate-dawn": {"accent": "#29224a", "header_alignment": "center", "section_alignment": "left", "layout": "two-column"},
    "minimalist-line": {"accent": "#334155", "header_alignment": "left", "section_alignment": "left", "layout": "single-column"},
    "sidebar-focus": {"accent": "#0f766e", "header_alignment": "left", "section_alignment": "left", "layout": "two-column"},
    "compact-impact": {"accent": "#1d4ed8", "header_alignment": "center", "section_alignment": "left", "layout": "single-column"},
    "studio-bold": {"accent": "#be123c", "header_alignment": "left", "section_alignment": "left", "layout": "single-column"},
    "timeline-teal": {"accent": "#0f766e", "header_alignment": "left", "section_alignment": "left", "layout": "two-column"},
    "sidebar-mono": {"accent": "#334155", "header_alignment": "left", "section_alignment": "left", "layout": "two-column"},
    "horizon-coral": {"accent": "#e76f51", "header_alignment": "left", "section_alignment": "left", "layout": "single-column"},
    "ledger-navy": {"accent": "#1e3a5f", "header_alignment": "left", "section_alignment": "left", "layout": "single-column"}, "split-olive": {"accent": "#556b2f", "header_alignment": "left", "section_alignment": "left", "layout": "two-column"}, "canvas-sand": {"accent": "#a16207", "header_alignment": "center", "section_alignment": "left", "layout": "single-column"}, "column-indigo": {"accent": "#4338ca", "header_alignment": "left", "section_alignment": "left", "layout": "two-column"}, "arc-slate": {"accent": "#475569", "header_alignment": "left", "section_alignment": "left", "layout": "single-column"}, "pulse-rose": {"accent": "#be185d", "header_alignment": "left", "section_alignment": "left", "layout": "two-column"}, "signal-amber": {"accent": "#b45309", "header_alignment": "left", "section_alignment": "left", "layout": "single-column"}, "navy-portrait": {"accent": "#13233a", "header_alignment": "left", "section_alignment": "center", "layout": "single-column"},
}


def template_style_spec(template_choice):
    return TEMPLATE_STYLE_SPECS.get(normalize_template_id(template_choice), TEMPLATE_STYLE_SPECS["steady-form"])


def render_resume_pdf(resume_data, template_choice):
    template = normalize_template_id(template_choice)
    # ReportLab is the canonical renderer on every platform. Keeping one engine
    # eliminates browser/canvas differences and avoids native GTK dependencies
    # on Windows while preserving selectable ATS-readable text.
    return render_reportlab_resume_pdf(resume_data, template)


def normalize_template_id(template_choice):
    template = (template_choice or "steady-form").lower()
    return LEGACY_TEMPLATE_ALIASES.get(template, template)


def header_role(resume):
    role = (
        resume.get("target_role")
        or resume.get("targetRole")
        or resume.get("target_job_title")
        or resume.get("role")
        or ""
    )
    return str(role).strip()


def render_reportlab_resume_pdf(resume, template_choice):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            KeepTogether,
            ListFlowable,
            ListItem,
            Paragraph,
            Indenter,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        return render_basic_resume_pdf(resume, template_choice)

    if template_choice == "navy-portrait":
        return render_reportlab_navy_portrait_pdf(resume, colors, A4, ParagraphStyle, getSampleStyleSheet, inch, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, keep_together=KeepTogether)
    if template_choice in VALID_TEMPLATE_IDS:
        return render_reportlab_analyst_pro_pdf(
            resume,
            template_choice,
            colors,
            A4,
            ParagraphStyle,
            getSampleStyleSheet,
            inch,
            ListFlowable,
            ListItem,
            Paragraph,
            Indenter,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
            keep_together=KeepTogether,
        )

    buffer = BytesIO()
    is_classic = template_choice in {"classic", "ats", "compact"}
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ResumeName",
            parent=styles["Heading1"],
            alignment=1,
            fontName="Times-Bold" if is_classic else "Helvetica-Bold",
            fontSize=24 if is_classic else 22,
            leading=28 if is_classic else 26,
            textColor=colors.HexColor("#172033"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ResumeTitle",
            parent=styles["Normal"],
            alignment=1,
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#526070"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ResumeSection",
            parent=styles["Heading2"],
            borderColor=colors.HexColor("#172033" if is_classic else "#cbd5e1"),
            borderPadding=(0, 0, 3, 0),
            borderWidth=0,
            borderWidthBottom=1,
            fontName="Times-Bold" if is_classic else "Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#172033"),
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    body_style = ParagraphStyle(
        name="ResumeBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        name="ResumeMeta",
        parent=body_style,
        alignment=1,
        fontSize=9,
        textColor=colors.HexColor("#526070"),
    )

    story = []
    info = resume.get("personal_info") or {}
    if template_choice == "modern":
        header_style = ParagraphStyle(
            name="ModernHeader",
            parent=styles["Normal"],
            backColor=colors.HexColor("#172033"),
            borderPadding=(14, 16, 14, 16),
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=colors.white,
            spaceAfter=10,
        )
        header_text = "<br/>".join(
            filter(
                None,
                [
                    f"<font size='26'>{pdf_text(info.get('name') or 'Your Name')}</font>",
                    pdf_text(header_role(resume)),
                    pdf_text(contact_line(info)),
                    links_markup_line(info),
                ],
            )
        )
        story.append(Paragraph(header_text, header_style))
    else:
        story.append(
            Paragraph(
                pdf_text(info.get("name") or "Your Name"),
                styles["ResumeName"],
            )
        )
        role = header_role(resume)
        if role:
            story.append(Paragraph(pdf_text(role), styles["ResumeTitle"]))

        contact = contact_line(info)
        links = links_markup_line(info)
        if contact:
            story.append(Paragraph(pdf_text(contact), meta_style))
        if links:
            story.append(Paragraph(links, meta_style))
        story.append(Spacer(1, 8))

    add_paragraph_section(
        story,
        "Professional Summary",
        resume.get("summary"),
        styles,
        body_style,
        Paragraph,
    )
    add_entries_section(
        story,
        "Education",
        [education_pdf_entry(item) for item in resume.get("education", [])],
        styles,
        body_style,
        meta_style,
        Paragraph,
        ListFlowable,
        ListItem,
    )
    add_list_section(
        story,
        "Technical Skills",
        [item.get("skill_name") for item in resume.get("skills", [])],
        styles,
        body_style,
        Paragraph,
    )
    add_entries_section(
        story,
        "Work Experience",
        [experience_pdf_entry(item) for item in resume.get("experience", [])],
        styles,
        body_style,
        meta_style,
        Paragraph,
        ListFlowable,
        ListItem,
    )
    add_entries_section(
        story,
        "Projects",
        [project_pdf_entry(item) for item in resume.get("projects", [])],
        styles,
        body_style,
        meta_style,
        Paragraph,
        ListFlowable,
        ListItem,
    )
    add_entries_section(
        story,
        "Publications",
        [generic_pdf_entry(item) for item in resume.get("publications", [])],
        styles,
        body_style,
        meta_style,
        Paragraph,
        ListFlowable,
        ListItem,
    )
    add_entries_section(
        story,
        "Certifications",
        [certification_pdf_entry(item) for item in resume.get("certifications", [])],
        styles,
        body_style,
        meta_style,
        Paragraph,
        ListFlowable,
        ListItem,
    )
    add_entries_section(
        story,
        "Languages",
        [language_pdf_entry(item) for item in resume.get("languages", [])],
        styles,
        body_style,
        meta_style,
        Paragraph,
        ListFlowable,
        ListItem,
    )
    add_entries_section(
        story,
        "Achievements",
        [generic_pdf_entry(item) for item in resume.get("achievements", [])],
        styles,
        body_style,
        meta_style,
        Paragraph,
        ListFlowable,
        ListItem,
    )
    declaration_text = resolved_declaration(resume)
    if declaration_text and declaration_text.strip():
        add_declaration_section(
            story,
            "Declaration",
            declaration_text,
            styles,
            body_style,
            Paragraph,
            keep_together=KeepTogether,
        )

    doc.build(story)
    return buffer.getvalue()


def render_reportlab_navy_portrait_pdf(resume, colors, page_size, paragraph_style, get_styles, inch, list_flowable, list_item, paragraph, document, spacer, table, table_style, keep_together=None):
    """FlowCV-inspired navy template with a readable, ATS-safe text structure."""
    buffer = BytesIO()
    page_width, _ = page_size
    doc = document(buffer, pagesize=page_size, leftMargin=0, rightMargin=0, topMargin=0.35 * inch, bottomMargin=0.4 * inch)
    styles = get_styles()
    navy, pale, ink, muted = "#13233a", "#edf0f3", "#18212d", "#5d6875"
    name = paragraph_style("NavyName", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=22, leading=25, textColor=colors.white)
    tagline = paragraph_style("NavyTagline", parent=styles["Normal"], fontName="Helvetica", fontSize=8.8, leading=12, textColor=colors.HexColor("#dbe7f4"))
    contact = paragraph_style("NavyContact", parent=tagline, fontSize=8, leading=11)
    section = paragraph_style("NavySection", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.2, leading=12, alignment=1, textColor=colors.HexColor(navy), backColor=colors.HexColor(pale), spaceBefore=9, spaceAfter=5, borderPadding=(4, 4, 4, 4))
    title = paragraph_style("NavyEntryTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.2, leading=11, textColor=colors.HexColor(ink))
    role = paragraph_style("NavyRole", parent=styles["Normal"], fontSize=8.4, leading=10.5, textColor=colors.HexColor(muted))
    body = paragraph_style("NavyBody", parent=styles["Normal"], fontSize=8.2, leading=10.5, textColor=colors.HexColor(ink))
    date = paragraph_style("NavyDate", parent=role, fontSize=7.7, alignment=0)
    info = resume.get("personal_info") or {}
    skills = [str(item.get("skill_name") or item.get("name") or "").strip() for item in resume.get("skills", [])]
    tag_parts = [header_role(resume)] + skills[:3]
    header_rows = [paragraph(pdf_text(info.get("name") or "Your Name"), name)]
    if any(tag_parts): header_rows.append(paragraph(pdf_text(" - ".join(part for part in tag_parts if part)), tagline))
    first_contact = " | ".join(part for part in [info.get("email"), info.get("phone")] if part)
    second_contact = " | ".join(part for part in [clean_location(info.get("location"))] + [format_profile_link(link) for link in info.get("links", []) if format_profile_link(link)])
    if first_contact: header_rows.append(paragraph(pdf_text(first_contact), contact))
    if second_contact: header_rows.append(paragraph(pdf_text(second_contact), contact))
    photo_name = str(resume.get("profile_photo") or "")
    photo_path = Path(__file__).resolve().parents[2] / "uploads" / "resume_photos" / Path(photo_name).name
    header_data, header_widths = [[header_rows]], [page_width]
    if photo_name and photo_path.is_file():
        from reportlab.platypus import Flowable
        from reportlab.lib.utils import ImageReader
        class CircularPhoto(Flowable):
            def __init__(self, path, size):
                super().__init__(); self.path, self.size = str(path), size; self.width = self.height = size
            def draw(self):
                path = self.canv.beginPath(); path.circle(self.size / 2, self.size / 2, self.size / 2); self.canv.saveState(); self.canv.clipPath(path, stroke=0, fill=0); self.canv.drawImage(ImageReader(self.path), 0, 0, self.size, self.size, preserveAspectRatio=True, anchor='c'); self.canv.restoreState()
        header_data, header_widths = [[CircularPhoto(photo_path, 0.62 * inch), header_rows]], [1.36 * inch, page_width - 1.36 * inch]
    header_style = [("BACKGROUND", (0,0), (-1,-1), colors.HexColor(navy)), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("TOPPADDING", (0,0), (-1,-1), 0.24*inch), ("BOTTOMPADDING", (0,0), (-1,-1), 0.2*inch)]
    if len(header_widths) == 1:
        header_style.extend([("LEFTPADDING", (0,0), (-1,-1), 0.62*inch), ("RIGHTPADDING", (0,0), (-1,-1), 0.62*inch)])
    else:
        header_style.extend([("LEFTPADDING", (0,0), (0,0), 0.62*inch), ("RIGHTPADDING", (0,0), (0,0), 0.08*inch), ("LEFTPADDING", (1,0), (1,0), 0.08*inch), ("RIGHTPADDING", (1,0), (1,0), 0.62*inch)])
    story = [table(header_data, colWidths=header_widths, style=table_style(header_style))]
    content_width = page_width - 1.24 * inch
    story.append(spacer(1, 8))
    def heading(label): story.append(paragraph(pdf_text(label.upper()), section))
    def entry(item, kind):
        if kind == "experience":
            left = "<br/>".join(filter(None, [pdf_text(date_range(item.get("start_date"), item.get("end_date"))), pdf_text(clean_location(item.get("location")))]))
            right = [paragraph(pdf_text(item.get("company") or ""), title), paragraph(pdf_text(item.get("role") or ""), role)]
            bullets = item.get("ai_generated_bullets") or ([item.get("raw_input")] if item.get("raw_input") else [])
        else:
            left = pdf_text(date_range(item.get("start_date"), item.get("end_date")) or item.get("date") or "")
            right = [paragraph(pdf_text(item.get("title") or item.get("name") or ""), title)]
            bullets = item.get("ai_generated_bullets") or ([item.get("description")] if item.get("description") else [])
        story.append(table([[paragraph(left, date), right]], colWidths=[1.22*inch, content_width-1.22*inch], style=table_style([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0), ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 1)])))
        if bullets:
            from reportlab.platypus import Indenter
            story.append(Indenter(left=1.22 * inch))
            for bullet in bullets:
                if bullet:
                    story.append(paragraph("- " + pdf_text(str(bullet)), body))
            story.append(Indenter(left=-1.22 * inch))
    if resume.get("summary"):
        heading("Profile"); story.append(paragraph(pdf_text(resume["summary"]), body))
    if resume.get("experience"):
        heading("Professional Experience"); [entry(item, "experience") for item in resume["experience"]]
    if resume.get("education"):
        heading("Education")
        for item in resume["education"]: entry({"title": item.get("school"), "description": " | ".join(filter(None, [item.get("degree"), item.get("field"), item.get("cgpa") and "CGPA: " + item["cgpa"]])), "start_date": item.get("start_date"), "end_date": item.get("end_date")}, "project")
    if skills:
        heading("Skills")
        cells = [paragraph("- " + pdf_text(skill), body) for skill in skills]
        rows = [cells[index:index+3] + [""] * max(0, 3-len(cells[index:index+3])) for index in range(0, len(cells), 3)]
        story.append(table(rows, colWidths=[content_width/3]*3, style=table_style([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 3)])))
    if resume.get("languages"):
        heading("Languages")
        for item in resume["languages"]:
            level = str(item.get("proficiency") or "").lower(); count = 5 if any(word in level for word in ["native", "fluent", "advanced"]) else 4 if "intermediate" in level else 3
            dots = "\u25cf" * count + "\u25cb" * (5 - count)
            story.append(paragraph(pdf_text(item.get("language_name") or item.get("name") or "") + "  " + dots, body))
    for label, key, mapper in [("Projects", "projects", "project"), ("Interests", "achievements", "project"), ("Certificates", "certifications", "project"), ("Publications", "publications", "project")]:
        if resume.get(key):
            heading(label)
            for item in resume[key]:
                if key == "certifications": item = {"title": item.get("name"), "description": item.get("issuer"), "date": item.get("date")}
                entry(item, mapper)
    declaration_text = resolved_declaration(resume)
    if declaration_text and declaration_text.strip():
        decl_flowables = [
            paragraph(pdf_text("DECLARATION"), section),
            paragraph(pdf_text(declaration_text), body),
        ]
        if keep_together:
            story.append(keep_together(decl_flowables))
        else:
            story.extend(decl_flowables)
    doc.build(story)
    return buffer.getvalue()


def render_reportlab_analyst_pro_pdf(
    resume,
    template_choice,
    colors,
    page_size,
    paragraph_style,
    get_styles,
    inch,
    list_flowable,
    list_item,
    paragraph,
    indenter,
    document,
    spacer,
    table,
    table_style,
    keep_together=None,
):
    buffer = BytesIO()
    doc = document(
        buffer,
        pagesize=page_size,
        leftMargin=0.0,
        rightMargin=0.0,
        topMargin=0.42 * inch,
        bottomMargin=0.42 * inch,
    )
    styles = get_styles()
    profile = reportlab_template_profile(template_choice)
    accent = colors.HexColor(profile["accent"])
    muted = colors.HexColor("#526070")
    body_color = colors.HexColor("#263942")
    header_text_color = colors.HexColor(profile["header_text"])
    header_meta_color = colors.HexColor(profile["header_meta"])

    name_style = paragraph_style(
        name="AnalystName",
        parent=styles["Normal"],
        fontName=profile["font_bold"],
        fontSize=profile["name_size"],
        leading=profile["name_leading"],
        textColor=header_text_color,
        spaceAfter=4,
        alignment=profile["header_alignment"],
    )
    title_style = paragraph_style(
        name="AnalystTitle",
        parent=styles["Normal"],
        fontName=profile["font_bold"],
        fontSize=9,
        leading=12,
        textColor=header_meta_color,
        spaceAfter=3,
        alignment=profile["header_alignment"],
    )
    contact_style = paragraph_style(
        name="AnalystContact",
        parent=styles["Normal"],
        fontName=profile["font_regular"],
        fontSize=8.5,
        leading=11,
        textColor=header_meta_color,
        alignment=profile["header_alignment"],
    )
    section_style = paragraph_style(
        name="AnalystSection",
        parent=styles["Heading2"],
        fontName=profile["font_bold"],
        fontSize=profile["section_size"],
        leading=profile["section_leading"],
        textColor=accent,
        backColor=colors.HexColor(profile["section_background"]),
        alignment=profile["section_alignment"],
        spaceBefore=7,
        spaceAfter=3,
        borderColor=colors.HexColor("#cbd5e1"),
        borderPadding=profile["section_padding"],
        borderWidth=profile["section_border_width"],
        borderWidthBottom=profile["section_border_bottom"],
    )
    entry_title_style = paragraph_style(
        name="AnalystEntryTitle",
        parent=styles["Normal"],
        fontName=profile["font_bold"],
        fontSize=profile["entry_size"],
        leading=profile["entry_leading"],
        textColor=colors.HexColor("#14202b"),
    )
    date_style = paragraph_style(
        name="AnalystDate",
        parent=styles["Normal"],
        fontName=profile["font_regular"],
        fontSize=8,
        leading=10,
        textColor=muted,
        alignment=2,
    )
    meta_style = paragraph_style(
        name="AnalystMeta",
        parent=styles["Normal"],
        fontName=profile["font_regular"],
        fontSize=profile["meta_size"],
        leading=profile["body_leading"],
        textColor=muted,
    )
    body_style = paragraph_style(
        name="AnalystBody",
        parent=styles["Normal"],
        fontName=profile["font_regular"],
        fontSize=profile["body_size"],
        leading=profile["body_leading"],
        textColor=body_color,
        spaceAfter=2,
    )
    chip_style = paragraph_style(
        name="AnalystChip",
        parent=body_style,
        fontName=profile["font_regular"],
        fontSize=profile["body_size"],
        leading=profile["body_leading"],
        spaceAfter=1.5,
    )

    info = resume.get("personal_info") or {}
    header_lines = [
        paragraph(pdf_text(info.get("name") or "Your Name"), name_style),
    ]
    role = header_role(resume)
    if role:
        header_lines.append(paragraph(pdf_text(role), title_style))
    contact = contact_line(info)
    links = links_markup_line(info)
    if contact:
        header_lines.append(paragraph(pdf_text(contact), contact_style))
    if links:
        header_lines.append(paragraph(links, contact_style))

    page_width, _page_height = page_size
    content_margin = profile["content_margin"] * inch
    content_width = page_width - content_margin - content_margin
    story = [
        table(
            [[header_lines]],
        colWidths=[page_width],
        style=table_style(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(profile["header_background"])),
                ("LEFTPADDING", (0, 0), (-1, -1), content_margin),
                ("RIGHTPADDING", (0, 0), (-1, -1), content_margin),
                ("TOPPADDING", (0, 0), (-1, -1), profile["header_top"] * inch),
                ("BOTTOMPADDING", (0, 0), (-1, -1), profile["header_bottom"] * inch),
                ("LINEBELOW", (0, 0), (-1, -1), profile["header_rule_width"], accent),
            ]
        ),
        )
    ]

    main = []
    side = []

    def add_entries(target, title, entries, stacked=False):
        add_rl_entries_section(
            target,
            title,
            entries,
            section_style,
            entry_title_style,
            meta_style,
            date_style,
            body_style,
            paragraph,
            table,
            table_style,
            list_flowable,
            list_item,
            stacked=stacked,
        )

    add_rl_paragraph_section(main, "Professional Summary", resume.get("summary"), section_style, body_style, paragraph)
    if profile["two_column"]:
        add_entries(main, "Experience", [experience_pdf_entry(item) for item in resume.get("experience", [])])
        add_entries(main, "Projects", [project_pdf_entry(item) for item in resume.get("projects", [])])
        add_entries(main, "Publications", [generic_pdf_entry(item) for item in resume.get("publications", [])])
        add_rl_skills_section(side, resume.get("skills", []), section_style, chip_style, paragraph)
        add_entries(side, "Education", [education_pdf_entry(item) for item in resume.get("education", [])], stacked=True)
        add_entries(side, "Certifications", [certification_pdf_entry(item) for item in resume.get("certifications", [])], stacked=True)
        add_entries(side, "Languages", [language_pdf_entry(item) for item in resume.get("languages", [])], stacked=True)
    else:
        add_entries(main, "Experience", [experience_pdf_entry(item) for item in resume.get("experience", [])])
        add_entries(main, "Projects", [project_pdf_entry(item) for item in resume.get("projects", [])])
        add_entries(main, "Education", [education_pdf_entry(item) for item in resume.get("education", [])])
        add_rl_skills_section(main, resume.get("skills", []), section_style, chip_style, paragraph)
        add_entries(main, "Publications", [generic_pdf_entry(item) for item in resume.get("publications", [])])
        add_entries(main, "Certifications", [certification_pdf_entry(item) for item in resume.get("certifications", [])])
        add_entries(main, "Languages", [language_pdf_entry(item) for item in resume.get("languages", [])])
    add_entries(
        side if profile["two_column"] else main,
        "Achievements",
        [generic_pdf_entry(item) for item in resume.get("achievements", [])],
        stacked=profile["two_column"],
    )
    declaration_text = resolved_declaration(resume)
    if profile["two_column"]:
        story.append(
            table(
                [[main, side]],
                colWidths=[content_width - profile["sidebar_width"], profile["sidebar_width"]],
                style=table_style(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (0, 0), 0.18 * inch),
                        ("LEFTPADDING", (1, 0), (1, 0), 0.18 * inch),
                        ("RIGHTPADDING", (1, 0), (1, 0), 0.12 * inch),
                        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#f5f4fa")),
                        ("LINEBEFORE", (1, 0), (1, 0), 0.6, colors.HexColor("#d7d2e8")),
                        ("TOPPADDING", (0, 0), (-1, -1), 0.18 * inch),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                ),
                hAlign="CENTER",
            )
        )
        if declaration_text and declaration_text.strip():
            story.append(spacer(1, 6))
            story.append(indenter(left=content_margin, right=content_margin))
            add_rl_declaration_section(
                story,
                "Declaration",
                declaration_text,
                section_style,
                body_style,
                paragraph_style,
                paragraph,
                keep_together=keep_together,
            )
            story.append(indenter(left=-content_margin, right=-content_margin))
    else:
        if declaration_text and declaration_text.strip():
            add_rl_declaration_section(
                main,
                "Declaration",
                declaration_text,
                section_style,
                body_style,
                paragraph_style,
                paragraph,
                keep_together=keep_together,
            )
        story.append(spacer(1, profile["content_gap"] * inch))
        story.append(indenter(left=content_margin, right=content_margin))
        story.extend(main + side)
        story.append(indenter(left=-content_margin, right=-content_margin))

    doc.build(story)
    return buffer.getvalue()


def reportlab_template_profile(template_choice):
    spec = template_style_spec(template_choice)
    accents = {
        "steady-form": "#26323f",
        "classic-serif": "#111111",
        "mercury-flow": "#5f655f",
        "slate-dawn": "#29224a",
        "timeline-teal": "#0f766e",
        "sidebar-mono": "#334155",
        "horizon-coral": "#e76f51",
    }
    centered_templates = {"steady-form", "classic-serif"}
    compact_templates = {"steady-form", "mercury-flow"}
    is_classic = template_choice == "classic-serif"
    is_steady = template_choice == "steady-form"
    is_mercury = template_choice == "mercury-flow"
    is_slate = template_choice == "slate-dawn"
    is_timeline = template_choice == "timeline-teal"
    is_sidebar_mono = template_choice == "sidebar-mono"
    is_horizon = template_choice == "horizon-coral"
    profile = {
        "accent": spec["accent"],
        "dark_header": is_slate or is_timeline or is_sidebar_mono or is_horizon,
        "two_column": spec["layout"] == "two-column",
        "sidebar_width": 2.18 * 72,
        "header_alignment": 1 if spec["header_alignment"] == "center" else 0,
        "font_regular": "Times-Roman" if is_classic else "Helvetica",
        "font_bold": "Times-Bold" if is_classic else "Helvetica-Bold",
        "header_background": "#e76f51" if is_horizon else ("#334155" if is_sidebar_mono else ("#0f766e" if is_timeline else ("#29224a" if is_slate else ("#dfe2dd" if is_mercury else "#ffffff")))),
        "header_text": "#ffffff" if is_slate or is_timeline or is_sidebar_mono or is_horizon else "#111111" if is_classic else "#172033",
        "header_meta": "#d8f1ec" if is_timeline else ("#d8e0ea" if is_slate else "#535a53" if is_mercury else "#526070"),
        "header_rule_width": 0 if is_classic else (2.2 if is_steady else 1.2),
        "name_size": 23 if is_classic else (21 if template_choice in compact_templates else 22),
        "name_leading": 26 if is_classic else (24 if template_choice in compact_templates else 25),
        "section_size": 10 if is_classic else (8.8 if template_choice in compact_templates else 9.2),
        "section_leading": 13 if is_classic else (11 if template_choice in compact_templates else 12),
        "section_background": "#e7f4f1" if is_timeline else ("#eef0f2" if is_steady else ("#eef0ec" if is_mercury else "#ffffff")),
        "section_alignment": 1 if spec["section_alignment"] == "center" else 0,
        "section_padding": (3, 4, 3, 4) if is_steady or is_mercury else (0, 0, 3, 0),
        "section_border_width": 0.45 if is_steady else 0,
        "section_border_bottom": 1.1 if is_classic else (0 if is_steady or is_mercury else 0.6),
        "entry_size": 9.2 if is_classic else (8.8 if template_choice in compact_templates else 9.2),
        "entry_leading": 11.5 if is_classic else (10.5 if template_choice in compact_templates else 11.5),
        "body_size": 8.7 if is_classic else (8.2 if template_choice in compact_templates else 8.6),
        "meta_size": 8.2 if is_classic else (8 if template_choice in compact_templates else 8.3),
        "body_leading": 11 if is_classic else (10.2 if template_choice in compact_templates else 11.2),
        "header_top": 0.34 if is_mercury or is_slate else 0.26,
        "header_bottom": 0.25 if is_mercury or is_slate else 0.18,
        "content_gap": 0.11,
        "content_margin": 1.08 if is_steady else 0.62,
    }
    profile_overrides = {
        "ats-standard": {"accent": "#1f2937", "header_alignment": 0, "section_background": "#ffffff", "content_gap": 0.09, "header_rule_width": 1.2},
        "timeline-teal": {"accent": "#0f766e", "header_alignment": 0, "section_background": "#e7f4f1", "sidebar_width": 2.12 * 72},
        "sidebar-mono": {"accent": "#334155", "header_alignment": 0, "section_background": "#f1f5f9", "sidebar_width": 2.08 * 72},
        "horizon-coral": {"accent": "#e76f51", "header_alignment": 0, "section_background": "#fff7ed", "header_top": 0.34},
        "ledger-navy": {"accent": "#1e3a5f", "header_alignment": 0, "section_background": "#ffffff", "content_gap": 0.09},
        "split-olive": {"accent": "#556b2f", "header_alignment": 0, "section_background": "#f4f5ef", "sidebar_width": 2.15 * 72},
        "canvas-sand": {"accent": "#a16207", "header_alignment": 1, "section_background": "#fffbeb", "header_top": 0.34},
        "column-indigo": {"accent": "#4338ca", "header_alignment": 0, "section_background": "#eef2ff", "sidebar_width": 2.12 * 72},
        "arc-slate": {"accent": "#475569", "header_alignment": 0, "section_background": "#f8fafc", "content_gap": 0.09},
        "pulse-rose": {"accent": "#be185d", "header_alignment": 0, "section_background": "#fff1f7", "sidebar_width": 2.12 * 72},
        "signal-amber": {"accent": "#b45309", "header_alignment": 0, "section_background": "#fffbeb", "header_top": 0.34},
    }
    profile.update(profile_overrides.get(template_choice, {}))
    return profile


def add_paragraph_section(story, title, value, styles, body_style, paragraph):
    if not value:
        return
    story.append(paragraph(pdf_text(title.upper()), styles["ResumeSection"]))
    story.append(paragraph(pdf_text(value), body_style))


DEFAULT_DECLARATION = (
    "I hereby declare that the information provided in this resume is true and accurate "
    "to the best of my knowledge and belief."
)


def split_declaration(value):
    lines = [
        line.strip()
        for line in str(value or "").splitlines()
        if line.strip()
    ]
    detail_start = next(
        (index for index, line in enumerate(lines) if line.lower().startswith(("place:", "date:", "signature:"))),
        -1,
    )
    if detail_start < 0:
        return " ".join(lines), []
    return " ".join(lines[:detail_start]), lines[detail_start:]


def resolved_declaration(resume):
    if not resume.get("declaration_enabled", True):
        return ""
    value = str(resume.get("declaration") or "").strip()
    if not value:
        return ""
    normalized = re.sub(r"\s+", " ", value).strip().lower()
    if normalized in {"none", "null", "n/a", "na", "undefined"} or normalized.startswith("[") or "placeholder" in normalized or normalized == "lorem ipsum":
        return ""
    info = resume.get("personal_info") or {}
    identity = {
        re.sub(r"\s+", " ", str(info.get("name") or "").strip().lower()),
        re.sub(r"\s+", " ", str(info.get("location") or "").strip().lower()),
    }
    if normalized and normalized in identity:
        return DEFAULT_DECLARATION
    return value


def add_declaration_section(story, title, value, styles, body_style, paragraph, keep_together=None):
    statement, details = split_declaration(value)
    flowables = [paragraph(pdf_text(title.upper()), styles["ResumeSection"])]
    if statement:
        flowables.append(paragraph(pdf_text(statement), body_style))
    if details:
        flowables.append(paragraph(pdf_markup("\n".join(details)), body_style))
    if keep_together:
        story.append(keep_together(flowables))
    else:
        story.extend(flowables)


def add_list_section(story, title, items, styles, body_style, paragraph):
    clean_items = [item for item in items if item]
    if not clean_items:
        return
    story.append(paragraph(pdf_text(title.upper()), styles["ResumeSection"]))
    story.append(paragraph(pdf_text(", ".join(clean_items)), body_style))


def add_entries_section(
    story,
    title,
    entries,
    styles,
    body_style,
    meta_style,
    paragraph,
    list_flowable,
    list_item,
):
    clean_entries = [entry for entry in entries if any(entry.values())]
    if not clean_entries:
        return
    story.append(paragraph(pdf_text(title.upper()), styles["ResumeSection"]))
    for item in clean_entries:
        heading = item.get("title")
        dates = item.get("dates")
        if dates:
            heading = f"{heading} | {dates}" if heading else dates
        if heading:
            story.append(paragraph(f"<b>{pdf_text(heading)}</b>", body_style))
        if item.get("subtitle"):
            story.append(paragraph(pdf_text(item["subtitle"]), meta_style))
        bullets = item.get("bullets") or []
        if bullets:
            story.append(
                list_flowable(
                    [
                        list_item(paragraph(pdf_text(bullet), body_style), leftIndent=8)
                        for bullet in bullets
                        if bullet
                    ],
                    bulletType="bullet",
                    leftIndent=14,
                )
            )
        elif item.get("body"):
            story.append(paragraph(pdf_text(item["body"]), body_style))


def add_rl_paragraph_section(story, title, value, section_style, body_style, paragraph):
    if not value:
        return
    story.append(paragraph(pdf_text(title).upper(), section_style))
    story.append(paragraph(pdf_markup(value), body_style))


def add_rl_declaration_section(story, title, value, section_style, body_style, paragraph_style, paragraph, keep_together=None):
    statement, details = split_declaration(value)
    flowables = [paragraph(pdf_text(title).upper(), section_style)]
    if statement:
        flowables.append(paragraph(pdf_text(statement), body_style))
    if details:
        detail_style = paragraph_style(
            name=f"{body_style.name}DeclarationDetails",
            parent=body_style,
            alignment=2,
            spaceBefore=4,
        )
        flowables.append(paragraph(pdf_markup("\n".join(details)), detail_style))
    if keep_together:
        story.append(keep_together(flowables))
    else:
        story.extend(flowables)


def add_rl_skills_section(story, skills, section_style, chip_style, paragraph):
    names = [
        item.get("skill_name")
        for item in skills
        if item.get("skill_name") and not is_placeholder(item.get("skill_name"))
    ]
    if not names:
        return
    story.append(paragraph("TECHNICAL SKILLS", section_style))
    story.extend(paragraph(pdf_text(name), chip_style) for name in names)


def add_rl_entries_section(
    story,
    title,
    entries,
    section_style,
    entry_title_style,
    meta_style,
    date_style,
    body_style,
    paragraph,
    table,
    table_style,
    list_flowable,
    list_item,
    stacked=False,
):
    clean_entries = [clean_pdf_entry(entry) for entry in entries]
    clean_entries = [entry for entry in clean_entries if any(entry.values())]
    if not clean_entries:
        return
    story.append(paragraph(pdf_text(title).upper(), section_style))
    for item in clean_entries:
        title_value = item.get("title")
        dates = item.get("dates")
        if title_value or dates:
            if stacked or not dates:
                if title_value:
                    story.append(paragraph(pdf_text(title_value), entry_title_style))
                if dates:
                    story.append(paragraph(pdf_text(dates), meta_style))
            else:
                story.append(
                    table(
                        [[
                            paragraph(pdf_text(title_value or ""), entry_title_style),
                            paragraph(pdf_text(dates), date_style),
                        ]],
                        colWidths=[None, 1.7 * 72],
                        style=table_style(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                            ]
                        ),
                    )
                )
        if item.get("subtitle"):
            story.append(paragraph(pdf_markup(item["subtitle"]), meta_style))
        bullets = item.get("bullets") or []
        if bullets:
            story.append(
                list_flowable(
                    [
                        list_item(paragraph(pdf_markup(bullet), body_style), leftIndent=8)
                        for bullet in bullets
                        if bullet
                    ],
                    bulletType="bullet",
                    leftIndent=13,
                )
            )
        elif item.get("body"):
            story.append(paragraph(pdf_markup(item["body"]), body_style))


def pdf_markup(value):
    return pdf_text(value).replace("\n", "<br/>")


def experience_pdf_entry(item):
    return {
        "title": item.get("role"),
        "subtitle": item.get("company"),
        "dates": date_range(item.get("start_date"), item.get("end_date")),
        "body": item.get("raw_input"),
        "bullets": item.get("ai_generated_bullets") or [],
    }


def project_pdf_entry(item):
    project = split_project_description(item.get("description"))
    generated_bullets = item.get("ai_generated_bullets") or []
    return {
        "title": item.get("title"),
        "subtitle": project["subtitle"],
        "body": "" if generated_bullets else project["body"],
        "bullets": generated_bullets or project["bullets"],
    }


def clean_pdf_entry(item):
    clean = {}
    for key, value in item.items():
        if isinstance(value, list):
            clean[key] = [entry for entry in value if entry and not is_placeholder(entry)]
        elif is_placeholder(value):
            clean[key] = ""
        else:
            clean[key] = value
    return clean


def is_placeholder(value):
    val = str(value or "").lower()
    return "[add" in val or "you can improve" in val or "lorem ipsum" in val or "enter details" in val


def clean_location(location):
    loc = str(location or "").strip()
    if not loc or is_placeholder(loc):
        return ""
    if ";" in loc or ":" in loc:
        sep = ";" if ";" in loc else ":"
        parts = [p.strip() for p in loc.split(sep)]
        filtered = [p for p in parts if p.lower() not in {"city", "state", "country", "location", "address"}]
        loc = ", ".join(filtered) if filtered else loc
    loc = re.sub(r"^(?:city|state|location|address)\s*[:\-;\s]+", "", loc, flags=re.I).strip()
    return loc.title() if loc.islower() else loc


def normalize_render_skills(skills):
    result = []
    seen = set()
    for item in skills or []:
        val = item.get("skill_name") if isinstance(item, dict) else str(item or "")
        val = str(val or "").strip()
        if not val or is_placeholder(val):
            continue
        val = re.sub(r"^Technical Skills:\s*", "", val, flags=re.I).strip()
        category_chunks = re.findall(r"(?:^|,\s*)([A-Za-z0-9 &]+):\s*([^:]+?)(?=(?:,\s*[A-Za-z0-9 &]+:|$))", val)
        if category_chunks:
            for cat, items_str in category_chunks:
                for sub in items_str.split(","):
                    clean = sub.strip()
                    if clean and not is_placeholder(clean):
                        if clean.lower() not in seen:
                            seen.add(clean.lower())
                            result.append(clean)
        else:
            for sub in val.split(","):
                clean = sub.strip()
                if clean and not is_placeholder(clean):
                    if ":" in clean:
                        clean = clean.split(":")[-1].strip()
                    if clean and clean.lower() not in seen:
                        seen.add(clean.lower())
                        result.append(clean)
    return result


def apply_content_density(profile, resume):
    prof = dict(profile)
    exp_count = len(resume.get("experience") or [])
    proj_count = len(resume.get("projects") or [])
    edu_count = len(resume.get("education") or [])
    summary_len = len(str(resume.get("summary") or ""))
    total_entries = exp_count + proj_count + edu_count
    
    if total_entries <= 3 and summary_len < 300:
        prof["content_gap"] = prof.get("content_gap", 0.11) * 1.2
        prof["section_leading"] = prof.get("section_leading", 12) + 0.5
        prof["section_before"] = 20
        prof["body_size"] = max(9.5, prof.get("body_size", 9.5))
    elif total_entries > 7 or summary_len > 800:
        prof["content_gap"] = prof.get("content_gap", 0.11) * 0.85
        prof["body_size"] = max(7.8, prof.get("body_size", 8.6) - 0.2)
    return prof


def education_pdf_entry(item):
    degree_field = ", ".join(filter(None, [item.get("degree"), item.get("field")]))
    scores = []
    if item.get("cgpa"):
        scores.append(f"CGPA: {item.get('cgpa')}")
    if item.get("percentage"):
        pct = str(item.get("percentage")).strip()
        scores.append(f"Percentage: {pct if pct.endswith('%') else pct + '%'}")
    score_str = " | ".join(scores)

    if degree_field:
        title = degree_field
        subtitle = " | ".join(filter(None, [item.get("school"), score_str]))
    else:
        title = item.get("school") or "Education"
        subtitle = score_str

    return {
        "title": title,
        "subtitle": subtitle,
        "dates": date_range(item.get("start_date"), item.get("end_date")),
    }


def certification_pdf_entry(item):
    return {
        "title": item.get("name"),
        "subtitle": item.get("issuer"),
        "dates": item.get("date"),
    }


def language_pdf_entry(item):
    return {"title": item.get("language_name"), "subtitle": item.get("proficiency")}


def generic_pdf_entry(item):
    return {
        "title": item.get("title") or item.get("name") or item.get("role"),
        "subtitle": item.get("organization") or item.get("publisher") or item.get("issuer") or item.get("technologies"),
        "dates": item.get("date") or date_range(item.get("start_date"), item.get("end_date")),
        "body": item.get("description") or item.get("summary") or item.get("details"),
        "bullets": item.get("bullets") or [],
    }


def render_resume_html(resume, template_choice):
    body = render_professional_resume(resume, template_choice)
    return f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <style>
      @page {{
        size: A4;
        margin: 0;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        background: #ffffff;
        color: #17212b;
        font-family: Arial, Helvetica, sans-serif;
        font-size: 10.5pt;
        line-height: 1.38;
      }}
      h1, h2, h3, p {{
        margin: 0;
      }}
      .resume-page {{
        --resume-accent: #1f6f78;
        --resume-accent-2: #18313a;
        --resume-muted: #526070;
        --resume-rule: #cbd5e1;
        --resume-soft: #f3f7f8;
        width: 210mm;
        min-height: 297mm;
        padding: 15mm 16mm;
        background: #ffffff;
      }}
      .template-analyst-pro {{
        --resume-accent: #128579;
        --resume-accent-2: #123c40;
        font-size: 10.8pt;
      }}
      .template-executive-line,
      .template-senior-impact,
      .template-two-page-pro,
      .template-professional-edge,
      .template-business-profile,
      .template-consulting-standard,
      .template-leadership-profile {{
        --resume-accent: #4b6477;
        --resume-accent-2: #171717;
        font-family: Georgia, "Times New Roman", serif;
      }}
      .template-corporate-blue,
      .template-cobalt-line,
      .template-horizon-blue {{
        --resume-accent: #1f5f9a;
        --resume-accent-2: #15304c;
      }}
      .template-tech-horizon {{
        --resume-accent: #315ea8;
        --resume-accent-2: #16233f;
      }}
      .template-creative-accent,
      .template-designer-portfolio {{
        --resume-accent: #b24a69;
        --resume-accent-2: #301923;
      }}
      .template-ats-classic {{
        --resume-accent: #111111;
        --resume-accent-2: #111111;
        padding: 14mm 17mm;
        font-size: 9.9pt;
      }}
      .template-executive-center {{
        --resume-accent: #0f766e;
        --resume-accent-2: #134e4a;
        padding: 11mm 15mm;
      }}
      .template-professional-teal {{
        --resume-accent: #0f766e;
        --resume-accent-2: #134e4a;
        padding: 11mm 15mm;
      }}
      .template-data-analyst-pro {{
        --resume-accent: #176b87;
        --resume-accent-2: #12343b;
        padding: 10mm 14mm;
        font-size: 8.9pt;
      }}
      .template-modern-sidebar-pro {{
        --resume-accent: #1f8a92;
        --resume-accent-2: #12343b;
      }}
      .template-compact-metrics {{
        --resume-accent: #15304c;
        --resume-accent-2: #15304c;
        padding: 10.5mm 14mm;
        font-size: 9pt;
      }}
      .template-corporate-blue {{
        --resume-accent: #1f5f9a;
        --resume-accent-2: #15304c;
        padding: 10.5mm 14mm;
        font-size: 9pt;
      }}
      .template-professional-teal .header {{
        margin: -11mm -15mm 0;
        padding: 10mm 15mm 8mm;
        border-bottom: 0;
        background: #0f766e;
        color: #ffffff;
        text-align: left;
      }}
      .template-professional-teal .header h1,
      .template-professional-teal .title,
      .template-professional-teal .contact,
      .template-professional-teal .links {{
        color: #ffffff;
        text-align: left;
      }}
      .template-professional-teal .section h2 {{
        border-bottom-color: #7ccbc6;
        color: #0f766e;
      }}
      .template-data-analyst-pro .header {{
        display: block;
        margin: -10mm -14mm 0;
        padding: 8mm 14mm 6mm;
        border-bottom: 0;
        background: #102f44;
        color: #ffffff;
        text-align: left;
      }}
      .template-data-analyst-pro .header h1,
      .template-data-analyst-pro .title,
      .template-data-analyst-pro .contact,
      .template-data-analyst-pro .links {{
        color: #ffffff;
        text-align: left;
      }}
      .template-data-analyst-pro .skill-list {{
        border: 1px solid #cfe4ee;
        border-radius: 4px;
        padding: 7px;
        background: #eef7fb;
      }}
      .template-data-analyst-pro .section h2 {{
        border-bottom-color: #9cc8da;
        color: #176b87;
      }}
      .template-data-analyst-pro .section:nth-of-type(5) .entry {{
        border-left: 2px solid #176b87;
        padding-left: 7px;
      }}
      .template-corporate-blue .header {{
        margin: -10.5mm -14mm 0;
        padding: 9mm 14mm 7mm;
        border-bottom: 0;
        background: #15304c;
        color: #ffffff;
        text-align: left;
      }}
      .template-corporate-blue .header h1,
      .template-corporate-blue .title,
      .template-corporate-blue .contact,
      .template-corporate-blue .links {{
        color: #ffffff;
        text-align: left;
      }}
      .template-corporate-blue .section h2 {{
        border-bottom: 0;
        border-left: 3px solid #2f6fab;
        padding: 4px 0 4px 7px;
        background: #eef5fb;
        color: #15304c;
      }}
      .template-steady-form {{
        --resume-accent: #26323f;
        --resume-accent-2: #0f2f3f;
        padding: 12mm 15mm;
        font-size: 9pt;
      }}
      .template-steady-form .section h2,
      .template-mercury-flow .section h2 {{
        justify-content: center;
        border-bottom: 0;
        background: #eef0f2;
        padding: 4px;
      }}
      .template-classic-serif {{
        --resume-accent: #111111;
        --resume-accent-2: #111111;
        font-family: Georgia, "Times New Roman", serif;
        padding: 13mm 16mm;
      }}
      .template-classic-serif .header {{
        text-align: center;
      }}
      .template-classic-serif .section h2 {{
        border-bottom: 2px solid #111111;
      }}
      .template-mercury-flow {{
        --resume-accent: #5f655f;
        --resume-accent-2: #353a35;
        font-family: Georgia, "Times New Roman", serif;
      }}
      .template-mercury-flow .header {{
        margin: -15mm -16mm 0;
        padding: 9mm 16mm 7mm;
        background: #dfe2dd;
        border-bottom: 0;
      }}
      .template-slate-dawn {{
        --resume-accent: #29224a;
        --resume-accent-2: #19132d;
        font-family: Georgia, "Times New Roman", serif;
      }}
      .template-slate-dawn .header {{
        margin: -15mm -16mm 0;
        padding: 9mm 16mm 7mm;
        background: #e3e6ef;
        border-bottom: 0;
      }}
      .template-slate-dawn .section h2 {{
        border-bottom: 2px solid #29224a;
      }}
      .template-timeline-teal {{
        --resume-accent: #0f766e;
        --resume-accent-2: #115e59;
      }}
      .template-timeline-teal .header {{
        margin: -15mm -16mm 0;
        padding: 9mm 16mm 7mm;
        background: #0f766e;
        border-bottom: 0;
        color: #ffffff;
        text-align: left;
      }}
      .template-timeline-teal .header h1,
      .template-timeline-teal .title,
      .template-timeline-teal .contact,
      .template-timeline-teal .links {{ color: #ffffff; text-align: left; }}
      .template-timeline-teal .section h2 {{ border-bottom: 0; color: #0f766e; background: #e7f4f1; padding: 4px 6px; }}
      .template-timeline-teal .entry {{ border-left: 2px solid #5eead4; padding-left: 8px; }}
      .template-sidebar-mono {{ --resume-accent: #334155; --resume-accent-2: #1e293b; }}
      .template-sidebar-mono .header {{ margin: -15mm -16mm 0; padding: 9mm 16mm 7mm; background: #334155; border-bottom: 0; color: #fff; text-align: left; }}
      .template-sidebar-mono .header h1, .template-sidebar-mono .title, .template-sidebar-mono .contact, .template-sidebar-mono .links {{ color: #fff; text-align: left; }}
      .template-sidebar-mono .section h2 {{ border-bottom: 1px solid #94a3b8; color: #334155; }}
      .template-horizon-coral {{ --resume-accent: #e76f51; --resume-accent-2: #9f3a25; }}
      .template-horizon-coral .header {{ margin: -15mm -16mm 0; padding: 10mm 16mm 8mm; background: #e76f51; border-bottom: 0; color: #fff; text-align: left; }}
      .template-horizon-coral .header h1, .template-horizon-coral .title, .template-horizon-coral .contact, .template-horizon-coral .links {{ color: #fff; text-align: left; }}
      .template-horizon-coral .section h2 {{ border-bottom: 2px solid #f4a261; color: #9f3a25; }}
      .template-ledger-navy {{ --resume-accent: #1e3a5f; --resume-accent-2: #173252; }}
      .template-ledger-navy .header {{ border-bottom: 3px solid #1e3a5f; text-align: left; }}
      .template-ledger-navy .section h2 {{ border-bottom: 1px solid #93a7bf; color: #1e3a5f; }}
      .template-split-olive {{ --resume-accent: #556b2f; --resume-accent-2: #3f5123; }}
      .template-split-olive .header {{ margin: -15mm -16mm 0; padding: 9mm 16mm 7mm; background: #eef0e7; border-bottom: 0; text-align: left; }}
      .template-split-olive .section h2 {{ color: #556b2f; border-bottom-color: #a9b78e; }}
      .template-canvas-sand {{ --resume-accent: #a16207; --resume-accent-2: #854d0e; }}
      .template-canvas-sand .header {{ margin: -15mm -16mm 0; padding: 9mm 16mm 7mm; background: #fef3c7; border-bottom: 0; text-align: center; }}
      .template-canvas-sand .section h2 {{ color: #a16207; border-bottom-color: #f4c96a; }}
      .template-column-indigo {{ --resume-accent: #4338ca; --resume-accent-2: #3730a3; }}
      .template-column-indigo .header {{ margin: -15mm -16mm 0; padding: 9mm 16mm 7mm; background: #4338ca; border-bottom: 0; color: #fff; text-align: left; }}
      .template-column-indigo .header h1, .template-column-indigo .title, .template-column-indigo .contact, .template-column-indigo .links {{ color: #fff; text-align: left; }}
      .template-column-indigo .section h2 {{ color: #4338ca; border-bottom-color: #a5b4fc; }}
      .template-arc-slate {{ --resume-accent: #475569; --resume-accent-2: #334155; }}
      .template-arc-slate .header {{ border-bottom: 3px solid #475569; text-align: left; }}
      .template-arc-slate .section h2 {{ color: #475569; border-bottom-color: #cbd5e1; }}
      .template-pulse-rose {{ --resume-accent: #be185d; --resume-accent-2: #9d174d; }}
      .template-pulse-rose .header {{ margin: -15mm -16mm 0; padding: 9mm 16mm 7mm; background: #fce7f3; border-bottom: 0; text-align: left; }}
      .template-pulse-rose .section h2 {{ color: #be185d; border-bottom-color: #f9a8d4; }}
      .template-signal-amber {{ --resume-accent: #b45309; --resume-accent-2: #92400e; }}
      .template-signal-amber .header {{ margin: -15mm -16mm 0; padding: 9mm 16mm 7mm; background: #b45309; border-bottom: 0; color: #fff; text-align: left; }}
      .template-signal-amber .header h1, .template-signal-amber .title, .template-signal-amber .contact, .template-signal-amber .links {{ color: #fff; text-align: left; }}
      .template-signal-amber .section h2 {{ color: #b45309; border-bottom-color: #fbbf24; }}
      .section {{
        margin-top: 12px;
        break-inside: avoid;
      }}
      .section h2 {{
        display: flex;
        align-items: center;
        gap: 10px;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 5px;
        color: var(--resume-accent-2);
        font-size: 10pt;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
      }}
      .entry {{
        margin-top: 7px;
        min-width: 0;
        break-inside: avoid;
        page-break-inside: avoid;
      }}
      .entry-head {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 12px;
        align-items: start;
      }}
      .entry strong {{
        display: block;
        font-size: 10.5pt;
        line-height: 1.2;
        white-space: normal;
        word-break: normal;
        overflow-wrap: break-word;
        hyphens: none;
      }}
      .entry small {{
        max-width: 38mm;
        text-align: right;
        white-space: nowrap;
      }}
      .entry small,
      .entry span,
      .entry p,
      .contact,
      .links {{
        color: var(--resume-muted);
        word-break: normal;
        overflow-wrap: break-word;
      }}
      .entry p {{
        margin-top: 4px;
      }}
      .entry ul {{
        margin: 5px 0 0;
        padding-left: 18px;
      }}
      .entry li {{
        color: #526070;
        margin-top: 3px;
      }}
      .header {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(45mm, auto);
        gap: 8mm;
        align-items: start;
        border-bottom: 1px solid var(--resume-rule);
        padding-bottom: 5mm;
      }}
      .template-analyst-pro .header,
      .template-modern-sidebar-pro .header,
      .template-modern-slate .header,
      .template-horizon-blue .header,
      .template-tech-horizon .header,
      .template-product-builder .header {{
        margin: -15mm -16mm 0;
        padding: 12mm 16mm 8mm;
        background: var(--resume-accent-2);
        color: #ffffff;
      }}
      .template-analyst-pro .header {{
        grid-template-columns: minmax(0, 1fr);
        gap: 4mm;
      }}
      .template-analyst-pro .contact,
      .template-analyst-pro .links {{
        text-align: left;
      }}
      .template-analyst-pro .header p,
      .template-analyst-pro .contact,
      .template-analyst-pro .links,
      .template-modern-sidebar-pro .header p,
      .template-modern-sidebar-pro .contact,
      .template-modern-sidebar-pro .links,
      .template-modern-slate .header p,
      .template-modern-slate .contact,
      .template-modern-slate .links,
      .template-horizon-blue .header p,
      .template-horizon-blue .contact,
      .template-horizon-blue .links,
      .template-tech-horizon .header p,
      .template-tech-horizon .contact,
      .template-tech-horizon .links,
      .template-product-builder .header p,
      .template-product-builder .contact,
      .template-product-builder .links {{
        color: #d8e0ea;
      }}
      .header h1 {{
        margin-top: 4px;
        color: var(--resume-accent-2);
        font-size: 25pt;
        line-height: 1.05;
        letter-spacing: 0;
        word-break: normal;
        overflow-wrap: break-word;
      }}
      .template-analyst-pro .header h1,
      .template-modern-sidebar-pro .header h1,
      .template-modern-slate .header h1,
      .template-horizon-blue .header h1,
      .template-tech-horizon .header h1,
      .template-product-builder .header h1 {{
        color: #ffffff;
      }}
      .title {{
        color: var(--resume-accent);
        font-size: 9pt;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
      }}
      .contact,
      .links {{
        text-align: right;
      }}
      .template-ats-prime .header,
      .template-ats-classic .header,
      .template-compact-metrics .header,
      .template-clearpath .header,
      .template-essential-one .header,
      .template-simple-standard .header,
      .template-precision-line .header,
      .template-clean-career .header,
      .template-graduate-launch .header,
      .template-first-career .header,
      .template-engineering-core .header,
      .template-datacraft .header,
      .template-ai-specialist .header,
      .template-minimal-focus .header,
      .template-compact-career .header,
      .template-academic-scholar .header,
      .template-research-profile .header {{
        display: block;
      }}
      .template-ats-prime .contact,
      .template-ats-prime .links,
      .template-compact-metrics .contact,
      .template-compact-metrics .links,
      .template-clearpath .contact,
      .template-clearpath .links,
      .template-essential-one .contact,
      .template-essential-one .links,
      .template-simple-standard .contact,
      .template-simple-standard .links,
      .template-precision-line .contact,
      .template-precision-line .links,
      .template-clean-career .contact,
      .template-clean-career .links,
      .template-graduate-launch .contact,
      .template-graduate-launch .links,
      .template-first-career .contact,
      .template-first-career .links,
      .template-engineering-core .contact,
      .template-engineering-core .links,
      .template-datacraft .contact,
      .template-datacraft .links,
      .template-ai-specialist .contact,
      .template-ai-specialist .links,
      .template-minimal-focus .contact,
      .template-minimal-focus .links,
      .template-compact-career .contact,
      .template-compact-career .links,
      .template-academic-scholar .contact,
      .template-academic-scholar .links,
      .template-research-profile .contact,
      .template-research-profile .links {{
        margin-top: 4px;
        text-align: left;
      }}
      .template-ats-classic .header,
      .template-executive-center .header {{
        display: block;
        text-align: center;
      }}
      .template-ats-classic .contact,
      .template-ats-classic .links,
      .template-executive-center .contact,
      .template-executive-center .links {{
        margin-top: 4px;
        text-align: center;
      }}
      .template-data-analyst-pro .header {{
        display: block;
        text-align: left;
      }}
      .template-data-analyst-pro .contact,
      .template-data-analyst-pro .links {{
        margin-top: 4px;
        text-align: left;
      }}
      .content {{
        display: grid;
        gap: 8mm;
        padding-top: 12px;
      }}
      .layout-two-column .content {{
        grid-template-columns: minmax(0, 1fr) 55mm;
      }}
      .template-analyst-pro .content {{
        grid-template-columns: minmax(0, 1fr) 66mm;
        gap: 7mm;
      }}
      .template-modern-sidebar-pro .content {{
        grid-template-columns: minmax(0, 1fr) 62mm;
      }}
      .layout-single-column .content {{
        grid-template-columns: 1fr;
      }}
      main, aside {{
        min-width: 0;
      }}
      .skill-list {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 10px;
      }}
      .skill-list span {{
        border-radius: 20px;
        padding: 4px 7px;
        background: #eef2f8;
        color: #25364d;
        font-weight: 700;
        overflow-wrap: break-word;
      }}
      .template-analyst-pro aside .entry-head {{
        grid-template-columns: minmax(0, 1fr);
      }}
      .template-analyst-pro aside .entry small {{
        max-width: none;
        text-align: left;
        white-space: normal;
      }}
      .template-professional-edge .header,
      .template-business-profile .header,
      .template-consulting-standard .header,
      .template-leadership-profile .header,
      .template-executive-line .header,
      .template-senior-impact .header,
      .template-two-page-pro .header {{
        display: block;
        text-align: center;
      }}
      .template-professional-edge .contact,
      .template-professional-edge .links,
      .template-business-profile .contact,
      .template-business-profile .links,
      .template-consulting-standard .contact,
      .template-consulting-standard .links,
      .template-leadership-profile .contact,
      .template-leadership-profile .links,
      .template-executive-line .contact,
      .template-executive-line .links,
      .template-senior-impact .contact,
      .template-senior-impact .links,
      .template-two-page-pro .contact,
      .template-two-page-pro .links {{
        margin-top: 4px;
        padding-bottom: 5mm;
        margin-bottom: 5mm;
        border-bottom: 2px solid var(--resume-accent);
      }}
      .resume-identity {{
        display: flex;
        flex-direction: column;
        gap: 1.5mm;
        flex: 1;
        min-width: 0;
        align-items: var(--resume-header-items);
        text-align: var(--resume-header-align);
      }}
      .resume-name {{
        font-size: 22pt;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.05;
        color: var(--resume-accent-2);
        margin: 0;
      }}
      .resume-role {{
        font-size: 9pt;
        font-weight: 700;
        text-transform: none;
        letter-spacing: 0;
        color: var(--resume-accent);
        margin: 0;
        line-height: 1.3;
      }}
      .resume-contact {{
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 1.2mm;
        flex-shrink: 0;
        min-width: 52mm;
        max-width: 68mm;
        text-align: right;
        color: var(--resume-muted);
        font-size: 8.4pt;
        line-height: 1.4;
      }}
      .resume-section h2 {{ text-align: var(--resume-section-align); }}
      .resume-contact span {{
        display: block;
        overflow-wrap: anywhere;
      }}
      /* ── SECTIONS ───────────────────────────────────────────────────────── */
      .resume-content {{
        display: flex;
        flex-direction: column;
      }}
      .resume-main {{
        display: flex;
        flex-direction: column;
      }}
      .resume-section {{
        margin-top: 4.5mm;
        break-inside: avoid;
      }}
      .resume-section:first-child {{
        margin-top: 0;
      }}
      .resume-section > h2 {{
        display: flex;
        align-items: center;
        gap: 3mm;
        font-size: 8.8pt;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: var(--resume-accent);
        margin-bottom: 2.5mm;
        line-height: 1;
      }}
      .resume-section > h2::after {{
        content: '';
        flex: 1;
        height: 1.5px;
        background: var(--resume-rule);
        border-radius: 1px;
      }}
      /* ── ITEMS ──────────────────────────────────────────────────────────── */
      .resume-item {{
        margin-bottom: 2.8mm;
        break-inside: avoid;
      }}
      .resume-item:last-child {{
        margin-bottom: 0;
      }}
      .resume-item-header {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 4mm;
        margin-bottom: 0.8mm;
      }}
      .resume-item-primary {{
        flex: 1;
        min-width: 0;
      }}
      .resume-entry-title,
      .resume-project-title {{
        font-size: 10pt;
        font-weight: 700;
        color: var(--resume-accent-2);
        margin-bottom: 0.5mm;
        line-height: 1.2;
      }}
      .resume-item-primary p {{
        font-size: 8.8pt;
        color: var(--resume-muted);
        font-style: italic;
        margin: 0;
      }}
      .resume-item-meta {{
        font-size: 8.4pt;
        color: var(--resume-muted);
        white-space: nowrap;
        flex-shrink: 0;
        text-align: right;
      }}
      /* ── BULLETS ────────────────────────────────────────────────────────── */
      .resume-bullets {{
        display: flex;
        flex-direction: column;
        gap: 0.8mm;
        margin-top: 1.2mm;
        padding-left: 4mm;
        list-style: none;
      }}
      .resume-bullets li {{
        font-size: 9.5pt;
        line-height: 1.42;
        color: #1a1a1a;
        position: relative;
        padding-left: 3mm;
      }}
      .resume-bullets li::before {{
        content: '\u2022';
        position: absolute;
        left: 0;
        color: var(--resume-accent);
        font-weight: 700;
      }}
      /* ── SUMMARY / BODY ─────────────────────────────────────────────────── */
      .resume-summary {{
        font-size: 9.5pt;
        line-height: 1.52;
        color: #2c2c2c;
        margin: 0;
      }}
      .resume-declaration {{
        font-size: 9pt;
        line-height: 1.48;
        color: #334155;
        font-style: italic;
        margin: 0;
      }}
      .resume-item-body {{
        font-size: 9.5pt;
        line-height: 1.45;
        color: #2c2c2c;
        margin-top: 1mm;
      }}
      /* ── SKILLS ─────────────────────────────────────────────────────────── */
      .resume-skill-list {{
        display: flex;
        flex-direction: column;
        gap: 1.2mm;
      }}
      .resume-skill {{
        font-size: 9.5pt;
        line-height: 1.42;
        display: block;
        color: #1a1a1a;
      }}
      .resume-skill.grouped {{
        display: flex;
        gap: 2mm;
        align-items: baseline;
        flex-wrap: wrap;
      }}
      .resume-skill.grouped strong {{
        font-weight: 700;
        color: var(--resume-accent-2);
        white-space: nowrap;
      }}
      .resume-skill.grouped span {{
        color: #2c2c2c;
      }}
      /* ── PRINT ──────────────────────────────────────────────────────────── */
      @media print {{
        body {{ background: none; }}
        .resume-page {{
          width: 210mm;
          min-height: 297mm;
          padding: 14mm 16mm;
          transform: none !important;
          box-shadow: none !important;
        }}
      }}
    </style>
  </head>
  <body>
    {body}
  </body>
</html>
"""


def render_professional_resume(resume, template_choice):
    info = resume.get("personal_info") or {}
    spec = template_style_spec(template_choice)
    layout_class = f"layout-{spec['layout']}"
    main_sections = render_html_sections(
        resume,
        ["summary", "education", "skills", "experience", "publications", "certifications", "languages", "achievements", "declaration"],
    )
    return f"""
<div class="resume-page template-{text(template_choice)} {layout_class}" style="--resume-accent: {spec['accent']}; --resume-header-align: {spec['header_alignment']}; --resume-header-items: {'center' if spec['header_alignment'] == 'center' else 'flex-start'}; --resume-section-align: {spec['section_alignment']};">
  <header class="resume-header">
    <div class="resume-identity">
      <h1 class="resume-name">{text(info.get("name") or "Your Name")}</h1>
      {f'<p class="resume-role">{text(header_role(resume))}</p>' if header_role(resume) else ''}
    </div>
    {render_contact_block(info)}
  </header>
  <div class="resume-content">
    <main class="resume-main">{main_sections}</main>
  </div>
</div>
"""
HTML_SECTION_LABELS = {
    "summary": "Professional Summary",
    "skills": "Technical Skills",
    "experience": "Experience",
    "projects": "Projects",
    "education": "Education",
    "certifications": "Certifications",
    "publications": "Publications",
    "achievements": "Achievements",
    "languages": "Languages",
    "internships": "Internships",
    "training": "Training",
    "courses": "Courses",
    "research_experience": "Research Experience",
    "conferences": "Conferences",
    "volunteering": "Volunteering",
    "professional_memberships": "Professional Memberships",
    "open_source_contributions": "Open-Source Contributions",
    "references": "References",
    "declaration": "Declaration",
    "custom_sections": "Custom Sections",
}


def render_html_sections(resume, section_ids):
    hidden_sections = set(resume.get("hidden_sections") or [])
    rendered = []
    for section_id in section_ids:
        if section_id in hidden_sections:
            continue
        if section_id == "summary":
            rendered.append(summary_section(resume.get("summary")))
        elif section_id == "declaration":
            declaration_text = resolved_declaration(resume)
            if declaration_text and declaration_text.strip():
                rendered.append(f'<section class="resume-section"><h2>Declaration</h2><p class="resume-declaration">{text(declaration_text)}</p></section>')
        elif section_id == "skills":
            rendered.append(skills_section(resume.get("skills", [])))
        else:
            rendered.append(section(HTML_SECTION_LABELS.get(section_id, section_id), html_entries_for_section(section_id, resume.get(section_id, []))))
    return "\n".join(item for item in rendered if item)


def render_contact_block(info):
    contact_items = [
        item
        for item in [info.get("email"), info.get("phone"), clean_location(info.get("location"))]
        if item and not is_placeholder(item)
    ]
    links = [
        formatted
        for formatted in (
            format_profile_link(link) for link in (info.get("links") or [])
        )
        if formatted
    ]
    spans = "".join(f"<span>{text(item)}</span>" for item in contact_items + links)
    return f'<div class="resume-contact resume-contact-list">{spans}</div>' if spans else ""


def contact_line(info):
    return " | ".join(
        item
        for item in [info.get("email"), info.get("phone"), clean_location(info.get("location"))]
        if item and not is_placeholder(item)
    )


def links_line(info):
    return " | ".join(
        formatted
        for formatted in (
            format_profile_link(link) for link in (info.get("links") or [])
        )
        if formatted
    )


def links_markup_line(info):
    return " | ".join(
        formatted
        for formatted in (
            format_profile_link_markup(link) for link in (info.get("links") or [])
        )
        if formatted
    )


def format_profile_link(link):
    value = str(link or "").strip()
    if not value or is_placeholder(value):
        return ""
    labeled = value.split(":", 1)
    if len(labeled) == 2 and labeled[0].strip().lower() in {"github", "linkedin", "portfolio", "website"}:
        label = labeled[0].strip().lower()
        target = compact_profile_target(labeled[1])
        display_label = {
            "github": "GitHub",
            "linkedin": "LinkedIn",
            "portfolio": "Portfolio",
            "website": "Website",
        }[label]
        return f"{display_label}: {target}" if target else display_label
    normalized = value.lower()
    if "github.com" in normalized:
        profile = compact_profile_target(value)
        return f"GitHub: {profile}" if profile else "GitHub"
    if "linkedin.com" in normalized:
        profile = compact_profile_target(value)
        return f"LinkedIn: {profile}" if profile else "LinkedIn"
    return f"Portfolio: {value.replace('https://', '').replace('http://', '').replace('www.', '')}"


def format_profile_link_markup(link):
    display = format_profile_link(link)
    url = profile_link_url(link)
    if not display:
        return ""
    if not url:
        return pdf_text(display)
    return f'<link href="{pdf_attr(url)}" color="blue">{pdf_text(display)}</link>'


def profile_link_url(link):
    value = str(link or "").strip()
    if not value or is_placeholder(value):
        return ""
    labeled = value.split(":", 1)
    if len(labeled) == 2 and labeled[0].strip().lower() in {"github", "linkedin", "portfolio", "website"}:
        value = labeled[1].strip()
    value = value.rstrip(".,; ")
    if not value or is_placeholder(value):
        return ""
    if value.startswith(("http://", "https://")):
        candidate = value
    else:
        candidate = f"https://{value.removeprefix('www.')}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or "." not in parsed.netloc:
        return ""
    return candidate


def compact_profile_target(value):
    clean_value = (
        str(value or "")
        .strip()
        .replace("https://", "")
        .replace("http://", "")
        .removeprefix("www.")
        .rstrip("/")
    )
    if clean_value in {"", "github.com", "linkedin.com"} or is_placeholder(clean_value):
        return ""
    if "github.com" in clean_value:
        return clean_value.split("github.com/", 1)[1].split("/", 1)[0] if "github.com/" in clean_value else ""
    if "linkedin.com" in clean_value:
        profile = clean_value.split("linkedin.com/", 1)[1] if "linkedin.com/" in clean_value else ""
        return profile.removeprefix("in/").split("/", 1)[0]
    return clean_value


def section(title, entries):
    rendered = "".join(entry for entry in entries if entry)
    if not rendered:
        return ""
    return f'<section class="resume-section"><h2>{text(title)}</h2>{rendered}</section>'


def entry(title, subtitle=None, dates=None, body=None):
    clean_title = "" if is_placeholder(title) else title
    clean_meta = "" if is_placeholder(subtitle) else subtitle
    bullets = [item for item in body if item and not is_placeholder(item)] if isinstance(body, list) else []
    clean_body = "" if bullets or is_placeholder(body) else body
    if not any([clean_title, clean_meta, dates, clean_body, bullets]):
        return ""

    title_class = "resume-project-title" if clean_title and "project" in str(clean_title).lower() else "resume-entry-title"

    header_inner = []
    if clean_title:
        header_inner.append(f'<h3 class="{title_class}">{text(clean_title)}</h3>')
    if clean_meta:
        header_inner.append(f'<p>{text(clean_meta)}</p>')

    primary_html = f'<div class="resume-item-primary">{"".join(header_inner)}</div>' if header_inner else ""
    meta_html = f'<div class="resume-item-meta">{text(dates)}</div>' if dates else ""
    
    header_html = f'<div class="resume-item-header">{primary_html}{meta_html}</div>' if (primary_html or meta_html) else ""
    body_html = f'<p class="resume-item-body">{text(clean_body)}</p>' if clean_body else ""
    bullets_html = (
        '<ul class="resume-bullets">' + "".join(f"<li>{text(bullet)}</li>" for bullet in bullets) + "</ul>"
        if bullets
        else ""
    )
    return f'<article class="resume-item">{header_html}{body_html}{bullets_html}</article>'


def experience_entry(item):
    return entry(
        item.get("role"),
        subtitle=item.get("company"),
        dates=date_range(item.get("start_date"), item.get("end_date")),
        body=item.get("ai_generated_bullets") or item.get("raw_input"),
    )


def education_entry(item):
    subtitle = ", ".join(
        filter(
            None,
            [
                item.get("degree"),
                item.get("field"),
                f"CGPA: {item.get('cgpa')}" if item.get("cgpa") else None,
            ],
        )
    )
    return entry(
        item.get("school"),
        subtitle=subtitle,
        dates=date_range(item.get("start_date"), item.get("end_date")),
    )


def certification_entry(item):
    return entry(item.get("name"), subtitle=item.get("issuer"), dates=item.get("date"))


def project_entry(item):
    project = split_project_description(item.get("description"))
    return entry(
        item.get("title"),
        subtitle=project["subtitle"],
        body=project["bullets"] or project["body"],
    )


def split_project_description(description):
    lines = [
        line.strip()
        for line in str(description or "").splitlines()
        if line.strip() and not is_placeholder(line)
    ]
    subtitles = []
    bullets = []
    for line in lines:
        match = re.match(r"^(Technologies|Tech Stack|Tools used):\s*(.*)", line, flags=re.I)
        if match:
            prefix = match.group(1)
            val = match.group(2).strip()
            verb_match = re.search(r"\b(Developed|Built|Implemented|Designed|Created|Engineered|Deployed|Integrated|Automated|Managed|Led|Provided|Achieved|Constructed|Configured)\b", val)
            if verb_match:
                tech_part = val[:verb_match.start()].strip().rstrip(",;.")
                narrative_part = val[verb_match.start():].strip()
                if tech_part:
                    subtitles.append(f"{prefix}: {tech_part}")
                else:
                    subtitles.append(f"{prefix}:")
                if narrative_part:
                    bullets.append(narrative_part.lstrip("-* "))
            else:
                subtitles.append(f"{prefix}: {val}")
        elif line.lower().startswith(("technologies:", "tech stack:", "tools used:")):
            subtitles.append(line)
        else:
            bullets.append(line.lstrip("-* "))
    return {
        "subtitle": " | ".join(subtitles),
        "body": "" if lines else description,
        "bullets": bullets,
    }


def language_entry(item):
    return entry(item.get("language_name"), subtitle=item.get("proficiency"))


def html_entries_for_section(section_id, items):
    if not isinstance(items, list):
        return []
    if section_id in {"experience", "internships", "research_experience"}:
        return [experience_entry(item) for item in items]
    if section_id == "education":
        return [education_entry(item) for item in items]
    if section_id in {"certifications", "courses", "training"}:
        return [
            entry(
                item.get("name") or item.get("title"),
                subtitle=item.get("issuer") or item.get("provider") or item.get("organization"),
                dates=item.get("date") or item.get("end_date"),
            )
            for item in items
        ]
    if section_id == "languages":
        return [language_entry(item) for item in items]
    return [
        entry(
            item.get("title") or item.get("name") or item.get("role"),
            subtitle=item.get("organization") or item.get("publisher") or item.get("issuer") or item.get("technologies"),
            dates=item.get("date") or date_range(item.get("start_date"), item.get("end_date")),
            body=item.get("description") or item.get("summary") or item.get("details"),
        )
        for item in items
    ]


def skills_section(skills, inline=False):
    if not isinstance(skills, list):
        return ""
    skill_items = []
    for item in skills:
        if isinstance(item, dict):
            val = item.get("skill_name") or item.get("name") or item.get("value")
        else:
            val = str(item)
        if val and not is_placeholder(val):
            skill_items.append(val)
    if not skill_items:
        return ""
    
    rendered_skills = []
    for val in skill_items:
        parts = str(val).split(":", 1)
        if len(parts) == 2:
            label, details = parts[0].strip(), parts[1].strip()
            rendered_skills.append(f'<p class="resume-skill grouped"><strong>{text(label)}:</strong> <span>{text(details)}</span></p>')
        else:
            rendered_skills.append(f'<span class="resume-skill">{text(val)}</span>')

    skills_html = "".join(rendered_skills)
    return (
        '<section class="resume-section"><h2>Technical Skills</h2>'
        f'<div class="resume-skill-list">{skills_html}</div></section>'
    )


def summary_section(summary):
    if not summary or is_placeholder(summary):
        return ""
    return f'<section class="resume-section"><h2>Professional Summary</h2><p class="resume-summary">{text(summary)}</p></section>'


def date_range(start_date, end_date):
    return " \u2013 ".join(
        compact_resume_date(value)
        for value in (start_date, end_date)
        if value
    )


def compact_resume_date(value):
    """Keep imported date ranges narrow enough for a reliable right-aligned column."""
    text_value = re.sub(r"\s+", " ", str(value or "")).strip()
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", text_value)
    if iso_match:
        months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        month_index = int(iso_match.group(2)) - 1
        if 0 <= month_index < len(months):
            return f"{months[month_index]} {iso_match.group(1)}"
    month_names = {
        "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
        "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
        "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec",
    }
    return re.sub(
        r"\b(" + "|".join(month_names) + r")\b",
        lambda match: month_names[match.group(1).capitalize()],
        text_value,
        flags=re.IGNORECASE,
    )



def text(value):
    return escape(str(value or ""))


def pdf_text(value):
    # Built-in ReportLab fonts do not reliably render Unicode dash variants.
    # Normalize only the affected punctuation before rendering; preserve all
    # other Unicode resume content.
    value = str(value or "")
    for character in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212", "\u25a0"):
        value = value.replace(character, "-")
    # This is the common mojibake sequence for a U+25A0 glyph when UTF-8 text
    # is decoded as Windows-1252. Do not let it reach the exported PDF.
    value = value.replace("\u00e2\u2013\u00a0", "-")
    return escape(value, quote=False)


def pdf_attr(value):
    return escape(str(value or ""), quote=True)


def render_basic_resume_pdf(resume, template_choice="modern"):
    lines = build_plain_resume_lines(resume, template_choice)
    is_classic = template_choice == "classic"
    font_size = 11 if is_classic else 10
    start_x = 72 if is_classic else 50
    content = ["BT", f"/F1 {font_size} Tf", f"{start_x} 750 Td", "14 TL"]
    first = True
    for line in lines:
        if not first:
            content.append("T*")
        content.append(f"({escape_pdf_string(line)}) Tj")
        first = False
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(pdf)


def build_plain_resume_lines(resume, template_choice="modern"):
    info = resume.get("personal_info") or {}
    name = info.get("name") or "Your Name"
    lines = [
        name.upper() if template_choice == "classic" else name,
        header_role(resume),
        " | ".join(filter(None, [info.get("email"), info.get("phone"), clean_location(info.get("location"))])),
        links_line(info),
        "",
    ]

    add_plain_section(lines, "PROFESSIONAL SUMMARY", [resume.get("summary")])
    add_plain_section(
        lines,
        "WORK EXPERIENCE",
        [
            plain_entry(
                item.get("role"),
                item.get("company"),
                date_range(item.get("start_date"), item.get("end_date")),
                item.get("ai_generated_bullets") or [item.get("raw_input")],
            )
            for item in resume.get("experience", [])
        ],
    )
    add_plain_section(
        lines,
        "PROJECTS",
        [plain_entry(item.get("title"), None, None, [item.get("description")]) for item in resume.get("projects", [])],
    )
    add_plain_section(
        lines,
        "EDUCATION",
        [
            plain_entry(
                item.get("school"),
                ", ".join(
                    filter(
                        None,
                        [
                            item.get("degree"),
                            item.get("field"),
                            f"CGPA: {item.get('cgpa')}" if item.get("cgpa") else None,
                        ],
                    )
                ),
                date_range(item.get("start_date"), item.get("end_date")),
                [],
            )
            for item in resume.get("education", [])
        ],
    )
    add_plain_section(lines, "TECHNICAL SKILLS", [", ".join(item.get("skill_name") for item in resume.get("skills", []) if item.get("skill_name"))])

    return wrap_pdf_lines([line for line in lines if line is not None])


def add_plain_section(lines, title, values):
    clean_values = [value for value in values if value]
    if not clean_values:
        return
    lines.extend([title, *clean_values, ""])


def plain_entry(title, subtitle, dates, bullets):
    header = " | ".join(filter(None, [title, subtitle, dates]))
    body = [f"- {bullet}" for bullet in bullets if bullet]
    return "\n".join([header, *body]).strip()


def wrap_pdf_lines(lines, width=92, max_lines=52):
    wrapped = []
    for line in lines:
        for part in str(line).splitlines() or [""]:
            text_line = part.strip()
            while len(text_line) > width:
                split_at = text_line.rfind(" ", 0, width)
                if split_at <= 0:
                    split_at = width
                wrapped.append(text_line[:split_at])
                text_line = text_line[split_at:].strip()
            wrapped.append(text_line)
    return wrapped[:max_lines]


def escape_pdf_string(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
