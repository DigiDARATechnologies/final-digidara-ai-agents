---
title: Django interview questions
summary: Django questions from basic to advanced, with short answers you can say aloud.
kind: qa
takeaways:
- Know MVT, the request flow, models and migrations, and the ORM
- Be ready to explain select_related, prefetch_related and the N+1 problem
- Have clear security, testing and deployment answers
---
### Q [Easy] What is Django and what does "batteries included" mean?
A high-level Python web framework. "Batteries included" means common needs come built in: ORM, migrations, admin, authentication, forms, templates, sessions and security protections, so you do not need to assemble them from separate libraries.

### Q [Easy] Explain the MVT pattern.
Model (data and database access), View (the request handling logic that returns a response) and Template (the HTML presentation). Django's own URL dispatcher plays the controller role by routing a URL to a view.

### Q [Easy] What is the difference between a project and an app?
A project is the whole website with its settings and root URLs. An app is a self-contained feature (accounts, courses) with its own models, views and templates, meant to be reusable. A project contains many apps listed in `INSTALLED_APPS`.

### Q [Easy] What does `manage.py` do?
It is the command-line utility for the project: `runserver`, `makemigrations`, `migrate`, `createsuperuser`, `shell`, `test`, `collectstatic` and more. It sets the settings module for you.

### Q [Medium] What happens when a request reaches Django?
The server passes it through the middleware stack, the URL resolver matches the path to a view, the view runs (using models and templates) and returns a response, which travels back up through the middleware to the client.

### Q [Medium] What are migrations and what is the difference between `makemigrations` and `migrate`?
Migrations are versioned files that record changes to your models so the database schema can be updated consistently. `makemigrations` creates the migration files from model changes; `migrate` applies them to the database.

### Q [Medium] What is a QuerySet and why is it lazy?
A QuerySet represents a database query. It is lazy because it does not run until you use it (iterate, slice with a step, `len`, `list`, `bool`). That lets you chain `filter`, `exclude` and `order_by` and run one combined query, and results are cached on the QuerySet after evaluation.

### Q [Medium] What is the difference between `null=True` and `blank=True`?
`null=True` lets the database store NULL for the column. `blank=True` lets forms and validation accept an empty value. For text fields, prefer `blank=True` with an empty string rather than NULL.

### Q [Medium] How do `ForeignKey`, `OneToOneField` and `ManyToManyField` differ?
`ForeignKey` is many-to-one (many students, one department). `OneToOneField` is one-to-one (a user and a profile). `ManyToManyField` is many-to-many (students and courses) and uses a hidden join table, or a custom `through` model when the link needs extra data.

### Q [Hard] What is the N+1 problem and how does Django solve it?
Loading N objects and then running one extra query for each to read a related object, giving N+1 queries. `select_related` fetches single-valued relations (ForeignKey, OneToOne) in one query with a JOIN. `prefetch_related` runs a second query for multi-valued relations (ManyToMany, reverse FK) and joins in Python.

### Q [Medium] What is the difference between function-based and class-based views?
A function-based view is a plain function taking a request. A class-based view organises handling into methods and supports inheritance and mixins; generic views (`ListView`, `CreateView`) implement common CRUD patterns. Function views are simpler to read; CBVs reduce repetition.

### Q [Medium] What is middleware?
A layer of code that wraps every request and response, in the order listed in `MIDDLEWARE`. Used for sessions, authentication, CSRF protection, security headers, logging and similar cross-cutting work. A middleware can also return a response early and skip the view.

### Q [Medium] What are Django signals and when would you avoid them?
Signals notify listeners of events such as `post_save`. They decouple code but hide control flow, make debugging harder, and are not triggered by bulk operations like `bulk_create` or `update()`. For core business logic prefer explicit function calls.

### Q [Medium] How does Django protect against CSRF?
`CsrfViewMiddleware` requires a secret token on unsafe requests (POST, PUT, DELETE). Forms include it through `{% csrf_token %}`, and JavaScript sends it in the `X-CSRFToken` header. Requests without a valid token get a 403.

### Q [Medium] How does Django protect against SQL injection and XSS?
The ORM uses parameterised queries so input cannot change the SQL. Templates autoescape variables so user text cannot run as HTML or script. Avoid raw SQL built with f-strings and avoid `|safe` or `mark_safe` on user input.

### Q [Medium] How does Django authentication work?
`authenticate()` checks credentials against hashed passwords (PBKDF2 by default), `login()` stores the user id in the session, and `AuthenticationMiddleware` sets `request.user`. Authorisation uses permissions and groups with `login_required`, `permission_required` or mixins.

### Q [Medium] Why should you use a custom user model from the start?
Changing `AUTH_USER_MODEL` after the first migration is very hard because other tables reference the user table. Starting with a subclass of `AbstractUser` costs nothing and allows adding fields later.

### Q [Medium] What is the difference between a Form and a ModelForm?
A `Form` declares its own fields. A `ModelForm` builds fields and validation from a model and can save an instance with `save()`. Always set `fields` explicitly to avoid exposing sensitive columns.

### Q [Hard] How would you build a REST API in Django?
With Django REST Framework: serializers to validate and convert data, `ModelViewSet` or `APIView` for logic, a router for URLs, plus authentication (session or JWT), permissions, pagination and throttling. Filter querysets by the current user and set owner fields on the server.

### Q [Hard] How would you improve the performance of a slow Django application?
Measure first with the debug toolbar or query logging. Fix N+1 queries with `select_related` and `prefetch_related`, add database indexes, paginate, use `only`, `values` and `bulk_*` methods, cache expensive results with Redis, and move slow work to Celery.

### Q [Hard] How do you deploy and scale a Django project?
Run it with Gunicorn behind Nginx, set `DEBUG=False`, read secrets from the environment, use PostgreSQL, serve static files through Nginx or a CDN after `collectstatic`, run migrations on release, containerise with Docker, add health checks and monitoring, and scale out with several workers or instances behind a load balancer while keeping the app stateless (sessions and cache in Redis).

:::practice mock-interview
Practise explaining the N+1 problem, MVT and Django's security features aloud in a Mock Interview.
:::
