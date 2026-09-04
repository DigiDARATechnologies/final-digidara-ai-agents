"""Best-effort entry-point detection for a submitted project, used to decide
what to hand Judge0 (or, for a static page, a headless browser) as the thing
to run. Execution is supplementary evidence (see code_execution_node) — when
nothing matches, we simply skip execution rather than guessing wrong."""
from __future__ import annotations

_PY_CANDIDATE_NAMES = ("main.py", "app.py", "run.py", "start.py")
_NODE_CANDIDATE_NAMES = ("index.js", "server.js", "app.js", "main.js")
_HTML_CANDIDATE_NAMES = ("index.html", "index.htm")


def _shallowest(paths: list[str]) -> str | None:
    if not paths:
        return None
    return sorted(paths, key=lambda p: p.count("/"))[0]


def find_python_entry_point(zip_code_files: dict[str, str]) -> str | None:
    py_files = {path: content for path, content in zip_code_files.items() if path.endswith(".py")}
    if not py_files:
        return None

    # 1. A conventionally-named entry file, preferring the shallowest path.
    for name in _PY_CANDIDATE_NAMES:
        match = _shallowest([path for path in py_files if path.lower().rsplit("/", 1)[-1] == name])
        if match:
            return match

    # 2. Otherwise, the shallowest file containing a __main__ guard — a
    # strong signal it's meant to be run directly, not just imported.
    guarded = _shallowest([path for path, content in py_files.items() if "__main__" in content])
    if guarded:
        return guarded

    return None


def find_node_entry_point(zip_code_files: dict[str, str]) -> str | None:
    """Same shape as find_python_entry_point, for server-side JS/GenAI-API
    projects. No __main__-style fallback exists for Node, so an unnamed
    entry file is left undetected rather than guessed at."""
    js_files = [path for path in zip_code_files if path.endswith(".js") and not path.endswith(".test.js")]
    if not js_files:
        return None

    for name in _NODE_CANDIDATE_NAMES:
        match = _shallowest([path for path in js_files if path.lower().rsplit("/", 1)[-1] == name])
        if match:
            return match

    return None


def find_html_entry_point(zip_code_files: dict[str, str]) -> str | None:
    """For a static HTML/CSS/JS project with no server-side entry point —
    the page a headless browser should actually load."""
    html_files = [path for path in zip_code_files if path.lower().endswith((".html", ".htm"))]
    if not html_files:
        return None

    for name in _HTML_CANDIDATE_NAMES:
        match = _shallowest([path for path in html_files if path.lower().rsplit("/", 1)[-1] == name])
        if match:
            return match

    # No conventional index page — fall back to the shallowest HTML file.
    return _shallowest(html_files)
