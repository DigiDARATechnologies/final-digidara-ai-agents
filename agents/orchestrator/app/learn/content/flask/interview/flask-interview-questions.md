---
title: Flask interview questions
summary: Flask questions from basic to advanced, with short answers you can say aloud.
kind: qa
takeaways:
- Know routing, request and response, templates and the application context
- Be ready to explain the factory pattern, blueprints and the N+1 problem
- Have a security and deployment answer ready
---
### Q [Easy] What is Flask, and how does it differ from Django?
Flask is a lightweight (micro) Python web framework with a small core and a choice of extensions. Django is a full-stack framework with an ORM, admin, authentication and a fixed structure included. Flask gives more freedom; Django gives more built in.

### Q [Easy] What is a route, and how do you define one?
A mapping from a URL to a Python function. `@app.route("/users/<int:id>", methods=["GET"])` above a function. In Flask 2 and later you can write `@app.get(...)`, `@app.post(...)` and so on.

### Q [Easy] What is the difference between GET and POST?
GET reads data and puts parameters in the URL, so it should have no side effects. POST sends data in the request body and is used to create or change data.

### Q [Easy] What is Jinja2?
Flask's template engine. It mixes HTML with `{{ }}` expressions, `{% %}` statements, filters and template inheritance, and it **autoescapes** output to prevent XSS.

### Q [Medium] What is the application context and the request context?
The **request context** holds `request` and `session` for the request being handled. The **application context** holds `current_app` and `g`. Flask pushes them automatically during a request. In scripts and tests you push the app context yourself with `with app.app_context():`.

### Q [Medium] What is the `g` object?
A per-request storage space in the application context, used to share data (the current user, a database connection) between hooks and views during one request. It is reset for every request.

### Q [Medium] What is the application factory pattern and why use it?
A function `create_app(config)` that builds and returns a new Flask app. It avoids circular imports, lets you have different configurations (tests, development, production), and lets tests create a fresh app each time.

### Q [Medium] What are blueprints?
A way to split an app into reusable groups of routes, templates and static files, registered on the app with an optional URL prefix. They keep large projects organised.

### Q [Medium] How do you handle configuration and secrets?
Use `app.config` loaded from config classes or environment variables. Secrets such as `SECRET_KEY` and the database URL come from the environment or a secrets manager, never from source control.

### Q [Medium] How do sessions work in Flask?
By default, session data is stored in a **cookie signed** with `SECRET_KEY`. The user can read it but cannot alter it without detection. It is not encrypted, so do not store secrets in it. For larger or private data, use server-side sessions (Flask-Session) or a database.

### Q [Medium] What is the difference between `before_request` and `after_request`?
`before_request` runs before each request, and may return a response to stop it (used for authentication checks). `after_request` runs after the view with the response, and must return a response (used to add headers or log).

### Q [Medium] How do you connect Flask to a database?
Usually with SQLAlchemy through Flask-SQLAlchemy: define models as classes, call `db.init_app(app)`, and use `db.session` to add, query and commit. Use Flask-Migrate (Alembic) for schema changes.

### Q [Hard] What is the N+1 query problem and how do you fix it in SQLAlchemy?
Loading a list of N parents and then running one extra query for each parent's related rows, giving N+1 queries. Fix it with eager loading (`selectinload` or `joinedload`) so the related data is loaded in one or two queries.

### Q [Medium] How do you protect a Flask app against SQL injection and XSS?
Use the ORM or parameterised queries so input is never concatenated into SQL. Keep Jinja autoescaping on and never mark user content `|safe`. Add CSRF tokens, secure cookie flags and a Content-Security-Policy.

### Q [Medium] How do you hash passwords?
With a slow salted algorithm: `werkzeug.security.generate_password_hash` and `check_password_hash`, or `argon2` or `bcrypt`. Never store plain text or a fast hash like MD5.

### Q [Medium] How do you test a Flask application?
With `pytest`, an application factory, fixtures that create an app with an in-memory database, and the `test_client` to call endpoints and assert on status codes and JSON.

### Q [Hard] Flask is single-threaded in development. How does it handle many requests in production?
In production it runs under a WSGI server such as Gunicorn, which starts several worker processes (and optionally threads or async workers), usually behind Nginx. Each worker handles requests, so the app serves many at once.

### Q [Hard] How would you run a slow task such as sending email without blocking the request?
Put it in a background queue, for example Celery or RQ with Redis. The view enqueues the job and returns immediately, and a separate worker process does the work, with retries. Pass IDs rather than objects, and make the task idempotent.

### Q [Hard] How do you scale a Flask API?
Keep the app stateless (sessions in Redis or tokens), run many Gunicorn workers behind a load balancer, cache hot reads, fix slow queries with indexes and eager loading, paginate lists, move slow work to queues, and add monitoring.

:::practice mock-interview
Practise explaining the application factory, blueprints and the N+1 problem aloud in a Mock Interview.
:::
