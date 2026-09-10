# Deployment

## Branch model

- `develop` is the integration branch for day-to-day feature work. Feature
  branches are cut from `develop` and merged back into it via PR.
- `main` is the release branch. `develop` is merged (or a release branch is
  cut from it) into `main` when a set of changes is ready to ship.
- Both `main` and `develop` are protected: direct pushes are blocked, at
  least one PR review is required, and the required CI checks below must be
  green before a PR can merge.

## CI/CD pipeline

`.github/workflows/ci.yml` runs on every push to `main`/`develop`, on pull
requests, and manually via `workflow_dispatch`. See
[CI_CD_SETUP.md](CI_CD_SETUP.md) for the full breakdown of the quality, unit
test, MySQL integration and security layers.

### Image publishing (GHCR)

On push to `main` only, once `docker-build`, `frontend-docker`,
`python-quality` and `frontend` all pass, two jobs build and push images to
GitHub Container Registry using the built-in `GITHUB_TOKEN`:

- `publish-ghcr` — one image per agent (`orchestrator`, `capstone-agent`,
  `codeforge-agent`, `communication-agent`, `aptitude-agent`,
  `resume-builder-agent`, `certificate-agent`), tagged
  `ghcr.io/<owner>/digidara-<agent>:<commit-sha>` and `:latest`.
- `publish-ghcr-frontend` — the frontend runtime image, tagged
  `ghcr.io/<owner>/digidara-frontend:<commit-sha>` and `:latest`.

Images are not pushed for PRs, `develop`, or manual dispatch runs on other
branches — only for commits that land on `main`.

### Manual approval before production

`deploy-approval` runs after both publish jobs succeed and targets the
`production` GitHub Environment, which requires a reviewer to approve the
run before it proceeds (configured under **Settings → Environments →
production** in the repository — note: required reviewers on environments
need GitHub Team/Enterprise for a private repo; this org is currently on
Free, so the environment exists but has no reviewer gate until upgraded).
After recording which images were approved, it SSHes into the deploy host
and runs `/opt/digidara-agents/deploy.sh`, via `appleboy/ssh-action`.

This step needs three repo secrets that do **not exist yet**
(`gh secret list` is currently empty) — the job will fail on `Deploy via
SSH` until they're added under **Settings → Secrets and variables →
Actions**:

- `DEPLOY_HOST` — the server's hostname/IP
- `DEPLOY_USER` — the SSH user `deploy.sh` runs as
- `DEPLOY_SSH_KEY` — private key for that user, authorized on the server

`deploy.sh` itself lives on the server, not in this repo — it's expected to
already pull the freshly published `:latest` (or `:<sha>`) images and
restart the Compose stack.

### Failure notifications

`notify-failure` runs after every job on a `main` push completes. If any of
them failed, it posts a message to Slack via the `SLACK_WEBHOOK_URL` repo
secret. The step is a no-op (does not fail the run) if that secret isn't
set, so the workflow is safe to use before the secret is configured.

To enable it: create a Slack Incoming Webhook and add its URL as the
`SLACK_WEBHOOK_URL` secret under **Settings → Secrets and variables →
Actions**.

## Required repository configuration

These are GitHub repository/organization settings, not code, and are not
recreated automatically if changed or removed:

- Branch protection on `main` and `develop` (PR review + required status
  checks).
- The `production` Environment with a required reviewer (needs a plan
  upgrade first, see above).
- `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` Actions secrets — required
  for `deploy-approval`'s SSH step; the job fails without them.
- The `SLACK_WEBHOOK_URL` Actions secret (optional — notifications no-op
  without it).

`deploy-approval` now actually deploys: on every push to `main`, once
images are published to GHCR, it SSHes into the configured host and runs
`deploy.sh`. Until the `production` Environment has a required reviewer
(blocked on the plan upgrade), this happens automatically with no human
approval step in between — treat merges to `main` accordingly.
