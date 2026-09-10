from pathlib import Path
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("entry_points", ROOT / "agents/project_AI_Agent/app/execution/entry_point.py")
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)

@pytest.mark.parametrize("files,expected", [({}, None), ({"library.py": "pass"}, None), ({"tool.py": "if __name__ == '__main__': pass"}, "tool.py"), ({"nested/main.py": "", "main.py": ""}, "main.py")])
def test_python_entrypoint(files, expected):
    assert entry.find_python_entry_point(files) == expected

@pytest.mark.parametrize("files,expected", [({"index.test.js": ""}, None), ({"index.js": ""}, "index.js"), ({"helper.js": ""}, None)])
def test_node_entrypoint(files, expected):
    assert entry.find_node_entry_point(files) == expected

def test_html_entrypoint_prefers_index():
    assert entry.find_html_entry_point({"about.html": "", "index.html": ""}) == "index.html"
