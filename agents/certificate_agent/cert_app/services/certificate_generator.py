import os
import logging
import tempfile
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

from cert_app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_SERVICE_DIR  = Path(__file__).resolve().parent
TEMPLATE_PATH = _SERVICE_DIR.parent / "attached_assets" / "templates" / "certificate_template.png"

_FONT_DIRS = [
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
]

# ── Layout: Pixel-verified coordinates for 1414 × 2000 px Canvas ───────────────
_Y_OF_ACHIEVEMENT = 518   # "OF ACHIEVEMENT" in Larger Gold Stylish Font
_Y_SUBTITLE       = 538   # "OF COMPLETION" / "OF ACHIEVEMENT"
_Y_FLORAL         = 585   # Golden Floral Ornament --- ❖ ---
_Y_PRESENTED      = 625   # "This certificate is proudly presented to" in Larger Italic
_Y_SUBHEADER      = 685   # "for successfully completing the course/assessment"
_Y_NAME           = 775   # Recipient Name (above gold bar y=882)
_Y_COURSE         = 940   # Course / Subject Title (below gold bar y=882, Stylish Serif)
_Y_SCORE_LBL1     = 1045  # "and demonstrating proficiency through"
_Y_SCORE_LBL2     = 1085  # "the final assessment with a score of" / "the assessment with a score of"
_Y_SCORE_VAL      = 1140  # Score value e.g. "85%"
_Y_LEVEL_BADGE    = 1230  # Certification-level pill badge
_Y_DOTTED_DIVIDER = 1315  # Dotted line with gold end-dots
_Y_DATE           = 1355  # Date of Issue
_Y_CERT_ID        = 1405  # Certificate ID
_Y_WEBSITE        = 1824  # Website footer line

# ── Layout & Colours ───────────────────────────────────────────────────────────
_COL_BLUE   = (11,  40,  78)    # Deep Navy Blue
_COL_GRAY   = (70,  70,  70)    # Soft Dark Gray
_COL_GOLD   = (197, 160, 89)    # DigiDARA Gold
_COL_LGRAY  = (210, 210, 210)   # Light Gray
_COL_RED    = (200, 30,  30)    # ISO Stamp Red

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_font(size: int, bold: bool = False, italic: bool = False, serif: bool = True) -> ImageFont.FreeTypeFont:
    if serif:
        candidates = (
            ["palab.ttf", "georgiab.ttf", "cambriab.ttf", "constanb.ttf"] if bold
            else ["palai.ttf", "georgiai.ttf", "cambriai.ttf", "constani.ttf"] if italic
            else ["pala.ttf", "georgia.ttf", "cambria.ttf", "constan.ttf"]
        )
    else:
        candidates = (
            ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
            else ["segoeuii.ttf", "ariali.ttf", "DejaVuSans-Oblique.ttf"] if italic
            else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
        )
    for font_dir in _FONT_DIRS:
        for name in candidates:
            path = font_dir / name
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size)
                except Exception:
                    continue
    return ImageFont.load_default()

def _centered_text(draw: ImageDraw.Draw, y: int, text: str,
                   font: ImageFont.FreeTypeFont, color: tuple, img_w: int) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x    = (img_w - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=color)

def _wrap_text(draw: ImageDraw.Draw, text: str,
               font: ImageFont.FreeTypeFont, max_w: int) -> list:
    words, lines, current = text.split(), [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]

def _draw_floral_ornament(draw: ImageDraw.Draw, img_w: int, y: int, color: tuple):
    cx = img_w // 2
    # Outer lines & end dots
    draw.line([(cx - 160, y), (cx - 30, y)], fill=color, width=2)
    draw.ellipse([(cx - 164, y - 4), (cx - 156, y + 4)], fill=color)
    draw.line([(cx + 30, y), (cx + 160, y)], fill=color, width=2)
    draw.ellipse([(cx + 156, y - 4), (cx + 164, y + 4)], fill=color)
    
    # Center diamond/leaf floral motif
    draw.polygon([(cx, y - 10), (cx + 10, y), (cx, y + 10), (cx - 10, y)], fill=color)
    draw.polygon([(cx - 18, y - 6), (cx - 12, y), (cx - 18, y + 6), (cx - 24, y)], fill=color)
    draw.polygon([(cx + 18, y - 6), (cx + 24, y), (cx + 18, y + 6), (cx + 12, y)], fill=color)

