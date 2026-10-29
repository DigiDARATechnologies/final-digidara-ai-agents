#!/bin/bash
# One-time (and safe to re-run) hardening of the production server for
# skilldara.com. Run as root on the server:
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
#   8. Confirms the skilldara.com certificate renews automatically.
#   9. Clock synced to India's NIC / NPL time servers (CERT-In).
#  10. Logs kept 180 days in the system journal, Docker logs included (CERT-In).
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
# All MySQL databases of the SkillDARA stack, gzipped, root-only, 14 days kept.
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

step "8. skilldara.com certificate auto-renewal"
systemctl enable --now certbot.timer >/dev/null 2>&1 || true
systemctl list-timers 2>/dev/null | grep -i certbot || echo "certbot timer not found"
certbot certificates --cert-name skilldara.com 2>/dev/null | grep -E "Expiry" || echo "certificate not managed by certbot"

step "9. Clock sync (CERT-In: sync with NIC / NPL time servers)"
mkdir -p /etc/systemd/timesyncd.conf.d
cat > /etc/systemd/timesyncd.conf.d/skilldara.conf <<'NTP'
[Time]
NTP=time.nplindia.org samay1.nic.in samay2.nic.in
FallbackNTP=ntp.ubuntu.com
NTP
if systemctl list-unit-files 2>/dev/null | grep -q '^systemd-timesyncd'; then
  timedatectl set-ntp true 2>/dev/null || true
  systemctl restart systemd-timesyncd 2>/dev/null || true
  sleep 2
  timedatectl 2>/dev/null | grep -E "synchronized|NTP service" || true
else
  echo "systemd-timesyncd is not installed here (chrony or ntpd may manage time): check that time.nplindia.org is configured"
fi

step "10. Keep logs for 180 days (CERT-In)"
# The system journal keeps 180 days, compressed, up to 8 GB on disk. Docker
# logs go to the journal too (see below), so they survive deploys: with the
# default json-file driver a container's log is deleted when the container
# is replaced, i.e. on every deploy.
mkdir -p /etc/systemd/journald.conf.d /var/log/journal
cat > /etc/systemd/journald.conf.d/skilldara.conf <<'JOURNAL'
[Journal]
Storage=persistent
Compress=yes
MaxRetentionSec=180day
SystemMaxUse=8G
# Busy hours produce many lines a second; never drop them.
RateLimitIntervalSec=0
JOURNAL
systemctl restart systemd-journald
journalctl --disk-usage 2>/dev/null || true
df -h / | tail -1 | awk '{print "disk free on /: " $4}'
if [ ! -s /etc/docker/daemon.json ]; then
  echo '{ "log-driver": "journald", "log-opts": { "tag": "{{.Name}}" } }' > /etc/docker/daemon.json
  echo "Docker will log to the journal. It takes effect after a Docker restart (about 1 minute of downtime):"
  echo "    at a quiet time:  systemctl restart docker && cd $APP && docker compose up -d --force-recreate"
elif grep -q '"log-driver"' /etc/docker/daemon.json; then
  echo "Docker log driver already set: $(grep -o '"log-driver"[^,}]*' /etc/docker/daemon.json)"
else
  echo "!! /etc/docker/daemon.json has other settings: add  \"log-driver\": \"journald\"  to it by hand, then restart Docker at a quiet time."
fi
echo "Read logs: docker compose logs <service>   or   journalctl CONTAINER_NAME=<container> --since '2026-10-01'"

step "Done"
[ -f /var/run/reboot-required ] && echo "A reboot is pending for installed updates: run 'reboot' at a quiet time."
echo "Before closing this SSH session, open a NEW one to confirm you can still log in."
