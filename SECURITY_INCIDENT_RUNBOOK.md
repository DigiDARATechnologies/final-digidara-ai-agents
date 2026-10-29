# Security incident runbook (SkillDARA)

Indian law (CERT-In Directions, 28 April 2022) requires reporting certain cyber
incidents to CERT-In **within 6 hours of noticing them**. If personal data is
involved, the DPDP Act 2023 also requires informing the Data Protection Board
and the affected users. This page is what to do, in order.

**Incident owner:** _(name, phone)_ · **Backup:** _(name, phone)_ — fill these in.

## What counts as an incident (report it)

- Someone got into a server, the database, an admin account or a GitHub/Razorpay/OpenAI account
- Student or payment data leaked, was changed or deleted
- The site was defaced, or serves something we did not put there
- A secret key was exposed (in code, a screenshot, a chat)
- Ransomware or malware on a server
- A denial-of-service attack that takes the site down
- Unusual scanning or probing of our servers that keeps going

Not sure? Treat it as an incident. Reporting something minor costs nothing.

## Hour 0–1: contain

1. Note the time you noticed it. Every later step is measured from this.
2. Do not delete anything. Logs are evidence (kept 180 days: `journalctl`, `docker compose logs`).
3. Rotate every secret that could be affected: `bash /opt/digidara-agents/scripts/server/rotate-secrets.sh`,
   plus the Razorpay, OpenAI and SMTP keys in their dashboards.
4. If an account is compromised: change its password, sign out all sessions, turn on 2-factor login.
5. If a server is compromised: take a snapshot in the hosting panel first, then cut access (firewall),
   then restore from the last good backup on a clean server.

## Hour 1–6: report

6. **CERT-In:** email **incident@cert-in.org.in** using the form at
   <https://www.cert-in.org.in> (Incident Reporting). Include: time noticed, what happened,
   systems affected, what you have done so far. Missing details can follow later.
7. If personal data is involved, prepare the DPDP notice to the Data Protection Board and
   to affected users (what happened, what data, what we are doing, what they should do).

## After

8. Write down: timeline, cause, what data was affected, what changed so it cannot happen again.
9. Keep this record and the related logs for at least 180 days.

## Useful commands (production server)

```bash
cd /opt/digidara-agents
docker compose ps                                   # what is running
docker compose logs --since 2h orchestrator         # recent app logs
journalctl CONTAINER_NAME=<container> --since "2026-10-01"   # older container logs
last -n 30; journalctl -u ssh --since today         # who logged in
fail2ban-client status sshd                         # blocked SSH attackers
ls -lh /opt/backups                                 # database backups
```
