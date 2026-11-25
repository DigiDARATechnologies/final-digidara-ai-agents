---
title: Application factory and blueprints
summary: Organise a growing app with the application factory pattern and blueprints, and see why it makes testing easier.
takeaways:
- A factory function builds a fresh app, so tests and servers can have their own
- A blueprint is a group of related routes you register on the app
- Extensions are created once and attached with init_app
---
## Why a single file stops working

A one-file app with `app = Flask(__name__)` at the top is fine for learning. As it grows you hit problems: circular imports, one global app that tests cannot reset, and a thousand lines in one file. The standard solution has two parts.

## 1. The application factory

Instead of creating `app` at import time, create it inside a **function**:

```python
from flask import Flask

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY="dev", GREETING="Hello")
    if config:
        app.config.update(config)          # tests can override settings

    @app.route("/")
    def home():
        return app.config["GREETING"]

    return app

one = create_app()
two = create_app({"GREETING": "Vanakkam"})

print(one.test_client().get("/").data.decode())
print(two.test_client().get("/").data.decode())
```

```output
Hello
Vanakkam
```

Two separate apps with different settings live side by side. That is impossible with a single global `app`, and it is exactly what tests need.

## 2. Blueprints

A **blueprint** holds a group of routes. You build it separately and register it on the app, usually under a URL prefix.

```python
from flask import Blueprint, Flask

courses = Blueprint("courses", __name__, url_prefix="/courses")

@courses.route("/")
def index():
    return {"courses": ["python", "sql"]}

@courses.route("/<slug>")
def detail(slug):
    return {"course": slug}

users = Blueprint("users", __name__, url_prefix="/users")

@users.route("/me")
def me():
    return {"user": "Asha"}

def create_app():
    app = Flask(__name__)
    app.register_blueprint(courses)
    app.register_blueprint(users)
    return app

app = create_app()
client = app.test_client()
print(client.get("/courses/").get_json())
print(client.get("/courses/python").get_json())
print(client.get("/users/me").get_json())
```

```output
{'courses': ['python', 'sql']}
{'course': 'python'}
{'user': 'Asha'}
```

With blueprints, `url_for` names get a prefix:

```python
from flask import url_for

with app.test_request_context():
    print(url_for("courses.detail", slug="flask"))
    print(sorted(rule.rule for rule in app.url_map.iter_rules() if rule.endpoint != "static"))
```

```output
/courses/flask
['/courses/', '/courses/<slug>', '/users/me']
```

## A typical layout

```py
project/
  app/
    __init__.py        # create_app() lives here
    extensions.py      # db = SQLAlchemy() ... created once, attached later
    config.py
    models.py
    courses/
      __init__.py
      routes.py        # the courses blueprint
    users/
      routes.py
    templates/
  tests/
    conftest.py        # builds an app with create_app({"TESTING": True})
  wsgi.py              # app = create_app(), used by Gunicorn
```

## Extensions with init_app

Extensions are created **without** an app, then attached inside the factory. This avoids importing a global app:

```py
# extensions.py
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# __init__.py
def create_app():
    app = Flask(__name__)
    db.init_app(app)
    return app
```

:::tip
Start with the factory pattern on **day one** of any real project. Moving a big single-file app to a factory later is much harder than starting with one.
:::
