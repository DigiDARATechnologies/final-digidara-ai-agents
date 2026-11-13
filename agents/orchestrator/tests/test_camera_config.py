"""Startup safety checks for development-only simulated camera support."""
import os
import subprocess
import sys
from pathlib import Path


ORCHESTRATOR_DIR = Path(__file__).resolve().parents[1]


def _run_config_import(env_name: str, allow_fake_camera: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        "ENV": env_name,
        "ALLOW_FAKE_CAMERA": allow_fake_camera,
        "DATABASE_URL": "mysql+pymysql://test:test@127.0.0.1/test",
    })
    return subprocess.run(
        [sys.executable, "-c", "from app import config; print(config.ALLOW_FAKE_CAMERA)"],
        cwd=ORCHESTRATOR_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_production_startup_refuses_fake_camera_flag():
    result = _run_config_import("production", "true")
    assert result.returncode != 0
    assert "Unsafe configuration: ALLOW_FAKE_CAMERA cannot be enabled when ENV=production." in result.stderr


def test_non_dev_non_test_environment_ignores_fake_camera_flag():
    result = _run_config_import("staging", "true")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
