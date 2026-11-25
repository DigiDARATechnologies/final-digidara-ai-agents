---
title: Testing Flask apps
summary: Test with pytest and the test client, use fixtures and an in-memory database, and test authentication and errors.
takeaways:
- The test client sends requests without a server
- A fixture builds a fresh app and database for each test
- Test the happy path, the error paths and the permissions
---
## Why test

Tests let you change code without fear: you run them and see what broke. Flask makes this easy because the **test client** talks to your app directly, with no server and no network.

## Fixtures: a clean app for every test

```py
# conftest.py
import pytest
from app import create_app, db

@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "SECRET_KEY": "test"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()
```

Each test gets a **new app with an empty in-memory database**, so tests never affect each other.

## Writing tests

```py
# test_students.py
def test_create_and_list(client):
    r = client.post("/students", json={"name": "Asha", "marks": 92})
    assert r.status_code == 201
    assert client.get("/students").get_json()["total"] == 1

def test_validation_error(client):
    r = client.post("/students", json={"name": "A", "marks": 250})
    assert r.status_code == 422
    assert "marks" in r.get_json()["details"]

def test_missing_student_is_404(client):
    assert client.get("/students/999").status_code == 404
```

Run them with:

```py
pytest -q
```

## Try it here: the same ideas, runnable

This example tests a tiny app by hand, in the same style:

```python
from flask import Flask, request

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(config or {})
    app.items = []

    @app.post("/items")
    def add():
        name = (request.get_json(silent=True) or {}).get("name", "")
        if not name:
            return {"error": "name required"}, 422
        app.items.append(name)
        return {"id": len(app.items)}, 201

    @app.get("/items")
    def items():
        return {"items": app.items}

    return app

def test_add_and_list():
    client = create_app({"TESTING": True}).test_client()
    assert client.post("/items", json={"name": "pen"}).status_code == 201
    assert client.get("/items").get_json() == {"items": ["pen"]}

def test_name_is_required():
    client = create_app({"TESTING": True}).test_client()
    response = client.post("/items", json={})
    assert response.status_code == 422 and response.get_json()["error"] == "name required"

def test_apps_do_not_share_state():
    first, second = create_app().test_client(), create_app().test_client()
    first.post("/items", json={"name": "pen"})
    assert second.get("/items").get_json() == {"items": []}

for test in (test_add_and_list, test_name_is_required, test_apps_do_not_share_state):
    test()
    print("passed:", test.__name__)
```

```output
passed: test_add_and_list
passed: test_name_is_required
passed: test_apps_do_not_share_state
```

The third test shows why the factory pattern matters: two apps from the same factory do not share any state.

## Testing login

```py
def login(client, username="asha", password="flask123"):
    return client.post("/login", json={"username": username, "password": password})

def test_login_required(client):
    assert client.get("/me").status_code == 401

def test_login_then_access(client):
    login(client)
    assert client.get("/me").get_json() == {"user": "asha"}   # the client keeps the cookie

def test_students_cannot_open_admin(client):
    login(client, "ravi", "python456")
    assert client.get("/admin").status_code == 403
```

## What to test

| Area | Examples |
| --- | --- |
| Happy path | create then read; the list shows the new item |
| Validation | missing fields, wrong types, values out of range |
| Errors | 404 for unknown ids, 405 for wrong methods |
| Permissions | logged out gets 401, wrong role gets 403 |
| Edge cases | empty lists, the last page, duplicate emails |

:::tip
Aim for tests that read like a sentence: `test_students_cannot_open_admin`. When one fails in six months, the name tells you what broke before you open the file.
:::

:::interview
**Interviewers often ask:** "How do you test a Flask app?" Use `pytest`, an application factory, a fixture that builds a fresh app with an in-memory database, and the `test_client` to send requests and check status codes and JSON.
:::
