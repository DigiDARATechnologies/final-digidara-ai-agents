---
title: Relationships, joins and the N+1 problem
summary: Link tables with foreign keys and relationship(), query across them, and fix the N+1 query problem with eager loading.
takeaways:
- ForeignKey stores the link; relationship gives Python-level access
- One-to-many and many-to-many cover most designs
- Loading related rows in a loop causes N+1 queries; selectinload fixes it
---
## One-to-many

A department has many students. Store the link in the "many" side with a **foreign key**, and add a `relationship` so you can move between them in Python.

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.orm import selectinload

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
db = SQLAlchemy()
db.init_app(app)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    students = db.relationship("Student", back_populates="department")

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    marks = db.Column(db.Integer, default=0)
    department_id = db.Column(db.ForeignKey("department.id"), nullable=False)
    department = db.relationship("Department", back_populates="students")
    courses = db.relationship("Course", secondary="enrolments", back_populates="students")   # explained below

enrolments = db.Table(                                       # the association table (explained below)
    "enrolments",
    db.Column("student_id", db.ForeignKey("student.id"), primary_key=True),
    db.Column("course_id", db.ForeignKey("course.id"), primary_key=True),
)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(60), nullable=False)
    students = db.relationship("Student", secondary=enrolments, back_populates="courses")

with app.app_context():
    db.create_all()
    cse, ece = Department(name="CSE"), Department(name="ECE")
    db.session.add_all([
        cse, ece,
        Student(name="Asha", marks=92, department=cse),
        Student(name="Ravi", marks=78, department=ece),
        Student(name="Meena", marks=85, department=cse),
        Student(name="Arun", marks=71, department=ece),
    ])
    db.session.commit()

    cse = db.session.scalar(db.select(Department).filter_by(name="CSE"))
    print([s.name for s in cse.students])               # department -> students
    print(db.session.get(Student, 2).department.name)   # student -> department
```

```output
['Asha', 'Meena']
CSE
```

## Many-to-many

A student takes many courses, and a course has many students. A third **association table** (`enrolments`, declared in the code above) holds the pairs of student id and course id. Both models point at it with `secondary=`, so you can use `student.courses` and `course.students` like plain lists.

```python
with app.app_context():
    python, sql = Course(title="Python"), Course(title="SQL")
    asha = db.session.get(Student, 1)
    asha.courses.extend([python, sql])
    ravi = db.session.get(Student, 2)
    ravi.courses.append(python)
    db.session.commit()
    print([c.title for c in asha.courses])
    print(sorted(s.name for s in python.students))
```

```output
['Python', 'SQL']
['Asha', 'Meena']
```

## Joins and aggregates

```python
with app.app_context():
    stmt = (
        db.select(Department.name, db.func.count(Student.id), db.func.avg(Student.marks))
        .join(Student)
        .group_by(Department.name)
        .order_by(Department.name)
    )
    for name, count, average in db.session.execute(stmt):
        print(name, count, average)
```

```output
CSE 2 88.5
ECE 2 74.5
```

## The N+1 query problem

This is the most common hidden performance bug. To print each department with its students you might write a loop. Count the SQL statements that run:

```python
from contextlib import contextmanager

@contextmanager
def count_queries():
    counter = {"n": 0}
    def on_query(*args, **kwargs):
        counter["n"] += 1
    event.listen(db.engine, "before_cursor_execute", on_query)
    try:
        yield counter
    finally:
        event.remove(db.engine, "before_cursor_execute", on_query)

with app.app_context():
    with count_queries() as lazy:
        for department in db.session.scalars(db.select(Department)).all():
            _ = [s.name for s in department.students]        # a new query for each department
    with count_queries() as eager:
        for department in db.session.scalars(db.select(Department).options(selectinload(Department.students))).all():
            _ = [s.name for s in department.students]        # students were loaded together
    print("lazy loading :", lazy["n"], "queries")
    print("eager loading:", eager["n"], "queries")
```

```output
lazy loading : 3 queries
eager loading: 2 queries
```

With 2 departments, lazy loading took 3 queries (1 for the departments, then 1 per department): that is **N+1**. With 2,000 departments it would be 2,001. `selectinload` fetches all the students in one extra query, so the count stays at 2.

| Strategy | Use when |
| --- | --- |
| `selectinload(Parent.children)` | loading a list of parents with their children (usual best choice) |
| `joinedload(...)` | one parent, or a to-one relationship (a student's department) |
| default lazy loading | you rarely need the related rows |

:::interview
**Interviewers often ask:** "What is the N+1 problem and how do you fix it?" Loading a list and then running one extra query per item to fetch related data. Fix it with eager loading (`selectinload` or `joinedload`) or a join, so the data comes in one or two queries.
:::
