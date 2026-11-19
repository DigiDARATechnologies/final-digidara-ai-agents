---
title: Securing a Django project
summary: See Django's built-in protections against SQL injection, XSS, CSRF and clickjacking, and the settings that finish the job.
takeaways:
- Django protects by default: use the ORM, keep autoescaping on, keep CSRF middleware on
- Never build SQL from strings, never mark user input safe
- Run manage.py check --deploy before every release
---
## SQL injection

The ORM sends user input as **parameters**, so it cannot change the meaning of a query:

```python
from django.db import models, connection

class Account(models.Model):
    username = models.CharField(max_length=30)
    secret = models.CharField(max_length=30)

with connection.schema_editor() as editor:
    editor.create_model(Account)
Account.objects.create(username="asha", secret="asha-secret")
Account.objects.create(username="ravi", secret="ravi-secret")

attack = "x' OR '1'='1"

orm_result = list(Account.objects.filter(username=attack))                           # safe
bad_sql = f"SELECT * FROM demo_account WHERE username = '{attack}'"                  # DANGER: string building
unsafe_result = [row.username for row in Account.objects.raw(bad_sql)]
safe_raw = [row.username for row in Account.objects.raw("SELECT * FROM demo_account WHERE username = %s", [attack])]

print("ORM filter     :", orm_result)
print("f-string raw   :", unsafe_result)
print("parameterised  :", safe_raw)
```

```output
ORM filter     : []
f-string raw   : ['asha', 'ravi']
parameterised  : []
```

The f-string version leaked every account. The ORM and the parameterised raw query treated the attack as plain text. If you must write raw SQL, always pass values as parameters (`%s` with a list), never with an f-string.

## XSS: escaping in templates

```python
from django.template import Engine, Context
from django.utils.safestring import mark_safe

engine = Engine()
comment = "<img src=x onerror=steal()>"
print(engine.from_string("{{ c }}").render(Context({"c": comment})))
print(engine.from_string("{{ c|safe }}").render(Context({"c": comment})))
print(engine.from_string("{{ c }}").render(Context({"c": mark_safe(comment)})))
```

```output
&lt;img src=x onerror=steal()&gt;
<img src=x onerror=steal()>
<img src=x onerror=steal()>
```

The second and third lines are **live attack code**. `|safe` and `mark_safe()` tell Django "trust this", so use them only for text you wrote. To allow limited formatting from users, sanitise first with a library such as **nh3** or **bleach**.

## CSRF: forged form posts

A malicious website can make a logged-in user's browser submit a form to your site, and the browser attaches the user's cookies. Django's `CsrfViewMiddleware` blocks any POST that does not carry the secret token (`{% csrf_token %}` in your forms):

```python
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.test import Client
from django.urls import path

def transfer(request):
    return HttpResponse("money moved")

def form_page(request):
    return HttpResponse(get_token(request))

urlpatterns = [path("transfer/", transfer), path("form/", form_page)]
from django.test import override_settings
with override_settings(MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"]):
    strict = Client(enforce_csrf_checks=True)
    print("no token   :", strict.post("/transfer/").status_code)
    token = strict.get("/form/").content.decode()
    print("with token :", strict.post("/transfer/", {"csrfmiddlewaretoken": token}).status_code)
```

```output
no token   : 403
with token : 200
```

For JavaScript requests, send the token in the `X-CSRFToken` header. `@csrf_exempt` switches protection off for a view: avoid it, except for endpoints (like payment webhooks) that verify a signature instead.

## Passwords and the hasher

```python
from django.contrib.auth.hashers import make_password, check_password

stored = make_password("S3cret-pass")
print(stored.split("$")[0], stored.count("$"), check_password("S3cret-pass", stored))
```

```output
pbkdf2_sha256 3 True
```

Django hashes with PBKDF2 by default, with a random salt and many iterations. It can upgrade old hashes automatically when users log in. Do not weaken this setting.

## Security settings for production

```py
# settings.py (production)
DEBUG = False
ALLOWED_HOSTS = ["skilldara.example.com"]
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

SECURE_SSL_REDIRECT = True                    # http becomes https
SECURE_HSTS_SECONDS = 31536000                # browsers insist on https for a year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True                  # session cookie only over https
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True                # hidden from JavaScript (the default)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"                      # no embedding in other sites (clickjacking)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")      # when behind Nginx or a load balancer
```

## Let Django audit you

```py
python manage.py check --deploy
```

It lists settings that are unsafe for production. This is what it reports for the demo project's current settings:

```python
from django.core.checks import run_checks

issues = run_checks(include_deployment_checks=True)
print(sorted({issue.id for issue in issues if issue.id.startswith("security")}))
```

```output
['security.W001', 'security.W002', 'security.W003', 'security.W009', 'security.W012']
```

Each id is a specific warning (for example `security.W009`: the `SECRET_KEY` is weak, `security.W012`: the session cookie is not marked secure). Which ones appear depends on your settings and installed middleware. Run the real command before every release and fix everything it lists.

## A checklist

| Risk | Defence |
| --- | --- |
| SQL injection | the ORM; parameters in raw SQL |
| XSS | autoescaping on; never `\|safe` on user input; sanitise rich text |
| CSRF | `CsrfViewMiddleware` and `{% csrf_token %}` |
| Clickjacking | `X-Frame-Options` middleware |
| Stolen sessions | secure, HttpOnly cookies and HTTPS |
| Weak passwords | built-in validators and PBKDF2 or Argon2 |
| Leaked secrets | environment variables, never in Git |
| Broken access control | check object ownership, not just login |
| Old libraries | update Django (security releases) and run `pip-audit` |

:::interview
**Interviewers often ask:** "What security features does Django give you by default?" The ORM guards against SQL injection, template autoescaping against XSS, CSRF middleware against forged posts, clickjacking protection through `X-Frame-Options`, hashed passwords, and host header validation through `ALLOWED_HOSTS`. Production settings (HTTPS, secure cookies, HSTS) must still be turned on.
:::
