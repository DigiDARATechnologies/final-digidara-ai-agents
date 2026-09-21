#!/usr/bin/env python3
"""Detect .env / .env.example drift. Prints key NAMES only, never values.

  python scripts/check_env_drift.py                 # every agent, .env vs .env.example
  python scripts/check_env_drift.py job_agent       # one agent (directory-name match)
  python scripts/check_env_drift.py --code          # also: keys the code reads but .env.example omits
  python scripts/check_env_drift.py --strict        # exit 1 on drift (default is always exit 0)

Categories:
  MISSING  in .env.example, absent from .env -> the app silently uses its code default
  ORPHAN   in .env, absent from .env.example -> undocumented setting
  UNDOCUMENTED (--code) read by the code, absent from .env.example
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "artifacts", "tests", "unit_tests", "migrations"}
# Keys the platform/runtime sets itself; not application configuration.
RUNTIME_KEYS = {"PATH", "HOME", "PYTHONPATH", "PWD", "HOSTNAME", "TZ", "LANG", "USER", "TEMP", "TMP", "PYTEST_CURRENT_TEST"}

KEY_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
COMMENTED_KEY = re.compile(r"^\s*#\s*([A-Z][A-Z0-9_]{2,})\s*=")
CODE_READ = re.compile(
    r"""(?:getenv|environ\.get|environ\[|env_flag|env_int|env_float|flag|_env|read_env|_int|_float|_bool|_str|os\.getenv)\s*\(?\s*\[?\s*["']([A-Z][A-Z0-9_]{2,})["']"""
)
# pydantic-settings classes read UPPER_CASE annotated fields straight from the environment.
SETTINGS_FIELD = re.compile(r"^\s{4}([A-Z][A-Z0-9_]{2,})\s*:\s*[\w\[\], |.]+\s*=", re.MULTILINE)
CODE_EXTS = {".py", ".mjs", ".js", ".ts"}


def keys_in(path: Path, include_commented: bool = False) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = KEY_LINE.match(line)
        if match:
            keys.add(match.group(1))
        elif include_commented and (commented := COMMENTED_KEY.match(line)):
            keys.add(commented.group(1))
    return keys


def code_keys(directory: Path) -> set[str]:
    found: set[str] = set()
    for path in directory.rglob("*"):
        if path.suffix not in CODE_EXTS or any(part in SKIP_DIRS for part in path.relative_to(directory).parts):
            continue
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found.update(CODE_READ.findall(text))
        if "BaseSettings" in text:
            found.update(SETTINGS_FIELD.findall(text))
    return found - RUNTIME_KEYS


def discover(selector: str | None) -> list[Path]:
    examples = []
    for path in sorted(ROOT.rglob(".env.example")):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts) or "agent_template" in rel.parts or "frontend" in rel.parts:
            continue
        if selector is None or selector in str(rel).replace("\\", "/"):
            examples.append(path)
    return examples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("agent", nargs="?", help="substring of the agent path, e.g. job_agent")
    parser.add_argument("--code", action="store_true", help="also list keys the code reads that .env.example omits")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any drift is found")
    args = parser.parse_args()

    examples = discover(args.agent)
    if not examples:
        print(f"No .env.example found for {args.agent!r}", file=sys.stderr)
        return 2

    drift = False
    for example in examples:
        directory = example.parent
        label = directory.relative_to(ROOT).as_posix() or "."
        documented = keys_in(example, include_commented=True)
        lines: list[str] = []

        real = directory / ".env"
        if real.exists():
            actual = keys_in(real)
            lines += [f"  MISSING   {key}  (in .env.example, not in .env -> code default is used)" for key in sorted(keys_in(example) - actual)]
            lines += [f"  ORPHAN    {key}  (in .env, not in .env.example)" for key in sorted(actual - documented)]
        else:
            lines.append("  (no .env here -- skipped the .env comparison)")

        if args.code and directory != ROOT:
            lines += [f"  UNDOCUMENTED {key}  (read by code, not in .env.example)" for key in sorted(code_keys(directory) - documented)]

        real_findings = [line for line in lines if not line.startswith("  (no .env")]
        drift = drift or bool(real_findings)
        print(f"[{label}] " + ("ok" if not lines else ""))
        for line in lines:
            print(line)

    print("\nDrift found." if drift else "\nNo drift found.")
    return 1 if (drift and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
