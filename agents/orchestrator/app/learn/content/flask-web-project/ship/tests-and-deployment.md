---
title: Tests, deployment and showing it to the world
summary: Test the whole API automatically, containerise the app, deploy it to a free host, and describe the project on your resume and in interviews.
takeaways:
- Automated tests protect features and security rules every time you change the code
- A production setup needs Gunicorn, environment variables, a real database and HTTPS
- A live link, a clean README and a clear story turn the project into a hiring asset
---
## Automated tests

Tests should create a **fresh app and database** for each test, so tests never affect one another. This is why we used the application factory.

```python
import unittest

from flask import Flask, jsonify, request, session
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
    owner_id = db.Column(db.ForeignKey("user.id"), nullable=False)

def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", SQLALCHEMY_DATABASE_URI="sqlite://", TESTING=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()

    @app.post("/api/register")
    def register():
        data = request.get_json()
        db.session.add(User(email=data["email"], password_hash=generate_password_hash(data["password"])))
        db.session.commit()
        return jsonify(ok=True), 201

    @app.post("/api/login")
    def login():
        data = request.get_json()
        user = db.session.scalar(db.select(User).filter_by(email=data["email"]))
        if not user or not check_password_hash(user.password_hash, data["password"]):
            return jsonify(error="Wrong email or password"), 401
        session["user_id"] = user.id
        return jsonify(ok=True)

    @app.get("/api/tasks")
    def tasks():
        if "user_id" not in session:
            return jsonify(error="Login required"), 401
        rows = db.session.scalars(db.select(Task).where(Task.owner_id == session["user_id"])).all()
        return jsonify([t.title for t in rows])

    @app.post("/api/tasks")
    def add():
        if "user_id" not in session:
            return jsonify(error="Login required"), 401
        title = (request.get_json() or {}).get("title", "").strip()
        if not title:
            return jsonify(error="A title is required"), 422
        db.session.add(Task(title=title, owner_id=session["user_id"]))
        db.session.commit()
        return jsonify(ok=True), 201

    return app

class TaskApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()                        # a fresh app and an empty database for every test
        self.client = self.app.test_client()

    def sign_up_and_log_in(self, client, email="asha@example.com"):
        client.post("/api/register", json={"email": email, "password": "S3cret-pass"})
        return client.post("/api/login", json={"email": email, "password": "S3cret-pass"})

    def test_tasks_need_login(self):
        self.assertEqual(self.client.get("/api/tasks").status_code, 401)

    def test_wrong_password_is_rejected(self):
        self.client.post("/api/register", json={"email": "a@x.com", "password": "S3cret-pass"})
        bad = self.client.post("/api/login", json={"email": "a@x.com", "password": "nope"})
        self.assertEqual(bad.status_code, 401)

    def test_create_and_list_a_task(self):
        self.sign_up_and_log_in(self.client)
        self.assertEqual(self.client.post("/api/tasks", json={"title": "Write tests"}).status_code, 201)
        self.assertEqual(self.client.get("/api/tasks").get_json(), ["Write tests"])

    def test_blank_title_is_rejected(self):
        self.sign_up_and_log_in(self.client)
        self.assertEqual(self.client.post("/api/tasks", json={"title": "   "}).status_code, 422)

    def test_users_cannot_see_each_others_tasks(self):
        other = self.app.test_client()
        self.sign_up_and_log_in(self.client, "asha@example.com")
        self.sign_up_and_log_in(other, "ravi@example.com")
        self.client.post("/api/tasks", json={"title": "Asha's secret"})
        self.assertEqual(other.get("/api/tasks").get_json(), [])

suite = unittest.defaultTestLoader.loadTestsFromTestCase(TaskApiTests)
import io
result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
print("tests run:", result.testsRun, "| failures:", len(result.failures), "| errors:", len(result.errors), "| all passed:", result.wasSuccessful())
```

```output
tests run: 5 | failures: 0 | errors: 0 | all passed: True
```

Five tests pass: the login rule, the validation rule and the **privacy rule** are now checked every time you run the tests. In a real project these live in `tests/test_api.py` and you run `pytest`. Add them to a **GitHub Actions** workflow so they run on every push:

```py
# .github/workflows/tests.yml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest -q
```

A green tick on your repository tells recruiters that your project is tested.

## Run it like a real server

`flask run` is for development. For production use **Gunicorn** (on Windows use Waitress):

```py
# wsgi.py
from app import create_app
app = create_app()
```

```py
gunicorn --workers 3 --bind 0.0.0.0:8000 wsgi:app
```

## Docker

```py
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8000", "wsgi:app"]
```

```py
docker build -t taskflow .
docker run -p 8000:8000 -e SECRET_KEY=change-me -e DATABASE_URL=sqlite:///taskflow.db taskflow
```

## Free places to deploy

| Platform | Notes |
| --- | --- |
| **Render** | connect your GitHub repo; set the start command `gunicorn wsgi:app`; add a free PostgreSQL database |
| **Railway** | similar, with a simple dashboard and a database add-on |
| **Fly.io** | runs your Docker image close to users |
| **PythonAnywhere** | a beginner-friendly Python host with a free tier |
| **A VPS (DigitalOcean, AWS, Azure)** | full control: Nginx, Gunicorn, HTTPS (more work, more to learn) |

Free tiers change over time, so check each provider's current offer. The general steps are the same everywhere:

1. Push your code to GitHub (without secrets).
2. Create the service and connect the repository.
3. Set **environment variables**: `SECRET_KEY`, `DATABASE_URL`.
4. Use a real database (PostgreSQL) and run migrations on release (`flask db upgrade`).
5. Set `SESSION_COOKIE_SECURE=True` (HTTPS only) and `DEBUG` off.
6. Open the live URL, create an account, and test the whole flow yourself.

## Pre-launch checklist

| Check | |
| --- | --- |
| tests pass | |
| no secrets in Git (search the history too) | |
| `SECRET_KEY` and the database URL come from the environment | |
| debug mode is off | |
| HTTPS is on and cookies are secure | |
| a health check URL works | |
| the README has a live link and screenshots | |

## Show it off

**On your resume:**

:::example Resume bullets
**TaskFlow: task manager web app** (Python, Flask, SQLAlchemy, PostgreSQL, Docker)
- Built a full-stack web app with registration, login and a JSON API; each user can only access their own data (verified with automated tests).
- Wrote 12 automated tests and set up GitHub Actions CI; deployed with Docker and Gunicorn to Render.
- Link: github.com/yourname/taskflow | Live: taskflow.onrender.com
:::

**In an interview**, be ready to explain:

| Question | Your answer should cover |
| --- | --- |
| "Walk me through the project." | the problem, the stack, the main features (60 seconds) |
| "How do you store passwords?" | salted hashes with Werkzeug, never plain text |
| "How do you stop users from seeing others' data?" | every query filters by owner; 404 for others; tested |
| "What was the hardest bug?" | a real story (STAR) |
| "What would you improve?" | rate limiting, CSRF tokens, pagination, a React front end |
| "How did you test it?" | the unit tests and what they cover |

:::interview
**Interviewers often ask:** "Why Flask and not Django for this?" Flask is lightweight and lets you understand each part (routing, ORM, sessions). Django would give admin, auth and forms out of the box, and would be a good choice for a larger product. The concepts you used (models, REST, hashing, testing, deployment) transfer to both.
:::

:::practice capstone-project
Ask the Capstone Project agent to review your repository against the pre-launch checklist and to suggest one feature that would make it stand out.
:::
