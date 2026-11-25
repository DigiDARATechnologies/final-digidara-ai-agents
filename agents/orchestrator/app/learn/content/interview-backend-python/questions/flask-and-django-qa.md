---
title: Flask and Django questions
summary: Routing, request handling, ORM, migrations, middleware, authentication and choosing between Flask and Django.
kind: qa
takeaways:
- Know the structure of a Flask and a Django project
- Explain ORM, migrations and middleware
- Compare the two frameworks with a reasoned choice
---
### Q [Easy] What is Flask?
A lightweight Python **micro-framework** for web apps and APIs. It gives routing and request handling and lets you choose the rest (database, forms, auth) through extensions.

### Q [Easy] What is Django?
A **batteries-included** Python framework with an ORM, admin panel, authentication, forms, templates and security features built in.

### Q [Medium] Flask vs Django?
Flask: small, flexible, you assemble the parts, good for APIs and small services. Django: opinionated and full-featured, faster to build large database-driven sites. Choose by project size and how much structure you want.

### Q [Medium] How does routing work in Flask?
```python
@app.route("/students/<int:student_id>", methods=["GET"])
def get_student(student_id):
    return {"id": student_id}
```
The decorator maps a URL pattern and methods to a function; `<int:...>` captures a typed part of the URL.

### Q [Medium] What is the `request` object in Flask?
It holds the incoming request data: `request.args` (query string), `request.form` (form data), `request.json` (JSON body), `request.headers`, and more. It is available during a request.

### Q [Medium] What is the application context vs request context?
The **application context** gives access to the app (config, extensions) and the **request context** gives access to the current request. Both are created automatically while handling a request.

### Q [Medium] What are Blueprints in Flask?
A way to organise an app into modules, each with its own routes, which are registered on the app. They help structure large projects.

### Q [Medium] What is the Django MVT pattern?
**Model** (data), **View** (logic that handles a request), **Template** (HTML). Django's URL configuration sends a URL to a view.

### Q [Medium] What is the Django ORM?
It lets you work with the database using Python classes instead of SQL: `Student.objects.filter(marks__gte=75).order_by("-marks")`.

### Q [Medium] What are migrations?
Files that describe changes to your models (new field, new table) so the database schema can be updated in a controlled, versioned way: `makemigrations` creates them and `migrate` applies them.

### Q [Medium] What is middleware?
Code that sits between the request and the view (and between the view and the response), for tasks like authentication, sessions, logging and security headers.

### Q [Medium] What are `select_related` and `prefetch_related`?
They fix the **N+1 query** problem. `select_related` follows foreign keys with a SQL join. `prefetch_related` runs a second query and joins in Python (good for many-to-many and reverse relations).

### Q [Medium] What is CSRF protection in Django?
Django includes a CSRF token in forms (`{% csrf_token %}`) and checks it on unsafe requests to stop forged cross-site requests.

### Q [Hard] How do you build a REST API in Django?
Use **Django REST Framework**: serializers convert models to JSON and validate input, viewsets and routers provide CRUD endpoints, and authentication, permissions and throttling are built in.

### Q [Hard] How do you deploy a Flask or Django app?
Run it with a production server (**Gunicorn** or uWSGI) behind **Nginx**, set `DEBUG` off, use environment variables for secrets, use a real database, serve static files properly, and use HTTPS and logging.
