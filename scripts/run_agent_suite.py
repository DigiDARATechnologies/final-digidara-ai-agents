"""Run isolated agent suites, keeping explicit unit and integration reports."""
import os
import subprocess
import sys

subprocess.run([sys.executable, '-m', 'pip', 'install', 'pytest>=8.3,<10'], check=True)
os.chdir('/app')
os.environ['PYTHONPATH'] = '/app'
paths = sys.argv[1:]
groups = [('suite', paths)]
if 'backend/unit_tests' in paths:
    groups = [('unit', ['backend/unit_tests']), ('integration', [p for p in paths if p != 'backend/unit_tests'])]
result = 0
for label, targets in groups:
    completed = subprocess.run([
        sys.executable, '-m', 'pytest', *targets, '-v',
        '-o', 'cache_dir=/tmp/pytest-cache', '--basetemp=/tmp/pytest-work',
        f'--junitxml=/test-results/{label}.xml',
    ])
    result = result or completed.returncode
raise SystemExit(result)
