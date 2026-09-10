"""Run browser tests while owning the frontend server's full lifetime."""
import subprocess
import sys
import time
from urllib.request import urlopen

with open('frontend-test.log', 'w') as log:
    server = subprocess.Popen([sys.executable, '-m', 'http.server', '4173', '--bind', '127.0.0.1', '--directory', 'dist'], stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(30):
            if server.poll() is not None:
                raise RuntimeError('Frontend server exited before tests started')
            try:
                with urlopen('http://127.0.0.1:4173/', timeout=1):
                    break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError('Frontend server did not become ready')
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/e2e'])
    finally:
        server.terminate()
        server.wait(timeout=10)
raise SystemExit(result.returncode)
