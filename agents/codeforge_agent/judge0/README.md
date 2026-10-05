# Judge0 (code execution sandbox)

CodeForge and the Capstone agent run learners' code in [Judge0](https://github.com/judge0/judge0).
Production runs the official `judge0/judge0` images; nothing here is built.

This folder keeps only what the deployment uses:

- `docker-compose.yml` — Judge0's server, worker, Postgres and Redis, folded into the root
  `docker-compose.yml` with `include:`. The worker uses our GHCR image with pandas/numpy
  (`../judge0-worker-image`).
- `judge0.conf` — secrets and settings, created on the server only and never committed
  (git-ignored). `scripts/prepare-production-env.sh` keeps the sandbox's network access off.
- `LICENSE` — Judge0's licence.

Judge0's Ruby source used to be vendored here as well. It was never built or run, and its
`Gemfile.lock` raised most of the repository's Dependabot alerts, so it was removed.
