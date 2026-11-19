---
title: Forms, sessions and flash messages
summary: Read form data, validate it, remember a user with the session cookie, and show one-time messages with flash.
takeaways:
- Validate every field on the server; browser checks are only a convenience
- The session stores small data in a signed cookie; set SECRET_KEY
- flash shows a message once, after a redirect
---
## Reading and validating a form

```python
from flask import Flask, request, session, redirect, url_for, flash, render_template_string, get_flashed_messages

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-only-change-me"       # signs the session cookie

@app.route("/signup", methods=["POST"])
def signup():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    errors = []
    if len(name) < 2:
        errors.append("Name must have at least 2 letters.")
    if "@" not in email or "." not in email.split("@")[-1]:
        errors.append("Please enter a valid email address.")
    if errors:
        return {"ok": False, "errors": errors}, 400
    return {"ok": True, "name": name.title(), "email": email}, 201

client = app.test_client()
print(client.post("/signup", data={"name": "A", "email": "nope"}).get_json())
print(client.post("/signup", data={"name": " asha k ", "email": "ASHA@Example.com"}).get_json())
```

```output
{'errors': ['Name must have at least 2 letters.', 'Please enter a valid email address.'], 'ok': False}
{'email': 'asha@example.com', 'name': 'Asha K', 'ok': True}
```

:::warning
Always validate **on the server**. HTML attributes like `required` and `type="email"` help honest users, but anyone can skip them by sending a request directly.
:::

## The session

`session` behaves like a dictionary that **remembers the user between requests**. Flask stores it in a cookie that is **signed** with `SECRET_KEY`: the user can read it but cannot change it without detection.

```python
@app.route("/login", methods=["POST"])
def login():
    session["user"] = request.form["name"]
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return f"Welcome back, {session['user']}"

@app.route("/login-page")
def login_page():
    return "Please log in"

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

browser = app.test_client()
print(browser.get("/dashboard").headers["Location"])           # not logged in yet
browser.post("/login", data={"name": "Asha"})
print(browser.get("/dashboard").data.decode())                 # the cookie is remembered
browser.get("/logout")
print(browser.get("/dashboard").status_code)
```

```output
/login-page
Welcome back, Asha
302
```

A real `test_client` keeps cookies between requests, just like a browser.

| Item | Good for | Not good for |
| --- | --- | --- |
| `session` | the logged-in user's id, a small preference | anything secret or large (the user can **read** it) |
| a database | everything that must last or stay private | |

:::remember
The session cookie is **signed, not encrypted**. Never put a password or a card number in it. Store the user's **id** and look the details up in the database.
:::

## Flash messages

A **flash** is a message shown **once**, usually after a redirect: "Saved!", "Wrong password."

```python
@app.route("/save", methods=["POST"])
def save():
    flash("Your profile was saved.", "success")
    return redirect(url_for("profile"))

@app.route("/profile")
def profile():
    return render_template_string(
        "{% for category, message in get_flashed_messages(with_categories=true) %}"
        "<div class='{{ category }}'>{{ message }}</div>{% endfor %}<p>Profile</p>"
    )

b = app.test_client()
b.post("/save")
print(b.get("/profile").data.decode())
print(b.get("/profile").data.decode())       # a second visit: the flash is gone
```

```output
<div class='success'>Your profile was saved.</div><p>Profile</p>
<p>Profile</p>
```

## CSRF protection

A forged page on another website could make a logged-in user's browser submit your form. Protect state-changing forms with a **CSRF token**, a hidden random value your server checks. The **Flask-WTF** extension does this (`pip install flask-wtf`):

```py
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)
```

```py
<form method="post">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  ...
</form>
```

Flask-WTF also provides `FlaskForm` classes with built-in validators, which are worth using on larger projects. The security lesson returns to this.
