# Local and GitHub agent tests

Run from the repository root with Docker Desktop's Linux engine running:

```powershell
python -m pip install "pytest>=8.3,<10"
npm run test:agents
```

The local default tests orchestrator, capstone, communication, aptitude, resume
builder, and certificate. CodeForge is excluded locally as requested.

Each agent is built and tested sequentially to limit peak Docker resource use.
The runner checks the health API, then runs every existing pytest/unittest suite
for that agent inside a disposable container. MySQL databases are isolated and
end in `_test`; production credentials and databases are not used.
Test containers and database volumes are removed after each agent. Images retain
stable names (`digidara-test/<agent>:local`) for reuse on subsequent runs.

Useful commands:

```powershell
python scripts/test_agents.py --agent aptitude-agent
python scripts/test_agents.py --skip-build
python scripts/test_agents.py --agent all
```

`--skip-build` requires images from a previous successful build. `--agent all`
explicitly includes CodeForge. Results and logs are in
`artifacts/agent-tests/<agent>/health.xml`, `suite.xml`, `suite.log`, and `startup.log`.
A failure in any health check or suite makes the command fail, while other agents
still run. The runner does not silently skip failing suites.

## Current coverage

| Agent | Existing automated checks |
| --- | --- |
| Orchestrator | Health API (no dedicated suite currently present) |
| Capstone | Health API (no dedicated suite currently present) |
| CodeForge | Health API and tests/test_standalone_workflow.py (GitHub by default) |
| Communication | Health API and tests/ |
| Aptitude | Health API, backend/unit_tests/, and backend/tests/ with dedicated MySQL |
| Resume builder | Health API and tests/ |
| Certificate | Health API and tests/ with dedicated MySQL |

These checks do not claim to validate every product feature or live AI provider.

## GitHub Actions

`.github/workflows/ci.yml` runs on every push to `main`, on pull requests, and
manually through Actions. Each of all seven agents, including CodeForge, runs in
its own matrix job using the same Docker runner as local testing. CodeForge's
`CODING_PRACTICE_ENABLED=true` is supplied by that shared runner.

The workflow also runs frontend lint/build, Python syntax validation, Compose
validation, a frontend Docker build, and Selenium checks. Test reports and logs
are uploaded even on failure. No deployment is performed.

Push only after reviewing local results. A workflow exists on GitHub only after
its files have been committed and pushed. A green Actions run must be observed
on GitHub before claiming CI passed. Requiring green checks before merging needs
repository branch protection; this workflow alone does not configure it.
