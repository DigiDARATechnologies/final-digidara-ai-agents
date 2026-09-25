"""Deterministic (non-LLM) syntax check over every source file in the zip.

Whether a file parses is a fact, not an opinion, so it is decided by real
parsers here and never left to an LLM's read of the code: the same file must
get the same verdict on every run, and a hallucinated "syntax error" must never
be able to fail a student's submission. Only languages that can be parsed
reliably and safely inside this process are checked -- Python (`ast`), JSON and
TOML. Everything else (JavaScript, TypeScript, Java, ...) needs its own
toolchain to parse without false positives on newer syntax, so those files are
listed as `unchecked_extensions` and the code reviewer is told to read them
line by line instead.

The archive contents are never written to disk or executed: `ast.parse` only
builds a tree, it does not import or run anything.
"""
from __future__ import annotations

import ast
import json
from pathlib import PurePosixPath
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 (production runs 3.12): TOML is simply not checked
    tomllib = None  # type: ignore[assignment]

# The report shown to a student stays readable; the true total is still counted.
MAX_REPORTED_ERRORS = 20
_MAX_SNIPPET_CHARS = 200

# JSON files that are, by convention, JSON *with comments* -- not valid strict
# JSON, but not broken either. Checking them would fail correct submissions.
_LENIENT_JSON_PREFIXES = ("tsconfig", "jsconfig", ".eslintrc", ".babelrc", "devcontainer")

# Languages the code reviewer must read for syntax itself, since nothing here
# parses them. Docs/markup/config (md, txt, html, css, ...) are not "code".
_UNCHECKED_CODE_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".c", ".h",
    ".cpp", ".hpp", ".cs", ".rs", ".sh", ".sql",
}


def _extension(path: str) -> str:
    return PurePosixPath(path).suffix.lower()


def _source_line(source: str, line: int | None) -> str:
    if not line or line < 1:
        return ""
    lines = source.splitlines()
    if line > len(lines):
        return ""
    return lines[line - 1].rstrip()[:_MAX_SNIPPET_CHARS]


def _error(path: str, language: str, line: int | None, column: int | None, message: str, source: str) -> dict[str, Any]:
    return {
        "path": path,
        "language": language,
        "line": line,
        "column": column,
        "message": message.strip() or "Invalid syntax",
        "source_line": _source_line(source, line),
    }


def _check_python(path: str, source: str) -> dict[str, Any] | None:
    try:
        ast.parse(source, filename=path)
    except SyntaxError as exc:  # also IndentationError and TabError
        return _error(path, "Python", exc.lineno, exc.offset, exc.msg or "Invalid syntax", source)
    except ValueError as exc:  # e.g. source containing null bytes
        return _error(path, "Python", None, None, str(exc), source)
    except (RecursionError, MemoryError):
        # Pathologically nested/huge input the parser gave up on -- that is not
        # evidence of a syntax error, so it is left to the reviewer.
        return None
    return None


def _check_json(path: str, source: str) -> dict[str, Any] | None:
    name = PurePosixPath(path).name.lower()
    if name.startswith(_LENIENT_JSON_PREFIXES) or ".vscode" in PurePosixPath(path).parts:
        return None
    try:
        json.loads(source)
    except json.JSONDecodeError as exc:
        return _error(path, "JSON", exc.lineno, exc.colno, exc.msg, source)
    except RecursionError:
        return None
    return None


def _check_toml(path: str, source: str) -> dict[str, Any] | None:
    try:
        tomllib.loads(source)
    except tomllib.TOMLDecodeError as exc:
        # tomllib only reports position inside its message ("... (at line 3, column 5)").
        line = column = None
        text = str(exc)
        marker = "(at line "
        if marker in text:
            try:
                position = text.rsplit(marker, 1)[1].rstrip(")")
                line_part, column_part = position.split(", column ")
                line, column = int(line_part), int(column_part)
            except ValueError:
                line = column = None
        return _error(path, "TOML", line, column, text.split(" (at ")[0], source)
    except RecursionError:
        return None
    return None


_CHECKERS = {".py": ("Python", _check_python), ".json": ("JSON", _check_json)}
if tomllib is not None:
    _CHECKERS[".toml"] = ("TOML", _check_toml)


def check_syntax(code_files: dict[str, str] | None) -> dict[str, Any]:
    """Parse every checkable file and report each syntax error found.

    Returns:
        checked_files:        paths that were parsed by a real parser
        checked_languages:    which languages those were
        unchecked_extensions: code extensions present but not machine-checked
        errors:               up to MAX_REPORTED_ERRORS error dicts, in path order
        error_count:          the true total (may exceed len(errors))
        has_errors:           error_count > 0
    """
    checked: list[str] = []
    languages: set[str] = set()
    unchecked: set[str] = set()
    errors: list[dict[str, Any]] = []
    error_count = 0

    for path in sorted(code_files or {}):
        extension = _extension(path)
        checker = _CHECKERS.get(extension)
        if checker is None:
            if extension in _UNCHECKED_CODE_EXTENSIONS:
                unchecked.add(extension)
            continue
        language, check = checker
        result = check(path, (code_files or {})[path])
        checked.append(path)
        languages.add(language)
        if result is not None:
            error_count += 1
            if len(errors) < MAX_REPORTED_ERRORS:
                errors.append(result)

    return {
        "checked_files": checked,
        "checked_languages": sorted(languages),
        "unchecked_extensions": sorted(unchecked),
        "errors": errors,
        "error_count": error_count,
        "has_errors": error_count > 0,
    }
