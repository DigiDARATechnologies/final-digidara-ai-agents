"""Safe normalization and validation for fenced learner-facing code."""

import re

from .security import clean_text


FENCE_PATTERN = re.compile(
    r"```(?P<language>[A-Za-z0-9_+#.-]+)[ \t]*\n(?P<code>[\s\S]*?)\n?```",
)
ANY_FENCE_PATTERN = re.compile(r"```")
UNLABELLED_FENCE_PATTERN = re.compile(
    r"```[ \t]*\n(?P<code>[\s\S]*?)\n?```",
)
LANGUAGE_PATTERN = re.compile(r"[A-Za-z0-9_+#.-]+")
LIKELY_CODE_PATTERN = re.compile(
    r"(?:"
    r"\bdef\s+\w+\s*\(|\bclass\s+\w+\s*[:{]|\bfunction\s+\w+\s*\(|"
    r"\b(?:print|console\.log)\s*\(|#include\s*[<\"]|"
    r"\bpublic\s+static\s+void\s+\w+\s*\(|"
    r"(?:^|\n)\s*for\s+\w+\s+in\s+.+:|"
    r"(?:^|\n)\s*(?:for|while|if)\s*\([^\n]+\)\s*[{:]?|"
    r"(?:^|\n)\s*import\s+[A-Za-z_][\w.]*|"
    r"(?:^|\n)\s*from\s+[A-Za-z_][\w.]*\s+import\s+"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def decode_literal_layout(value):
    """Decode a fully escaped multi-line layout without touching code escapes.

    Groq occasionally double-escapes every layout newline. Only decode when
    the string has no real newline and contains at least two consistent
    escaped separators; a lone C/Java string escape such as ``"\\n"`` is
    therefore preserved.
    """
    raw=str(value or "").replace("\x00","").replace("\r\n","\n").replace("\r","\n")
    if "\n" in raw:
        return raw
    double_crlf=raw.count(r"\\r\\n")
    double_count=raw.replace(r"\\r\\n","").count(r"\\n")+double_crlf
    if double_count>=2:
        return raw.replace(r"\\r\\n","\n").replace(r"\\n","\n").replace(r"\\t","\t")
    without_double=raw.replace(r"\\r\\n","").replace(r"\\n","")
    single_crlf=without_double.count(r"\r\n")
    single_count=without_double.replace(r"\r\n","").count(r"\n")+single_crlf
    if single_count>=2:
        return raw.replace(r"\r\n","\n").replace(r"\n","\n").replace(r"\t","\t")
    return raw


def normalize_fenced_text(value, maximum=3000, prose_normalizer=clean_text):
    """Preserve fenced code exactly while safely normalizing surrounding prose."""
    raw=decode_literal_layout(value).strip()
    parts=[]
    cursor=0
    for match in FENCE_PATTERN.finditer(raw):
        prose=prose_normalizer(raw[cursor:match.start()],maximum)
        if prose:
            parts.append(prose)
        code=match.group("code").strip("\n")
        parts.append(f"```{match.group('language').lower()}\n{code}\n```")
        cursor=match.end()
    tail=prose_normalizer(raw[cursor:],maximum)
    if tail:
        parts.append(tail)
    return "\n\n".join(parts)[:maximum]


def validate_fenced_code(value, expected_language=None):
    """Reject malformed or unfenced program snippets in technical content."""
    raw=decode_literal_layout(value)
    matches=list(FENCE_PATTERN.finditer(raw))
    if len(ANY_FENCE_PATTERN.findall(raw)) != len(matches)*2:
        raise ValueError("technical code must use complete language-labelled fenced code blocks")
    for match in matches:
        if not match.group("code").strip():
            raise ValueError("technical code block cannot be empty")
        if expected_language and match.group("language").casefold()!=str(expected_language).casefold():
            raise ValueError(f"technical code language must be {str(expected_language).lower()}")
    outside=FENCE_PATTERN.sub(" ",raw)
    # A single inline token such as ``print()`` or ``class`` is often normal
    # technical prose. Require a multiline layout, or multiple code cues on
    # one line, before treating the content as an unfenced program.
    code_cues=LIKELY_CODE_PATTERN.findall(outside)
    if ("\n" in outside and code_cues) or len(code_cues)>=2:
        raise ValueError("technical code must be inside a language-labelled fenced code block")


def canonicalize_unlabelled_fences(value, language):
    """Label complete, unlabeled Markdown blocks with the selected language,
    and fence bare program lines (see fence_bare_code).

    This is deliberately narrow: unmatched fences remain invalid, while a
    structurally complete block is made compatible with the learner-facing
    fenced-code contract.
    """
    raw=decode_literal_layout(value)
    label=str(language or "python").strip().lower()
    if not LANGUAGE_PATTERN.fullmatch(label):
        label="python"
    labelled=UNLABELLED_FENCE_PATTERN.sub(
        lambda match:f"```{label}\n{match.group('code').strip(chr(10))}\n```",
        raw,
    )
    return fence_bare_code(labelled,label)


# A line that reads like code rather than prose: indented, a keyword or call
# at the start, an assignment, or ending in a block/statement delimiter.
CODE_LINE_HINT=re.compile(
    r"^\s{2,}\S|^\t+\S|"
    r"^\s*(?:return|elif|else\b|try\s*:|except|finally\s*:|while|for|if|def|class|import|from|print|"
    r"console\.log|System\.out|#include|public|private|static|int\s|var\s|let\s|const\s|#)|"
    r"[;{}]\s*$|:\s*$|"
    r"^\s*[A-Za-z_][\w\[\].\"']*\s*(?:[+\-*/%]?=)(?!=)|"
    r"^\s*[})\]]"
)
# A sentence: capitalised word followed by at least three more words.
PROSE_LINE=re.compile(r"^\s*[A-Z][a-z]+(?:\s+\S+){3,}")
BARE_CODE_ERROR="technical code must be inside a language-labelled fenced code block"


def _is_code_line(line):
    if not line.strip():
        return False
    if PROSE_LINE.match(line) and not LIKELY_CODE_PATTERN.search(line):
        return False
    return bool(LIKELY_CODE_PATTERN.search(line) or CODE_LINE_HINT.search(line))


def fence_bare_code(value, language):
    """Wrap program lines the model wrote without a code block.

    Models sometimes put a question's code on plain lines ("What is the
    output?" then `print(type([]) == list)`) despite being asked for a fenced
    block, and repeat it on every retry, so one such question used to fail a
    whole test. This repairs only text that has no fences at all AND is
    rejected for bare code: consecutive code lines become one fenced block in
    the selected language. The result must still pass validate_fenced_code,
    otherwise the original text is returned and rejected as before.
    """
    raw=str(value or "")
    if "```" in raw or "\n" not in raw.strip():
        return raw
    try:
        validate_fenced_code(raw,language)
        return raw
    except ValueError as exc:
        if str(exc)!=BARE_CODE_ERROR:
            return raw
    lines=raw.strip("\n").split("\n")
    flags=[_is_code_line(line) for line in lines]
    # A blank line between two code lines belongs to the block.
    for index,line in enumerate(lines):
        if not line.strip() and 0<index<len(lines)-1 and flags[index-1] and any(flags[index+1:]) and flags[index+1]:
            flags[index]=True
    out=[]
    block=[]
    for line,is_code in zip(lines,flags):
        if is_code:
            block.append(line)
            continue
        if block:
            out.append(f"```{language}\n"+"\n".join(block).strip("\n")+"\n```")
            block=[]
        out.append(line)
    if block:
        out.append(f"```{language}\n"+"\n".join(block).strip("\n")+"\n```")
    repaired="\n".join(out)
    try:
        validate_fenced_code(repaired,language)
    except ValueError:
        return raw
    return repaired


def apply_structured_code_fields(item, category, expected_language=None):
    """Convert optional JSON-safe code fields into the existing text contract."""
    if category!="Technical Aptitude" or not isinstance(item,dict):
        return item
    prepared={**item,"options":dict(item.get("options") or {})}

    expected=str(expected_language or "").strip().lower()

    def fenced(payload):
        if payload in (None,{}):
            return None
        if not isinstance(payload,dict):
            raise ValueError("technical code field must be an object")
        language=str(payload.get("language") or "").strip().lower()
        code=str(payload.get("code") or "").replace("\r\n","\n").replace("\r","\n").strip("\n")
        if not LANGUAGE_PATTERN.fullmatch(language) or not code.strip():
            raise ValueError("technical code field requires language and code")
        if expected and language!=expected:
            raise ValueError(f"technical code language must be {expected}")
        outer=FENCE_PATTERN.fullmatch(code.strip())
        if outer:
            if outer.group("language").lower()!=language:
                raise ValueError("technical code field language does not match its fenced code")
            code=outer.group("code").strip("\n")
        elif "```" in code:
            raise ValueError("technical code field must contain raw code without Markdown fences")
        return f"```{language}\n{code}\n```"

    for field,code_field in (("question","question_code"),("explanation","explanation_code")):
        block=fenced(prepared.get(code_field))
        if block:
            prose=str(prepared.get(field) or "").strip()
            # The structured object is authoritative. If the model duplicated
            # a Markdown block in the prose field, discard that duplicate so
            # malformed or conflicting fences cannot poison valid code data.
            prose=FENCE_PATTERN.sub("",canonicalize_unlabelled_fences(prose,expected or "python")).strip()
            if "```" in prose:
                raise ValueError("technical prose contains an incomplete code fence")
            prepared[field]=f"{prose}\n\n{block}" if prose else block

    option_code=prepared.get("option_code") or {}
    if not isinstance(option_code,dict):
        raise ValueError("option_code must be an object")
    for key,payload in option_code.items():
        if key not in {"A","B","C","D"}:
            raise ValueError("option_code keys must be A-D")
        block=fenced(payload)
        if block:
            prose=str(prepared["options"].get(key) or "").strip()
            prose=FENCE_PATTERN.sub("",canonicalize_unlabelled_fences(prose,expected or "python")).strip()
            if "```" in prose:
                raise ValueError("technical option contains an incomplete code fence")
            prepared["options"][key]=f"{prose}\n\n{block}" if prose else block
    return prepared
