---
title: Registration, login and security
summary: Add real accounts: register with a hashed password, log in with a session, protect routes, and prove that users cannot reach each other's data.
takeaways:
- Store only a salted hash of the password and check it with check_password_hash
- A session cookie remembers the logged-in user; a decorator protects routes
- Test the security rules (401, 403, 404) just like features
---
## What we are adding

| Feature | How |
| --- | --- |
| register | validate email and password, store a hash |
| log in | check the password, store the user id in the session |
| log out | clear the session |
| protect routes | a `login_required` decorator |
| separate data | every query filters by the current user |

## The code

```python
import re
from functools import wraps

from flask import Flask, jsonify, request, session, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    owner_id = db.Column(db.ForeignKey("user.id"), nullable=False, index=True)

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY="dev-only", SQLALCHEMY_DATABASE_URI="sqlite://",
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    if config:
        app.config.update(config)
    db.init_app(app)
    with app.app_context():
        db.create_all()

    EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @app.before_request
    def load_user():
        g.user = db.session.get(User, session["user_id"]) if "user_id" in session else None

    def login_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.user is None:
                return jsonify(error="Login required"), 401
            return view(*args, **kwargs)
        return wrapper

    @app.post("/api/register")
    def register():
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        errors = {}
        if not EMAIL.match(email):
            errors["email"] = "Enter a valid email address"
        if len(password) < 8:
            errors["password"] = "Use at least 8 characters"
        if errors:
            return jsonify(error="Validation failed", details=errors), 422
        if db.session.scalar(db.select(User).filter_by(email=email)):
            return jsonify(error="That email is already registered"), 409
        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return jsonify(id=user.id, email=user.email), 201

    @app.post("/api/login")
    def login():
        data = request.get_json(silent=True) or {}
        user = db.session.scalar(db.select(User).filter_by(email=str(data.get("email", "")).strip().lower()))
        if user is None or not check_password_hash(user.password_hash, str(data.get("password", ""))):
            return jsonify(error="Wrong email or password"), 401          # the same message for both cases
        session.clear()
        session["user_id"] = user.id
        return jsonify(ok=True)

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/tasks")
    @login_required
    def list_tasks():
        tasks = db.session.scalars(db.select(Task).where(Task.owner_id == g.user.id)).all()
        return jsonify([{"id": t.id, "title": t.title} for t in tasks])

    @app.post("/api/tasks")
    @login_required
    def add_task():
        title = str((request.get_json(silent=True) or {}).get("title", "")).strip()
        if not title:
            return jsonify(error="A title is required"), 422
        task = Task(title=title, owner_id=g.user.id)
        db.session.add(task)
        db.session.commit()
        return jsonify(id=task.id, title=task.title), 201

    @app.delete("/api/tasks/<int:task_id>")
    @login_required
    def delete_task(task_id):
        task = db.session.scalar(db.select(Task).where(Task.id == task_id, Task.owner_id == g.user.id))
        if task is None:
            return jsonify(error="Task not found"), 404
        db.session.delete(task)
        db.session.commit()
        return "", 204

    return app

app = create_app()
```

## Registering

```python
client = app.test_client()

print(client.post("/api/register", json={"email": "not-an-email", "password": "short"}).get_json())
print(client.post("/api/register", json={"email": "Asha@Example.com", "password": "S3cret-pass"}).get_json())
print(client.post("/api/register", json={"email": "asha@example.com", "password": "S3cret-pass"}).status_code)

with app.app_context():
    stored = db.session.scalar(db.select(User)).password_hash
print("stored value is a hash, not the password:", "S3cret-pass" not in stored, "| starts with", stored.split("$")[0])
```

```output
{'details': {'email': 'Enter a valid email address', 'password': 'Use at least 8 characters'}, 'error': 'Validation failed'}
{'email': 'asha@example.com', 'id': 1}
409
stored value is a hash, not the password: True | starts with scrypt:32768:8:1
```

Passwords of fewer than 8 characters and malformed emails are rejected with details. The email is normalised to lowercase, so `Asha@Example.com` and `asha@example.com` are the same account (the duplicate gets **409 Conflict**). The database holds only a hash.

## Login and protected routes

```python
asha = app.test_client()
print("before login:", asha.get("/api/tasks").status_code)
print("wrong password:", asha.post("/api/login", json={"email": "asha@example.com", "password": "wrong"}).status_code)
print("unknown email :", asha.post("/api/login", json={"email": "nobody@example.com", "password": "x"}).get_json())
print("correct login :", asha.post("/api/login", json={"email": "asha@example.com", "password": "S3cret-pass"}).get_json())
print("after login   :", asha.get("/api/tasks").status_code)

asha.post("/api/tasks", json={"title": "Finish the project"})
asha.post("/api/tasks", json={"title": "Prepare for interviews"})
print(asha.get("/api/tasks").get_json())

asha.post("/api/logout")
print("after logout  :", asha.get("/api/tasks").status_code)
```

```output
before login: 401
wrong password: 401
unknown email : {'error': 'Wrong email or password'}
correct login : {'ok': True}
after login   : 200
[{'id': 1, 'title': 'Finish the project'}, {'id': 2, 'title': 'Prepare for interviews'}]
after logout  : 401
```

Both failures give the **same** message, so an attacker cannot tell whether an email exists. Each test client keeps its own cookies, just like a real browser.

## Prove that users are separated

```python
client.post("/api/register", json={"email": "ravi@example.com", "password": "Pass-w0rd-9"})
asha = app.test_client()
asha.post("/api/login", json={"email": "asha@example.com", "password": "S3cret-pass"})
ravi = app.test_client()
ravi.post("/api/login", json={"email": "ravi@example.com", "password": "Pass-w0rd-9"})

ravi.post("/api/tasks", json={"title": "Ravi's private plan"})
print("Asha sees:", [t["title"] for t in asha.get("/api/tasks").get_json()])
print("Ravi sees:", [t["title"] for t in ravi.get("/api/tasks").get_json()])

ravis_task_id = ravi.get("/api/tasks").get_json()[0]["id"]
print("Asha deletes Ravi's task:", asha.delete(f"/api/tasks/{ravis_task_id}").status_code)
print("Ravi still has it:", len(ravi.get("/api/tasks").get_json()), "task")
```

```output
Asha sees: ['Finish the project', 'Prepare for interviews']
Ravi sees: ["Ravi's private plan"]
Asha deletes Ravi's task: 404
Ravi still has it: 1 task
```

Neither user sees the other's tasks, and Asha's attempt to delete Ravi's task fails with 404. **This is the test that matters most.** Many real breaches happen because this check was forgotten.

## Security checklist for the project

| Item | Done in this lesson |
| --- | --- |
| passwords hashed with a salt | yes (`generate_password_hash`) |
| same error for wrong email and wrong password | yes |
| sessions with `HttpOnly` and `SameSite` cookies | yes |
| every query filtered by the logged-in user | yes |
| input validated on the server | yes |
| secrets from environment variables | `SECRET_KEY` from the environment in production |
| HTTPS in production | on deployment (secure cookie flag, `SESSION_COOKIE_SECURE=True`) |
| rate limiting for login (Flask-Limiter) | an improvement to add |
| CSRF protection on forms | add Flask-WTF for page forms |

:::warning
Never invent your own password hashing or login system for a real product. For a learning project the approach above is fine; in production consider a vetted library or service (Flask-Login, an identity provider such as Auth0 or Firebase), and always use HTTPS.
:::
