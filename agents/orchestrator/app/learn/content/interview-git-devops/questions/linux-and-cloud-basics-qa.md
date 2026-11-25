---
title: Linux and cloud basics questions
summary: Common Linux commands, file permissions, processes, SSH, and cloud ideas such as IaaS, PaaS, SaaS, regions and scaling.
kind: qa
takeaways:
- Use the everyday Linux commands confidently
- Read and set file permissions with chmod
- Explain IaaS, PaaS and SaaS and basic cloud services
---
### Q [Easy] Name common Linux commands.
`ls` (list), `cd` (change directory), `pwd` (current directory), `mkdir`, `rm`, `cp`, `mv`, `cat` (show a file), `grep` (search text), `find`, `chmod` (permissions), `ps` and `top` (processes), `df` and `du` (disk), `tail -f` (follow a log).

### Q [Medium] Explain file permissions such as `rwxr-xr--`.
Three groups: **owner**, **group**, **others**. Each has read (r = 4), write (w = 2) and execute (x = 1). `rwxr-xr--` means owner 7 (rwx), group 5 (r-x), others 4 (r--), so `chmod 754 file`.

### Q [Medium] What does `chmod +x script.sh` do?
Makes the file executable so you can run it with `./script.sh`.

### Q [Medium] How do you find a text in files and count lines?
```bash
grep -rn "ERROR" /var/log/app/        # search recursively, show line numbers
grep "ERROR" app.log | wc -l          # count matching lines
```

### Q [Medium] What are pipes and redirection?
A **pipe** (`|`) sends one command's output to another: `cat app.log | grep ERROR`. **Redirection** sends output to a file (`>` overwrite, `>>` append) or reads input from a file (`<`).

### Q [Medium] How do you see running processes and stop one?
`ps aux` or `top` shows processes. Stop with `kill <pid>` (polite) or `kill -9 <pid>` (force). Use `systemctl` to manage services.

### Q [Medium] What is SSH?
Secure Shell: an encrypted way to log in to and run commands on a remote machine, usually with a key pair instead of a password: `ssh user@server`.

### Q [Medium] Absolute vs relative path?
An **absolute** path starts from the root (`/home/asha/app/main.py`). A **relative** path starts from the current directory (`app/main.py`).

### Q [Medium] What is an environment variable?
A named value available to programs (`DATABASE_URL`). Used for configuration and secrets so they stay out of the code: `export DATABASE_URL=...`.

### Q [Easy] What is cloud computing?
Renting computing resources (servers, storage, databases) over the internet and paying for what you use, instead of owning hardware.

### Q [Medium] IaaS vs PaaS vs SaaS?
**IaaS**: raw infrastructure (virtual machines such as EC2). **PaaS**: a platform where you deploy code without managing servers (Heroku, Elastic Beanstalk, App Service). **SaaS**: finished software you just use (Gmail, Office 365).

### Q [Medium] What are regions and availability zones?
A **region** is a geographic area with cloud data centres. An **availability zone** is one or more separate data centres inside a region. Spreading across zones keeps your app available if one fails.

### Q [Medium] Name the main services of a cloud provider (AWS examples).
Compute: **EC2**, **Lambda** (serverless functions). Storage: **S3** (object storage). Database: **RDS**, **DynamoDB**. Networking: **VPC**, **Route 53** (DNS), **ELB** (load balancer). Identity: **IAM**.

### Q [Medium] What is auto scaling?
Automatically adding or removing servers based on load (such as CPU or requests), so you handle traffic spikes and pay less when it is quiet.

### Q [Medium] What is serverless?
You write functions and the provider runs them on demand, scaling automatically, and you pay per use without managing servers (AWS Lambda). It suits short, event-driven tasks.

### Q [Hard] Explain the principle of least privilege in the cloud.
Give each user, role or service only the permissions it needs. For example, an app that only reads a bucket should not be allowed to delete it. This limits the damage from mistakes or stolen credentials.
