---
title: Testing Django projects
summary: Write tests with Django's TestCase and test client, cover views, models and permissions, and run them with one command.
takeaways:
- TestCase gives every test a clean database that rolls back afterwards
- The test Client acts like a browser: it logs in, posts forms and keeps cookies
- Test the happy path, validation, permissions and edge cases
---
## Tests that clean up after themselves

Django's `TestCase` creates a **test database** and wraps each test in a transaction that is rolled back, so tests never affect each other or your real data.

```py
python manage.py test                  # run everything
python manage.py test courses          # one app
python manage.py test courses.tests.CourseTests.test_list   # one test
```

## A full example

This runs a real `TestCase` against the demo project:

```python
import unittest
from django.contrib.auth import get_user_model
from django.db import models, connection
from django.http import JsonResponse
from django.test import TestCase
from django.urls import path, reverse
from django.contrib.auth.decorators import login_required

class Course(models.Model):
    title = models.CharField(max_length=60)
    published = models.BooleanField(default=True)

    def short_title(self):
        return self.title[:10]

with connection.schema_editor() as editor:
    editor.create_model(Course)

def course_list(request):
    titles = list(Course.objects.filter(published=True).values_list("title", flat=True))
    return JsonResponse({"courses": titles})

@login_required(login_url="/login/")
def my_page(request):
    return JsonResponse({"user": request.user.username})

urlpatterns = [path("courses/", course_list, name="courses"), path("me/", my_page, name="me")]

class CourseTests(TestCase):
    @classmethod
    def setUpTestData(cls):                         # runs once; data is shared and protected by rollbacks
        Course.objects.create(title="Python")
        Course.objects.create(title="Hidden draft", published=False)
        cls.user = get_user_model().objects.create_user(username="asha", password="pass-12345")

    def test_list_shows_only_published_courses(self):
        response = self.client.get(reverse("courses"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"courses": ["Python"]})

    def test_my_page_needs_login(self):
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/login/"))

    def test_logged_in_user_sees_their_page(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("me")).json(), {"user": "asha"})

    def test_model_method(self):
        self.assertEqual(Course(title="A very long title").short_title(), "A very lon")

suite = unittest.defaultTestLoader.loadTestsFromTestCase(CourseTests)
import io
result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
print("tests run:", result.testsRun, "| failures:", len(result.failures), "| errors:", len(result.errors), "| passed:", result.wasSuccessful())
```

```output
tests run: 4 | failures: 0 | errors: 0 | passed: True
```

## The test client

| Call | Does |
| --- | --- |
| `self.client.get(url)` / `.post(url, data)` | send a request |
| `self.client.get(url, follow=True)` | follow redirects to the final page |
| `self.client.force_login(user)` | log in without a password |
| `self.client.post(url, data, content_type="application/json")` | send JSON |
| `response.status_code`, `.json()`, `.content`, `.context` | inspect the result |
| `self.assertContains(response, "text")` | the page has this text (and a 200 status) |
| `self.assertRedirects(response, "/next/")` | redirected to the right place |
| `self.assertTemplateUsed(response, "x.html")` | the right template was used |

## What to test

| Area | Examples |
| --- | --- |
| Happy path | list shows the new course; create saves a row |
| Validation | bad input gives errors and saves nothing |
| Permissions | anonymous gets redirected; a student cannot reach admin pages |
| Object ownership | user A cannot open user B's order (expect 404 or 403) |
| Edge cases | empty lists, the last page, duplicates, huge values |
| Query counts | `with self.assertNumQueries(2):` keeps N+1 from creeping in |

```py
def test_list_uses_two_queries(self):
    with self.assertNumQueries(2):
        self.client.get(reverse("course-list"))
```

:::tip
Use **factory_boy** or small helper functions to build test data. Keep tests fast, because developers run them constantly. For speed, use `setUpTestData` for shared data and `pytest-django` with `--reuse-db` if the suite grows large.
:::

:::interview
**Interviewers often ask:** "How do you test a Django view?" Use `TestCase` with the test client: create data in `setUp` or `setUpTestData`, send a request, and assert the status code, content, redirects and database changes. Also test permissions and `assertNumQueries`.
:::
