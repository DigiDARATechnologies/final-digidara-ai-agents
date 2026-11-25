---
title: Docker, CI/CD and deployment questions
summary: Containers versus virtual machines, images, Dockerfiles, CI versus CD, pipelines and basic Kubernetes ideas.
kind: qa
takeaways:
- Explain containers, images and a simple Dockerfile
- Describe CI and CD and a typical pipeline
- Know the basic purpose of Kubernetes
---
### Q [Easy] What is Docker?
A tool that packages an application with everything it needs (code, libraries, runtime) into a **container**, so it runs the same on any machine.

### Q [Easy] Container vs virtual machine?
A **VM** includes a full operating system and is heavy and slow to start. A **container** shares the host's kernel, is lightweight, starts in seconds and uses less memory.

### Q [Medium] Image vs container?
An **image** is a read-only template (the recipe). A **container** is a running instance of an image.

### Q [Medium] What is a Dockerfile? Show a simple one.
A text file of instructions to build an image.
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```
Order matters: copy `requirements.txt` first so the dependency layer is **cached** when only your code changes.

### Q [Medium] What is Docker Compose?
A tool that defines and runs **multi-container** applications (app, database, cache) from one `docker-compose.yml` file with a single command.

### Q [Medium] How do you persist data in Docker?
Containers are temporary; their data disappears when removed. Use **volumes** (or bind mounts) to store data outside the container, such as a database folder.

### Q [Medium] What is CI/CD?
**Continuous Integration**: every code change is automatically built and tested. **Continuous Delivery**: tested code is always ready to release. **Continuous Deployment**: every passing change is released automatically.

### Q [Medium] Describe a typical CI/CD pipeline.
Commit and push, then **build**, **lint and test**, **security checks**, build a Docker image, push it to a registry, **deploy** to staging, run checks, then deploy to production. Tools: GitHub Actions, Jenkins, GitLab CI.

### Q [Medium] How should secrets be handled in pipelines?
Store them in the CI system's **secret store** or a secrets manager, inject them as environment variables at run time, never commit them, and rotate them if exposed.

### Q [Medium] What are blue-green and rolling deployments?
**Blue-green**: run two environments, switch traffic from the old (blue) to the new (green) at once, and switch back if something fails. **Rolling**: replace instances gradually so there is no downtime.

### Q [Medium] What is Kubernetes?
A system that runs and manages many containers across many machines: it schedules them, restarts failed ones, scales up or down and balances traffic. Core ideas: **Pod** (one or more containers), **Deployment** (desired number of pods), **Service** (stable network address).

### Q [Hard] What is Infrastructure as Code?
Defining servers and networks in files (Terraform, CloudFormation) that are versioned and reviewed like code, so environments are repeatable and changes are tracked.

### Q [Medium] What is a health check and why is it important?
An endpoint or command the platform calls to see whether the app is alive and ready (`/health`). It lets load balancers and orchestrators stop sending traffic to, or restart, unhealthy instances.

### Q [Hard] How do you roll back a bad deployment?
Keep previous versions available (image tags), deploy through a pipeline that can redeploy the last good version quickly, use blue-green or rolling updates, and watch metrics and logs after each release.
