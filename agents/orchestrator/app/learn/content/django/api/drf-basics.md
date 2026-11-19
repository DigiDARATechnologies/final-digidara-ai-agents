---
title: REST APIs with Django REST Framework
summary: Build a JSON API with serializers, viewsets, routers, validation, pagination and permissions.
takeaways:
- A serializer converts model objects to JSON and validates incoming JSON
- A ModelViewSet gives full CRUD in a few lines; a router creates the URLs
- Set permissions, pagination and throttling for every real API
---
## Why DRF

Django can return JSON by itself, but a real API needs validation, error formats, pagination, authentication and a browsable page. **Django REST Framework (DRF)** is the standard toolkit for that.

```py
pip install djangorestframework
```

```py
INSTALLED_APPS += ["rest_framework"]
```

## Serializers

A **serializer** turns a model object into plain data (to send as JSON) and checks data coming in:

```python
from django.db import models, connection
from rest_framework import serializers

class Student(models.Model):
    name = models.CharField(max_length=80)
    email = models.EmailField(unique=True)
    marks = models.PositiveIntegerField(default=0)

with connection.schema_editor() as editor:
    editor.create_model(Student)

class StudentSerializer(serializers.ModelSerializer):
    result = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["id", "name", "email", "marks", "result"]

    def get_result(self, obj):
        return "Pass" if obj.marks >= 50 else "Fail"

    def validate_marks(self, value):
        if value > 100:
            raise serializers.ValidationError("Marks cannot be more than 100.")
        return value

asha = Student.objects.create(name="Asha", email="asha@x.com", marks=92)
print(StudentSerializer(asha).data)

bad = StudentSerializer(data={"name": "", "email": "nope", "marks": 150})
print(bad.is_valid())
print({field: [str(e) for e in errors] for field, errors in bad.errors.items()})
```

```output
{'id': 1, 'name': 'Asha', 'email': 'asha@x.com', 'marks': 92, 'result': 'Pass'}
False
{'name': ['This field may not be blank.'], 'email': ['Enter a valid email address.'], 'marks': ['Marks cannot be more than 100.']}
```

The same class **reads** (object to dictionary) and **validates** (dictionary to object). `ModelSerializer` builds the fields and basic rules from the model.

## ViewSets and routers

```python
from rest_framework import viewsets
from rest_framework.routers import DefaultRouter
from rest_framework.test import APIClient

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.order_by("id")
    serializer_class = StudentSerializer

router = DefaultRouter()
router.register("students", StudentViewSet, basename="student")
urlpatterns = router.urls

api = APIClient()
print(api.post("/students/", {"name": "Ravi", "email": "ravi@x.com", "marks": 78}, format="json").status_code)
print(api.post("/students/", {"name": "Bad", "email": "bad@x.com", "marks": 500}, format="json").json())
print(api.get("/students/").json())
print(api.get("/students/2/").json())
print(api.patch("/students/2/", {"marks": 81}, format="json").json()["marks"])
print(api.delete("/students/2/").status_code, api.get("/students/2/").status_code)
```

```output
201
{'marks': ['Marks cannot be more than 100.']}
[{'id': 1, 'name': 'Asha', 'email': 'asha@x.com', 'marks': 92, 'result': 'Pass'}, {'id': 2, 'name': 'Ravi', 'email': 'ravi@x.com', 'marks': 78, 'result': 'Pass'}]
{'id': 2, 'name': 'Ravi', 'email': 'ravi@x.com', 'marks': 78, 'result': 'Pass'}
81
204 404
```

Six actions (list, create, retrieve, update, partial update, destroy) from about five lines, with correct status codes (201, 400, 200, 204, 404) and JSON error messages.

| Class | Gives you |
| --- | --- |
| `ModelViewSet` | list, create, retrieve, update, partial_update, destroy |
| `ReadOnlyModelViewSet` | list and retrieve only |
| `APIView` | full control: write `get`, `post` yourself |
| `@api_view(["GET"])` | a function-based API view |
| `@action(detail=True)` on a viewset | an extra endpoint such as `/students/3/certificate/` |

## Custom actions

```python
from rest_framework.decorators import action
from rest_framework.response import Response

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.order_by("id")
    serializer_class = StudentSerializer

    @action(detail=False, methods=["get"])
    def toppers(self, request):
        best = self.get_queryset().filter(marks__gte=80)
        return Response(StudentSerializer(best, many=True).data)

router = DefaultRouter()
router.register("students", StudentViewSet, basename="student")
urlpatterns = router.urls

Student.objects.create(name="Meena", email="meena@x.com", marks=85)
print([s["name"] for s in api.get("/students/toppers/").json()])
```

```output
['Asha', 'Meena']
```

## Pagination

```python
from rest_framework.pagination import PageNumberPagination

class SmallPages(PageNumberPagination):
    page_size = 2

class PagedStudents(viewsets.ReadOnlyModelViewSet):
    queryset = Student.objects.order_by("id")
    serializer_class = StudentSerializer
    pagination_class = SmallPages

router = DefaultRouter()
router.register("paged", PagedStudents, basename="paged")
urlpatterns = router.urls

body = api.get("/paged/").json()
print(body["count"], body["next"] is not None, [s["name"] for s in body["results"]])
```

```output
2 False ['Asha', 'Meena']
```

## Authentication and permissions

```py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",     # pip install djangorestframework-simplejwt
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "50/hour", "user": "1000/hour"},
}
```

```py
from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.owner == request.user

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return Order.objects.filter(owner=self.request.user)          # users only ever see their own rows

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)                      # the server sets the owner
```

:::warning
The default in DRF is **open to everyone**. Set `DEFAULT_PERMISSION_CLASSES` to `IsAuthenticated` globally, and relax it per view when needed. Filter querysets by the current user, and set owner fields on the server, never from request data.
:::

:::interview
**Interviewers often ask:** "What is a serializer in DRF?" A class that converts complex objects (model instances, querysets) to Python data for rendering as JSON, and converts incoming data back into validated Python types or model instances.
:::
