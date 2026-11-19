---
title: Authentication and permissions
summary: Use Django's built-in users, hashed passwords, login sessions, permissions and groups, and protect views.
takeaways:
- Django ships with a User model, secure password hashing and session login
- authenticate() checks credentials; login() starts the session
- login_required and permission_required protect views; use a custom user model from day one
---
## Users and passwords

Django stores users in `django.contrib.auth`. Passwords are **never** stored as text: Django saves a salted, slow hash.

```python
from django.contrib.auth import get_user_model, authenticate

User = get_user_model()
asha = User.objects.create_user(username="asha", email="asha@example.com", password="S3cret-pass")

print(asha.password.split("$")[0], asha.check_password("S3cret-pass"), asha.check_password("wrong"))
print(authenticate(username="asha", password="S3cret-pass") == asha)
print(authenticate(username="asha", password="nope"))
print(asha.is_active, asha.is_staff, asha.is_superuser)
```

```output
pbkdf2_sha256 True False
True
None
True False False
```

`create_user` hashes the password. Never assign `user.password = "text"`; call `user.set_password("text")`. `authenticate` returns the user, or `None` when the credentials are wrong.

## Logging in and out

```python
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import path
from django.test import Client

def sign_in(request):
    user = authenticate(request, username=request.POST.get("username"), password=request.POST.get("password"))
    if user is None:
        return JsonResponse({"error": "invalid_credentials"}, status=401)
    login(request, user)                                   # stores the user id in the session
    return JsonResponse({"ok": True})

def sign_out(request):
    logout(request)
    return JsonResponse({"ok": True})

@login_required(login_url="/login/")
def dashboard(request):
    return JsonResponse({"user": request.user.username})

urlpatterns = [path("sign-in/", sign_in), path("sign-out/", sign_out), path("dashboard/", dashboard)]

browser = Client()
response = browser.get("/dashboard/")
print(response.status_code, response["Location"])
print(browser.post("/sign-in/", {"username": "asha", "password": "wrong"}).status_code)
browser.post("/sign-in/", {"username": "asha", "password": "S3cret-pass"})
print(browser.get("/dashboard/").json())
browser.post("/sign-out/")
print(browser.get("/dashboard/").status_code)
```

```output
302 /login/?next=/dashboard/
401
{'user': 'asha'}
302
```

`@login_required` sends visitors who are not logged in to the login page (with `?next=` so they return afterwards). `request.user` is always available; for a visitor who is not logged in it is an `AnonymousUser`.

## Permissions and groups

Every model gets four permissions automatically: add, change, delete, view. You give them to users directly or, better, to **groups**:

```python
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.decorators import permission_required
from django.contrib.contenttypes.models import ContentType

ravi = User.objects.create_user(username="ravi", password="Pass-word-9")
print(ravi.has_perm("auth.change_user"))

editors = Group.objects.create(name="Editors")
editors.permissions.add(Permission.objects.get(codename="change_user"))
ravi.groups.add(editors)

ravi = User.objects.get(pk=ravi.pk)                        # permissions are cached on the object: reload it
print(ravi.has_perm("auth.change_user"), ravi.has_perm("auth.delete_user"))

@permission_required("auth.change_user", raise_exception=True)      # 403 instead of a redirect
def edit_users(request):
    return JsonResponse({"ok": True})

urlpatterns = [path("edit/", edit_users)]
other = User.objects.create_user(username="meena", password="Pass-word-9")
client = Client()
client.force_login(other)
print(client.get("/edit/").status_code)
client.force_login(ravi)
print(client.get("/edit/").status_code)
```

```output
False
True False
403
200
```

Notice the three outcomes: not logged in gets redirected, logged in without the permission gets **403**, and a user in the Editors group gets through. Superusers pass every permission check.

## Custom user model: decide on day one

```py
# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    phone = models.CharField(max_length=15, blank=True)
    college = models.CharField(max_length=100, blank=True)
```

```py
# settings.py
AUTH_USER_MODEL = "accounts.User"
```

Changing the user model after the first migration is painful. Even if you add nothing now, start every project with your own `User` that extends `AbstractUser`.

## Password rules and ready-made views

```py
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
```

```py
# urls.py: login, logout, password change and reset pages, already built
path("accounts/", include("django.contrib.auth.urls")),
```

You only supply the templates. For social login, email verification or two-factor, the usual add-on is **django-allauth**.

:::warning
`login_required` and permissions protect **views**. Always check that a user may touch the specific **object** too (`get_object_or_404(Order, pk=pk, owner=request.user)`), otherwise one user can read another's data by changing the id in the URL.
:::

:::interview
**Interviewers often ask:** "How does Django authentication work?" `authenticate()` verifies credentials against hashed passwords, `login()` stores the user id in the session, and the `AuthenticationMiddleware` puts the user on `request.user` for each request. Authorisation uses permissions, groups and decorators or mixins.
:::
