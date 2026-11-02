"""Minimal Judge0 CE client for supplementary "does it run" evidence on a
capstone submission. Judge0 is the same sandboxed execution service
`agents/codeforge_agent` already depends on for the identical class of
problem (running untrusted, submitted code safely) — reusing it here keeps
execution outside this service's own process/disk entirely, consistent with
zip_ingest.py's "never touches our disk" handling of untrusted submissions.

Best-effort only: a submission is diverse and AI-generated, often with no
well-defined "run it with no input and check exit code" behavior (a Flask
app, a script needing a real API key, one expecting interactive stdin). A
failed or unavailable execution is one more data point for the reviewing
LLM, never a hard gate — see prompts.output_verification_prompt."""
from __future__ import annotations

import base64
import io
import logging
import shlex
import zipfile

import httpx

from app import config

logger = logging.getLogger("capstone.execution")

PYTHON3_LANGUAGE_ID = 71
NODE_LANGUAGE_ID = 63  # JavaScript (Node.js 12.14.0) — see judge0 v1.13.1 db/languages/active.rb (github.com/judge0/judge0)
NODE_MEMORY_LIMIT_KB = 512000  # Judge0's largest allowed memory limit (MAX_MEMORY_LIMIT)


class Judge0Unavailable(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _pack_additional_files(code_files: dict[str, str], exclude: str) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in code_files.items():
            if path == exclude:
                continue
            zf.writestr(path, content)
    return _b64(buffer.getvalue())


def _auth_headers() -> dict[str, str]:
    """Judge0's access token, as the CodeForge agent sends it."""
    headers = {}
    if config.JUDGE0_AUTHN_TOKEN:
        headers[config.JUDGE0_AUTHN_HEADER] = config.JUDGE0_AUTHN_TOKEN
    if config.JUDGE0_AUTHZ_TOKEN:
        headers[config.JUDGE0_AUTHZ_HEADER] = config.JUDGE0_AUTHZ_TOKEN
    return headers


def _python_launcher(code_files: dict[str, str], entry_point: str) -> str:
    """Judge0 runs the program as /box/script.py, in the top folder. A project
    whose entry is in a folder (src/main.py, as in our own example project) then
    could not import the files beside it: every such project failed with
    ModuleNotFoundError, however correct. This runs the entry as `python
    src/main.py` would, from the project's own top folder."""
    top = entry_point.split("/", 1)[0]
    project = top if all(path.startswith(f"{top}/") for path in code_files) else ""
    return (
        "import os, runpy, sys\n"
        f"entry = os.path.abspath({entry_point!r})\n"
        "sys.path.insert(0, os.path.dirname(entry))\n"
        f"os.chdir({project!r} or '.')\n"
        "sys.argv = [entry]\n"
        "runpy.run_path(entry, run_name='__main__')\n"
    )


def _run_submission(language_id: int, code_files: dict[str, str], entry_point: str, node: bool = False) -> dict:
    """Submits `entry_point` as the program and every other file as
    `additional_files` (Judge0 extracts these into the same working
    directory before running), synchronously (`wait=true`) so Judge0 itself
    blocks server-side until done — capped by its own wall_time_limit, so
    there's no separate client-side poll loop to get wrong.

    Raises Judge0Unavailable if the service can't be reached at all —
    callers should treat that as "no execution evidence", not a submission
    failure. No network access is granted inside the sandbox, so code that
    calls a real external API is expected to fail there; that's expected,
    not a bug in this client."""
    payload = {
        "language_id": language_id,
        "source_code": _b64(code_files[entry_point].encode("utf-8")),
        "additional_files": _pack_additional_files(code_files, exclude=entry_point),
        "cpu_time_limit": config.CODE_EXECUTION_CPU_SECONDS,
        "wall_time_limit": config.CODE_EXECUTION_WALL_SECONDS,
        "memory_limit": config.CODE_EXECUTION_MEMORY_KB,
        "enable_network": False,
        # Per-process limits: the only kind this Judge0 host can enforce. With
        # Judge0's default (cgroup) limits every run, Python included, ended
        # in "Internal Error: No such file or directory /box/script.py".
        "enable_per_process_and_thread_time_limit": True,
        "enable_per_process_and_thread_memory_limit": True,
    }
    if node:
        # Judge0's largest memory limit: address space, not real use (~30 MB).
        payload["memory_limit"] = NODE_MEMORY_LIMIT_KB
    try:
        with httpx.Client(base_url=config.JUDGE0_URL, timeout=config.CODE_EXECUTION_WALL_SECONDS + 10.0,
                          headers=_auth_headers()) as client:
            response = client.post(
                "/submissions",
                params={"base64_encoded": "true", "wait": "true"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Judge0 unreachable or errored: %s", exc)
        raise Judge0Unavailable(str(exc)) from exc

    status = data.get("status") or {}
    return {
        "available": True,
        "completed": True,
        "kind": "process",
        "status": status.get("description", "Unknown"),
        "status_id": status.get("id"),
        "stdout": _decode(data.get("stdout"))[:4000],
        "stderr": _decode(data.get("stderr"))[:4000],
        "compile_output": _decode(data.get("compile_output"))[:2000],
        "message": _decode(data.get("message")),
        "time_seconds": data.get("time"),
        "memory_kb": data.get("memory"),
    }


def run_python_submission(code_files: dict[str, str], entry_point: str) -> dict:
    if "/" in entry_point:
        launcher = "__digidara_run__.py"
        result = _run_submission(PYTHON3_LANGUAGE_ID, {**code_files, launcher: _python_launcher(code_files, entry_point)}, launcher)
    else:
        result = _run_submission(PYTHON3_LANGUAGE_ID, code_files, entry_point)
    result["entry_point"] = entry_point
    return result


BASH_LANGUAGE_ID = 46
NODE_BINARY = "/usr/local/node-12.14.0/bin/node"
_NODE_RUNNER = "__skilldara_run_node.sh"


def run_node_submission(code_files: dict[str, str], entry_point: str) -> dict:
    """Same evidence shape as run_python_submission — server-side JS/GenAI-API
    projects get the identical "real stdout/stderr/exit status" treatment
    Python submissions already get.

    Node.js runs through a Bash script with one V8 worker and one libuv
    thread: under Judge0's per-process memory limit a default Node.js 12
    reserves too much address space to even start (it hung or crashed on
    console.log). All project files, the entry point included, go in as
    additional files; the script only starts Node on the entry point."""
    script = (f"UV_THREADPOOL_SIZE=1 exec {NODE_BINARY} --v8-pool-size=1 --max-old-space-size=256 "
              f"{shlex.quote(entry_point)}\n")
    result = _run_submission(BASH_LANGUAGE_ID, {**code_files, _NODE_RUNNER: script}, _NODE_RUNNER, node=True)
    result["entry_point"] = entry_point
    return result
