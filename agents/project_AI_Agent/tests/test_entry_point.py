from app.execution.entry_point import find_html_entry_point, find_node_entry_point, find_python_entry_point


def test_python_prefers_shallowest_root_file_over_nested_higher_priority_name():
    # Regression case: a root "app.py" (the real entry point) must win over
    # a nested "tests/fixtures/main.py" even though "main.py" is checked
    # first in the name-priority list -- depth comes first, name priority
    # only breaks a tie at equal depth.
    files = {"app.py": "", "tests/fixtures/main.py": ""}
    assert find_python_entry_point(files) == "app.py"


def test_python_uses_name_priority_as_tiebreak_at_equal_depth():
    files = {"app.py": "", "main.py": ""}
    assert find_python_entry_point(files) == "main.py"


def test_python_falls_back_to_shallowest_main_guard():
    files = {"lib/helpers.py": "", "cli.py": "if __name__ == '__main__':\n    run()"}
    assert find_python_entry_point(files) == "cli.py"


def test_python_returns_none_with_no_candidates():
    assert find_python_entry_point({"lib/helpers.py": "print('hi')"}) is None


def test_node_prefers_shallowest_root_file_over_nested_higher_priority_name():
    files = {"server.js": "", "tests/fixtures/index.js": ""}
    assert find_node_entry_point(files) == "server.js"


def test_html_prefers_shallowest_root_file_over_nested_higher_priority_name():
    # "index.html" is checked before "index.htm" in the name-priority list,
    # but a root-level "index.htm" is still the real entry point over a
    # deeply nested "index.html".
    files = {"nested/folder/index.html": "", "index.htm": ""}
    assert find_html_entry_point(files) == "index.htm"


def test_html_falls_back_to_shallowest_html_when_no_conventional_name():
    files = {"pages/about.html": "", "landing.html": ""}
    assert find_html_entry_point(files) == "landing.html"
