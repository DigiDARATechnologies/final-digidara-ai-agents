"""A project with its entry in a folder runs like `python src/main.py`, and
imports the files beside it. Runs the launcher for real, the way Judge0 does."""
import subprocess
import sys

from app.execution import judge0_client


def _run(tmp_path, files, entry):
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    (tmp_path / "script.py").write_text(judge0_client._python_launcher(files, entry), encoding="utf-8")
    return subprocess.run([sys.executable, "script.py"], cwd=tmp_path, capture_output=True, text=True, timeout=30)


MAIN = "from storage import load\nif __name__ == '__main__':\n    print(load())\n"
STORAGE = "from pathlib import Path\ndef load():\n    return Path('data.txt').read_text() + Path(__file__).name\n"


def test_src_main_imports_the_file_beside_it_and_reads_from_the_project_folder(tmp_path):
    done = _run(tmp_path, {"src/main.py": MAIN, "src/storage.py": STORAGE, "data.txt": "ok-"}, "src/main.py")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok-storage.py"


def test_a_project_inside_one_top_folder_runs_from_that_folder(tmp_path):
    files = {"tracker/src/main.py": MAIN, "tracker/src/storage.py": STORAGE, "tracker/data.txt": "ok-"}
    done = _run(tmp_path, files, "tracker/src/main.py")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok-storage.py"


def test_a_real_error_in_the_project_still_shows(tmp_path):
    done = _run(tmp_path, {"src/main.py": "import not_a_real_module\n"}, "src/main.py")
    assert done.returncode != 0 and "ModuleNotFoundError" in done.stderr


def test_a_nested_entry_goes_through_the_launcher_and_a_top_level_one_does_not(monkeypatch):
    sent = {}

    def fake(language, files, entry, node=False):
        sent.update(entry=entry, files=files)
        return {}

    monkeypatch.setattr(judge0_client, "_run_submission", fake)
    judge0_client.run_python_submission({"src/main.py": "x", "src/a.py": "y"}, "src/main.py")
    assert sent["entry"] == "__digidara_run__.py" and "src/main.py" in sent["files"]
    judge0_client.run_python_submission({"main.py": "x"}, "main.py")
    assert sent["entry"] == "main.py" and list(sent["files"]) == ["main.py"]
