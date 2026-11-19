---
title: Plan and set up: a Task Manager web app
summary: Define what the project does, choose the structure, set up the environment, and create a working skeleton before writing any feature.
takeaways:
- Plan features, pages and data before coding, and keep version 1 small
- Use a virtual environment, a requirements file and the application factory pattern
- A tiny working skeleton with a health check proves that your setup is right
---
## The project

You will build **TaskFlow**, a small web app where people sign up, log in and manage their own to-do lists. It is small enough to finish in a week and covers what companies expect from a first full-stack project: a database, a JSON API, web pages, login, tests and deployment.

| Version 1 (MVP) | Later ideas |
| --- | --- |
| register and log in | due dates and reminders |
| create, list, complete and delete tasks | task categories and filters |
| each user sees **only their own** tasks | sharing a list with a friend |
| a web page and a JSON API | email notifications |
| tests and deployment | a React front end |

## Plan the data and the pages

**Data (two tables):**

| User | Task |
| --- | --- |
| id | id |
| email (unique) | title |
| password hash | done (yes or no) |
| | created time |
| | owner (a link to the User) |

One user has many tasks: a **one-to-many** relationship.

**Pages and API:**

| Page or endpoint | Purpose |
| --- | --- |
| `GET /health` | proves the app is alive |
| `POST /api/register`, `POST /api/login` | accounts |
| `GET /api/tasks`, `POST /api/tasks` | list and create |
| `PATCH /api/tasks/<id>`, `DELETE /api/tasks/<id>` | complete or remove |
| `GET /` | the web page showing your tasks |

## Set up the environment

```py
mkdir taskflow
cd taskflow
python -m venv .venv
.venv\Scripts\activate           # macOS and Linux: source .venv/bin/activate
pip install flask flask-sqlalchemy pytest gunicorn
pip freeze > requirements.txt    # records exact versions so others can install the same
git init
```

Add a `.gitignore` so private and generated files stay out of Git:

```py
.venv/
__pycache__/
*.db
.env
instance/
```

## The folder structure

```py
taskflow/
  app/
    __init__.py        # create_app(): builds the app
    models.py          # User and Task tables
    api.py             # JSON endpoints (a blueprint)
    pages.py           # HTML pages (a blueprint)
    templates/
      base.html
      index.html
  tests/
    test_api.py
  wsgi.py              # the entry point for the production server
  requirements.txt
  README.md
  .gitignore
```

## A working skeleton

Start with the smallest possible app that runs: the application factory (from the Flask course) and one health route.

```python
from flask import Flask, jsonify

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY="dev-only-change-me", SQLALCHEMY_DATABASE_URI="sqlite://")
    if config:
        app.config.update(config)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app

app = create_app()
client = app.test_client()
print(client.get("/health").status_code, client.get("/health").get_json())
print("a different config for tests:", create_app({"TESTING": True}).config["TESTING"])
```

```output
200 {'status': 'ok'}
a different config for tests: True
```

The factory returns a **new** app each time, which is exactly what tests need. Running it for real:

```py
flask --app app run --debug
```

Open http://127.0.0.1:5000/health and you should see `{"status":"ok"}`. If you do, your environment, Flask and your folder structure all work. **Commit now**: `git add . && git commit -m "Project skeleton with health check"`.

## Configuration and secrets

Settings that differ between your laptop and the server must not be hard-coded. Read them from environment variables:

```python
import os

def load_config():
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-only-change-me"),
        "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL", "sqlite:///taskflow.db"),
    }

print(sorted(load_config()))
os.environ["DATABASE_URL"] = "postgresql://user:pass@db-host/taskflow"
print(load_config()["SQLALCHEMY_DATABASE_URI"].split("://")[0])
```

```output
['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']
postgresql
```

Locally the app uses SQLite (a file), and on the server an environment variable switches it to PostgreSQL. **Never commit real passwords or keys to GitHub.**

## Commit habits for a portfolio project

| Habit | Why |
| --- | --- |
| small commits with clear messages: "Add task model", "Add login endpoint" | recruiters read the history |
| a commit after each working step | easy to go back |
| a README from day one | you will forget how to run it |
| a separate branch for big features (`git switch -c feature/auth`) | safe experiments |

:::practice capstone-project
Share your own plan (features, data, pages) with the Capstone Project agent before you start coding, and ask what to cut for version 1.
:::
