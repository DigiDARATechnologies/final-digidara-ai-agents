---
title: Validation and error handling
summary: Validate input with a clear error format, handle exceptions in one place, and return helpful JSON errors.
takeaways:
- Never trust client input: check types, ranges and required fields
- Register error handlers so every failure returns the same JSON shape
- 400 for bad input, 404 for missing, 409 for conflicts, 422 for failed validation
---
## What goes wrong without validation

```python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.post("/bad")
def bad():
    data = request.get_json()
    return {"name": data["name"], "marks": data["marks"] + 5}

c = app.test_client()
print(c.post("/bad", json={"name": "Asha"}).status_code)          # a missing key
print(c.post("/bad", json={"name": "Asha", "marks": "x"}).status_code)   # the wrong type
```

```output
500
500
```

Both mistakes are the client's fault, but the server answers **500** (a crash), which looks like a bug in your code and leaks nothing useful to the client.

## A small validator

```python
class ValidationError(Exception):
    def __init__(self, errors, status=422):
        self.errors = errors
        self.status = status

def validate_student(data):
    errors = {}
    if not isinstance(data, dict):
        raise ValidationError({"body": "Send a JSON object."}, 400)
    name = data.get("name")
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
        errors["name"] = "Required: text of 2 to 80 characters."
    marks = data.get("marks", 0)
    if isinstance(marks, bool) or not isinstance(marks, int) or not 0 <= marks <= 100:
        errors["marks"] = "Must be a whole number from 0 to 100."
    if errors:
        raise ValidationError(errors)
    return {"name": name.strip(), "marks": marks}
```

## One place for all errors

Register handlers once, and every error has the **same JSON shape**:

```python
app = Flask(__name__)

@app.errorhandler(ValidationError)
def on_validation_error(error):
    return jsonify({"error": "validation_failed", "details": error.errors}), error.status

@app.errorhandler(404)
def on_not_found(error):
    return jsonify({"error": "not_found", "message": "No such resource."}), 404

@app.errorhandler(405)
def on_method_not_allowed(error):
    return jsonify({"error": "method_not_allowed"}), 405

@app.errorhandler(Exception)
def on_unexpected(error):
    app.logger.exception("Unhandled error")                 # the full detail goes to the log
    return jsonify({"error": "server_error", "message": "Something went wrong."}), 500   # not to the client

@app.post("/students")
def create():
    clean = validate_student(request.get_json(silent=True))
    return jsonify(clean), 201

@app.get("/boom")
def boom():
    return 1 / 0

c = app.test_client()
print(c.post("/students", json={"name": "A", "marks": 250}).get_json())
print(c.post("/students", data="not json").status_code)
print(c.post("/students", json={"name": "  Asha  ", "marks": 92}).get_json())
print(c.get("/missing").get_json())
print(c.delete("/students").status_code)
```

```output
{'details': {'marks': 'Must be a whole number from 0 to 100.', 'name': 'Required: text of 2 to 80 characters.'}, 'error': 'validation_failed'}
400
{'marks': 92, 'name': 'Asha'}
{'error': 'not_found', 'message': 'No such resource.'}
405
```

The last handler, for `Exception`, is a safety net. A user never sees a traceback or a file path: they get a short, safe message, while you read the details in the log.

:::warning
Do not return `str(error)` from an unexpected exception to the client. Messages can contain SQL, file paths or other internal detail that helps an attacker.
:::

## Which status code?

| Situation | Code |
| --- | --- |
| the body is not valid JSON, or a parameter is malformed | 400 |
| not logged in | 401 |
| logged in, but not allowed | 403 |
| the resource does not exist | 404 |
| valid JSON, but a field fails a rule | 422 (some APIs use 400) |
| the request conflicts with the current state (duplicate email) | 409 |
| too many requests | 429 |
| your bug | 500 |

## Libraries for bigger projects

Hand-written validators get long. Teams usually use a library: **Marshmallow** or **Pydantic** (declare the fields and rules, get validated data or a list of errors). The idea is the same as above: validate at the edge, then work with clean data.

```py
pip install marshmallow       # or: pip install pydantic
```

:::interview
**Interviewers often ask:** "How do you handle errors in a Flask API?" Validate input at the boundary, raise specific exceptions, register `errorhandler`s so all errors return a consistent JSON shape with the right status code, and log unexpected errors without leaking details to the client.
:::
