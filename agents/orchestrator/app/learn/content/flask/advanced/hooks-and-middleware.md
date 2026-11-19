---
title: Hooks, the g object and request context
summary: Run code around every request with before_request and after_request, share data with g, and add timing, IDs and logging.
takeaways:
- before_request and after_request run around every request
- g holds data for the current request only
- Hooks are the Flask way to do cross-cutting work such as logging and security headers
---
## Request hooks

Flask lets you run a function **before** every request, **after** every response, and when the request context ends. This is where cross-cutting work belongs: logging, timing, authentication checks, response headers.

```python
import time
import uuid
from flask import Flask, g, request

app = Flask(__name__)
log = []

@app.before_request
def start():
    g.started = time.perf_counter()
    g.request_id = uuid.uuid4().hex[:8]

@app.after_request
def finish(response):
    elapsed_ms = (time.perf_counter() - g.started) * 1000
    response.headers["X-Request-ID"] = g.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    log.append(f"{request.method} {request.path} -> {response.status_code}")
    return response

@app.route("/ping")
def ping():
    return {"id_matches_header": True}

c = app.test_client()
r = c.get("/ping")
print(len(r.headers["X-Request-ID"]), r.headers["X-Content-Type-Options"])
print(log)
c.get("/nowhere")
print(log)
```

```output
8 nosniff
['GET /ping -> 200']
['GET /ping -> 200', 'GET /nowhere -> 404']
```

The hooks ran for the real route **and** for the 404.

| Hook | When it runs |
| --- | --- |
| `before_request` | before the view; returning a response here **skips** the view |
| `after_request` | after the view, with the response (you must return it) |
| `teardown_request` | at the end, even when there was an error (clean up) |
| `errorhandler` | when an exception or error status happens |
| `before_first_request` | removed in Flask 2.3: use app start-up code instead |

## The g object

`g` is a scratch space **for one request**. Store things the view or the hooks need to share, such as the current user or a database connection. It is reset for every request, so one user's data never leaks into another's.

```python
USERS = {"token-asha": "Asha", "token-ravi": "Ravi"}

@app.before_request
def load_user():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    g.user = USERS.get(token)

@app.route("/whoami")
def whoami():
    return {"user": g.user}

print(c.get("/whoami", headers={"Authorization": "Bearer token-asha"}).get_json())
print(c.get("/whoami").get_json())
```

```output
{'user': 'Asha'}
{'user': None}
```

## Stopping a request early

Returning a value from `before_request` ends the request right there:

```python
@app.before_request
def maintenance():
    if request.path.startswith("/admin") and not g.get("user"):
        return {"error": "login_required"}, 401

@app.route("/admin/stats")
def stats():
    return {"visits": 1234}

print(c.get("/admin/stats").status_code)
print(c.get("/admin/stats", headers={"Authorization": "Bearer token-ravi"}).status_code)
```

```output
401
200
```

## Context locals

`request`, `session` and `g` look like global variables, but each one is **bound to the request being handled**, even with many requests running at once. Flask does this with **context locals**. Outside a request they do not exist:

```python
try:
    request.path
except RuntimeError as error:
    print("RuntimeError:", str(error).splitlines()[0])

with app.test_request_context("/ping"):
    print("inside a context:", request.path)
```

```output
RuntimeError: Working outside of request context.
inside a context: /ping
```

:::tip
Keep hooks fast and small: they run on **every** request. Do heavy work (sending email, generating reports) in a background job instead.
:::

:::interview
**Interviewers often ask:** "What is `g` in Flask?" An object that lives for one request (inside one application context) and holds data shared by the hooks and views of that request, such as the current user or a database connection.
:::
