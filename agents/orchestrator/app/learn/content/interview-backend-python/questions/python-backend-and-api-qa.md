---
title: Python backend and API questions
summary: Virtual environments, async, FastAPI, caching, queues, testing and designing a small backend.
kind: qa
takeaways:
- Explain virtual environments, dependencies and configuration
- Know when async and background jobs help
- Describe how you would test and structure a backend
---
### Q [Easy] Why use a virtual environment?
It isolates a project's packages and versions from other projects and from the system Python, avoiding conflicts. Record dependencies in `requirements.txt`.

### Q [Medium] How do you manage configuration and secrets?
Keep them out of the code and Git: use **environment variables** or a secrets manager, a `.env` file for local development (git-ignored), and different settings for development and production.

### Q [Medium] What is FastAPI and why is it popular?
A modern Python framework for APIs built on type hints. It validates input with **Pydantic**, generates interactive documentation automatically and supports async, with high performance.

### Q [Medium] Sync vs async in Python web apps?
Async (`async def`, `await`) lets one process handle many **waiting** (I/O) tasks, such as calling APIs or databases, without blocking. It does not speed up CPU-heavy work, which needs processes or workers.

### Q [Medium] What is the GIL?
The Global Interpreter Lock lets only one thread run Python bytecode at a time in CPython. Threads still help with I/O waiting; for CPU-bound work use multiprocessing or native extensions.

### Q [Medium] What is a background job queue and when do you use one?
A system (Celery with Redis or RabbitMQ) that runs slow tasks outside the web request: sending emails, generating reports, calling LLMs. The web request returns quickly and the worker does the job.

### Q [Medium] What is caching and where can you cache?
Storing results to avoid repeated work. Options: in memory (`functools.lru_cache`), **Redis** for shared caching, HTTP caching with headers and a CDN. Always decide how entries expire.

### Q [Medium] What is an ORM and its trade-offs?
It maps database tables to classes (SQLAlchemy, Django ORM). It speeds development and prevents SQL injection, but can hide inefficient queries (N+1), so check the generated SQL for important paths.

### Q [Medium] What is the N+1 query problem?
Running one query for a list and then one extra query for each item (1 + N queries). Fix by loading related data in advance (joins or eager loading).

### Q [Medium] How do you test a backend?
**Unit tests** for functions, **integration tests** for endpoints with a test database, and mocks for external services. Tools: `pytest`, a test client. Run them in CI on every change.

### Q [Medium] How do you handle errors and logging?
Return clear status codes and messages without leaking internals, log errors with context (request id, user), use structured logs and monitoring (Sentry), and never log passwords or tokens.

### Q [Hard] How would you design a simple URL shortener backend?
A table mapping a short code to the long URL; generate unique codes (random or base62 of an id); `GET /<code>` looks up and redirects (301 or 302); cache hot links in Redis; add rate limits and expiry; index the code column.

### Q [Hard] How do you make an endpoint idempotent?
Accept a client-supplied **idempotency key** and store the result of the first request; repeated requests with the same key return the stored result instead of repeating the action (important for payments and retries).

### Q [Hard] How do you scale a Python web app?
Run several stateless app instances behind a load balancer, move sessions and caches to Redis, use a connection pool and read replicas for the database, push slow work to queues, add caching and a CDN, and monitor to find the real bottleneck.
