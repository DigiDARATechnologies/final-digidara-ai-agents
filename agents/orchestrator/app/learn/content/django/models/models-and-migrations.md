---
title: Models and migrations
summary: Describe tables as Python classes, see the SQL Django generates, and change the schema safely with migrations.
takeaways:
- A model is a class; each attribute is a column; Django writes the SQL
- makemigrations records a change; migrate applies it
- Add validation, choices, ordering and __str__ to make models pleasant to use
---
## A model

```python
from django.db import models

class Student(models.Model):
    class Level(models.TextChoices):
        BEGINNER = "B", "Beginner"
        ADVANCED = "A", "Advanced"

    name = models.CharField(max_length=80)
    email = models.EmailField(unique=True)
    marks = models.PositiveIntegerField(default=0)
    level = models.CharField(max_length=1, choices=Level.choices, default=Level.BEGINNER)
    joined = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-marks", "name"]

    def __str__(self):
        return self.name

print([f.name for f in Student._meta.get_fields()])
print(Student._meta.db_table)
```

```output
['id', 'name', 'email', 'marks', 'level', 'joined']
demo_student
```

Django makes an `id` primary key automatically, and names the table `<app>_<model>`.

## The SQL behind it

You never write `CREATE TABLE` by hand. Here is what Django would run for this model:

```python
from django.db import connection

with connection.schema_editor(collect_sql=True) as editor:
    editor.create_model(Student)
print("\n".join(editor.collected_sql))
```

```output
CREATE TABLE "demo_student" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(80) NOT NULL, "email" varchar(254) NOT NULL UNIQUE, "marks" integer unsigned NOT NULL CHECK ("marks" >= 0), "level" varchar(1) NOT NULL, "joined" date NULL);
```

## Migrations: the history of your schema

Changing a model does not change the database. Two commands connect them:

```py
python manage.py makemigrations     # compare models with past migrations, write a new migration file
python manage.py migrate            # run the unapplied migrations on the database
```

A migration is a Python file in `migrations/` that you commit with your code:

```py
# courses/migrations/0002_student_phone.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("courses", "0001_initial")]
    operations = [
        migrations.AddField("student", "phone", models.CharField(max_length=15, blank=True)),
    ]
```

| Command | Use |
| --- | --- |
| `makemigrations` | create the migration file |
| `migrate` | apply it |
| `migrate courses 0001` | roll back to an earlier state |
| `showmigrations` | list which are applied |
| `sqlmigrate courses 0002` | print the SQL a migration will run |

:::warning
Never edit or delete a migration that others (or production) have already applied. Add a **new** migration instead. Adding a required column to a table with rows needs a `default` (or make it nullable first), otherwise the migration fails.
:::

## Fields you will use most

| Field | Stores |
| --- | --- |
| `CharField(max_length=...)`, `TextField` | short and long text |
| `IntegerField`, `PositiveIntegerField`, `DecimalField` | numbers (use `DecimalField` for money) |
| `BooleanField`, `DateField`, `DateTimeField` | yes/no and dates |
| `EmailField`, `URLField`, `SlugField` | text with built-in validation |
| `ForeignKey`, `ManyToManyField`, `OneToOneField` | links between tables |
| `FileField`, `ImageField` | uploaded files |
| `JSONField` | structured data |

Common options: `null=True` (the database may store NULL), `blank=True` (a form may leave it empty), `default`, `unique`, `choices`, `db_index`.

## Using the model

```python
with connection.schema_editor() as editor:
    editor.create_model(Student)

asha = Student.objects.create(name="Asha", email="asha@x.com", marks=92)
ravi = Student(name="Ravi", email="ravi@x.com", marks=78, level="A")
ravi.save()

print(Student.objects.count(), [str(s) for s in Student.objects.all()])
print(ravi.get_level_display(), ravi.level)
```

```output
2 ['Asha', 'Ravi']
Advanced A
```

`get_level_display()` returns the human label for a field with `choices`.

## Validation

`save()` does not check your rules. Call `full_clean()` (forms do this for you):

```python
from django.core.exceptions import ValidationError

bad = Student(name="X" * 100, email="not-an-email")
try:
    bad.full_clean()
except ValidationError as error:
    print(sorted(error.message_dict))
```

```output
['email', 'name']
```

:::interview
**Interviewers often ask:** "What is the difference between `makemigrations` and `migrate`?" `makemigrations` writes migration files from your model changes. `migrate` applies those files to the database. The first creates the plan, the second runs it.
:::
