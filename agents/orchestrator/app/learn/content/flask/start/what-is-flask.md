---
title: What is Flask?
summary: Flask is a small Python web framework. See what a web framework does, why Flask is popular, and when to choose it.
takeaways:
- A web framework turns HTTP requests into Python function calls
- Flask is a micro-framework: a small core, with extensions you add as needed
- Flask gives you freedom; Django gives you more built in
---
## What a web server really does

When your browser opens a page, it sends an **HTTP request** ("GET /courses") to a server. The server runs some code and sends back an **HTTP response**: HTML, JSON, an image or an error. A **web framework** handles the plumbing so you only write the part in the middle.

| Browser sends | Your code decides | Server returns |
| --- | --- | --- |
| `GET /courses` | which courses to show | an HTML page |
| `POST /login` | whether the password is right | a redirect, or an error |
| `GET /api/users/7` | what user 7 looks like | JSON |

## Flask in one sentence

**Flask** is a lightweight Python framework that connects URLs to Python functions. Its core is small (routing, requests, responses, templates), and everything else (databases, login, forms, admin) comes from extensions you choose.

| | Flask | Django |
| --- | --- | --- |
| Style | micro-framework: you choose the parts | batteries included |
| Best for | APIs, small to medium apps, learning, custom designs | large apps with admin, auth and ORM out of the box |
| Learning curve | gentle start | more to learn up front |
| Structure | your decision | a fixed project layout |

Neither is "better". Flask is a very good way to learn how the web works, because nothing is hidden.

## Install

```py
python -m venv .venv
.venv\Scripts\activate          # macOS and Linux: source .venv/bin/activate
pip install flask
```

Use a **virtual environment** (the first two lines) so each project has its own packages.

## The smallest Flask app

```python
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello from Flask!"

client = app.test_client()          # a pretend browser, used here so you can run this anywhere
response = client.get("/")
print(response.status_code)
print(response.data.decode())
```

```output
200
Hello from Flask!
```

Three things happened:

1. `Flask(__name__)` created the application.
2. `@app.route("/")` told Flask: "when someone asks for `/`, call `home()`".
3. `home()` returned a string, which Flask turned into a response with status 200.

## What this course covers

| Part | You will learn |
| --- | --- |
| Basics | routes, templates, forms, sessions |
| Structure | the application factory, blueprints, configuration |
| Data | SQLAlchemy models, relationships, migrations |
| APIs | JSON endpoints, validation, authentication |
| Advanced | hooks, testing, security, caching, deployment |

:::note
Flask does not allow **new routes after the app has served its first request**, and raises an `AssertionError` if you try. In a real project all routes are defined first, then the app runs. In these lessons we add a route, call it, then add the next one so you can see each result, so when you copy code into a file, put all the routes **above** the `client` calls.
:::

:::tip
Every code box in this course that uses `app.test_client()` runs as is, with no server. The `test_client` sends requests to your app directly, which is also how you will test real projects.
:::
