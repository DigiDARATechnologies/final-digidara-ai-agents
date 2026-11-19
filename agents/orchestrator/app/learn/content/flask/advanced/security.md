---
title: Securing a Flask app
summary: Defend against SQL injection, XSS, CSRF and common mistakes with safe cookies, headers and input handling.
takeaways:
- Use parameterised queries or the ORM, never string-built SQL
- Jinja escapes output by default; do not switch that off for user content
- Secure cookies, CSRF tokens and security headers close the rest of the common gaps
---
## SQL injection

If you build a query by pasting user input into a string, an attacker can change the query itself:

```python
import sqlite3

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE users (name TEXT, password TEXT)")
db.execute("INSERT INTO users VALUES ('asha', 'secret1'), ('ravi', 'secret2')")

def unsafe_lookup(name):
    query = f"SELECT name FROM users WHERE name = '{name}'"      # DANGER: string building
    return db.execute(query).fetchall()

def safe_lookup(name):
    return db.execute("SELECT name FROM users WHERE name = ?", (name,)).fetchall()   # a parameter

attack = "x' OR '1'='1"
print("unsafe:", unsafe_lookup(attack))
print("safe  :", safe_lookup(attack))
```

```output
unsafe: [('asha',), ('ravi',)]
safe  : []
```

The attack input turned the unsafe query into "...WHERE name = 'x' OR '1'='1'", which is **always true**, so it returned every user. The safe version treats the whole input as plain data. SQLAlchemy does this for you whenever you use its query API.

:::warning
Never put user input into SQL with an f-string, `%` or `+`. Always use parameters (`?`, `:name`) or the ORM.
:::

## Cross-site scripting (XSS)

XSS happens when text typed by one user runs as **code** in another user's browser. Jinja's autoescaping prevents it, as long as you leave it on:

```python
from flask import Flask, render_template_string
from markupsafe import Markup, escape

app = Flask(__name__)
comment = '<script>steal(document.cookie)</script>'

with app.app_context():
    print(render_template_string("{{ c }}", c=comment))
    print(render_template_string("{{ c|safe }}", c=comment))       # switched off: dangerous
    print(escape(comment))
```

```output
&lt;script&gt;steal(document.cookie)&lt;/script&gt;
<script>steal(document.cookie)</script>
&lt;script&gt;steal(document.cookie)&lt;/script&gt;
```

The second line is an **active script tag**: that is the bug. The `|safe` filter and `Markup()` tell Jinja "trust this", so only use them on text **you** wrote. To allow limited formatting from users, clean it first with a sanitiser library such as **bleach**.

## Cookies and the session

```python
app.config.update(
    SECRET_KEY="a-long-random-value-from-the-environment",
    SESSION_COOKIE_SECURE=True,        # only over HTTPS
    SESSION_COOKIE_HTTPONLY=True,      # JavaScript cannot read it
    SESSION_COOKIE_SAMESITE="Lax",     # not sent on most cross-site requests
    PERMANENT_SESSION_LIFETIME=3600,   # seconds
)
print({k: app.config[k] for k in ("SESSION_COOKIE_SECURE", "SESSION_COOKIE_HTTPONLY", "SESSION_COOKIE_SAMESITE")})
```

```output
{'SESSION_COOKIE_SECURE': True, 'SESSION_COOKIE_HTTPONLY': True, 'SESSION_COOKIE_SAMESITE': 'Lax'}
```

| Flag | Protects against |
| --- | --- |
| `Secure` | the cookie travelling over plain HTTP, where it can be read |
| `HttpOnly` | JavaScript (and so XSS) stealing the session |
| `SameSite` | cross-site requests carrying the cookie (the basis of CSRF) |

## CSRF

A malicious page can make a logged-in user's browser send a request to your site, and the browser attaches the session cookie. A **CSRF token** (a secret value only your own pages know) stops this. Use **Flask-WTF**'s `CSRFProtect`. APIs that use `Authorization` headers instead of cookies are not exposed in the same way.

## Security headers

```python
@app.after_request
def secure_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"                       # no embedding in other sites (clickjacking)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

@app.route("/")
def home():
    return "ok"

headers = app.test_client().get("/").headers
for name in ("X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy"):
    print(name + ":", headers[name])
```

```output
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'
```

For HTTPS sites also send `Strict-Transport-Security`. The **Flask-Talisman** extension sets a sensible group of these for you.

## Limiting uploads and size

```python
app.config["MAX_CONTENT_LENGTH"] = 1024            # reject bodies over 1 KB in this demo

@app.post("/upload")
def upload():
    return {"size": len(__import__("flask").request.get_data())}

client = app.test_client()
print(client.post("/upload", data=b"x" * 100).status_code)
print(client.post("/upload", data=b"x" * 5000).status_code)
```

```output
200
413
```

A request larger than the limit gets **413 Payload Too Large** before your code reads it. For file uploads also check the file type and use `werkzeug.utils.secure_filename`.

## A checklist

| Risk | Defence |
| --- | --- |
| SQL injection | the ORM or parameterised queries |
| XSS | keep Jinja autoescaping on; sanitise rich text |
| CSRF | CSRF tokens, `SameSite` cookies |
| Stolen sessions | `Secure`, `HttpOnly`, short lifetime, HTTPS |
| Weak passwords | slow salted hashes (argon2, bcrypt), rate limits on login |
| Brute force | rate limiting (Flask-Limiter) and account lockouts |
| Leaked secrets | environment variables, never in Git |
| Debug mode online | `DEBUG = False` in production |
| Vulnerable libraries | keep dependencies updated, run `pip-audit` |

:::interview
**Interviewers often ask:** "How do you secure a Flask application?" Parameterised queries, Jinja escaping, CSRF protection, secure cookie flags, password hashing, HTTPS, security headers, rate limiting, no debug mode in production, and keeping secrets and dependencies safe.
:::
