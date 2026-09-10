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
| Orchestrator | Health API and tests/ (registry signatures, lifecycle, gateway authentication, forwarding and billing) |
| Capstone | Health API and tests/ (topics, upload validation, evaluation persistence, timers and viva) |
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

Direct orchestrator, capstone, communication and resume pytest runs default to disposable SQLite databases. The Docker runner sets INTEGRATION_DATABASE_URL to its isolated MySQL database so these suites exercise real MySQL reads/writes, authentication and workflow persistence. Fixtures reject non-MySQL URLs and database names without the _test suffix before resetting tables. CodeForge also tests its real MySqlRepository registration, sessions and request nonces. Aptitude and certificate retain their existing MySQL integration coverage. Capstone checkpoints remain in memory; AI and remote-agent responses are controlled fixtures. These checks do not measure live AI answer quality.

## CI quality and security layers

- Python: Ruff catches syntax, undefined-name and invalid-control-flow errors across agent code, scripts and tests (E9, F63, F7, F82). This is an initial correctness lint policy, not a repository-wide style rewrite.
- Python types: mypy checks annotated code and untyped function bodies in the CI runners and capstone entry-point detection. Other backend modules are not yet covered by mypy; this is an incremental adoption scope.
- Python unit layer: tests/unit runs independently of Docker and databases. Aptitude's existing backend/unit_tests runs separately from backend/tests in Docker, with unit.xml and integration.xml reports.
- Frontend: Jest exercises agent selection and aptitude flow transitions, including duplicate-answer prevention after network failure. npm run typecheck checks application and test TypeScript; npm run test:ci saves coverage under artifacts/frontend-coverage. Coverage describes tested modules, not the entire UI.
- Caching: setup-python caches pip downloads using requirements-file hashes. Docker buildx caches dependency/image layers per agent in GitHub Actions; changed requirements invalidate the dependency layer. npm caching remains enabled.
- Security: npm audit fails on high/critical findings; pip-audit checks exact installed dependencies exported from each built agent image and fails on any known vulnerability. Trivy scans all seven agent images and the frontend runtime image for high/critical vulnerabilities, including unfixed findings. JSON reports upload even on failure. Two findings are explicitly ignored via `--ignore-vuln` because pip-audit itself reports no available fix version for either: `PYSEC-2025-183` (PyJWT) and `PYSEC-2026-1325` (ecdsa, a transitive dependency). No other vulnerabilities are suppressed and no scan uses continue-on-error; re-check these two periodically and remove the ignore once upstream ships a fix.
- Failures stop subsequent normal steps within a job. Matrices intentionally keep fail-fast: false so all agents and browsers report results; a failed matrix job still fails CI. Security/report steps explicitly run after test failures when the image was built.

Local quality commands (no Docker needed):

```powershell
python -m pip install -r requirements-quality.txt
python -m ruff check agents scripts tests
python -m mypy
python -m pytest tests/unit -v
npm ci
npm run lint
npm run typecheck
npm run test:ci
npm run build
npm audit --audit-level=high
```

Database integration: start Docker Desktop and run python scripts/test_agents.py (six agents locally by default), or add --agent all to include CodeForge. Never manually set INTEGRATION_DATABASE_URL to an existing development database: fixtures reset tables. The runner creates and removes its own test database containers.

Security findings are actionable failures, not evidence that the scan is broken. Upgrade the reported package/base image and rerun the affected suites; unresolved findings must remain visible in the PR.

## Branches, publishing and deployment gate

- `main` and `develop` are protected: PR review plus these required checks
  before merge (see repository branch protection settings for the current
  list).
- On push to `main`, once quality/build/test jobs pass, `publish-ghcr` and
  `publish-ghcr-frontend` push per-agent and frontend images to
  `ghcr.io/<owner>/digidara-*`, tagged with the commit SHA and `latest`.
- `deploy-approval` then gates on the `production` GitHub Environment,
  which requires manual reviewer approval before the job runs.
- `notify-failure` posts to Slack (via the `SLACK_WEBHOOK_URL` secret) when
  any job on a `main` push fails; it no-ops if the secret isn't set.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full branch model and pipeline
details.
