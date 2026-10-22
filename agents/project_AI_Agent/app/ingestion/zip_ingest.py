"""ZipIngestNode (deterministic, non-LLM) — safely unpacks the submitted
source-code zip *in memory only* (never extracted to disk) and builds the
flattened file tree + a dict of readable source-file contents for review.

Treats the archive as untrusted input: rejects path traversal, password
protection, oversized archives, and archives with too many entries before
reading a single byte of content.
"""
from __future__ import annotations

import zipfile
from pathlib import PurePosixPath

from app import config
from app.ingestion.screenshots import ingest_screenshots


class ZipIngestError(Exception):
    pass


def _is_ignored(rel_path: str) -> bool:
    parts = PurePosixPath(rel_path).parts
    return any(part in config.ZIP_IGNORE_DIR_NAMES for part in parts)


_IGNORE_HINT = "node_modules, venv, .git, dist and build"


def _is_safe_member(name: str) -> bool:
    if name.startswith("/") or name.startswith("\\"):
        return False
    if ":" in name:  # e.g. "C:\..." on a crafted archive
        return False
    posix = PurePosixPath(name)
    return ".." not in posix.parts


def ingest_zip(zip_path: str) -> dict:
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise ZipIngestError("The uploaded file is not a valid .zip archive.") from exc

    with zf:
        infos = zf.infolist()

        if len(infos) == 0:
            raise ZipIngestError("The zip is empty.")
        if len(infos) > config.MAX_ZIP_ENTRIES_TOTAL:
            raise ZipIngestError(
                f"Your zip has {len(infos)} files, which is far more than a project needs. "
                f"Delete folders like {_IGNORE_HINT} from your project, zip it again and upload it."
            )

        for info in infos:
            if not _is_safe_member(info.filename):
                raise ZipIngestError(
                    f"The zip contains an unsafe path entry ('{info.filename}') and was rejected."
                )

        # Dependency and build folders are skipped from here on: they don't
        # count towards the limits and are never decompressed.
        kept = [info for info in infos if not _is_ignored(info.filename)]
        kept_files = [info for info in kept if not info.is_dir()]

        if len(kept_files) > config.MAX_ZIP_FILES:
            raise ZipIngestError(
                f"Your zip has {len(kept_files)} project files, more than the {config.MAX_ZIP_FILES} allowed. "
                f"Remove generated or downloaded files (for example {_IGNORE_HINT}), zip the project again "
                "and upload it."
            )

        for info in kept:
            if info.flag_bits & 0x1:
                raise ZipIngestError("The zip is password-protected and cannot be scanned.")

        total_uncompressed = sum(info.file_size for info in kept)
        if total_uncompressed > config.MAX_UPLOAD_BYTES * 10:
            # Generous multiple of the upload cap — catches zip-bomb style
            # archives without penalizing normal small-project submissions.
            raise ZipIngestError("The zip's uncompressed contents are too large to process.")

        for info in kept_files:
            try:
                with zf.open(info) as fh:
                    while fh.read(1024 * 1024):
                        pass
            except (zipfile.BadZipFile, OSError, EOFError) as exc:
                raise ZipIngestError(
                    f"The zip is corrupt — entry '{info.filename}' could not be read."
                ) from exc

        file_tree: list[str] = []
        code_files: dict[str, str] = {}

        for info in kept_files:
            rel_path = info.filename
            file_tree.append(rel_path)

            suffix = "." + rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
            if suffix in config.CODE_TEXT_EXTENSIONS:
                raw = zf.read(info)
                try:
                    code_files[rel_path] = raw.decode("utf-8")
                except UnicodeDecodeError:
                    code_files[rel_path] = raw.decode("utf-8", errors="replace")

        screenshot_evidence = ingest_screenshots(zf, kept_files)

        if not code_files:
            found = sorted(file_tree)[:8]
            listing = ", ".join(found) if found else "nothing"
            more = f" (and {len(file_tree) - len(found)} more)" if len(file_tree) > len(found) else ""
            raise ZipIngestError(
                "Your zip has no source code files we can read. Put your project's code (for example .py, .js, "
                "or .java files) inside the project folder - typically in a src folder such as "
                f"MyProject/src/main.py - then zip that folder and upload it again. What was found in your zip: "
                f"{listing}{more}."
            )

    return {
        "zip_file_tree": sorted(file_tree),
        "zip_code_files": code_files,
        "screenshot_evidence": screenshot_evidence,
    }
