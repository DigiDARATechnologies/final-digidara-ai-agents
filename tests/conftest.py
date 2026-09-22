"""Repository-wide cleanup for local pytest artifacts."""

from pathlib import Path
import shutil


ARTIFACT_PATTERNS = (
    ".tmp_*.py",
    "test_output_*",
    "*_test_report.*",
    "*_test_output.*",
    "*_calibration_live.json",
    "*_calibration_live.md",
    "mock_*_live.json",
    "mock_*_live.md",
    "mock_followup_removal_review.diff",
)
ARTIFACT_DIRECTORIES = (
    "test-output",
    "test_artifacts",
    "test-artifacts",
    "screenshots",
    "screenshot-dumps",
)


def _remove_local_artifacts() -> None:
    root = Path(__file__).resolve().parents[1]
    for pattern in ARTIFACT_PATTERNS:
        for path in root.glob(pattern):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
    for directory in ARTIFACT_DIRECTORIES:
        path = root / directory
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Remove known root-level test outputs after pytest completes."""
    _remove_local_artifacts()

