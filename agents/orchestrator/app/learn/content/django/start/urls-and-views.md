---
title: URLs and views
summary: Map URLs to views, capture values from the path, read the request, return text, JSON and redirects, and avoid hard-coded links with reverse.
takeaways:
- urlpatterns map URLs to views; path converters capture typed values
- A view takes a request and returns a response
- Name your URLs and use reverse or {% url %} instead of typing paths
---
## The URL map

```python
from django.http import HttpResponse, JsonResponse
from django.urls import path, reverse
from django.test import Client

def course(request, slug):
    return JsonResponse({"course": slug})

def student(request, student_id):
    return HttpResponse(f"Student number {student_id} (type {type(student_id).__name__})")

urlpatterns = [
    path("courses/<slug:slug>/", course, name="course"),
    path("students/<int:student_id>/", student, name="student"),
]

client = Client()
print(client.get("/courses/python/").json())
print(client.get("/students/7/").content.decode())
print(client.get("/students/abc/").status_code)
```

```output
{'course': 'python'}
Student number 7 (type int)
404
```

`<int:student_id>` only matches whole numbers and hands your view an `int`, so `/students/abc/` becomes a 404 with no code from you.

| Converter | Matches |
| --- | --- |
| `<str:name>` (default) | any text without a slash |
| `<int:id>` | whole numbers |
| `<slug:slug>` | letters, numbers, hyphens, underscores |
| `<uuid:id>` | a UUID |
| `<path:p>` | any text including slashes |

## Reading the request

```python
def search(request):
    term = request.GET.get("q", "")                      # ?q=django
    page = int(request.GET.get("page", 1))
    return JsonResponse({"term": term, "page": page, "method": request.method})

def echo(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    return JsonResponse({"form": request.POST.get("name"), "agent": request.headers.get("User-Agent", "")[:6]})

urlpatterns = [path("search/", search, name="search"), path("echo/", echo, name="echo")]

client = Client()
print(client.get("/search/?q=django&page=2").json())
print(client.post("/echo/", {"name": "Asha"}, HTTP_USER_AGENT="tester").json())
print(client.get("/echo/").status_code)
```

```output
{'term': 'django', 'page': 2, 'method': 'GET'}
{'form': 'Asha', 'agent': 'tester'}
405
```

| You want | Use |
| --- | --- |
| a query string value | `request.GET.get("q")` |
| a form field | `request.POST.get("name")` |
| the HTTP method | `request.method` |
| a header | `request.headers.get("Authorization")` |
| the logged-in user | `request.user` |
| a JSON body | `json.loads(request.body)` |
| uploaded files | `request.FILES["photo"]` |

## Redirects and reverse

Name every URL, then build links from the **name**. If you change a URL later, nothing breaks:

```python
from django.shortcuts import redirect

def old_page(request):
    return redirect("course", slug="python")            # builds /courses/python/ from the name

def home(request):
    return HttpResponse("home")

urlpatterns = [
    path("", home, name="home"),
    path("courses/<slug:slug>/", course, name="course"),
    path("old/", old_page),
]

print(reverse("course", kwargs={"slug": "flask"}))
response = Client().get("/old/")
print(response.status_code, response["Location"])
```

```output
/courses/flask/
302 /courses/python/
```

In a template you do the same with `{% url 'course' slug='flask' %}`.

## Including an app's URLs

In a real project each app has its own `urls.py`, and the root file includes them:

```py
# courses/urls.py
from django.urls import path
from . import views

app_name = "courses"                       # a namespace: reverse("courses:detail", ...)
urlpatterns = [
    path("", views.course_list, name="list"),
    path("<slug:slug>/", views.course_detail, name="detail"),
]
```

```py
# config/urls.py
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("courses/", include("courses.urls")),
]
```

## Errors and shortcuts

```python
from django.http import Http404
from django.shortcuts import get_object_or_404

def lesson(request, number):
    if number > 3:
        raise Http404("No such lesson")                     # shown as the 404 page
    return HttpResponse(f"Lesson {number}")

urlpatterns = [path("lessons/<int:number>/", lesson)]
client = Client()
print(client.get("/lessons/2/").status_code, client.get("/lessons/9/").status_code)
```

```output
200 404
```

`get_object_or_404(Model, pk=1)` does the same for database lookups, and you will use it constantly.

:::tip
Django adds a missing trailing slash for you (`/courses` redirects to `/courses/`) when `APPEND_SLASH` is on, which it is by default. Design your URLs with a trailing slash.
:::
