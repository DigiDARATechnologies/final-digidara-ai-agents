"""Automated NLP Skill Extraction and Taxonomy Engine for DigiDARA Job Agent.

Extracts technical skills, frameworks, tools, and competencies from:
1. Job titles and descriptions (to enrich raw scraped job postings).
2. User conversational messages (e.g. "I know Python, React, SQL", "update my skills: Node.js").
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# Comprehensive canonical tech skill taxonomy and common aliases
SKILL_TAXONOMY: Dict[str, str] = {
    # Core Languages
    "python": "Python",
    "python3": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    ".net": ".NET",
    "dotnet": ".NET",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "php": "PHP",
    "ruby": "Ruby",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "dart": "Dart",
    "scala": "Scala",
    "r": "R",
    "sql": "SQL",
    "nosql": "NoSQL",
    "html": "HTML",
    "html5": "HTML5",
    "css": "CSS",
    "css3": "CSS3",
    "sass": "SASS",
    "scss": "SCSS",
    "bash": "Bash",
    "shell": "Shell Scripting",

    # Frontend Frameworks & Libraries
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "react native": "React Native",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "svelte": "Svelte",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "redux": "Redux",
    "material-ui": "Material-UI",
    "mui": "Material-UI",
    "webpack": "Webpack",
    "vite": "Vite",

    # Backend Frameworks
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "node": "Node.js",
    "express": "Express.js",
    "express.js": "Express.js",
    "expressjs": "Express.js",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "laravel": "Laravel",
    "ruby on rails": "Ruby on Rails",
    "rails": "Ruby on Rails",
    "asp.net": "ASP.NET",
    "graphql": "GraphQL",
    "rest": "REST API",
    "rest api": "REST API",
    "restful": "REST API",
    "microservices": "Microservices",

    # Mobile
    "flutter": "Flutter",
    "android": "Android",
    "ios": "iOS",

    # Databases & Storage
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "oracle": "Oracle",
    "cassandra": "Cassandra",
    "elasticsearch": "Elasticsearch",
    "dynamodb": "DynamoDB",
    "firebase": "Firebase",

    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "jenkins": "Jenkins",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "linux": "Linux",
    "nginx": "Nginx",

    # AI, ML & Data Science
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "artificial intelligence": "AI",
    "ai": "AI",
    "deep learning": "Deep Learning",
    "generative ai": "Generative AI",
    "gen ai": "Generative AI",
    "ai agents": "AI Agents",
    "agentic ai": "AI Agents",
    "voice ai": "Voice AI",
    "llm": "LLM",
    "prompt engineering": "Prompt Engineering",
    "langchain": "LangChain",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "computer vision": "Computer Vision",
    "data science": "Data Science",
    "data analysis": "Data Analysis",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "opencv": "OpenCV",
    "powerbi": "Power BI",
    "power bi": "Power BI",
    "tableau": "Tableau",
    "excel": "Excel",

    # QA & Testing
    "selenium": "Selenium",
    "cypress": "Cypress",
    "jest": "Jest",
    "junit": "JUnit",
    "pytest": "pytest",
    "postman": "Postman",
    "manual testing": "Manual Testing",
    "automation testing": "Automation Testing",

    # Design & UI/UX
    "figma": "Figma",
    "ui/ux": "UI/UX",
    "ui design": "UI Design",
    "ux design": "UX Design",
}

# Ambiguous short tokens that require strict whole-word uppercase or explicit tech context
SHORT_AMBIGUOUS_TOKENS = {"r", "go", "c", "ai", "ml", "ts", "js"}


def _build_skill_regex(token: str) -> re.Pattern:
    """Builds a safe word-boundary regular expression for a skill token."""
    escaped = re.escape(token)
    # Handle symbols like C++, C#, .NET, AI&DS
    if token in {"c++", "c#", ".net"} or "&" in token or "/" in token:
        return re.compile(rf"(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9+])", re.IGNORECASE)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


COMPILED_SKILL_PATTERNS = [
    (alias, canonical, _build_skill_regex(alias))
    for alias, canonical in sorted(SKILL_TAXONOMY.items(), key=lambda x: -len(x[0]))
]


def extract_skills_from_text(text: str) -> List[str]:
    """
    Scans free text (job description, resume, or message) and extracts all
    matching canonical tech skills in order of appearance without duplicates.
    """
    if not text or not isinstance(text, str):
        return []

    found_skills: List[str] = []
    seen: Set[str] = set()

    for alias, canonical, pattern in COMPILED_SKILL_PATTERNS:
        if canonical in seen:
            continue

        # Ambiguous 1-2 char tokens like 'r', 'go', 'ai', 'c' require careful matching
        if alias in SHORT_AMBIGUOUS_TOKENS:
            # Check for uppercase or accompanied by other tech words
            raw_match = re.search(rf"\b{re.escape(alias)}\b", text)
            if not raw_match:
                continue
            matched_str = raw_match.group(0)
            if alias in {"ai", "ml", "js", "ts", "r"} and matched_str != alias.upper() and not text.isupper():
                # Ignore lowercase 'r' or 'ai' in normal sentences unless capitalized
                continue
            if alias == "go":
                # Only accept "Go" or "Golang" in technical context
                if not (matched_str == "Go" or re.search(r"\bgolang\b", text, re.I)):
                    continue

        if pattern.search(text):
            found_skills.append(canonical)
            seen.add(canonical)

    return found_skills


def extract_skills_from_job(job: Dict[str, Any]) -> List[str]:
    """
    Returns populated skills for a job posting.
    If `job['skills']` already contains a valid non-empty list, returns it.
    Otherwise, dynamically extracts skills from the job's title, department,
    and description.
    """
    raw_skills = job.get("skills")
    if raw_skills:
        if isinstance(raw_skills, list) and len(raw_skills) > 0:
            return raw_skills
        if isinstance(raw_skills, str):
            import json
            try:
                parsed = json.loads(raw_skills)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except Exception:
                parts = [p.strip() for p in raw_skills.split(",") if p.strip()]
                if parts:
                    return parts

    # Fallback to extraction from title, category, and description
    title = str(job.get("title") or "")
    dept = str(job.get("department") or "")
    desc = str(job.get("description") or "")
    combined = f"{title}\n{dept}\n{desc}"

    extracted = extract_skills_from_text(combined)
    return extracted[:12]  # Keep top 12 relevant skills for clean UI


def extract_skills_from_user_message(message: str) -> List[str]:
    """
    Extracts skills stated by a user in natural language chat.
    Examples:
    - "My skills are Python, React and SQL"
    - "I updated my skills: Java, Spring Boot, MySQL"
    - "Add Docker and AWS to my skills"
    - "I know React, TypeScript and Node"
    """
    if not message or not isinstance(message, str):
        return []

    msg = message.strip()

    # 1. Look for explicit pattern: "skills (are|include|: ) X, Y, Z"
    explicit_match = re.search(
        r"(?:skills?|tech\s*stack|technologies?|know|learned|proficient\s*in|experience\s*with)\s*(?:are|is|include|to|:|-)?\s*([A-Za-z0-9+#.,\s/_-]+)",
        msg,
        re.IGNORECASE,
    )
    if explicit_match:
        candidate_segment = explicit_match.group(1)
        extracted = extract_skills_from_text(candidate_segment)
        if extracted:
            return extracted

    # 2. General text extraction across the message
    return extract_skills_from_text(msg)


def extract_text_from_resume_file(file_path: Path | str) -> str:
    """Extracts raw text from an uploaded resume (.pdf, .docx, .txt)."""
    p = Path(file_path)
    if not p.is_file():
        return ""

    ext = p.suffix.lower()
    text = ""
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(p))
            extracted_pages = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append(page_text)
            text = "\n".join(extracted_pages)
        except Exception as exc:
            logger.warning("[Skills] Failed to extract text from PDF %s: %s", p.name, exc)
    elif ext == ".docx":
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(str(p)) as docx_zip:
                xml_content = docx_zip.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                paragraphs = []
                for p_node in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                    texts = [
                        node.text
                        for node in p_node.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
                        if node.text
                    ]
                    if texts:
                        paragraphs.append("".join(texts))
                text = "\n".join(paragraphs)
        except Exception as exc:
            logger.warning("[Skills] Failed to extract text from DOCX %s: %s", p.name, exc)
    elif ext in {".txt", ".md"}:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("[Skills] Failed to read text file %s: %s", p.name, exc)

    return text.strip()


def parse_resume_for_profile(file_path: Path | str) -> Dict[str, Any]:
    """Parses an uploaded resume file and extracts technical skills and years of experience."""
    raw_text = extract_text_from_resume_file(file_path)
    if not raw_text:
        return {"skills": [], "experience_years": None, "text_length": 0}

    extracted_skills = extract_skills_from_text(raw_text)

    # Detect years of experience if mentioned
    exp_years: Optional[float] = None
    exp_match = re.search(
        r"(\d+(?:\.\d+)?)\+?\s*years?(?:\s*of)?\s*(?:total\s*)?(?:work\s*|relevant\s*)?experience",
        raw_text,
        re.IGNORECASE,
    )
    if exp_match:
        try:
            exp_val = float(exp_match.group(1))
            if 0.0 <= exp_val <= 40.0:
                exp_years = exp_val
        except (ValueError, TypeError):
            pass

    return {
        "skills": extracted_skills,
        "experience_years": exp_years,
        "text_length": len(raw_text),
    }
