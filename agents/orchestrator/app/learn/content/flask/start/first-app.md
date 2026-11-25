---
title: Your first real app
summary: Run a Flask server, return text, HTML and JSON, and use debug mode safely.
takeaways:
- flask run starts the development server; debug mode reloads on every change
- A view function can return text, HTML, JSON or a (body, status) pair
- Never run debug mode on a public server
---
## Running a server

Put this in `app.py`:

```py
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>SkillDARA</h1><p>Hello!</p>"
```

Then start it from the terminal:

```py
flask --app app run --debug
```

Open http://127.0.0.1:5000 in your browser. With `--debug`, the server **restarts when you save the file** and shows a helpful error page with a traceback when something breaks.

:::warning
Debug mode lets anyone who can reach the page run code on your computer through the error page. Use it **only on your own machine**, never on a server other people can reach.
:::

## What a view can return

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/text")
def text():
    return "plain text"

@app.route("/html")
def html():
    return "<h1>A heading</h1>"

@app.route("/json")
def as_json():
    return {"name": "Asha", "marks": [92, 88]}       # a dict becomes JSON

@app.route("/created")
def created():
    return {"id": 7}, 201                            # (body, status code)

@app.route("/header")
def with_header():
    return "ok", 200, {"X-Course": "Flask"}          # (body, status, headers)

client = app.test_client()
for path in ["/text", "/html", "/json", "/created", "/header"]:
    r = client.get(path)
    print(path, r.status_code, r.content_type.split(";")[0], r.headers.get("X-Course"))
```

```output
/text 200 text/html None
/html 200 text/html None
/json 200 application/json None
/created 201 application/json None
/header 200 text/html Flask
```

A returned dict (or list) is turned into **JSON** automatically, with the right `Content-Type`.

## Status codes you will use

| Code | Meaning | When |
| --- | --- | --- |
| 200 | OK | a normal response |
| 201 | Created | a new record was saved |
| 204 | No Content | success, nothing to return (a delete) |
| 301 / 302 | Redirect | send the browser to another URL |
| 400 | Bad Request | the client sent something invalid |
| 401 | Unauthorized | not logged in |
| 403 | Forbidden | logged in but not allowed |
| 404 | Not Found | no such page or record |
| 500 | Server Error | a bug in your code |

## Missing pages

```python
r = client.get("/nothing-here")
print(r.status_code)
print("Not Found" in r.data.decode())
```

```output
404
True
```

Flask returns a 404 page on its own for any URL you did not define.

:::note
`flask run` is the **development** server. It is fine for learning but is not built to serve real traffic. The deployment lesson shows how to run Flask with Gunicorn behind Nginx.
:::
