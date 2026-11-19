---
title: Routing and the request object
summary: Capture parts of the URL, handle GET and POST, read query strings and JSON, redirect, and build URLs with url_for.
takeaways:
- Angle brackets in a route capture a value, with an optional converter such as <int:id>
- methods=[...] limits which HTTP methods a route accepts
- request holds the incoming data; url_for builds URLs so they never go stale
---
## Routes with variables

```python
from flask import Flask, request, redirect, url_for

app = Flask(__name__)

@app.route("/courses/<slug>")
def course(slug):
    return f"Course: {slug}"

@app.route("/users/<int:user_id>")
def user(user_id):
    return f"User number {user_id} (type {type(user_id).__name__})"

client = app.test_client()
print(client.get("/courses/python").data.decode())
print(client.get("/users/7").data.decode())
print(client.get("/users/abc").status_code)
```

```output
Course: python
User number 7 (type int)
404
```

`<int:user_id>` only matches whole numbers and passes an `int` to your function, so `/users/abc` becomes a 404 without any code from you.

| Converter | Matches |
| --- | --- |
| `<name>` or `<string:name>` | any text without a slash |
| `<int:n>` | whole numbers |
| `<float:n>` | decimals |
| `<path:p>` | text that may contain slashes |
| `<uuid:id>` | a UUID |

## HTTP methods

A route accepts only GET unless you say otherwise:

```python
@app.route("/greet", methods=["GET", "POST"])
def greet():
    if request.method == "POST":
        return f"Hello, {request.form.get('name', 'stranger')}! (POST)"
    return "Send me a name with POST."

print(client.get("/greet").data.decode())
print(client.post("/greet", data={"name": "Asha"}).data.decode())
print(client.put("/greet").status_code)
```

```output
Send me a name with POST.
Hello, Asha! (POST)
405
```

An unsupported method gives **405 Method Not Allowed**.

## Reading the request

```python
@app.route("/search")
def search():
    term = request.args.get("q", "")                  # ?q=flask
    page = request.args.get("page", 1, type=int)      # ?page=2, converted to int
    return {"term": term, "page": page}

@app.route("/echo", methods=["POST"])
def echo():
    data = request.get_json(silent=True)              # None if the body is not valid JSON
    return {"you_sent": data, "agent": request.headers.get("User-Agent", "unknown")[:10]}

print(client.get("/search?q=flask&page=2").get_json())
print(client.post("/echo", json={"a": 1}, headers={"User-Agent": "demo-client"}).get_json())
```

```output
{'page': 2, 'term': 'flask'}
{'agent': 'demo-clien', 'you_sent': {'a': 1}}
```

| You want | Use |
| --- | --- |
| a query string value (`?q=`) | `request.args.get("q")` |
| form fields | `request.form.get("name")` |
| a JSON body | `request.get_json()` |
| uploaded files | `request.files["photo"]` |
| a header | `request.headers.get("Authorization")` |
| a cookie | `request.cookies.get("theme")` |

## Redirects and url_for

Never type URLs by hand inside your code. `url_for` builds them from the **function name**, so renaming a route cannot break a link:

```python
@app.route("/old-page")
def old_page():
    return redirect(url_for("course", slug="python"))      # 302 to /courses/python

with app.test_request_context():
    print(url_for("course", slug="flask"))
    print(url_for("user", user_id=3))
    print(url_for("search", q="numpy", page=2))

r = client.get("/old-page")
print(r.status_code, r.headers["Location"])
```

```output
/courses/flask
/users/3
/search?q=numpy&page=2
302 /courses/python
```

Extra keyword arguments that are not part of the route become the query string.

:::tip
After a successful POST (saving a form, for example), **redirect** to a GET page instead of rendering directly. Then refreshing the page does not submit the form a second time. This is the Post/Redirect/Get pattern.
:::
