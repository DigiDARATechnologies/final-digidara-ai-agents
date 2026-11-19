---
title: Authentication and authorisation
summary: Hash passwords properly, log users in with sessions, issue JWT tokens for APIs, and protect routes with decorators.
takeaways:
- Never store passwords; store salted hashes made with a slow algorithm
- Sessions suit browser apps; tokens (JWT) suit APIs and mobile apps
- Authentication asks who you are; authorisation asks what you may do
---
## Hash passwords, never store them

If your database leaks, plain passwords expose every user (and their accounts on other sites). Store a **hash**: a one-way scrambled form. Werkzeug (installed with Flask) does it with a random **salt**:

```python
from werkzeug.security import generate_password_hash, check_password_hash

stored = generate_password_hash("S3cret-passw0rd")
print(stored.split("$")[0], "hash, length", len(stored))
print(check_password_hash(stored, "S3cret-passw0rd"))
print(check_password_hash(stored, "wrong-guess"))
print(generate_password_hash("S3cret-passw0rd") != stored)
```

```output
scrypt:32768:8:1 hash, length 162
True
False
True
```

Hashing the **same password twice gives different results**, because each hash has its own salt. `check_password_hash` reads the salt from the stored value, so it still verifies correctly. For stronger protection against guessing, use `argon2` or `bcrypt` through a library.

:::warning
Never use a fast hash such as MD5 or SHA-256 alone for passwords: attackers can try billions per second. Use a deliberately **slow** password hash.
:::

## A decorator that protects routes

```python
from functools import wraps
from flask import Flask, session, jsonify, request, g

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-only-change-me"

USERS = {"asha": {"hash": generate_password_hash("flask123"), "role": "admin"},
         "ravi": {"hash": generate_password_hash("python456"), "role": "student"}}

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "login_required"}), 401          # not authenticated
        return view(*args, **kwargs)
    return wrapper

def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if USERS[session["user"]]["role"] != role:
                return jsonify({"error": "forbidden"}), 403            # authenticated but not allowed
            return view(*args, **kwargs)
        return wrapper
    return decorator

@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = USERS.get(data.get("username"))
    if not user or not check_password_hash(user["hash"], data.get("password", "")):
        return jsonify({"error": "invalid_credentials"}), 401         # same message either way
    session.clear()
    session["user"] = data["username"]
    return {"ok": True}

@app.get("/me")
@login_required
def me():
    return {"user": session["user"]}

@app.get("/admin")
@role_required("admin")
def admin_page():
    return {"secret": "admin stuff"}

c = app.test_client()
print(c.get("/me").status_code)
print(c.post("/login", json={"username": "asha", "password": "nope"}).status_code)
c.post("/login", json={"username": "ravi", "password": "python456"})
print(c.get("/me").get_json(), c.get("/admin").status_code)
admin = app.test_client()
admin.post("/login", json={"username": "asha", "password": "flask123"})
print(admin.get("/admin").get_json())
```

```output
401
401
{'user': 'ravi'} 403
{'secret': 'admin stuff'}
```

Notice the three codes: **401** (not logged in), **403** (logged in as a student, but the page needs an admin), and success for the admin.

:::note
The login route gives the **same** error for "no such user" and "wrong password". Telling them apart helps attackers find which usernames exist. `session.clear()` before setting the user also prevents session fixation.
:::

## Tokens (JWT) for APIs

A browser keeps a cookie automatically. A mobile app or another service calls your API directly, so it sends a **token** in the `Authorization` header. A **JWT** is a signed token that carries claims such as the user id and an expiry time.

```python
import datetime
import jwt          # pip install pyjwt

SECRET = "jwt-secret-from-the-environment"

def make_token(user_id, minutes=15):
    payload = {"sub": str(user_id), "role": "student",
               "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)}
    return jwt.encode(payload, SECRET, algorithm="HS256")

token = make_token(7)
claims = jwt.decode(token, SECRET, algorithms=["HS256"])
print(claims["sub"], claims["role"])

try:
    jwt.decode(make_token(7, minutes=-1), SECRET, algorithms=["HS256"])
except jwt.ExpiredSignatureError:
    print("expired token rejected")

try:
    jwt.decode(token + "x", SECRET, algorithms=["HS256"])
except jwt.InvalidTokenError:
    print("tampered token rejected")
```

```output
7 student
expired token rejected
tampered token rejected
```

The server proves a token is genuine by **verifying the signature**, so it does not need to look the user up in a session store.

| | Session cookie | JWT |
| --- | --- | --- |
| Best for | browser sites | APIs, mobile apps, services |
| Where the state lives | on the server | inside the token |
| Logging out | delete the session | hard: the token stays valid until it expires |
| Sent as | cookie | `Authorization: Bearer <token>` |

:::warning
A JWT is **signed, not encrypted**: anyone can read it. Put no secrets in it. Keep expiry times short, always pass `algorithms=[...]` when decoding, and keep the signing secret out of your code.
:::

:::interview
**Interviewers often ask:** "Authentication versus authorisation?" Authentication proves **who** you are (login). Authorisation decides **what** you are allowed to do (roles, permissions). They map to HTTP 401 and 403.
:::
