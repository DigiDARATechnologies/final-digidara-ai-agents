---
title: Project 4: Student marks manager (classes and objects)
summary: Model students and a grade book with classes, calculate averages, grades and rankings, and print a neat report.
takeaways:
- A class bundles data and the functions that work on it
- Keep each class focused: Student knows about one student, Gradebook manages many
- Formatted reports make results easy to read and share
---
## The idea

A teacher wants to store marks for several students, find the average and class topper, assign grades, and print a report. This is a perfect first project for **classes and objects**.

## Step 1: the Student class

```python
class Student:
    def __init__(self, name, marks):
        if not marks:
            raise ValueError("A student needs at least one mark")
        if any(m < 0 or m > 100 for m in marks.values()):
            raise ValueError("Marks must be between 0 and 100")
        self.name = name
        self.marks = dict(marks)                   # subject -> mark

    def total(self):
        return sum(self.marks.values())

    def average(self):
        return self.total() / len(self.marks)

    def grade(self):
        avg = self.average()
        if avg >= 90:
            return "A"
        if avg >= 75:
            return "B"
        if avg >= 50:
            return "C"
        return "F"

    def best_subject(self):
        return max(self.marks, key=self.marks.get)

    def __repr__(self):
        return f"Student({self.name!r}, average={self.average():.1f})"

asha = Student("Asha", {"Maths": 92, "Science": 88, "English": 79})
print(asha)
print("total:", asha.total())
print("average:", round(asha.average(), 2))
print("grade:", asha.grade())
print("best subject:", asha.best_subject())
```

```output
Student('Asha', average=86.3)
total: 259
average: 86.33
grade: B
best subject: Maths
```

The class validates in its constructor, so an invalid student can never exist. That is the key benefit of putting rules inside a class.

## Step 2: the Gradebook

```python
class Gradebook:
    def __init__(self):
        self.students = []

    def add(self, student):
        if any(s.name == student.name for s in self.students):
            raise ValueError(f"{student.name} is already in the gradebook")
        self.students.append(student)

    def topper(self):
        return max(self.students, key=lambda s: s.average())

    def ranking(self):
        return sorted(self.students, key=lambda s: s.average(), reverse=True)

    def subject_average(self, subject):
        marks = [s.marks[subject] for s in self.students if subject in s.marks]
        return sum(marks) / len(marks)

    def grade_counts(self):
        counts = {}
        for s in self.students:
            counts[s.grade()] = counts.get(s.grade(), 0) + 1
        return dict(sorted(counts.items()))

book = Gradebook()
book.add(Student("Asha", {"Maths": 92, "Science": 88, "English": 79}))
book.add(Student("Ravi", {"Maths": 48, "Science": 55, "English": 61}))
book.add(Student("Meena", {"Maths": 85, "Science": 91, "English": 88}))
book.add(Student("Arun", {"Maths": 71, "Science": 64, "English": 70}))

print("topper:", book.topper().name)
print("maths average:", round(book.subject_average("Maths"), 2))
print("grade counts:", book.grade_counts())

try:
    book.add(Student("Asha", {"Maths": 50}))
except ValueError as error:
    print("rejected:", error)
```

```output
topper: Meena
maths average: 74.0
grade counts: {'B': 2, 'C': 2}
rejected: Asha is already in the gradebook
```

Two classes, each with one clear job: `Student` knows about one person, `Gradebook` manages the collection. Putting a duplicate-name check in `add` protects the gradebook's data.

## Step 3: a formatted report

```python
def format_report(book):
    subjects = sorted({subject for s in book.students for subject in s.marks})
    header = f"{'Rank':<5}{'Name':<8}" + "".join(f"{subject:>9}" for subject in subjects) + f"{'Avg':>8}{'Grade':>7}"
    lines = [header, "-" * len(header)]
    for rank, s in enumerate(book.ranking(), start=1):
        row = f"{rank:<5}{s.name:<8}" + "".join(f"{s.marks.get(subject, '-'):>9}" for subject in subjects)
        row += f"{s.average():>8.1f}{s.grade():>7}"
        lines.append(row)
    lines.append("-" * len(header))
    class_average = sum(s.average() for s in book.students) / len(book.students)
    lines.append(f"Class average: {class_average:.1f}    Topper: {book.topper().name}")
    return "\n".join(lines)

print(format_report(book))
```

```output
Rank Name      English    Maths  Science     Avg  Grade
-------------------------------------------------------
1    Meena          88       85       91    88.0      B
2    Asha           79       92       88    86.3      B
3    Arun           70       71       64    68.3      C
4    Ravi           61       48       55    54.7      C
-------------------------------------------------------
Class average: 74.3    Topper: Meena
```

The format codes (`<5`, `>9`, `.1f`) line the columns up. Returning a string again keeps the function reusable: print it, save it to a file, or send it as an email.

## Step 4: read marks from a CSV

Real marks come from files, not from typing in code.

```python
import csv
import io

csv_text = """name,subject,mark
Asha,Maths,92
Asha,Science,88
Ravi,Maths,48
Ravi,Science,55
Meena,Maths,85
Meena,Science,91
"""

def load_from_csv(file):
    marks = {}
    for row in csv.DictReader(file):
        marks.setdefault(row["name"], {})[row["subject"]] = int(row["mark"])
    book = Gradebook()
    for name, subject_marks in marks.items():
        book.add(Student(name, subject_marks))
    return book

loaded = load_from_csv(io.StringIO(csv_text))
print([f"{s.name}: {s.average():.1f}" for s in loaded.ranking()])
```

```output
['Asha: 90.0', 'Meena: 88.0', 'Ravi: 51.5']
```

`setdefault(name, {})` creates the inner dictionary the first time a name appears. It is a handy way to group rows.

## Step 5: add behaviour with inheritance (optional)

Suppose some students are on a scholarship with a higher pass mark. A **subclass** reuses everything and changes one thing:

```python
class ScholarshipStudent(Student):
    PASS_MARK = 60

    def passed(self):
        return all(mark >= self.PASS_MARK for mark in self.marks.values())

class RegularStudent(Student):
    PASS_MARK = 40

    def passed(self):
        return all(mark >= self.PASS_MARK for mark in self.marks.values())

marks = {"Maths": 65, "Science": 52}
print("regular student passes:", RegularStudent("A", marks).passed())
print("scholarship student passes:", ScholarshipStudent("B", marks).passed())
```

```output
regular student passes: True
scholarship student passes: False
```

The same marks pass under one rule and fail under the other. (If you notice the repeated `passed` method, you could move it into `Student` and keep only `PASS_MARK` in each subclass: a nice refactoring exercise.)

## Improvements to try

| Idea | What you practise |
| --- | --- |
| save the gradebook to a file and load it next time | files, JSON (`json.dump`) |
| weighted subjects (Maths counts double) | dictionaries, arithmetic |
| attendance and a warning below 75% | more fields, conditions |
| a bar chart of subject averages | `matplotlib` |
| a Flask page that shows the report | the web project that follows |
| unit tests for `grade()` boundaries (89.9, 90, 74.9) | the next lesson |

:::interview
**Interviewers often ask:** "What is the difference between a class and an object?" A class is the blueprint (like `Student`); an object is one thing made from it (like `asha`). They may also ask why you used a class instead of dictionaries: it keeps data and rules together, and lets you enforce validation in one place.
:::
