---
title: Class-based views
summary: Replace repeated view code with ListView, DetailView, CreateView and friends, and customise them with small overrides.
takeaways:
- Generic class-based views do the common list, detail, create, update and delete work
- You customise by setting attributes or overriding small methods
- Function views are still fine for simple or unusual pages
---
## Why class-based views

Most views repeat the same four steps: fetch objects, check the user, build a context, render. **Class-based views (CBVs)** package those steps, so you write only what is different.

## Setup

```python
from django.db import models, connection

class Course(models.Model):
    title = models.CharField(max_length=60)
    slug = models.SlugField(unique=True)
    published = models.BooleanField(default=True)

    def __str__(self):
        return self.title

with connection.schema_editor() as editor:
    editor.create_model(Course)

Course.objects.create(title="Python", slug="python")
Course.objects.create(title="Flask", slug="flask")
Course.objects.create(title="Draft course", slug="draft", published=False)
```

## ListView and DetailView

```python
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.urls import path
from django.test import Client

class CourseList(ListView):
    model = Course
    paginate_by = 1

    def get_queryset(self):
        return Course.objects.filter(published=True).order_by("title")      # hide drafts

    def render_to_response(self, context, **kwargs):                       # JSON, so we can see the result here
        return JsonResponse({"titles": [c.title for c in context["object_list"]], "page": context["page_obj"].number})

class CourseDetail(DetailView):
    model = Course
    slug_field = "slug"

    def render_to_response(self, context, **kwargs):
        return JsonResponse({"title": self.object.title})

urlpatterns = [
    path("courses/", CourseList.as_view()),
    path("courses/<slug:slug>/", CourseDetail.as_view()),
]

client = Client()
print(client.get("/courses/").json())
print(client.get("/courses/?page=2").json())
print(client.get("/courses/flask/").json())
print(client.get("/courses/nothing/").status_code)
```

```output
{'titles': ['Flask'], 'page': 1}
{'titles': ['Python'], 'page': 2}
{'title': 'Flask'}
404
```

You wrote almost nothing, yet you got pagination, a 404 for missing objects and the context for the template. Normally you would not override `render_to_response`: the view would render `course_list.html` or `course_detail.html` by naming convention (`<app>/<model>_list.html`).

## Create, update, delete

```py
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin

class CourseCreate(LoginRequiredMixin, CreateView):
    model = Course
    fields = ["title", "slug", "published"]
    success_url = reverse_lazy("course-list")          # template: course_form.html

class CourseUpdate(LoginRequiredMixin, UpdateView):
    model = Course
    fields = ["title", "published"]
    success_url = reverse_lazy("course-list")

class CourseDelete(LoginRequiredMixin, DeleteView):
    model = Course
    success_url = reverse_lazy("course-list")          # template: course_confirm_delete.html
```

The mixin `LoginRequiredMixin` must come **first** in the class list. Each of these builds the form, validates it, saves and redirects.

## Customising with small overrides

| Override | Use for |
| --- | --- |
| `get_queryset()` | limit what the view can see (only this user's rows, only published) |
| `get_context_data()` | add extra values for the template |
| `form_valid(form)` | do something just before or after saving (set the owner) |
| `get_success_url()` | redirect somewhere that depends on the saved object |
| `dispatch()` | run a check before any method |

```py
class MyCourseList(LoginRequiredMixin, ListView):
    def get_queryset(self):
        return Course.objects.filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total"] = self.get_queryset().count()
        return context

class CourseCreate(LoginRequiredMixin, CreateView):
    model = Course
    fields = ["title", "slug"]

    def form_valid(self, form):
        form.instance.owner = self.request.user          # never trust an owner field from the form
        return super().form_valid(form)
```

## A plain View for custom logic

```python
from django.views import View

class Health(View):
    def get(self, request):
        return JsonResponse({"status": "ok"})

    def post(self, request):
        return JsonResponse({"error": "read only"}, status=405)

urlpatterns = [path("health/", Health.as_view())]
client = Client()
print(client.get("/health/").json(), client.post("/health/").status_code)
```

```output
{'status': 'ok'} 405
```

## Function or class?

| Choose a function view when | Choose a class-based view when |
| --- | --- |
| the page is simple or unusual | it is a standard list, detail, create, update or delete |
| you want every step visible | you want to reuse behaviour through mixins |
| the logic is one-off | several views share the same structure |

Neither is wrong. Many teams use generic CBVs for CRUD and functions for everything else.

:::interview
**Interviewers often ask:** "What are the advantages of class-based views?" Reuse through inheritance and mixins, built-in generic views for common CRUD, and a clear place for each step (`get_queryset`, `get_context_data`, `form_valid`). The cost is that the flow is less obvious than in a plain function.
:::
