#!/bin/bash
# One-time (and safe to re-run) hardening of the production server for
# digidaraaiagents.com. Run as root on the server:
#
#     bash /opt/digidara-agents/scripts/server/harden.sh
#
# What it does, each step idempotent:
#   1. Points apt at Ubuntu's official mirror if the configured one is down,
#      so security updates can install again.
#   2. Firewall: only SSH, HTTP, HTTPS (and the aaPanel panel port) inbound.
#      Skipped if aaPanel's firewalld already manages the firewall.
#   3. fail2ban: bans an IP for 1 h after 5 failed SSH logins in 10 min.
#   4. Automatic security updates (unattended-upgrades).
#   5. Daily MySQL backup at 02:30, kept 14 days, in /opt/backups.
#   6. Every .env readable by root only; judge0.conf by the Judge0 user only.
#   7. Lists old backups that contain secrets, for you to delete.
#   8. Confirms the digidaraaiagents.com certificate renews automatically.
#
# It never touches other websites' configs or certificates.
set -uo pipefail

if [ "$(id -u)" -ne 0 ]; then echo "Run as root."; exit 1; fi
APP=/opt/digidara-agents
step() { printf '\n=== %s\n' "$1"; }

step "1. apt mirror"
BROKEN=$(grep -rlE "mirrors\.iitd\.ac\.in" /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null || true)
if [ -n "$BROKEN" ]; then
  for f in $BROKEN; do
    cp -p "$f" "$f.bak-$(date +%Y%m%d)"
    sed -i -E 's#https?://mirrors\.iitd\.ac\.in/ubuntu/?#http://archive.ubuntu.com/ubuntu/#g' "$f"
    echo "switched $f to archive.ubuntu.com (backup: $f.bak-$(date +%Y%m%d))"
  done
else
  echo "no unreachable mirror configured"
fi
apt-get update -qq 2>&1 | grep -E "^(W|E):" || echo "package lists updated"

step "2. Firewall"
PANEL_PORT=$(cat /www/server/panel/data/port.pl 2>/dev/null | tr -dc '0-9' || true)
if systemctl is-active --quiet firewalld; then
  echo "firewalld is active (managed by aaPanel): in aaPanel > Security, allow only 22, 80, 443${PANEL_PORT:+ and $PANEL_PORT}"
else
  apt-get install -y -qq ufw >/dev/null
  ufw default deny incoming >/dev/null
  ufw default allow outgoing >/dev/null
  ufw allow 22/tcp >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  if [ -n "$PANEL_PORT" ]; then ufw allow "${PANEL_PORT}/tcp" >/dev/null; echo "allowed aaPanel port $PANEL_PORT"; fi
  ufw --force enable >/dev/null
  ufw status | sed -n '1,12p'
fi

step "3. fail2ban (SSH brute-force protection)"
apt-get install -y -qq fail2ban >/dev/null
cat > /etc/fail2ban/jail.local <<'JAIL'
[sshd]
enabled  = true
maxretry = 5
findtime = 10m
bantime  = 1h
JAIL
systemctl enable --now fail2ban >/dev/null 2>&1
systemctl restart fail2ban
sleep 2
fail2ban-client status sshd 2>/dev/null | sed -n '1,4p' || echo "fail2ban installed"

step "4. Automatic security updates"
apt-get install -y -qq unattended-upgrades >/dev/null
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'AUTO'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
AUTO
systemctl enable --now unattended-upgrades >/dev/null 2>&1
echo "unattended-upgrades: $(systemctl is-active unattended-upgrades)"

step "5. Daily database backup (02:30, keeps 14 days)"
mkdir -p /opt/backups && chmod 700 /opt/backups
cat > /usr/local/bin/digidara-db-backup <<'BACKUP'
#!/bin/bash
# All MySQL databases of the DigiDARA stack, gzipped, root-only, 14 days kept.
set -euo pipefail
cd /opt/digidara-agents
OUT="/opt/backups/db-$(date +%F).sql.gz"
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --all-databases --single-transaction --quick --routines' </dev/null | gzip > "$OUT"
chmod 600 "$OUT"
find /opt/backups -name 'db-*.sql.gz' -mtime +14 -delete
BACKUP
chmod 700 /usr/local/bin/digidara-db-backup
( crontab -l 2>/dev/null | grep -v digidara-db-backup; echo "30 2 * * * /usr/local/bin/digidara-db-backup >/var/log/digidara-db-backup.log 2>&1" ) | crontab -
if /usr/local/bin/digidara-db-backup; then
  ls -lh /opt/backups/db-*.sql.gz | tail -1
else
  echo "!! first backup failed - check: docker compose ps mysql"
fi
echo "Copy /opt/backups off this server regularly (another machine or cloud storage)."

step "6. Secret files readable by root only"
find "$APP" -maxdepth 6 \( -name ".env" -o -name ".env.bak-*" \) -type f -exec chmod 600 {} \; -print | sed 's/^/600 /'
# judge0.conf is bind-mounted into the Judge0 containers, which run as uid
# 1000 (gid 999). Root-only 600 makes it unreadable there: Judge0 falls back
# to localhost for Postgres and Redis and crash-loops. Owned by that uid it
# stays 600 -- private to everyone else on the host.
find "$APP" -maxdepth 6 -name "judge0.conf" -type f -exec chown 1000:999 {} \; -exec chmod 600 {} \; -print | sed 's/^/600 (uid 1000) /'

step "7. Old backups that contain secrets (delete once the site works)"
find /opt /root -maxdepth 3 \( -name "*.tar.gz" -o -name ".env.bak-*" \) -type f 2>/dev/null | grep -v '^/opt/backups/' || echo "none found"

step "8. digidaraaiagents.com certificate auto-renewal"
systemctl enable --now certbot.timer >/dev/null 2>&1 || true
systemctl list-timers 2>/dev/null | grep -i certbot || echo "certbot timer not found"
certbot certificates --cert-name digidaraaiagents.com 2>/dev/null | grep -E "Expiry" || echo "certificate not managed by certbot"

step "Done"
[ -f /var/run/reboot-required ] && echo "A reboot is pending for installed updates: run 'reboot' at a quiet time."
echo "Before closing this SSH session, open a NEW one to confirm you can still log in."
