"""Execute the existing test suite inside an ephemeral agent container."""
import os
import subprocess
import sys

subprocess.run([sys.executable, '-m', 'pip', 'install', 'pytest>=8.3,<10'], check=True)
os.chdir('/app')
os.environ['PYTHONPATH'] = '/app'
raise SystemExit(subprocess.run([
    sys.executable, '-m', 'pytest', *sys.argv[1:], '-v',
    '-o', 'cache_dir=/tmp/pytest-cache', '--basetemp=/tmp/pytest-work',
    '--junitxml=/test-results/suite.xml',
]).returncode)
