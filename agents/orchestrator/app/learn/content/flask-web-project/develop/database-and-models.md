---
title: The database and models
summary: Define User and Task models with Flask-SQLAlchemy, create the tables, link tasks to their owner and run the queries the app will need.
takeaways:
- A model is a class that becomes a table; a foreign key links tasks to users
- Add, query, update and delete with db.session, and commit to save
- Design queries so each user can only reach their own rows
---
## The models

```python
from datetime import datetime, timezone

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    tasks = db.relationship("Task", back_populates="owner", cascade="all, delete-orphan")

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    owner_id = db.Column(db.ForeignKey("user.id"), nullable=False, index=True)
    owner = db.relationship("User", back_populates="tasks")

    def to_dict(self):
        return {"id": self.id, "title": self.title, "done": self.done}

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
db.init_app(app)

with app.app_context():
    db.create_all()
    print(sorted(db.metadata.tables))
    print([c.name for c in Task.__table__.columns])
```

```output
['task', 'user']
['id', 'title', 'done', 'created', 'owner_id']
```

Some design choices worth explaining in an interview:

| Choice | Reason |
| --- | --- |
| `unique=True` on email | the database itself refuses duplicate accounts |
| `password_hash`, never `password` | we never store the real password |
| `owner_id` with `index=True` | listing "my tasks" will be fast even with many rows |
| `cascade="all, delete-orphan"` | deleting a user removes their tasks |
| `to_dict()` | lists exactly what is safe to send in the API (never the password hash) |

## Adding and querying data

```python
from werkzeug.security import generate_password_hash

with app.app_context():
    asha = User(email="asha@example.com", password_hash=generate_password_hash("S3cret-pass"))
    ravi = User(email="ravi@example.com", password_hash=generate_password_hash("Pass-w0rd-9"))
    db.session.add_all([asha, ravi])
    db.session.commit()

    db.session.add_all([
        Task(title="Finish Flask project", owner=asha),
        Task(title="Practise SQL joins", owner=asha),
        Task(title="Revise aptitude formulas", owner=asha, done=True),
        Task(title="Update resume", owner=ravi),
    ])
    db.session.commit()

    print("users:", db.session.scalar(db.select(db.func.count(User.id))))
    print("tasks:", db.session.scalar(db.select(db.func.count(Task.id))))

    asha = db.session.scalar(db.select(User).filter_by(email="asha@example.com"))
    print("Asha's tasks:", [t.title for t in asha.tasks])

    open_tasks = db.session.scalars(
        db.select(Task).where(Task.owner_id == asha.id, Task.done.is_(False)).order_by(Task.id)
    ).all()
    print("Asha's open tasks:", [t.title for t in open_tasks])
```

```output
users: 2
tasks: 4
Asha's tasks: ['Finish Flask project', 'Practise SQL joins', 'Revise aptitude formulas']
Asha's open tasks: ['Finish Flask project', 'Practise SQL joins']
```

## Owner-safe queries

The most important rule of this app: **a user must never see or change another user's tasks.** Build it into every query by always filtering by owner:

```python
def get_task_for_user(task_id, user_id):
    return db.session.scalar(db.select(Task).where(Task.id == task_id, Task.owner_id == user_id))

with app.app_context():
    asha = db.session.scalar(db.select(User).filter_by(email="asha@example.com"))
    ravi = db.session.scalar(db.select(User).filter_by(email="ravi@example.com"))
    ravis_task = db.session.scalar(db.select(Task).where(Task.owner_id == ravi.id))

    print("Ravi opens his own task:", get_task_for_user(ravis_task.id, ravi.id) is not None)
    print("Asha tries to open Ravi's task:", get_task_for_user(ravis_task.id, asha.id))
```

```output
Ravi opens his own task: True
Asha tries to open Ravi's task: None
```

The lookup returns `None` for the wrong user, and the endpoints will answer with 404. This is the fix for a common web vulnerability (people changing the id in the URL to reach someone else's data).

## Update and delete

```python
with app.app_context():
    task = db.session.scalar(db.select(Task).where(Task.title == "Practise SQL joins"))
    task.done = True
    db.session.commit()
    print("marked done:", task.done)

    db.session.delete(task)
    db.session.commit()
    print("remaining tasks:", db.session.scalar(db.select(db.func.count(Task.id))))
```

```output
marked done: True
remaining tasks: 3
```

## Migrations

`create_all()` only creates **missing tables**. When you add a column later, use **Flask-Migrate** (see the Flask course): `flask db init`, `flask db migrate`, `flask db upgrade`. Commit the migration files with your code.

## Checklist for this step

| Check | |
| --- | --- |
| tables created and a few rows added | |
| a user cannot reach someone else's task | |
| the password is stored only as a hash | |
| model code committed to Git | |
