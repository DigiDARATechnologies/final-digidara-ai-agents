# Env default changes

One line per change to the **code default** (or clamp) of an existing environment variable.
Why this exists: a key that is uncommented in a server's real `.env` keeps overriding a new
code default, so the change silently does nothing until someone edits that file.
Add a line in the same PR that changes the default, and say what to do on the server.

Check for drift any time: `python scripts/check_env_drift.py --code` (names only, never values).

| Key | Service | Old default | New default | PR | Server action |
|---|---|---|---|---|---|
| `BATCH_GENERATION_MAX_ATTEMPTS` | aptitude | 2 | 3 | #63 | If `.env` sets it, change it to 3 (or delete the line), then `docker compose up -d aptitude-agent` |
| `DB_POOL_SIZE` (clamped to max 4) | job-agent | 10 | 4 | #66 | None; values above 4 are now clamped. Set to 4 in `.env` to match |
| `DB_POOL_SIZE` (clamped to max 4) | mock-interview | 10 | 4 | earlier mock-interview fix | None; values above 4 are now clamped |
| `AGENT_SIGNATURE_MODE` (new) | all 8 agents | n/a | `warn` | this PR | None. Optional. Flip an agent to `enforce` only after `docker compose logs --since 24h <service> \| grep -c gateway_signature_invalid` prints 0 |
