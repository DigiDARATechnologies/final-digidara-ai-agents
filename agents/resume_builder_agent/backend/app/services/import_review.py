import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import os

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.services.ats_scoring import analyze_resume

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
MAX_DOCX_FILES = 250
DOCX_READ_CHUNK_BYTES = 64 * 1024
DEFAULT_LIBREOFFICE_BINARIES = (
    Path("/usr/bin/soffice"),
    Path("/usr/local/bin/soffice"),
    Path(r"C:/Program Files/LibreOffice/program/soffice.exe"),
)
SUPPORTED_TYPES = {
    ".txt": {"type": "txt", "mimes": {"text/plain", "text/markdown", "application/octet-stream", ""}},
    ".pdf": {"type": "pdf", "mimes": {"application/pdf", "application/octet-stream", ""}},
    ".docx": {
        "type": "docx",
        "mimes": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/octet-stream",
            "",
        },
    },
    ".doc": {"type": "doc", "mimes": {"application/msword", "application/octet-stream", ""}},
}

SECTION_ALIASES = {
    "summary": {"summary", "profile", "about", "objective", "career objective", "professional summary"},
    "experience": {"experience", "employment", "work history", "professional experience"},
    "education": {"education", "academic background", "qualifications"},
    "skills": {"skills", "technical skills", "core skills", "competencies", "core competencies"},
    "projects": {"projects", "personal projects", "academic projects", "project experience"},
    "publications": {"publications", "publication", "papers", "published work"},
    "certifications": {"certifications", "certificates", "licenses", "certificates and licenses"},
    "achievements": {"achievements", "honors", "accomplishments"},
    "languages": {"languages", "language"},
    "declaration": {"declaration"},
}
UNMAPPED_HEADINGS = {
    "awards",
    "achievements",
    "volunteering",
    "interests",
    "hobbies",
    "references",
}

REQUIRED_SECTIONS = ["summary", "education", "skills", "experience", "publications", "certifications"]
DATE_PATTERN = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}\b|\b\d{4}\b|\bpresent\b",
    re.IGNORECASE,
)


def validate_import_file(file_storage):
    if not file_storage:
        raise ImportValidationError("Missing file.", 400)
    filename = file_storage.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_TYPES:
        raise ImportValidationError("Unsupported format. Upload a PDF, Word (.doc or .docx), or TXT resume.", 415)
    mimetype = (file_storage.mimetype or "").lower()
    if mimetype not in SUPPORTED_TYPES[extension]["mimes"]:
        raise ImportValidationError("File extension and MIME type do not match a supported resume format.", 415)
    raw = file_storage.read()
    if len(raw) > MAX_IMPORT_BYTES:
        raise ImportValidationError("Resume file must be 5 MB or smaller.", 413)
    if not raw:
        raise ImportValidationError("The uploaded resume is empty.", 400)
    return extract_resume_file(filename, extension, raw)


def extract_resume_file(filename, extension, raw):
    if extension == ".txt":
        result = extract_txt(filename, raw)
    elif extension == ".pdf":
        result = extract_pdf(filename, raw)
    elif extension == ".docx":
        result = extract_docx(filename, raw)
    elif extension == ".doc":
        result = extract_doc(filename, raw)
    else:
        raise ImportValidationError("Unsupported format. Upload a PDF, Word (.doc or .docx), or TXT resume.", 415)
    if not result["text"].strip():
        raise ImportValidationError("No extractable resume text was found in the uploaded file.", 422)
    return result


def extract_txt(filename, raw):
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportValidationError("The uploaded TXT resume must be valid UTF-8 text.", 400) from exc
    text = sanitize_text(text)
    if not text:
        raise ImportValidationError("The uploaded resume is empty.", 400)
    return normalized_extraction(filename, "txt", len(raw), None, text)


OCR_MIN_WORDS = 20
OCR_MAX_PAGES = 10


