#!/bin/bash
# The certificate agent emails certificates with its own SMTP settings. When they
# are out of date Gmail refuses them. This copies the orchestrator's working
# settings across, keeps a backup, restarts the agent, and tests the login.
# Nothing is printed except the result. Run once on each server, as root:
#   bash scripts/server/sync-certificate-smtp.sh
set -euo pipefail
cd /opt/digidara-agents
SOURCE=agents/orchestrator/.env
TARGET=agents/certificate_agent/.env
value() { grep -E "^$1=" "$SOURCE" | tail -1 | cut -d= -f2- || true; }
HOST=$(value SMTP_HOST); PORT=$(value SMTP_PORT); USER_NAME=$(value SMTP_USER); PASSWORD=$(value SMTP_PASSWORD); FROM=$(value SMTP_FROM)
if [ -z "$HOST" ] || [ -z "$USER_NAME" ] || [ -z "$PASSWORD" ]; then
  echo "The orchestrator has no SMTP settings in $SOURCE, so nothing was changed."
  exit 1
fi
cp -p "$TARGET" "$TARGET.bak-$(date +%Y%m%d%H%M%S)"
sed -i -E '/^SMTP_(HOST|PORT|USERNAME|USER|PASSWORD|FROM|USE_TLS)=/d' "$TARGET"
{
  echo "SMTP_HOST=$HOST"
  echo "SMTP_PORT=${PORT:-587}"
  echo "SMTP_USERNAME=$USER_NAME"
  echo "SMTP_PASSWORD=$PASSWORD"
  echo "SMTP_FROM=${FROM:-$USER_NAME}"
  echo "SMTP_USE_TLS=True"
} >> "$TARGET"
docker compose up -d --wait --wait-timeout 180 certificate-agent
docker compose exec -T certificate-agent python - <<'PY'
import os, smtplib, ssl
host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
password = "".join(os.environ["SMTP_PASSWORD"].strip().strip("\"'").split())
context = ssl.create_default_context()
smtp = smtplib.SMTP_SSL(host, port, timeout=25, context=context) if port == 465 else smtplib.SMTP(host, port, timeout=25)
try:
    if port != 465:
        smtp.starttls(context=context)
    smtp.login(os.environ["SMTP_USERNAME"], password)
    print("Certificate email login works.")
except Exception as error:
    print(f"Certificate email login FAILED: {type(error).__name__}")
    raise SystemExit(1)
finally:
    try:
        smtp.quit()
    except Exception:
        pass
PY
