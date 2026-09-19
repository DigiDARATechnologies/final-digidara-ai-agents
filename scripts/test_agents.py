"""Build and test isolated agent containers locally or in GitHub Actions."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
AGENTS = [
    ('orchestrator', 'agents/orchestrator', 8100, 'app.main:app', 'uvicorn.workers.UvicornWorker'),
    ('capstone-agent', 'agents/project_AI_Agent', 8000, 'app.api.main:app', 'uvicorn.workers.UvicornWorker'),
    ('codeforge-agent', 'agents/codeforge_agent/services/lms-api', 4000, 'lms_api:create_app()', 'sync'),
    ('communication-agent', 'agents/communication-ai-agent/backend', 5001, 'run:app', 'sync'),
    ('aptitude-agent', 'agents/aptitude_agent', 5000, 'app:app', 'sync'),
    ('mock-interview-agent', 'agents/mock_interview_agent/backend', 5030, 'app:app', 'sync'),
    ('resume-builder-agent', 'agents/resume_builder_agent/backend', 5010, 'run:app', 'sync'),
    ('certificate-agent', 'agents/certificate_agent', 8008, 'cert_app.main:app', 'uvicorn.workers.UvicornWorker'),
    ('job-agent', 'agents/job_agent', 5020, 'job_agent.app:create_app()', 'sync'),
]
SUITES = {
    'orchestrator': ['tests'],
    'capstone-agent': ['tests'],
    'codeforge-agent': ['tests'],
    'communication-agent': ['tests'],
    'aptitude-agent': ['backend/unit_tests', 'backend/tests'],
    'mock-interview-agent': ['tests'],
    'resume-builder-agent': ['tests'],
    'certificate-agent': ['tests'],
    'job-agent': ['tests'],
}


def compose_config(init_file, agents=None):
    services = {'mysql': {
        'image': 'mysql:8',
        'environment': {'MYSQL_ROOT_PASSWORD': 'local-test-password', 'MYSQL_ROOT_HOST': '%'},
        'volumes': [f'{init_file.as_posix()}:/docker-entrypoint-initdb.d/databases.sql:ro'],
        'healthcheck': {
            'test': ['CMD', 'mysqladmin', 'ping', '-h', '127.0.0.1', '-plocal-test-password'],
            'interval': '5s', 'timeout': '5s', 'retries': 30,
        },
    }}
    for name, context, port, app, worker in (AGENTS if agents is None else agents):
        database = name.replace('-', '_') + '_test'
        database_url = f'mysql+pymysql://root:local-test-password@mysql:3306/{database}'
        gunicorn_workers = '4' if name == 'job-agent' else '1'
        services[name] = {
            'image': f'digidara-test/{name}:local',
            'build': {'context': (ROOT / context).as_posix()},
            'ports': [f'127.0.0.1::{port}'],
            'depends_on': {'mysql': {'condition': 'service_healthy'}},
            'command': ['gunicorn', '-w', gunicorn_workers, '-k', worker, '-b', f'0.0.0.0:{port}', app],
            'environment': {
                'DATABASE_URL': database_url, 'TEST_DATABASE_URL': database_url,
                'INTEGRATION_DATABASE_URL': database_url,
                'DB_HOST': 'mysql', 'DB_USER': 'root', 'DB_PASSWORD': 'local-test-password', 'DB_NAME': database,
                'MYSQL_HOST': 'mysql', 'MYSQL_USER': 'root', 'MYSQL_PASSWORD': 'local-test-password', 'MYSQL_DATABASE': database,
                'SECRET_KEY': 'local-test-secret-at-least-32-characters',
                'JWT_SECRET': 'local-test-jwt-secret-at-least-32-characters',
                'JWT_SECRET_KEY': 'local-test-jwt-secret-at-least-32-characters',
                'AGENT_SHARED_SECRET': 'local-test-agent-secret',
                'LMS_API_SHARED_SECRET': 'local-test-agent-secret',
                'CODING_PRACTICE_ENABLED': 'true',
                'OPENAI_API_KEY': 'local-test-unused-key',
                'OPENAI_BASE_URL': 'http://127.0.0.1:9/v1',
                'ORCHESTRATOR_URL': 'http://127.0.0.1:9',
            },
        }
    return {'services': services}


def run_agent(agent, skip_build):
    name, context, port, *_ = agent
    artifacts = ROOT / 'artifacts' / 'agent-tests' / name
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='digidara-tests-') as directory:
        temp = Path(directory)
        init_file = temp / 'databases.sql'
        init_file.write_text('CREATE DATABASE IF NOT EXISTS `' + name.replace('-', '_') + '_test`;', encoding='utf-8')
        config_file = temp / 'compose.json'
        config_file.write_text(json.dumps(compose_config(init_file, [agent])), encoding='utf-8')
        compose = ['docker', 'compose', '-p', f'digidara-test-{uuid.uuid4().hex[:10]}', '-f', str(config_file)]
        result_code = 0
        try:
            subprocess.run(compose + ['up', '--no-build' if skip_build else '--build', '-d'], check=True, cwd=ROOT, timeout=1800)
            env = os.environ.copy()
            env['AGENT_NAME'] = name
            env['AGENT_HEALTH_TIMEOUT'] = '90'
            result = subprocess.run(compose + ['port', name, str(port)], check=True, capture_output=True, text=True, timeout=30)
            env[name.upper().replace('-', '_') + '_URL'] = 'http://' + result.stdout.strip()
            result_code = subprocess.run(
                [sys.executable, '-m', 'pytest', 'tests/agents/test_agent_health.py', '-v',
                 '--junitxml=' + str(artifacts / 'health.xml')], cwd=ROOT, env=env, timeout=120,
            ).returncode
            if name in SUITES:
                # Stop the app before fixtures reset this agent's dedicated test database.
                subprocess.run(compose + ['stop', name], check=True, timeout=60)
                command = compose + ['run', '--rm', '--no-deps', '-T', '--user', '0',
                    '-v', f'{artifacts.as_posix()}:/test-results',
                    '-v', f'{(ROOT / "scripts/run_agent_suite.py").as_posix()}:/test_runner.py:ro']
                for path in SUITES[name]:
                    command += ['-v', f'{(ROOT / context / path).as_posix()}:/app/{path}:ro']
                if name == 'resume-builder-agent':
                    for source, target in [
                        ('agents/resume_builder_agent/.github', '/.github'),
                        ('agents/resume_builder_agent/SECURITY_AUDIT.md', '/SECURITY_AUDIT.md'),
                    ]:
                        command += ['-v', f'{(ROOT / source).as_posix()}:{target}:ro']
                if name == 'mock-interview-agent':
                    # Source-contract tests read the module's React files next to the backend.
                    command += ['-v', f'{(ROOT / "agents/mock_interview_agent/frontend").as_posix()}:/frontend:ro']
                command += ['--entrypoint', 'python', name, '/test_runner.py', *SUITES[name]]
                with (artifacts / 'suite.log').open('w', encoding='utf-8') as log:
                    suite_result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
                suite_output = (artifacts / 'suite.log').read_text(encoding='utf-8')
                output_encoding = sys.stdout.encoding or 'utf-8'
                print(suite_output.encode(output_encoding, errors='replace').decode(output_encoding), flush=True)
                result_code = result_code or suite_result.returncode
            else:
                print(f'{name}: no existing unit/integration suite; health check only.', flush=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            print(f'{name}: {exc}', file=sys.stderr)
            result_code = 1
        finally:
            try:
                with (artifacts / 'startup.log').open('w', encoding='utf-8') as log:
                    subprocess.run(compose + ['logs', '--no-color'], stdout=log, stderr=subprocess.STDOUT, timeout=30)
                cleanup = subprocess.run(compose + ['down', '--volumes', '--remove-orphans'], timeout=60)
                result_code = result_code or cleanup.returncode
            except subprocess.TimeoutExpired:
                print(f'Docker cleanup timed out for {compose[3]}.', file=sys.stderr)
                result_code = 1
        return result_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=['all'] + [a[0] for a in AGENTS], help='Default: all except CodeForge. CI selects each agent explicitly.')
    parser.add_argument('--skip-build', action='store_true', help='Use existing digidara-test images.')
    args = parser.parse_args()
    selected = [a for a in AGENTS if (args.agent == 'all' or a[0] == args.agent or (args.agent is None and a[0] != 'codeforge-agent'))]
    if not shutil.which('docker'):
        print('Install and start Docker Desktop using Linux containers.', file=sys.stderr)
        return 1
    try:
        import pytest
        check = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=20)
    except ImportError:
        print('Install pytest first: python -m pip install "pytest>=8.3,<10"', file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print('Docker is unresponsive. Restart Docker Desktop before retrying.', file=sys.stderr)
        return 1
    if check.returncode:
        print('Docker is unavailable. Start Docker Desktop before retrying.', file=sys.stderr)
        return 1
    results = {}
    for agent in selected:
        print(f'\n=== Testing {agent[0]} ===', flush=True)
        results[agent[0]] = run_agent(agent, args.skip_build)
    print('\nAgent results:', results, flush=True)
    return int(any(results.values()))


if __name__ == '__main__':
    sys.exit(main())
