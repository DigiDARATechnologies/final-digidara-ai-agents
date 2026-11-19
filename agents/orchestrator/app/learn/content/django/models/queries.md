---
title: The ORM: querying data
summary: Filter, order, combine conditions, aggregate, update and delete with QuerySets, and see the SQL they produce.
takeaways:
- A QuerySet is lazy: the database is queried only when you use the result
- filter, exclude, Q, F, annotate and aggregate cover most needs
- Use update, bulk_create and get_or_create instead of looping over save()
---
## Set up some data

```python
from django.db import models, connection

class Student(models.Model):
    name = models.CharField(max_length=80)
    department = models.CharField(max_length=20)
    marks = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

with connection.schema_editor() as editor:
    editor.create_model(Student)

Student.objects.bulk_create([
    Student(name="Asha", department="CSE", marks=92),
    Student(name="Ravi", department="ECE", marks=48),
    Student(name="Meena", department="CSE", marks=85),
    Student(name="Arun", department="ECE", marks=71, active=False),
    Student(name="Divya", department="IT", marks=64),
])
print(Student.objects.count())
```

```output
5
```

## Filtering

```python
print(list(Student.objects.filter(department="CSE")))
print(list(Student.objects.filter(marks__gte=70).order_by("-marks")))
print(list(Student.objects.exclude(department="CSE").values_list("name", flat=True)))
print(Student.objects.filter(name__startswith="A").count(), Student.objects.filter(name__icontains="vy").count())
print(Student.objects.get(name="Meena").marks)
```

```output
[<Student: Asha>, <Student: Meena>]
[<Student: Asha>, <Student: Meena>, <Student: Arun>]
['Ravi', 'Arun', 'Divya']
2 1
85
```

Field lookups use double underscores: `__gte`, `__lt`, `__in`, `__contains`, `__icontains`, `__startswith`, `__isnull`, `__range`.

| Method | Returns |
| --- | --- |
| `all()`, `filter()`, `exclude()` | a new QuerySet |
| `get()` | **one** object (raises `DoesNotExist` or `MultipleObjectsReturned`) |
| `first()`, `last()` | one object or `None` |
| `count()`, `exists()` | a number, or True/False (cheap) |
| `values()`, `values_list()` | dictionaries or tuples instead of objects |

## QuerySets are lazy and chainable

```python
passed = Student.objects.filter(marks__gte=50)          # no query yet
cse_passed = passed.filter(department="CSE")           # still none
print(str(cse_passed.query))                            # the SQL it will run
print(len(cse_passed))                                  # now it hits the database
```

```output
SELECT "demo_student"."id", "demo_student"."name", "demo_student"."department", "demo_student"."marks", "demo_student"."active" FROM "demo_student" WHERE ("demo_student"."marks" >= 50 AND "demo_student"."department" = CSE)
2
```

## Q objects: OR, NOT and complex conditions

```python
from django.db.models import Q

either = Student.objects.filter(Q(department="IT") | Q(marks__gt=90))
print(sorted(s.name for s in either))
print(sorted(s.name for s in Student.objects.filter(~Q(department="CSE") & Q(active=True))))
```

```output
['Asha', 'Divya']
['Divya', 'Ravi']
```

## F expressions: use a column's own value

```python
from django.db.models import F

Student.objects.filter(department="IT").update(marks=F("marks") + 5)     # one UPDATE, done in the database
print(Student.objects.get(name="Divya").marks)
```

```output
69
```

`F()` makes the **database** do the arithmetic, which is faster and safe when many requests update the same row at once.

## Aggregation and annotation

```python
from django.db.models import Avg, Count, Max

print(Student.objects.aggregate(average=Avg("marks"), best=Max("marks")))

per_department = Student.objects.values("department").annotate(people=Count("id"), average=Avg("marks")).order_by("department")
for row in per_department:
    print(row)
```

```output
{'average': 73.0, 'best': 92}
{'department': 'CSE', 'people': 2, 'average': 88.5}
{'department': 'ECE', 'people': 2, 'average': 59.5}
{'department': 'IT', 'people': 1, 'average': 69.0}
```

`aggregate()` collapses everything into one dictionary. `values(...).annotate(...)` works like SQL `GROUP BY`.

## Creating, updating, deleting

```python
student, created = Student.objects.get_or_create(name="Kiran", defaults={"department": "IT", "marks": 55})
print(student.name, created)
student, created = Student.objects.get_or_create(name="Kiran", defaults={"department": "IT", "marks": 55})
print(created)

updated = Student.objects.filter(active=False).update(active=True)
print("updated", updated)

deleted, _ = Student.objects.filter(marks__lt=50).delete()
print("deleted", deleted)
print(Student.objects.count())
```

```output
Kiran True
False
updated 1
deleted 1
5
```

## Slicing and pagination

```python
print([s.name for s in Student.objects.order_by("-marks")[:3]])        # LIMIT 3

from django.core.paginator import Paginator
page = Paginator(Student.objects.order_by("id"), per_page=2).page(2)
print([s.name for s in page], page.has_next(), page.paginator.num_pages)
```

```output
['Asha', 'Meena', 'Arun']
['Arun', 'Divya'] True 3
```

:::tip
Use `.exists()` instead of `len(qs) > 0` and `.count()` instead of `len(qs)` when you only need a yes/no or a number: they ask the database for just that, not every row.
:::
