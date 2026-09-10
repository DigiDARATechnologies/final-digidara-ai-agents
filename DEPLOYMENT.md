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

### Automatic deploy

`deploy` runs after both publish jobs succeed, on every push to `main`, with
no manual approval step — it SSHes into the deploy host and runs
`/opt/digidara-agents/deploy.sh`, via `appleboy/ssh-action`. There is
deliberately no `production` Environment gate here: GitHub's required-reviewer
protection needs Team/Enterprise for a private repo, and this org is on Free,
so an approval gate would have been permanently inert anyway.

This step needs three repo secrets:

- `DEPLOY_HOST` — the server's hostname/IP
- `DEPLOY_USER` — the SSH user `deploy.sh` runs as
- `DEPLOY_SSH_KEY` — private key for that user, authorized on the server

`deploy.sh` itself lives on the server, not in this repo — it's expected to
already pull the freshly published `:latest` (or `:<sha>`) images and
restart the Compose stack. It requires `/opt/digidara-agents` to be an actual
git clone of this repo (`git init` + `git remote add origin` + a fetch/reset
against `main`) since `deploy.sh` itself runs `git fetch`/`git reset --hard`
— if that directory was ever set up by copying files instead of `git clone`,
the deploy step fails with `fatal: not a git repository`.

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
- `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` Actions secrets — required
  for `deploy`'s SSH step; the job fails without them.
- The `SLACK_WEBHOOK_URL` Actions secret (optional — notifications no-op
  without it).

Every push to `main` deploys automatically once images are published to
GHCR — there is no human approval step in between. Treat merges to `main`
accordingly: they go live.
