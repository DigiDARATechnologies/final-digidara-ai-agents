---
title: The web page: templates and forms
summary: Show tasks in an HTML page with Jinja, add a form that creates tasks, and follow the redirect-after-post pattern with flash messages.
takeaways:
- Jinja templates turn data into HTML, and template inheritance shares the layout
- A form posts to the server, which validates, saves and redirects (Post/Redirect/Get)
- Jinja escapes output automatically, so user text cannot inject scripts
---
## The page

We want a page at `/` with a list of the user's tasks, a form to add a new one, and buttons to complete or delete. The server renders HTML using **Jinja** (see the Flask course).

## Templates

In a real project these live in `app/templates/`. Here they are in a dictionary so the example runs anywhere:

```python
from jinja2 import DictLoader

TEMPLATES = {
    "base.html": """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{% block title %}TaskFlow{% endblock %}</title></head>
<body>
<header><a href="{{ url_for('home') }}">TaskFlow</a></header>
{% for category, message in get_flashed_messages(with_categories=true) %}
  <p class="flash {{ category }}">{{ message }}</p>
{% endfor %}
{% block content %}{% endblock %}
</body>
</html>""",
    "index.html": """{% extends "base.html" %}
{% block content %}
<h1>My tasks ({{ tasks|length }})</h1>
<form method="post" action="{{ url_for('add') }}">
  <input name="title" placeholder="What needs doing?" required>
  <button>Add</button>
</form>
<ul>
{% for task in tasks %}
  <li class="{{ 'done' if task.done else 'open' }}">{{ task.title }}
    <form method="post" action="{{ url_for('toggle', task_id=task.id) }}"><button>{{ 'Undo' if task.done else 'Done' }}</button></form>
  </li>
{% else %}
  <li>No tasks yet. Add your first one above.</li>
{% endfor %}
</ul>
{% endblock %}""",
}
```

The page extends the base layout, loops over `tasks`, and builds each URL with `url_for` so links never break if routes change.

## The routes

```python
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)

app = Flask(__name__)
app.config.update(SECRET_KEY="dev", SQLALCHEMY_DATABASE_URI="sqlite://")
app.jinja_loader = DictLoader(TEMPLATES)
db.init_app(app)
with app.app_context():
    db.create_all()

@app.get("/")
def home():
    tasks = db.session.scalars(db.select(Task).order_by(Task.id)).all()
    return render_template("index.html", tasks=tasks)

@app.post("/add")
def add():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Please type a task.", "error")
    else:
        db.session.add(Task(title=title))
        db.session.commit()
        flash("Task added.", "success")
    return redirect(url_for("home"))             # Post/Redirect/Get

@app.post("/toggle/<int:task_id>")
def toggle(task_id):
    task = db.get_or_404(Task, task_id)
    task.done = not task.done
    db.session.commit()
    return redirect(url_for("home"))
```

After a form is processed, the server **redirects** to a normal page. If the user presses refresh, the browser repeats the harmless GET, not the form submission, so tasks are not added twice.

## Try it

```python
client = app.test_client()

page = client.get("/").get_data(as_text=True)
print("empty page shows the hint:", "No tasks yet" in page)

response = client.post("/add", data={"title": "Finish the web page"})
print(response.status_code, response.headers["Location"])

page = client.get("/", follow_redirects=True).get_data(as_text=True)
print("task is listed:", "Finish the web page" in page)
print("flash message shown:", "Task added." in page)

client.post("/add", data={"title": "   "})
page = client.get("/").get_data(as_text=True)
print("empty title rejected with a message:", "Please type a task." in page)

client.post("/toggle/1")
page = client.get("/").get_data(as_text=True)
print("marked done:", 'class="done"' in page)
print("task count shown:", "My tasks (1)" in page)
```

```output
empty page shows the hint: True
302 /
task is listed: True
flash message shown: True
empty title rejected with a message: True
marked done: True
task count shown: True
```

## Safe by default

User text is shown inside the page. Jinja **escapes** it, so a malicious task title cannot run code in another browser:

```python
client.post("/add", data={"title": "<script>alert('hacked')</script>"})
page = client.get("/").get_data(as_text=True)
print("raw script tag in the page:", "<script>alert" in page)
print("escaped text in the page  :", "&lt;script&gt;alert" in page)
```

```output
raw script tag in the page: False
escaped text in the page  : True
```

The script is displayed as plain text. Never mark user text with `|safe`.

## CSRF protection

Any page with a form that changes data needs **CSRF protection**: a hidden token that proves the form came from your own site. In a real app add **Flask-WTF** (`CSRFProtect(app)`) and put `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` in each form. The Security lesson in the Flask course explains why.

## Making it look good

| Step | Tool |
| --- | --- |
| a responsive layout and clean styling quickly | **Bootstrap** or **Tailwind CSS** through a CDN link in `base.html` |
| small interactions without reloading | a little JavaScript with `fetch` calling your JSON API |
| a modern single-page front end | **React** calling the same `/api/tasks` endpoints |

Your API and your pages share the same data, which is why the two lessons were kept separate: you can later replace the HTML pages with React and keep everything else.

## Checklist for this step

| Check | |
| --- | --- |
| the page lists tasks, with an empty-state message | |
| adding with an empty title shows a friendly error | |
| refreshing after adding does not duplicate | |
| user text is escaped | |
| the page works on a phone-size screen | |
