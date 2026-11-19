---
title: Relationships and query optimisation
summary: Link models with ForeignKey and ManyToManyField, then remove the N+1 problem with select_related and prefetch_related.
takeaways:
- ForeignKey is many-to-one, ManyToManyField is many-to-many, OneToOneField is one-to-one
- Reading related objects in a loop causes N+1 queries
- select_related (joins) and prefetch_related (second query) fix it
---
## Models with relationships

```python
from django.db import models, connection

class Department(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name

class Course(models.Model):
    title = models.CharField(max_length=60)

    def __str__(self):
        return self.title

class Student(models.Model):
    name = models.CharField(max_length=80)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="students")
    courses = models.ManyToManyField(Course, related_name="students")

    def __str__(self):
        return self.name

with connection.schema_editor() as editor:
    for model in (Department, Course, Student):
        editor.create_model(model)

cse, ece = Department.objects.create(name="CSE"), Department.objects.create(name="ECE")
python, sql = Course.objects.create(title="Python"), Course.objects.create(title="SQL")
asha = Student.objects.create(name="Asha", department=cse)
ravi = Student.objects.create(name="Ravi", department=ece)
meena = Student.objects.create(name="Meena", department=cse)
asha.courses.add(python, sql)
ravi.courses.add(python)

print(asha.department, [str(c) for c in asha.courses.all()])
print(sorted(str(s) for s in cse.students.all()))
print(sorted(str(s) for s in python.students.all()))
```

```output
CSE ['Python', 'SQL']
['Asha', 'Meena']
['Asha', 'Ravi']
```

`on_delete` says what happens to students if their department is deleted: `CASCADE` deletes them too, `PROTECT` blocks the deletion, `SET_NULL` keeps them with an empty link. `related_name` names the reverse direction (`cse.students`).

## Querying across relationships

Double underscores follow the link:

```python
print(sorted(str(s) for s in Student.objects.filter(department__name="CSE")))
print(sorted(str(d) for d in Department.objects.filter(students__courses__title="Python").distinct()))
```

```output
['Asha', 'Meena']
['CSE', 'ECE']
```

## The N+1 problem

Reading a related object inside a loop sends one extra query for each row:

```python
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as slow:
    for student in Student.objects.all():
        _ = student.department.name                      # a new query for every student
print("without select_related:", len(slow), "queries")

with CaptureQueriesContext(connection) as fast:
    for student in Student.objects.select_related("department"):
        _ = student.department.name                      # already loaded by a JOIN
print("with select_related   :", len(fast), "query")
```

```output
without select_related: 4 queries
with select_related   : 1 query
```

With 3 students, the slow loop ran 4 queries (1 for the list plus 1 per student). With 3,000 students it would run 3,001. That is the **N+1 problem**.

## select_related and prefetch_related

| Tool | How | Use for |
| --- | --- | --- |
| `select_related("department")` | one query with a SQL JOIN | ForeignKey and OneToOne (single related object) |
| `prefetch_related("courses")` | a second query, joined in Python | ManyToMany and reverse ForeignKey (many related objects) |

```python
with CaptureQueriesContext(connection) as slow:
    for student in Student.objects.all():
        _ = [c.title for c in student.courses.all()]
print("without prefetch_related:", len(slow), "queries")

with CaptureQueriesContext(connection) as fast:
    for student in Student.objects.prefetch_related("courses"):
        _ = [c.title for c in student.courses.all()]
print("with prefetch_related   :", len(fast), "queries")

with CaptureQueriesContext(connection) as both:
    rows = [(s.name, s.department.name, [c.title for c in s.courses.all()])
            for s in Student.objects.select_related("department").prefetch_related("courses").order_by("id")]
print("both together:", len(both), "queries")
print(rows)
```

```output
without prefetch_related: 4 queries
with prefetch_related   : 2 queries
both together: 2 queries
[('Asha', 'CSE', ['Python', 'SQL']), ('Ravi', 'ECE', ['Python']), ('Meena', 'CSE', [])]
```

## Other habits that keep queries cheap

| Habit | Why |
| --- | --- |
| `.only("name")` / `.defer("bio")` | skip heavy columns you do not need |
| `.values("name")` | plain dicts instead of full objects |
| `.count()` and `.exists()` | do not load rows just to count them |
| `bulk_create`, `bulk_update` | one query for many rows |
| `db_index=True` on fields you filter by | the database searches instead of scanning |
| **django-debug-toolbar** in development | shows the number and time of queries for each page |

:::interview
**Interviewers often ask:** "What is the difference between `select_related` and `prefetch_related`?" `select_related` uses a SQL JOIN to fetch single-valued relations (ForeignKey, OneToOne) in one query. `prefetch_related` runs a separate query for multi-valued relations (ManyToMany, reverse FK) and joins them in Python. Both avoid N+1 queries.
:::