def ocr_pdf_pages(raw):
    """Best-effort OCR fallback for scanned/image-only PDFs.

    Returns the OCR'd text, or None if OCR dependencies are not available on this
    server (pytesseract/pdf2image/poppler/tesseract), so callers can fall back to
    the existing "no extractable text" error instead of crashing.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        return None

    try:
        images = convert_from_bytes(raw, dpi=300, fmt="png")
    except Exception:
        return None

    if not images:
        return None

    page_texts = []
    for image in images[:OCR_MAX_PAGES]:
        try:
            page_texts.append(pytesseract.image_to_string(image) or "")
        except Exception:
            return None
    return sanitize_text("\n\n".join(page_texts))


def extract_pdf(filename, raw):
    if not raw.startswith(b"%PDF"):
        raise ImportValidationError("The uploaded PDF is corrupted or has an invalid signature.", 400)
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportValidationError("PDF extraction is unavailable on this server.", 500) from exc

    try:
        reader = PdfReader(BytesIO(raw))
    except Exception as exc:
        raise ImportValidationError("The uploaded PDF is corrupted and could not be read.", 400) from exc
    if reader.is_encrypted:
        raise ImportValidationError("Encrypted or password-protected PDFs cannot be imported.", 422)
    try:
        page_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ImportValidationError("The uploaded PDF text could not be extracted.", 400) from exc
    text = sanitize_text("\n\n".join(page_text))
    warnings = []
    if len(text.split()) < OCR_MIN_WORDS:
        ocr_text = ocr_pdf_pages(raw)
        if ocr_text and len(ocr_text.split()) >= OCR_MIN_WORDS:
            text = ocr_text
            warnings.append(
                "This looked like a scanned/image-based PDF, so text was extracted with OCR. "
                "Please double-check the imported fields for accuracy."
            )
        else:
            raise ImportValidationError(
                "This PDF contains little or no selectable text, and OCR could not recover enough text either. "
                "Upload a clearer scan, a text-based PDF, a Word file, or a TXT file.",
                422,
            )
    return normalized_extraction(filename, "pdf", len(raw), len(reader.pages), text, warnings)


def extract_docx(filename, raw):
    if not raw.startswith(b"PK"):
        raise ImportValidationError("The uploaded DOCX is corrupted or has an invalid signature.", 400)
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_DOCX_FILES:
                raise ImportValidationError("The uploaded DOCX contains too many internal files.", 400)
            names = {info.filename for info in infos}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise ImportValidationError("The uploaded DOCX is malformed.", 400)
            xml_parts = read_docx_xml_parts(archive, infos)
            text = "\n".join(extract_docx_xml_text(xml_parts[name]) for name in xml_parts)
    except ImportValidationError:
        raise
    except (zipfile.BadZipFile, ElementTree.ParseError, DefusedXmlException, RuntimeError) as exc:
        raise ImportValidationError("The uploaded DOCX is corrupted and could not be read.", 400) from exc
    text = sanitize_text(text)
    if not text:
        raise ImportValidationError("No extractable resume text was found in the uploaded DOCX.", 422)
    return normalized_extraction(filename, "docx", len(raw), None, text)


def read_docx_xml_parts(archive, infos):
    total_uncompressed = 0
    xml_parts = {}
    for info in infos:
        chunks = []
        with archive.open(info) as member:
            while True:
                chunk = member.read(DOCX_READ_CHUNK_BYTES)
                if not chunk:
                    break
                total_uncompressed += len(chunk)
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise ImportValidationError("The uploaded DOCX is too large after decompression.", 400)
                if is_docx_text_xml_part(info.filename):
                    chunks.append(chunk)
        if chunks:
            xml_parts[info.filename] = b"".join(chunks)
    return xml_parts


def is_docx_text_xml_part(name):
    return name == "word/document.xml" or name.startswith("word/header") or name.startswith("word/footer")


def extract_docx_xml_text(xml_bytes):
    root = ElementTree.fromstring(xml_bytes)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines = []
    for paragraph in root.iter(f"{namespace}p"):
        fragments = []
        for node in paragraph.iter():
            if node.tag == f"{namespace}t" and node.text:
                fragments.append(node.text)
            elif node.tag == f"{namespace}tab":
                fragments.append(" ")
            elif node.tag == f"{namespace}br":
                fragments.append("\n")
        line = "".join(fragments).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def extract_doc(filename, raw):
    if not raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise ImportValidationError("The uploaded legacy Word document is corrupted or has an invalid signature.", 400)
    converter = configured_libreoffice_binary()
    if not converter:
        raise ImportValidationError(
            "This legacy Word document could not be processed. Please save it as .docx or PDF and upload it again.",
            422,
        )
    with tempfile.TemporaryDirectory(prefix="resume-import-") as temp_dir:
        temp_path = Path(temp_dir)
        profile_path = temp_path / "lo-profile"
        write_libreoffice_macro_lockdown_profile(profile_path)
        input_path = temp_path / safe_internal_filename(filename, ".doc")
        input_path.write_bytes(raw)
        try:
            subprocess.run(
                [
                    converter,
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--nolockcheck",
                    "--norestore",
                    f"-env:UserInstallation={profile_path.resolve().as_uri()}",
                    "--convert-to",
                    "txt:Text",
                    "--outdir",
                    str(temp_path),
                    str(input_path),
                ],
                cwd=temp_dir,
                check=True,
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            raise ImportValidationError(
                "This legacy Word document could not be processed. Please save it as .docx or PDF and upload it again.",
                422,
            ) from exc
        output_candidates = list(temp_path.glob("*.txt"))
        if not output_candidates:
            raise ImportValidationError(
                "This legacy Word document could not be processed. Please save it as .docx or PDF and upload it again.",
                422,
            )
        return extract_txt(filename, output_candidates[0].read_bytes()) | {"fileType": "doc"}


def configured_libreoffice_binary():
    """Return a configured absolute LibreOffice binary, never a PATH lookup."""
    configured = os.getenv("LIBREOFFICE_BINARY", "").strip()
    candidates = (Path(configured),) if configured else DEFAULT_LIBREOFFICE_BINARIES
    for candidate in candidates:
        if candidate.is_absolute() and candidate.is_file():
            return str(candidate)
    return None


def write_libreoffice_macro_lockdown_profile(profile_path):
    config_path = profile_path / "user"
    config_path.mkdir(parents=True, exist_ok=True)
    (config_path / "registrymodifications.xcu").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry"
           xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <item oor:path="/org.openoffice.Office.Common/Security/Scripting">
    <prop oor:name="MacroSecurityLevel" oor:op="fuse">
      <value>3</value>
    </prop>
  </item>
</oor:items>
""",
        encoding="utf-8",
    )


