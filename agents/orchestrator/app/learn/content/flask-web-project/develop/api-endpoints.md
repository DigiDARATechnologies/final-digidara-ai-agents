---
title: The JSON API: create, read, update, delete
summary: Build the task endpoints with validation, proper status codes and consistent error responses, and check them with the test client.
takeaways:
- Each endpoint does one job and returns JSON with the right status code
- Validate all input on the server and return clear, consistent errors
- Register error handlers once so every failure has the same shape
---
## The endpoints

| Method and URL | Action | Success | Errors |
| --- | --- | --- | --- |
| `GET /api/tasks` | list my tasks | 200 | 401 not logged in |
| `POST /api/tasks` | create a task | 201 | 400 or 422 invalid |
| `PATCH /api/tasks/<id>` | change title or done | 200 | 404 not found |
| `DELETE /api/tasks/<id>` | delete a task | 204 | 404 not found |

Login comes in the next lesson. To concentrate on the API, we pretend that there is a logged-in user with id 1 by reading a header. Later this one function is replaced by real login.

## The code

```python
from flask import Flask, jsonify, request, abort, g
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    owner_id = db.Column(db.Integer, nullable=False, index=True)

    def to_dict(self):
        return {"id": self.id, "title": self.title, "done": self.done}

class ApiError(Exception):
    def __init__(self, message, status=400, details=None):
        self.message, self.status, self.details = message, status, details

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    with app.app_context():
        db.create_all()

    @app.before_request
    def current_user():
        user_id = request.headers.get("X-Demo-User")          # a stand-in for real login (next lesson)
        g.user_id = int(user_id) if user_id and user_id.isdigit() else None

    def login_required():
        if g.user_id is None:
            raise ApiError("Login required", 401)

    def clean_title(data):
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ApiError("Validation failed", 422, {"title": "A title is required"})
        if len(title.strip()) > 200:
            raise ApiError("Validation failed", 422, {"title": "Use at most 200 characters"})
        return title.strip()

    def own_task_or_404(task_id):
        task = db.session.scalar(db.select(Task).where(Task.id == task_id, Task.owner_id == g.user_id))
        if task is None:
            raise ApiError("Task not found", 404)
        return task

    @app.get("/api/tasks")
    def list_tasks():
        login_required()
        tasks = db.session.scalars(db.select(Task).where(Task.owner_id == g.user_id).order_by(Task.id)).all()
        return jsonify([t.to_dict() for t in tasks])

    @app.post("/api/tasks")
    def create_task():
        login_required()
        data = request.get_json(silent=True) or {}
        task = Task(title=clean_title(data), owner_id=g.user_id)
        db.session.add(task)
        db.session.commit()
        return jsonify(task.to_dict()), 201

    @app.patch("/api/tasks/<int:task_id>")
    def update_task(task_id):
        login_required()
        task = own_task_or_404(task_id)
        data = request.get_json(silent=True) or {}
        if "title" in data:
            task.title = clean_title(data)
        if "done" in data:
            if not isinstance(data["done"], bool):
                raise ApiError("Validation failed", 422, {"done": "Must be true or false"})
            task.done = data["done"]
        db.session.commit()
        return jsonify(task.to_dict())

    @app.delete("/api/tasks/<int:task_id>")
    def delete_task(task_id):
        login_required()
        db.session.delete(own_task_or_404(task_id))
        db.session.commit()
        return "", 204

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        body = {"error": error.message}
        if error.details:
            body["details"] = error.details
        return jsonify(body), error.status

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify(error="Not found"), 404

    return app

app = create_app()
client = app.test_client()
asha = {"X-Demo-User": "1"}
ravi = {"X-Demo-User": "2"}
```

## Try every endpoint

```python
print(client.get("/api/tasks").status_code)                                   # not logged in
r = client.post("/api/tasks", json={"title": "Write README"}, headers=asha)
print(r.status_code, r.get_json())
client.post("/api/tasks", json={"title": "Deploy the app"}, headers=asha)
client.post("/api/tasks", json={"title": "Ravi's private task"}, headers=ravi)

print(client.get("/api/tasks", headers=asha).get_json())
print(client.patch("/api/tasks/1", json={"done": True}, headers=asha).get_json())
print(client.delete("/api/tasks/2", headers=asha).status_code)
print(client.get("/api/tasks", headers=asha).get_json())
```

```output
401
201 {'done': False, 'id': 1, 'title': 'Write README'}
[{'done': False, 'id': 1, 'title': 'Write README'}, {'done': False, 'id': 2, 'title': 'Deploy the app'}]
{'done': True, 'id': 1, 'title': 'Write README'}
204
[{'done': True, 'id': 1, 'title': 'Write README'}]
```

You can see the whole life of a task: create (201), list, mark done, delete (204). The first request without a user got **401**.

## Validation and errors

```python
print(client.post("/api/tasks", json={"title": "   "}, headers=asha).get_json())
print(client.post("/api/tasks", json={}, headers=asha).status_code)
print(client.post("/api/tasks", data="not json", headers=asha).status_code)
print(client.patch("/api/tasks/1", json={"done": "yes"}, headers=asha).get_json())
print(client.get("/api/nothing-here").get_json())
```

```output
{'details': {'title': 'A title is required'}, 'error': 'Validation failed'}
422
422
{'details': {'done': 'Must be true or false'}, 'error': 'Validation failed'}
{'error': 'Not found'}
```

Every error is JSON with the same shape (`error`, and optional `details`), and bad input never crashes the server. A front end can show the `details` next to the right form field.

## Ownership is enforced

```python
print("Asha changes Ravi task:", client.patch("/api/tasks/3", json={"done": True}, headers=asha).status_code)
print("Ravi's task is untouched:", client.get("/api/tasks", headers=ravi).get_json())
print("Ravi deletes his own task:", client.delete("/api/tasks/3", headers=ravi).status_code)
```

```output
Asha changes Ravi task: 404
Ravi's task is untouched: [{'done': False, 'id': 3, 'title': "Ravi's private task"}]
Ravi deletes his own task: 204
```

Asha gets **404** for Ravi's task, not 403. A 404 does not even reveal that the task exists. Ravi can still change his own.

## Design decisions to remember

| Decision | Reason |
| --- | --- |
| validation in one function (`clean_title`) | the same rules for create and update |
| `own_task_or_404` for every task lookup | one place guarantees ownership |
| `ApiError` plus one handler | every error looks the same |
| status codes: 201, 204, 401, 404, 422 | clients can rely on them |
| the response lists only chosen fields (`to_dict`) | no accidental leaks |

:::tip
A tool such as **Postman**, **Thunder Client** (VS Code) or `curl` lets you try the API by hand while the real server runs:
`curl -X POST http://127.0.0.1:5000/api/tasks -H "Content-Type: application/json" -H "X-Demo-User: 1" -d "{\"title\": \"Test\"}"`.
:::