def _draw_dotted_divider(draw: ImageDraw.Draw, img_w: int, y: int, line_color: tuple, dot_color: tuple):
    cx = img_w // 2
    half_w = 380
    x0, x1 = cx - half_w, cx + half_w
    
    # Draw end dots
    draw.ellipse([(x0 - 6, y - 6), (x0 + 6, y + 6)], fill=dot_color)
    draw.ellipse([(x1 - 6, y - 6), (x1 + 6, y + 6)], fill=dot_color)
    
    # Draw dotted line
    for x in range(x0 + 14, x1 - 14, 10):
        draw.rectangle([(x, y), (x + 4, y + 2)], fill=line_color)

def _get_level(score: float) -> tuple:
    if score >= 90:
        return "MASTER LEVEL: DISTINCTION", _COL_GOLD
    elif score >= 80:
        return "ACHIEVEMENT LEVEL: DISTINCTION", _COL_GOLD
    elif score >= 70:
        return "PROFESSIONAL LEVEL: CREDIT", (27, 79, 138)
    elif score >= 50:
        return "PRACTITIONER LEVEL: PASS", (46, 125, 50)
    else:
        return "RETAKE REQUIRED", (180, 40, 40)

def _draw_level_badge(draw: ImageDraw.Draw, img_w: int, y: int,
                      level: str, badge_color: tuple) -> None:
    f_badge   = _load_font(28, bold=True, serif=True)
    badge_txt = f"  \u2605  {level}  \u2605  "
    bbox      = draw.textbbox((0, 0), badge_txt, font=f_badge)
    tw, th    = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 36, 14
    rw  = tw + 2 * pad_x
    rh  = th + 2 * pad_y
    x0  = (img_w - rw) // 2
    y0  = y
    x1, y1 = x0 + rw, y0 + rh
    try:
        draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=rh // 2, fill=badge_color)
    except AttributeError:
        draw.rectangle([(x0, y0), (x1, y1)], fill=badge_color)
    draw.text(((img_w - tw) // 2, y0 + pad_y), badge_txt, font=f_badge, fill=(255, 255, 255))

def _ordinal_date(dt: datetime) -> str:
    day = dt.day
    sfx = (
        "th" if 11 <= day % 100 <= 13
        else ["th", "st", "nd", "rd", "th"][min(day % 10, 4)]
    )
    return f"{day}{sfx} {dt.strftime('%b %Y')}"

# ── DigiDARA Layout Rendering Helpers ──────────────────────────────────────────

def _draw_geometric_borders(draw: ImageDraw.Draw, w: int, h: int):
    # Outer borders
    draw.rectangle([(80, 80), (w - 80, h - 80)], outline=_COL_BLUE, width=4)
    draw.rectangle([(92, 92), (w - 92, h - 92)], outline=_COL_GOLD, width=2)
    
    # Corner geometric triangles
    # Top-Left
    draw.polygon([(0, 0), (220, 0), (0, 220)], fill=_COL_BLUE)
    draw.polygon([(220, 0), (245, 0), (0, 245), (0, 220)], fill=_COL_GOLD)
    draw.polygon([(245, 0), (260, 0), (0, 260), (0, 245)], fill=(60, 110, 170))
    
    # Top-Right
    draw.polygon([(w, 0), (w - 220, 0), (w, 220)], fill=_COL_BLUE)
    draw.polygon([(w - 220, 0), (w - 245, 0), (w, 245), (w, 220)], fill=_COL_GOLD)
    draw.polygon([(w - 245, 0), (w - 260, 0), (w, 260), (w, 245)], fill=(60, 110, 170))
    
    # Bottom-Left
    draw.polygon([(0, h), (220, h), (0, h - 220)], fill=_COL_BLUE)
    draw.polygon([(220, h), (245, h), (0, h - 245), (0, h - 220)], fill=_COL_GOLD)
    draw.polygon([(245, h), (260, h), (0, h - 260), (0, h - 245)], fill=(60, 110, 170))
    
    # Bottom-Right
    draw.polygon([(w, h), (w - 220, h), (w, h - 220)], fill=_COL_BLUE)
    draw.polygon([(w - 220, h), (w - 245, h), (w, h - 245), (w, h - 220)], fill=_COL_GOLD)
    draw.polygon([(w - 245, h), (w - 260, h), (w, h - 260), (w, h - 245)], fill=(60, 110, 170))

    # Side border triangles pointing inwards
    left_positions = [450, 950, 1450]
    for py in left_positions:
        draw.polygon([(0, py - 100), (90, py), (0, py + 100)], fill=_COL_BLUE)
        draw.polygon([(0, py - 60), (60, py), (0, py + 60)], fill=_COL_GOLD)
        draw.polygon([(0, py - 30), (30, py), (0, py + 30)], fill=(60, 110, 170))

    right_positions = [450, 950, 1450]
    for py in right_positions:
        draw.polygon([(w, py - 100), (w - 90, py), (w, py + 100)], fill=_COL_BLUE)
        draw.polygon([(w, py - 60), (w - 60, py), (w, py + 60)], fill=_COL_GOLD)
        draw.polygon([(w, py - 30), (w - 30, py), (w, py + 30)], fill=(60, 110, 170))

def _draw_logo(draw: ImageDraw.Draw, w: int, h: int):
    cx, cy = w - 480, 185
    
    # Double 'D' interlocking arcs
    draw.arc([(cx - 45, cy - 45), (cx + 45, cy + 45)], start=30, end=330, fill=_COL_BLUE, width=8)
    draw.arc([(cx - 30, cy - 30), (cx + 30, cy + 30)], start=210, end=150, fill=_COL_GOLD, width=8)
    
    tx = w - 410
    f_brand = _load_font(38, bold=True, serif=True)
    draw.text((tx, cy - 45), "DigiDARA", font=f_brand, fill=_COL_BLUE)
    
    f_sub1 = _load_font(12, bold=True, serif=False)
    draw.text((tx, cy + 2), "TECHNOLOGIES PVT LTD...", font=f_sub1, fill=_COL_BLUE)
    
    f_sub2 = _load_font(10, bold=True, serif=False)
    draw.text((tx, cy + 22), "LEARN, LEAD AND TRANSFORM TOGETHER", font=f_sub2, fill=_COL_GOLD)

def _draw_gold_seal(draw: ImageDraw.Draw, cx: int, cy: int):
    # Two golden ribbons
    draw.polygon([(cx - 30, cy + 20), (cx - 50, cy + 120), (cx - 30, cy + 100), (cx - 10, cy + 120)], fill=_COL_GOLD)
    draw.polygon([(cx + 10, cy + 120), (cx + 30, cy + 100), (cx + 50, cy + 120), (cx + 30, cy + 20)], fill=_COL_GOLD)
    
    # Serrated seal outer wheel
    import math
    num_points = 32
    r_outer = 65
    r_inner = 55
    points = []
    for i in range(num_points * 2):
        angle = i * (math.pi / num_points)
        r = r_outer if i % 2 == 0 else r_inner
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    draw.polygon(points, fill=_COL_GOLD)
    
    # Inner circles
    draw.ellipse([(cx - 48, cy - 48), (cx + 48, cy + 48)], fill=(225, 195, 125))
    draw.ellipse([(cx - 42, cy - 42), (cx + 42, cy + 42)], outline=_COL_GOLD, width=2)

def _draw_left_stamps(draw: ImageDraw.Draw, cx: int, cy: int):
    # ISO Stamp
    draw.rectangle([(cx - 100, cy - 40), (cx - 40, cy + 20)], fill=_COL_RED)
    f_iso = _load_font(18, bold=True, serif=False)
    draw.text((cx - 90, cy - 25), "ISO", font=f_iso, fill=(255, 255, 255))
    f_iso_sub = _load_font(10, bold=False, serif=False)
    draw.text((cx - 90, cy), "9001:2015", font=f_iso_sub, fill=(255, 255, 255))
    
    # IAF Stamp
    draw.ellipse([(cx - 20, cy - 40), (cx + 40, cy + 20)], fill=(27, 79, 138))
    f_iaf = _load_font(16, bold=True, serif=False)
    draw.text((cx - 5, cy - 20), "IAF", font=f_iaf, fill=(255, 255, 255))
    
    # ISO 27001 Stamp
    draw.ellipse([(cx + 60, cy - 40), (cx + 120, cy + 20)], fill=(27, 79, 138))
    f_sec = _load_font(11, bold=True, serif=False)
    draw.text((cx + 70, cy - 20), "ISO 27001", font=f_sec, fill=(255, 255, 255))
    draw.text((cx + 78, cy - 5), "Certified", font=_load_font(9, serif=False), fill=(255, 255, 255))

def _draw_signature(draw: ImageDraw.Draw, cx: int, cy: int):
    f_sig = _load_font(36, italic=True, serif=True)
    draw.text((cx - 80, cy - 40), "Senthil R.", font=f_sig, fill=_COL_BLUE)
    
    # Underline
    draw.line([(cx - 90, cy + 5), (cx + 90, cy + 5)], fill=_COL_BLUE, width=2)
    
    f_name = _load_font(18, bold=True, serif=True)
    f_title = _load_font(14, bold=False, serif=True)
    
    draw.text((cx - 100, cy + 15), "Senthil Rajamarthandan", font=f_name, fill=_COL_GOLD)
    draw.text((cx - 65, cy + 38), "Managing Director", font=f_title, fill=_COL_GRAY)
    draw.text((cx - 100, cy + 56), "DigiDARA Technologies Pvt Ltd", font=f_title, fill=_COL_GRAY)

def _render_certificate_image(username: str, topic: str, score: float, cert_number: str, is_course_final: bool = False):
    try:
        IMG_W, IMG_H = 1414, 2000
        
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Certificate template not found at {TEMPLATE_PATH}")
            
        img  = Image.open(str(TEMPLATE_PATH)).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # Cover pre-printed text "OF COMPLETION" on the template background
        draw.rectangle([(400, 530), (1014, 595)], fill=(255, 255, 255))

        # Draw "OF ACHIEVEMENT" dynamically
        subtitle_text = "OF ACHIEVEMENT"
        f_subtitle = _load_font(36, bold=True, serif=True)
        _centered_text(draw, _Y_SUBTITLE, subtitle_text, f_subtitle, _COL_GOLD, IMG_W)
        
        # Cover pre-printed text "This certificate is proudly awarded to" on the template background
        draw.rectangle([(200, 620), (1214, 700)], fill=(255, 255, 255))

        # 1. "This certificate is proudly presented to" (italic, soft dark gray)
        f_pres = _load_font(28, italic=True, serif=True)
        _centered_text(draw, _Y_PRESENTED, "This certificate is proudly presented to", f_pres, _COL_GRAY, IMG_W)

        # 2. Sub-header line above student name
        sub_text = "for successfully completing the course" if is_course_final else "for successfully completing the assessment"
        f_sub = _load_font(24, bold=False, serif=True)
        _centered_text(draw, _Y_SUBHEADER, sub_text, f_sub, _COL_GRAY, IMG_W)

        # 3. Recipient Name (centered, bold navy blue)
        name_text = username.strip().upper()
        f_name_size = 64
        f_name = _load_font(f_name_size, bold=True, serif=True)
        name_bbox = draw.textbbox((0, 0), name_text, font=f_name)
        name_w = name_bbox[2] - name_bbox[0]

        max_name_w = IMG_W - 300
        if name_w > max_name_w:
            scaled_size = max(36, int(f_name_size * max_name_w / name_w))
            f_name = _load_font(scaled_size, bold=True, serif=True)

        _centered_text(draw, _Y_NAME, name_text, f_name, _COL_BLUE, IMG_W)

        # 4. Course / Topic title (centered, bold navy blue)
        f_course = _load_font(44, bold=True, serif=True)
        course_lines = _wrap_text(draw, topic.strip().upper(), f_course, IMG_W - 300)
        y_cur = _Y_COURSE
        line_h = draw.textbbox((0, 0), "A", font=f_course)[3] + 10
        for line in course_lines:
            _centered_text(draw, y_cur, line, f_course, _COL_BLUE, IMG_W)
            y_cur += line_h

        # 5. Proficiency description text
        demo_line1 = "and demonstrating proficiency through"
        demo_line2 = "the final assessment with a score of" if is_course_final else "the assessment with a score of"
        f_body = _load_font(24, bold=False, serif=True)
        _centered_text(draw, _Y_SCORE_LBL1, demo_line1, f_body, _COL_GRAY, IMG_W)
        _centered_text(draw, _Y_SCORE_LBL2, demo_line2, f_body, _COL_GRAY, IMG_W)

        # 6. Score percentage (large gold)
        f_score_val = _load_font(72, bold=True, serif=True)
        _centered_text(draw, _Y_SCORE_VAL, f"{score:.0f}%", f_score_val, _COL_GOLD, IMG_W)

        # 7. Certification level badge (gold pill)
        level, badge_color = _get_level(score)
        _draw_level_badge(draw, IMG_W, _Y_LEVEL_BADGE, level, badge_color)

        # 8. Dotted divider line with gold end-dots
        _draw_dotted_divider(draw, IMG_W, _Y_DOTTED_DIVIDER, (210, 210, 210), _COL_GOLD)

        # 9. Date of issue (gold)
        issued = _ordinal_date(datetime.now())
        f_date = _load_font(26, bold=True, serif=True)
        _centered_text(draw, _Y_DATE, f"Date of Issue:  {issued}", f_date, _COL_GOLD, IMG_W)

        # 10. Certificate ID (gold)
        f_cert_id = _load_font(22, bold=True, serif=True)
        _centered_text(draw, _Y_CERT_ID, f"Certificate ID:  {cert_number}", f_cert_id, _COL_GOLD, IMG_W)

        # 11. Website / contact footer line (centered, gold)
        f_website = _load_font(24, bold=True, serif=True)
        _centered_text(draw, _Y_WEBSITE,
                       "www.digidaratechnologies.com  |  support@digidaratechnologies.com",
                       f_website, _COL_GOLD, IMG_W)

        return img

    except Exception as e:
        logger.error(f"Failed to render certificate image: {e}")
        return None

# ── Main generator ────────────────────────────────────────────────────────────

def generate_certificate(username: str, topic: str, score: float,
                         cert_number: str = None, is_course_final: bool = False) -> str:
    os.makedirs(settings.CERTIFICATES_DIR, exist_ok=True)

    if not cert_number:
        from cert_app.db.database import get_connection
        year = datetime.now().year
        prefix = f"DDT-AI-{year}-"
        try:
            conn = get_connection()
            cur  = conn.cursor()
            cur.execute(
                "SELECT certificate_number FROM certificates "
                "WHERE certificate_number LIKE %s ORDER BY id DESC LIMIT 1",
                (f"{prefix}%",)
            )
            row = cur.fetchone()
            cur.close(); conn.close()
            seq = int(row["certificate_number"].rsplit("-", 1)[-1]) + 1 if row else 1
        except Exception:
            seq = 1
        cert_number = f"{prefix}{seq:03d}"

    file_path = os.path.join(settings.CERTIFICATES_DIR, f"cert_{cert_number}.pdf")

    img = _render_certificate_image(username, topic, score, cert_number, is_course_final=is_course_final)
    if img is None:
        raise RuntimeError("Failed to render certificate image")

    page_w_pt, page_h_pt = A4
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        img.save(tmp_path, format="PNG")
        pdf_canvas = canvas.Canvas(file_path, pagesize=A4)
        pdf_canvas.drawImage(
            ImageReader(tmp_path), 0, 0,
            width=page_w_pt, height=page_h_pt,
            preserveAspectRatio=False,
        )
        pdf_canvas.save()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    logger.info("[OK] Certificate generated: %s", file_path)
    return file_path