def normalized_extraction(filename, file_type, file_size, page_count, text, warnings=None, metadata=None):
    return {
        "fileName": filename,
        "fileType": file_type,
        "fileSize": file_size,
        "pageCount": page_count,
        "text": text,
        "warnings": warnings or [],
        "metadata": metadata or {},
    }


def safe_internal_filename(filename, extension):
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(filename).stem).strip("_") or "resume"
    return f"{stem[:40]}{extension}"


class ImportValidationError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def sanitize_text(value):
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<[^>\n]{1,120}>", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def analyze_resume_text(text, filename="resume.txt", job_description="", target_role=""):
    parsed, unmapped = parse_resume_text(text)
    analysis = score_resume(parsed, unmapped, text, job_description, target_role)
    return {
        "originalFileName": filename,
        "importDate": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "parsedResume": parsed,
        "unmappedContent": unmapped,
        "atsAnalysis": analysis,
    }


def parse_resume_text(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    sections = split_sections(lines)
    top_lines = sections.pop("_top", [])
    full_text = "\n".join(lines)

    email = first_match(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", full_text)
    phone = first_match(r"(?:\+?\d[\d\s().-]{7,}\d)", full_text)
    linkedin = first_match(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s,;]+", full_text, flags=re.I)
    github = first_match(r"(?:https?://)?(?:www\.)?github\.com/[^\s,;]+", full_text, flags=re.I)
    urls = re.findall(r"(?:https?://|www\.)[^\s,;]+", full_text, flags=re.I)
    portfolio = next((url for url in urls if "linkedin.com" not in url.lower() and "github.com" not in url.lower()), "")

    name = detect_name(top_lines)
    target_role = detect_target_role(top_lines, name)
    location = detect_location(top_lines, {name, target_role, email, phone})

    publications = parse_publications(sections.get("publications", []))
    projects = parse_projects(sections.get("projects", []))
    if not projects:
        projects = infer_projects_from_publications(publications)

    parsed = {
        "personalInfo": {
            "fullName": name,
            "email": email or "",
            "phone": phone or "",
            "location": location,
            "linkedin": linkedin or "",
            "github": github or "",
            "portfolio": portfolio or "",
        },
        "targetRole": target_role,
        "summary": "\n".join(sections.get("summary", [])).strip(),
        "education": parse_education(sections.get("education", [])),
        "skills": parse_skills(sections.get("skills", [])),
        "experience": parse_experience(sections.get("experience", [])),
        "projects": projects,
        "publications": publications,
        "certifications": parse_certifications(sections.get("certifications", [])),
        "achievements": parse_achievements(sections.get("achievements", [])),
        "languages": parse_languages(sections.get("languages", [])),
        "declaration": "\n".join(sections.get("declaration", [])).strip(),
    }

    unmapped = []
    mapped_sections = set(sections)
    for key, section_lines in sections.items():
        if key not in SECTION_ALIASES:
            unmapped.extend(section_lines)
    for line in top_lines:
        if line and line not in {name, target_role, email, phone, location}:
            if "linkedin.com" not in line.lower() and "github.com" not in line.lower():
                unmapped.append(line)
    known = set()
    for key in mapped_sections & set(REQUIRED_SECTIONS + ["languages"]):
        known.update(sections.get(key, []))
    return parsed, dedupe([item for item in unmapped if item not in known])


def split_sections(lines):
    sections = {"_top": []}
    current = "_top"
    for line in lines:
        section = normalize_heading(line)
        if section:
            current = section
            sections.setdefault(current, [])
        elif current != "_top" and looks_like_unknown_heading(line):
            current = f"unmapped_{re.sub(r'[^a-z0-9]+', '_', line.lower()).strip('_') or 'section'}"
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return sections


def normalize_heading(line):
    cleaned = re.sub(r"[^A-Za-z &]", " ", line).lower()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > 38:
        return ""
    for section, aliases in SECTION_ALIASES.items():
        if cleaned in aliases:
            return section
    return ""


def looks_like_unknown_heading(line):
    cleaned = re.sub(r"[^A-Za-z ]", " ", line).strip()
    if not cleaned or len(cleaned) > 32:
        return False
    normalized = re.sub(r"\s+", " ", cleaned).lower()
    return normalized in UNMAPPED_HEADINGS


def detect_name(lines):
    if lines:
        first_line = re.split(r"\s*[|\u2022]\s*", lines[0], maxsplit=1)[0].strip()
        if (
            len(first_line.split()) == 1
            and len(first_line) >= 5
            and re.search(r"[A-Z]", first_line)
            and not re.search(r"@|\d|linkedin|github|https?://", first_line, re.I)
        ):
            return first_line
    for line in lines[:6]:
        labeled = re.match(r"^(?:full\s+name|name)\s*[:\-]\s*(.+)$", line, re.I)
        if labeled:
            candidate = re.split(r"\s*[|\u2022]\s*", labeled.group(1), maxsplit=1)[0].strip()
            if 2 <= len(candidate.split()) <= 5 and not re.search(r"@|\d|https?://", candidate, re.I):
                return candidate
        # Resumes frequently place a name and headline on one top line.
        line = re.split(r"\s*[|\u2022]\s*", line, maxsplit=1)[0].strip()
        if re.search(r"@|\d|linkedin|github|https?://", line, re.I):
            continue
        words = line.split()
        if 2 <= len(words) <= 5:
            return line
    return ""


def detect_target_role(lines, name):
    for line in lines[:8]:
        if line == name or re.search(r"@|\+?\d|linkedin|github|https?://", line, re.I):
            continue
        if 1 <= len(line.split()) <= 10:
            return line
    return ""


def detect_location(lines, excluded):
    for line in lines[:10]:
        if line in excluded or re.search(r"@|linkedin|github|https?://", line, re.I):
            continue
        if re.search(r"\b(india|usa|remote|chennai|bangalore|bengaluru|delhi|mumbai|hyderabad|pune)\b", line, re.I):
            return line
    return ""


def parse_education(lines):
    degree_pattern = r"\b(?:B\.?E|B\.?Tech|BSc|MSc|MCA|MBA|Bachelor|Master|Diploma)[^,;]*"
    degree_indexes = [
        index for index, line in enumerate(lines)
        if re.search(degree_pattern, line, re.I)
    ]
    if degree_indexes:
        result = []
        for position, index in enumerate(degree_indexes):
            degree = first_match(degree_pattern, lines[index], flags=re.I)
            before = lines[degree_indexes[position - 1] + 1:index] if position else lines[:index]
            after = lines[index + 1:degree_indexes[position + 1] if position + 1 < len(degree_indexes) else len(lines)]
            date_candidates = DATE_PATTERN.findall(" ".join(before)) or DATE_PATTERN.findall(" ".join(after))
            school_candidates = [
                line.strip() for line in after + list(reversed(before))
                if line.strip()
                and not DATE_PATTERN.search(line)
                and not re.search(r"(?:CGPA|GPA)[:\s]*[0-9.]", line, re.I)
                and not re.fullmatch(r"[A-Za-z .'-]+", line) is None
            ]
            institution = next(
                (line for line in school_candidates if re.search(r"college|university|institute|school", line, re.I)),
                school_candidates[0] if school_candidates else "",
            )
            result.append({
                "school": institution,
                "degree": degree,
                "field": "",
                "start_date": date_candidates[0] if len(date_candidates) > 1 else "",
                "end_date": date_candidates[-1] if date_candidates else "",
                "cgpa": first_match(r"(?:CGPA|GPA)[:\s]*([0-9.]+)", " ".join(before + after), flags=re.I),
            })
        return result

    result = []
    current = None

    def finish_current():
        if current and any(current.values()):
            result.append(current.copy())

    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        dates = DATE_PATTERN.findall(clean)
        cgpa = first_match(r"(?:CGPA|GPA)[:\s]*([0-9.]+)", clean, flags=re.I)
        degree = first_match(
            degree_pattern,
            clean,
            flags=re.I,
        )
        is_detail = bool(dates or cgpa or degree)
        if not is_detail:
            # A degree is often printed above its institution. Keep both lines
            # in one entry instead of splitting them into two partial records.
            if current and not current.get("school") and any(
                current.get(field) for field in ("degree", "start_date", "end_date", "cgpa")
            ):
                current["school"] = clean
                continue
            finish_current()
            current = {"school": clean, "degree": "", "field": "", "start_date": "", "end_date": "", "cgpa": ""}
            continue
        if current is None:
            current = {"school": "", "degree": "", "field": "", "start_date": "", "end_date": "", "cgpa": ""}
        if dates:
            current["start_date"] = dates[0] if len(dates) > 1 else current.get("start_date", "")
            current["end_date"] = dates[-1]
        if degree:
            current["degree"] = degree.strip()
        if cgpa:
            current["cgpa"] = cgpa.strip()

    finish_current()
    return result


def parse_skills(lines):
    skills = []
    current_label = ""
    current_values = []

    def flush_group():
        if current_label and current_values:
            skills.append(f"{current_label}: {', '.join(dedupe(current_values))}")

    for line in lines:
        clean = strip_bullet(line)
        if not clean:
            continue
        labeled = re.match(r"^([^:]{2,45}):\s*(.+)$", clean)
        if labeled:
            flush_group()
            current_label = labeled.group(1).strip()
            current_values = split_skill_values(labeled.group(2))
            continue
        if current_label:
            current_values.extend(split_skill_values(clean))
        else:
            skills.extend(split_skill_values(clean))

    flush_group()
    normalized = []
    pending = ""
    seen = set()
    for item in skills:
        item = item.strip()
        if not item:
            continue
        if item.endswith("&"):
            pending = f"{pending} {item[:-1].strip()}".strip()
            continue
        if pending:
            item = f"{pending} & {item}"
            pending = ""
        key = re.sub(r"[^a-z0-9]+", "", item.lower())
        if key and key not in seen:
            seen.add(key)
            normalized.append(item)
    if pending:
        key = re.sub(r"[^a-z0-9]+", "", pending.lower())
        if key and key not in seen:
            normalized.append(pending)
    return [{"skill_name": item} for item in normalized]


def split_skill_values(value):
    return [
        item.strip(" -")
        for item in re.split(r"[,|;•\n]+", str(value or ""))
        if item.strip(" -")
    ]


def parse_experience(lines):
    entries = split_experience_entries(lines)
    result = []
    for entry in entries:
        if not entry:
            continue
        heading = entry[0]
        company, role = split_role_company(heading)
        bullets = [strip_bullet(line) for line in entry[1:] if line]
        joined = " ".join(entry)
        dates = DATE_PATTERN.findall(joined)
        result.append({
            "company": company,
            "role": role,
            "start_date": dates[0] if dates else "",
            "end_date": dates[-1] if len(dates) > 1 else "",
            "is_current": any(value.lower() == "present" for value in dates),
            "raw_input": "\n".join(bullets),
            "ai_generated_bullets": bullets,
        })
    return result


def parse_projects(lines):
    return [
        {"title": entry[0], "description": "\n".join(entry[1:])}
        for entry in split_project_entries(lines)
        if entry
    ]


def parse_publications(lines):
    if not lines:
        return []
    # PDF column extraction often separates a publication's date from its
    # title/description. Keep it as one complete, candidate-provided record.
    title = DATE_PATTERN.sub("", lines[0], count=1).strip(" -") or lines[0]
    date = last_date(lines[0]) or last_date(" ".join(lines[1:2]))
    description = " ".join(
        line.strip() for line in lines[1:]
        if line.strip() and not re.fullmatch(DATE_PATTERN, line.strip())
    )
    if description:
        return [{"title": title, "description": description, "date": date}]
    return [
        {"title": entry[0], "description": "\n".join(entry[1:]), "date": last_date(" ".join(entry))}
        for entry in split_entries(lines)
        if entry
    ]


def infer_projects_from_publications(publications):
    """Expose implementation evidence as a project when no project section exists."""
    projects = []
    for publication in publications:
        description = (publication.get("description") or "").strip()
        if description and re.search(r"\b(built|developed|designed|implemented|created)\b", description, re.I):
            projects.append({
                "title": publication.get("title") or "Candidate project",
                "description": description,
            })
    return projects


def parse_certifications(lines):
    result = []
    for entry in split_entries(lines):
        joined = " ".join(entry)
        result.append({"name": entry[0] if entry else "", "issuer": "", "date": last_date(joined)})
    return result


def parse_achievements(lines):
    return [
        {"title": entry[0], "description": " ".join(entry[1:]), "date": last_date(" ".join(entry))}
        for entry in split_entries(lines)
        if entry
    ]


def parse_languages(lines):
    return [{"language_name": item.strip(), "proficiency": ""} for item in re.split(r"[,|;]", " ".join(lines)) if item.strip()]


def split_entries(lines):
    entries = []
    current = []
    for line in lines:
        if current and not is_bullet(line) and (DATE_PATTERN.search(line) or len(current) >= 3):
            entries.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append(current)
    return entries


def split_experience_entries(lines):
    """Keep a role, its dates, and all of its bullets in one work record.

    PDF/DOCX extraction commonly removes blank lines. The old generic splitter
    treated a date or a third line as a new record, which split a single job
    into phantom entries. A later date after an existing dated record is a
    reliable boundary for the next role, while bullets always stay attached.
    """
    entries, current = [], []
    has_dates = False
    cleaned = [str(line or "").strip() for line in lines if str(line or "").strip()]
    for index, clean in enumerate(cleaned):
        if not clean:
            continue
        next_line = cleaned[index + 1] if index + 1 < len(cleaned) else ""
        line_has_date = bool(DATE_PATTERN.search(clean))
        if current and experience_heading_boundary(clean, next_line, current):
            entries.append(current)
            current, has_dates = [clean], False
            continue
        if current and line_has_date and has_dates and not is_bullet(clean):
            entries.append(current)
            current, has_dates = [clean], True
            continue
        current.append(clean)
        has_dates = has_dates or line_has_date
    if current:
        entries.append(current)
    return entries


def experience_heading_boundary(line, next_line, current):
    if is_bullet(line) or DATE_PATTERN.search(line) or len(line) > 120:
        return False
    if not any(is_bullet(value) for value in current):
        return False
    return bool(DATE_PATTERN.search(next_line))


def split_project_entries(lines):
    """Split projects only at a credible new project heading.

    Narrative lines, technologies, dates, and long bullets belong to the
    current project. A new heading is accepted only after the current project
    has evidence and the following line looks like a project detail, avoiding
    the arbitrary line-count split that caused one project to become several.
    """
    cleaned = [str(line or "").strip() for line in lines if str(line or "").strip()]
    entries, current = [], []
    for index, line in enumerate(cleaned):
        next_line = cleaned[index + 1] if index + 1 < len(cleaned) else ""
        if current and project_heading_boundary(line, next_line, current):
            entries.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append(current)
    return entries


def project_heading_boundary(line, next_line, current):
    if is_bullet(line) or DATE_PATTERN.fullmatch(line) or re.match(r"^(technologies|tech stack|tools|github|demo|url)\s*:", line, re.I):
        return False
    if not any(is_bullet(value) or re.match(r"^(technologies|tech stack|tools)\s*:", value, re.I) for value in current[1:]):
        return False
    if len(line) > 100 or line.endswith((".", ";", ":")):
        return False
    return bool(is_bullet(next_line) or re.match(r"^(technologies|tech stack|tools|github|demo|url)\s*:", next_line, re.I))


def score_resume(parsed, unmapped, original_text, job_description="", target_role=""):
    return analyze_resume(
        parsed, original_text, job_description,
        extraction_warnings=unmapped, target_role=target_role,
    )


def category(name, earned, maximum, explanation, action):
    return {
        "category": name,
        "pointsEarned": max(0, min(maximum, int(round(earned)))),
        "maxPoints": maximum,
        "status": "Passed" if earned >= maximum * 0.8 else "Warning" if earned >= maximum * 0.45 else "Critical",
        "explanation": explanation,
        "recommendedAction": action,
    }


def contact_score(parsed):
    info = parsed["personalInfo"]
    earned = sum([bool(info["fullName"]) * 2, valid_email(info["email"]) * 3, valid_phone(info["phone"]) * 2, bool(info["location"]) * 1, bool(info["linkedin"] or info["github"] or info["portfolio"]) * 2])
    return category("Contact information", earned, 10, "Contact fields are checked for name, email, phone, location, and profile links.", "Add missing or invalid contact details at the top of the resume.")


def summary_score(parsed):
    words = word_count(parsed["summary"])
    earned = (bool(parsed["targetRole"]) * 5) + (5 if words >= 25 else 2 if words >= 10 else 0) + (5 if words <= 90 and words >= 25 else 2 if words else 0)
    return category("Professional title and summary", earned, 15, "Target role and summary length are evaluated.", "Add a focused target role and a 2-3 sentence summary.")


def required_sections_score(parsed):
    present = sum(bool(parsed[key]) for key in REQUIRED_SECTIONS)
    return category("Required resume sections", present / len(REQUIRED_SECTIONS) * 20, 20, f"{present} of {len(REQUIRED_SECTIONS)} required sections were detected.", "Use clear headings for Summary, Education, Skills, Experience, Publications, and Certifications.")


def skills_score(parsed):
    skills = [item["skill_name"].lower() for item in parsed["skills"] if item.get("skill_name")]
    unique = len(set(skills))
    earned = min(15, unique * 1.5)
    if len(skills) != unique:
        earned -= 2
    return category("Skills quality", earned, 15, f"{unique} unique skills were detected.", "Add specific tools and remove duplicate or generic skills.")


def experience_score(parsed):
    entries = parsed["experience"]
    bullets = " ".join(item.get("raw_input", "") for item in entries)
    metrics = len(re.findall(r"\b\d+(?:\.\d+)?%|\b\d+\s*(?:hours|users|records|reports|projects|clients|customers)\b", bullets, re.I))
    complete = sum(bool(item.get("company") and item.get("role")) for item in entries)
    earned = min(20, len(entries) * 5 + complete * 3 + metrics * 3)
    return category("Experience quality", earned, 20, f"{len(entries)} experience entries and {metrics} measurable result(s) were detected.", "Add company, role, dates, action bullets, and measurable achievements.")


def supporting_sections_score(parsed):
    earned = min(10, bool(parsed["education"]) * 4 + bool(parsed["publications"]) * 3 + bool(parsed["certifications"]) * 3)
    return category("Education, publications and certifications", earned, 10, "Education, publications, and certifications are checked as supporting proof.", "Add relevant publications or certifications if work experience is limited.")


def readability_score(text, unmapped):
    long_paragraphs = [line for line in text.split("\n") if word_count(line) > 55]
    symbols = len(re.findall(r"[★◆■●▪▬═]{1,}", text))
    first_person = bool(re.search(r"\b(i|me|my|mine)\b", text, re.I))
    earned = 10 - min(4, len(long_paragraphs) * 2) - min(2, symbols) - (2 if first_person else 0) - (2 if unmapped else 0)
    return category("ATS readability and formatting", earned, 10, "Formatting is checked for long paragraphs, decorative symbols, first-person wording, and unmapped content.", "Use simple headings, concise bullets, and avoid decorative symbols.")


def build_critical_issues(parsed, text, unmapped):
    info = parsed["personalInfo"]
    issues = []
    if not info["fullName"]:
        issues.append(issue("Missing full name", "Recruiters and ATS systems need a clear candidate name.", "Personal Information"))
    if not valid_email(info["email"]):
        issues.append(issue("Missing or invalid email", "Employers need a reliable contact method.", "Contact Information"))
    if not valid_phone(info["phone"]):
        issues.append(issue("Missing or invalid phone", "Phone contact is a common ATS field.", "Contact Information"))
    if not parsed["targetRole"]:
        issues.append(issue("Missing target role", "A target title improves role alignment.", "Header"))
    if not parsed["education"] or any(
        not (entry.get("school") or entry.get("degree")) for entry in parsed["education"]
    ):
        issues.append(
            issue(
                "Missing education details",
                "We could not confidently extract an education entry. Review it before generating or exporting your resume.",
                "Education",
            )
        )
    if unmapped:
        issues.append(issue("Unmapped content detected", "Unclassified text may not import into the correct section.", "Import Review"))
    return issues


def build_recommendations(parsed, text, unmapped):
    recs = []
    if word_count(parsed["summary"]) < 25:
        recs.append(rec("High", "Weak professional summary", "ATS systems and recruiters use the summary to understand fit quickly.", "Write 2-3 concise sentences with role, tools, and impact.", "Professional Summary"))
    if len(parsed["skills"]) < 8:
        recs.append(rec("Medium", "Limited skills list", "Skills are one of the easiest fields for ATS keyword extraction.", "Add specific tools, languages, BI tools, databases, and domain skills.", "Technical Skills"))
    if not parsed["experience"]:
        recs.append(rec("High", "Missing work experience", "Experience entries carry major ranking and recruiter value.", "Add internships, freelance work, or practical experience with role, company, dates, and bullets.", "Experience"))
    if parsed["experience"] and not re.search(r"\d", " ".join(item.get("raw_input", "") for item in parsed["experience"])):
        recs.append(rec("Medium", "Few measurable achievements", "Numbers make impact easier to evaluate.", "Add metrics such as percentage improvement, reports built, hours saved, or users supported.", "Experience"))
    if not parsed["publications"]:
        recs.append(rec("Medium", "Missing publications", "Publications help show domain knowledge and proof of work.", "Add relevant articles, papers, or published work with title, date, and details.", "Publications"))
    if re.search(r"\b(i|me|my|mine)\b", text, re.I):
        recs.append(rec("Optional", "First-person wording detected", "Resumes are usually stronger without first-person phrasing.", "Rewrite bullets to start with action verbs.", "Formatting"))
    if unmapped:
        recs.append(rec("High", "Review unmapped content", "Unmapped content may be lost if not assigned before import.", "Move each unmapped line into the correct editable field.", "Import Review"))
    return recs


def issue(problem, why, section):
    return {"problem": problem, "whyItMatters": why, "section": section}


def rec(priority, problem, why, suggestion, section):
    return {"priority": priority, "problem": problem, "whyItMatters": why, "suggestedImprovement": suggestion, "section": section}


def score_rating(score):
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Needs Improvement"
    return "Poor"


def job_match(parsed, job_description):
    resume_terms = normalized_terms(resume_value_text(parsed))
    stopwords = {
        "about", "after", "also", "and", "are", "been", "being", "but", "can",
        "candidate", "company", "experience", "for", "from", "have", "into", "job",
        "looking", "must", "our", "role", "should", "team", "that", "the", "their",
        "this", "through", "using", "will", "with", "work", "years", "you", "your",
    }
    raw_terms = re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}", job_description.lower())
    frequencies = {}
    for term in raw_terms:
        if term not in stopwords:
            frequencies[term] = frequencies.get(term, 0) + 1
    keywords = sorted(frequencies, key=lambda term: (-frequencies[term], raw_terms.index(term)))[:35]
    matched = [term for term in keywords if normalize_match_term(term) in resume_terms]
    total_weight = sum(1 + min(frequencies[term] - 1, 2) * 0.35 for term in keywords)
    matched_weight = sum(1 + min(frequencies[term] - 1, 2) * 0.35 for term in matched)
    score = round(matched_weight / total_weight * 100) if total_weight else 0
    return {
        "score": score,
        "matchedKeywords": matched,
        "missingKeywords": [term for term in keywords if term not in matched],
        "keywordsEvaluated": len(keywords),
        "method": "Deterministic weighted keyword coverage; use as guidance, not an employer ATS result.",
    }


def resume_value_text(value):
    """Flatten only candidate-provided strings; never index structural dict keys."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(resume_value_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(resume_value_text(item) for item in value)
    return ""


def normalized_terms(text):
    return {
        normalize_match_term(term)
        for term in re.findall(r"[a-z0-9+.#-]+", str(text or "").lower())
        if term
    }


def normalize_match_term(value):
    """Lightweight English normalization for deterministic job-keyword matching."""
    term = str(value or "").strip().lower()
    if len(term) <= 4:
        return term
    if term.endswith("ies") and len(term) > 5:
        return f"{term[:-3]}y"
    if term.endswith("ing") and len(term) > 6:
        stem = term[:-3]
        return stem[:-1] if len(stem) > 3 and stem[-1:] == stem[-2:-1] else stem
    if term.endswith("ed") and len(term) > 5:
        stem = term[:-2]
        return stem[:-1] if len(stem) > 3 and stem[-1:] == stem[-2:-1] else stem
    if term.endswith("es") and len(term) > 5:
        return term[:-2]
    if term.endswith("s") and len(term) > 4:
        return term[:-1]
    if term.endswith("e") and len(term) > 5:
        return term[:-1]
    return term


def map_import_to_resume_payload(parsed, filename, user_id):
    info = parsed.get("personalInfo") or {}
    links = [
        f"LinkedIn: {info.get('linkedin')}" if info.get("linkedin") else "",
        f"GitHub: {info.get('github')}" if info.get("github") else "",
        f"Portfolio: {info.get('portfolio')}" if info.get("portfolio") else "",
    ]
    title = parsed.get("targetRole") or filename.rsplit(".", 1)[0] or "Imported Resume"
    return {
        "user_id": user_id,
        "title": title,
        "target_role": parsed.get("targetRole") or "",
        "template_choice": "steady-form",
        "summary": parsed.get("summary") or "",
        "declaration": parsed.get("declaration") or "",
        "personal_info": {
            "name": info.get("fullName") or "",
            "email": info.get("email") or "",
            "phone": info.get("phone") or "",
            "location": info.get("location") or "",
            "links": [link for link in links if link],
        },
        "education": [
            {**item, "school": item.get("school") or ""}
            for item in (parsed.get("education") or [])
        ],
        "skills": parsed.get("skills") or [],
        "experience": [
            {
                **item,
                "company": item.get("company"),
                "role": item.get("role"),
            }
            for item in merge_imported_experience_fragments(parsed.get("experience") or [])
            if item.get("company") and item.get("role")
        ],
        "projects": [
            {**item, "title": item.get("title")}
            for item in merge_imported_project_fragments(parsed.get("projects") or [])
            if item.get("title")
        ],
        "publications": [
            {**item, "title": item.get("title") or "Imported Publication"}
            for item in (parsed.get("publications") or [])
        ],
        "certifications": [
            {**item, "name": item.get("name") or "Imported Certification"}
            for item in (parsed.get("certifications") or [])
        ],
        "achievements": [
            {**item, "title": item.get("title") or "Imported Achievement"}
            for item in (parsed.get("achievements") or [])
        ],
        "languages": [
            {**item, "language_name": item.get("language_name") or "Imported Language"}
            for item in (parsed.get("languages") or [])
        ],
    }


def merge_imported_project_fragments(projects):
    """Attach parser-created sentence fragments to the preceding project.

    This is deliberately conservative: valid project titles are preserved;
    only an otherwise empty lower-case sentence is folded into the previous
    project's description.
    """
    merged = []
    for project in projects:
        item = dict(project or {})
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if merged and not description and is_import_continuation(title):
            previous = merged[-1]
            previous["description"] = "\n".join(
                value for value in [str(previous.get("description") or "").strip(), title] if value
            )
            continue
        merged.append(item)
    return merged


def merge_imported_experience_fragments(experience):
    """Repair legacy date/bullet fragments without merging real work roles."""
    merged = []
    for entry in experience:
        item = dict(entry or {})
        company = str(item.get("company") or "").strip()
        role = str(item.get("role") or "").strip()
        bullets = [str(value).strip() for value in (item.get("ai_generated_bullets") or []) if str(value).strip()]
        raw_input = str(item.get("raw_input") or "").strip()
        is_fragment = (
            merged
            and company in {"", "Imported Company"}
            and (DATE_PATTERN.search(role) or is_import_continuation(role) or not role)
        )
        if is_fragment:
            previous = merged[-1]
            if not previous.get("start_date") and item.get("start_date"):
                previous["start_date"] = item["start_date"]
            if not previous.get("end_date") and item.get("end_date"):
                previous["end_date"] = item["end_date"]
            previous["ai_generated_bullets"] = [*(previous.get("ai_generated_bullets") or []), *bullets]
            previous["raw_input"] = "\n".join(value for value in [str(previous.get("raw_input") or "").strip(), raw_input] if value)
            continue
        merged.append(item)
    return merged


def is_import_continuation(value):
    text = str(value or "").strip()
    return bool(text and text[0].islower() and (text.endswith((".", ";", ":")) or len(text.split()) > 4))


def split_role_company(value):
    parts = re.split(r"\s+[-|@]\s+", value, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip(), parts[0].strip()
    return "", value.strip()


def strip_bullet(value):
    return re.sub(r"^\s*[-*•]\s*", "", value).strip()


def is_bullet(value):
    return bool(re.match(r"^\s*[-*•]\s+", value))


def first_match(pattern, value, flags=0):
    match = re.search(pattern, value or "", flags)
    return match.group(1 if match.lastindex else 0).strip() if match else ""


def last_date(value):
    dates = DATE_PATTERN.findall(value or "")
    return dates[-1] if dates else ""


def valid_email(value):
    return bool(re.fullmatch(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value or ""))


def valid_phone(value):
    return bool(re.fullmatch(r"(?:\+?\d[\d\s().-]{7,}\d)", value or ""))


def word_count(value):
    return len(re.findall(r"\b\w+\b", value or ""))


def dedupe(values):
    seen = set()
    result = []
    for value in values:
        item = str(value or "").strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result
