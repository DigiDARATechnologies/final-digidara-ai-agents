from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("agent_runner", ROOT / "scripts/test_agents.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

def test_all_agents_have_dedicated_suites():
    assert len(runner.AGENTS) == 8
    assert {agent[0] for agent in runner.AGENTS} == set(runner.SUITES)
    for name, context, *_ in runner.AGENTS:
        assert all((ROOT / context / suite).is_dir() for suite in runner.SUITES[name])

def test_database_isolation_and_codegen_feature_setting(tmp_path):
    config = runner.compose_config(tmp_path / "init.sql")
    databases = set()
    for name, *_ in runner.AGENTS:
        service = config['services'][name]
        env = service['environment']
        assert env['DATABASE_URL'] == env['TEST_DATABASE_URL'] == env['INTEGRATION_DATABASE_URL']
        assert env['DB_NAME'].endswith('_test')
        databases.add(env['DB_NAME'])
        assert service['ports'][0].startswith('127.0.0.1::')
        assert env['CODING_PRACTICE_ENABLED'] == 'true'
    assert len(databases) == 8

def test_single_agent_configuration_does_not_start_other_agents(tmp_path):
    config = runner.compose_config(tmp_path / "init.sql", [runner.AGENTS[0]])
    assert set(config['services']) == {'mysql', 'orchestrator'}
