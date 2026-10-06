#!/bin/bash
# Rotate the platform secrets that touch every service, together:
#   - MySQL root password (in docker/mysql/.env and every agent .env that has it)
#   - orchestrator JWT_SECRET (everyone has to log in again)
#   - AGENT_SHARED_SECRET (identical in the orchestrator and every agent)
#
#     bash /opt/digidara-agents/scripts/server/rotate-secrets.sh          # dry run: only reports
#     bash /opt/digidara-agents/scripts/server/rotate-secrets.sh apply    # does it
#
# apply backs up the database and every .env first, prints the rollback
# command, and ends with a health check of the site and all agents. New
# values are random hex, so they are safe in URLs and .env files. Secret
# values are never printed.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then echo "Run as root."; exit 1; fi
cd /opt/digidara-agents
MODE="${1:-dry-run}"
STAMP=$(date +%Y%m%d-%H%M%S)
mapfile -t ENVS < <(find agents docker -name .env -type f | sort)

python3 - "${ENVS[@]}" <<'PY'
import sys, pathlib
files = sys.argv[1:]
def val(path, key):
    for line in pathlib.Path(path).read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
old_db = val("docker/mysql/.env", "MYSQL_ROOT_PASSWORD") or ""
if len(old_db) < 8:
    sys.exit("The current MySQL root password is shorter than 8 characters; it can't be replaced safely by search. Stopping.")
text = {f: pathlib.Path(f).read_text() for f in files}
print("MySQL root password is used in:")
for f in files:
    if old_db in text[f]:
        print("   ", f)
print("AGENT_SHARED_SECRET is set in:")
for f in files:
    if val(f, "AGENT_SHARED_SECRET") is not None:
        print("   ", f)
shared = {val(f, "AGENT_SHARED_SECRET") for f in files if val(f, "AGENT_SHARED_SECRET") is not None}
if len(shared) > 1:
    print("NOTE: AGENT_SHARED_SECRET currently differs between files; apply makes them all the same.")
missing = [f for f in files
           if any(k in text[f] for k in ("DATABASE_URL=mysql", "DB_PASSWORD=", "MYSQL_PASSWORD="))
           and old_db not in text[f]]
for f in missing:
    print("WARNING: has database settings but NOT the current root password (check by hand):", f)
PY

if [ "$MODE" != "apply" ]; then
  echo
  echo "Dry run only - nothing changed. If the lists above look right, run:"
  echo "  bash /opt/digidara-agents/scripts/server/rotate-secrets.sh apply"
  exit 0
fi

echo "=== Backups"
mkdir -p /opt/backups && chmod 700 /opt/backups
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --all-databases --single-transaction --quick --routines' </dev/null \
  | gzip > "/opt/backups/pre-rotate-$STAMP.sql.gz"
tar -czf "/opt/backups/env-pre-rotate-$STAMP.tgz" "${ENVS[@]}"
chmod 600 "/opt/backups/pre-rotate-$STAMP.sql.gz" "/opt/backups/env-pre-rotate-$STAMP.tgz"
echo "saved /opt/backups/pre-rotate-$STAMP.sql.gz and /opt/backups/env-pre-rotate-$STAMP.tgz"

OLD_DB=$(grep -E '^MYSQL_ROOT_PASSWORD=' docker/mysql/.env | head -1 | cut -d= -f2-)
NEW_DB=$(openssl rand -hex 24)
NEW_JWT=$(openssl rand -hex 32)
NEW_SHARED=$(openssl rand -hex 32)

echo "=== 1. MySQL root password"
# A ready-to-run undo, root-only next to the backups (it holds both passwords).
ROLLBACK="/opt/backups/rollback-$STAMP.sh"
cat > "$ROLLBACK" <<RB
#!/bin/bash
# Undo rotate-secrets.sh run $STAMP: old .env files and the old MySQL root password.
set -e
cd /opt/digidara-agents
tar -xzf /opt/backups/env-pre-rotate-$STAMP.tgz
docker compose exec -T mysql sh -c "MYSQL_PWD='$NEW_DB' mysql -uroot -e \"ALTER USER IF EXISTS 'root'@'%' IDENTIFIED BY '$OLD_DB'; ALTER USER IF EXISTS 'root'@'localhost' IDENTIFIED BY '$OLD_DB'; FLUSH PRIVILEGES;\"" </dev/null
docker compose up -d --force-recreate --wait --wait-timeout 120 mysql
docker compose up -d --force-recreate
echo "rolled back to the secrets from before $STAMP"
RB
chmod 700 "$ROLLBACK"
docker compose exec -T mysql sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot -e \"ALTER USER IF EXISTS 'root'@'%' IDENTIFIED BY '$NEW_DB'; ALTER USER IF EXISTS 'root'@'localhost' IDENTIFIED BY '$NEW_DB'; FLUSH PRIVILEGES;\"" </dev/null
echo "changed in MySQL"

echo "=== 2. Every .env"
python3 - "$NEW_DB" "$NEW_JWT" "$NEW_SHARED" "${ENVS[@]}" <<'PY'
import sys, pathlib
new_db, new_jwt, new_shared, files = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
def val(path, key):
    for line in pathlib.Path(path).read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
old_db = val("docker/mysql/.env", "MYSQL_ROOT_PASSWORD")
for f in files:
    p = pathlib.Path(f)
    before = p.read_text()
    lines = before.replace(old_db, new_db).splitlines()
    for i, line in enumerate(lines):
        if line.startswith("AGENT_SHARED_SECRET="):
            lines[i] = "AGENT_SHARED_SECRET=" + new_shared
        if f.endswith("orchestrator/.env") and line.startswith("JWT_SECRET="):
            lines[i] = "JWT_SECRET=" + new_jwt
    after = "\n".join(lines) + "\n"
    if after != before:
        p.write_text(after)
        print("updated", f)
PY

echo "=== 3. Restart: MySQL first, then every service"
docker compose up -d --force-recreate --wait --wait-timeout 120 mysql
docker compose up -d --force-recreate --wait --wait-timeout 240 || echo "!! some containers are not healthy yet - see the checks below"

echo "=== 4. Health"
sleep 10
printf "auth/me (expect 401): "; curl -s -o /dev/null -w "%{http_code}\n" https://digidaraaiagents.com/auth/me
for a in aptitude_agent mock_interview_agent capstone_project_agent communication_agent resume_builder_agent certificate_agent job_agent codeforge_agent; do
  printf "%-24s " "$a"
  curl -s -m 20 -X POST -H "Content-Type: application/json" -d '{"action":"health"}' \
    "https://digidaraaiagents.com/gateway/agents/$a/invoke" | tr -d '\n ' | cut -c1-60
  echo
done
echo
echo "Done. Everyone has to log in again (new JWT_SECRET)."
echo "If anything is wrong, undo everything with:"
echo "  bash $ROLLBACK"
