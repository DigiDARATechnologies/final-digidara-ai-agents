---
title: Databases with SQLAlchemy
summary: Define models with Flask-SQLAlchemy, then create, read, update and delete rows, with pagination.
takeaways:
- A model is a Python class that maps to a database table
- db.session adds, changes and deletes; commit() saves
- Use db.select with db.session.scalars for queries
---
## An ORM

Writing SQL strings in Python gets repetitive and error-prone. An **ORM** (object-relational mapper) lets you work with Python classes instead. **SQLAlchemy** is the standard Python ORM, and **Flask-SQLAlchemy** connects it to Flask.

```py
pip install flask-sqlalchemy
```

## Models

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"        # an in-memory database for this lesson
db = SQLAlchemy()
db.init_app(app)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    marks = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<Student {self.name}>"

with app.app_context():
    db.create_all()
    print(Student.__tablename__, [c.name for c in Student.__table__.columns])
```

```output
student ['id', 'name', 'email', 'marks']
```

Flask-SQLAlchemy names the table after the class (`student`). `db.create_all()` creates the tables that do not exist yet.

:::note
Database work needs an **application context** (`with app.app_context():`). Inside a request Flask has one already; in scripts and tests you open it yourself.
:::

## Create

```python
with app.app_context():
    db.session.add_all([
        Student(name="Asha", email="asha@x.com", marks=92),
        Student(name="Ravi", email="ravi@x.com", marks=78),
        Student(name="Meena", email="meena@x.com", marks=85),
    ])
    db.session.commit()
    print(db.session.scalar(db.select(db.func.count(Student.id))))
```

```output
3
```

## Read

```python
with app.app_context():
    everyone = db.session.scalars(db.select(Student).order_by(Student.marks.desc())).all()
    print([s.name for s in everyone])

    one = db.session.get(Student, 2)                                  # by primary key
    print(one.name, one.marks)

    toppers = db.session.scalars(db.select(Student).where(Student.marks >= 85)).all()
    print([s.name for s in toppers])

    asha = db.session.scalar(db.select(Student).filter_by(email="asha@x.com"))
    print(asha)
    print(db.session.scalar(db.select(db.func.avg(Student.marks))))
```

```output
['Asha', 'Meena', 'Ravi']
Ravi 78
['Asha', 'Meena']
<Student Asha>
85.0
```

## Update and delete

```python
with app.app_context():
    student = db.session.get(Student, 2)
    student.marks = 81                    # change the object...
    db.session.commit()                   # ...and save

    db.session.delete(db.session.get(Student, 3))
    db.session.commit()

    print([(s.name, s.marks) for s in db.session.scalars(db.select(Student).order_by(Student.id))])
```

```output
[('Asha', 92), ('Ravi', 81)]
```

## Handling errors and rolling back

```python
from sqlalchemy.exc import IntegrityError

with app.app_context():
    db.session.add(Student(name="Copy", email="asha@x.com"))        # the email already exists
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()                                        # undo, so the session is usable again
        print("duplicate email rejected")
    print(db.session.scalar(db.select(db.func.count(Student.id))))
```

```output
duplicate email rejected
2
```

## Pagination

Never load a million rows. Page through them:

```python
with app.app_context():
    page = db.paginate(db.select(Student).order_by(Student.id), page=1, per_page=1)
    print([s.name for s in page], page.page, page.pages, page.has_next)
```

```output
['Asha'] 1 2 True
```

:::warning
Never build SQL by joining strings with user input. The ORM and parameterised queries protect you from **SQL injection**; string-formatted SQL does not. The security lesson shows an example.
:::
