---
title: Building a REST API
summary: Design resource URLs, use the right HTTP methods and status codes, and build a full CRUD JSON API.
takeaways:
- A REST API exposes resources at URLs and uses HTTP methods as the verbs
- Return JSON with the right status code: 200, 201, 204, 400, 404
- Keep list endpoints paginated
---
## Resources and verbs

A **REST** API treats things (students, courses) as **resources** with their own URLs, and uses the HTTP **method** to say what to do.

| Method and URL | Meaning | Success code |
| --- | --- | --- |
| `GET /students` | list students | 200 |
| `POST /students` | create a student | 201 |
| `GET /students/7` | read student 7 | 200 |
| `PUT /students/7` or `PATCH` | update student 7 (PUT replaces, PATCH changes part) | 200 |
| `DELETE /students/7` | delete student 7 | 204 |

URLs are **nouns** in the plural (`/students`), not verbs (`/getStudents`).

## A complete CRUD API

```python
from flask import Flask, jsonify, request, abort
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
db = SQLAlchemy()
db.init_app(app)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    marks = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "marks": self.marks}

with app.app_context():
    db.create_all()

@app.get("/students")
def list_students():
    page = request.args.get("page", 1, type=int)
    result = db.paginate(db.select(Student).order_by(Student.id), page=page, per_page=2, error_out=False)
    return jsonify({"items": [s.to_dict() for s in result], "page": result.page, "pages": result.pages, "total": result.total})

@app.post("/students")
def create_student():
    data = request.get_json(silent=True) or {}
    student = Student(name=data["name"], marks=data.get("marks", 0))
    db.session.add(student)
    db.session.commit()
    return jsonify(student.to_dict()), 201

@app.get("/students/<int:student_id>")
def get_student(student_id):
    student = db.get_or_404(Student, student_id)
    return jsonify(student.to_dict())

@app.patch("/students/<int:student_id>")
def update_student(student_id):
    student = db.get_or_404(Student, student_id)
    data = request.get_json()
    student.name = data.get("name", student.name)
    student.marks = data.get("marks", student.marks)
    db.session.commit()
    return jsonify(student.to_dict())

@app.delete("/students/<int:student_id>")
def delete_student(student_id):
    db.session.delete(db.get_or_404(Student, student_id))
    db.session.commit()
    return "", 204

c = app.test_client()
print(c.post("/students", json={"name": "Asha", "marks": 92}).status_code)
c.post("/students", json={"name": "Ravi", "marks": 78})
c.post("/students", json={"name": "Meena", "marks": 85})
print(c.get("/students").get_json())
print(c.get("/students/2").get_json())
print(c.patch("/students/2", json={"marks": 81}).get_json())
print(c.delete("/students/3").status_code)
print(c.get("/students/3").status_code)
```

```output
201
{'items': [{'id': 1, 'marks': 92, 'name': 'Asha'}, {'id': 2, 'marks': 78, 'name': 'Ravi'}], 'page': 1, 'pages': 2, 'total': 3}
{'id': 2, 'marks': 78, 'name': 'Ravi'}
{'id': 2, 'marks': 81, 'name': 'Ravi'}
204
404
```

`@app.get`, `@app.post`, `@app.patch` and `@app.delete` are shortcuts for `@app.route(..., methods=[...])`. `db.get_or_404` gives a 404 automatically when the row does not exist.

## Design habits that save pain later

| Habit | Why |
| --- | --- |
| Always return JSON, including errors | clients can parse every response the same way |
| Paginate every list | a list that works with 10 rows may crash with 10 million |
| Use plural nouns and nested paths: `/courses/7/lessons` | URLs stay predictable |
| Version it: `/api/v1/students` | you can change the API without breaking existing clients |
| Filter and sort by query string: `?dept=CSE&sort=-marks` | one endpoint, many views |
| Do not expose internal columns (password hashes!) | `to_dict` lists only what is safe |

:::warning
The `create_student` above trusts the client: `data["name"]` raises a `KeyError` (a 500 error) if the name is missing, and nothing checks the marks. The next lesson adds validation and proper error responses.
:::
