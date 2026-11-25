---
title: Classes and objects
summary: Model things with classes, __init__, attributes, methods and inheritance.
takeaways:
- A class is a blueprint; an object is one thing made from it
- __init__ sets up a new object
- self is the object the method is working on
---
## A blueprint for things

When you have several students, each with a name and marks, a class keeps the data and the actions together.

```python
class Student:
    def __init__(self, name, marks):
        self.name = name
        self.marks = marks

    def grade(self):
        return "Pass" if self.marks >= 40 else "Fail"

asha = Student("Asha", 72)
ravi = Student("Ravi", 35)
print(asha.name, asha.grade())
print(ravi.name, ravi.grade())
```

```output
Asha Pass
Ravi Fail
```

- `class Student` is the blueprint.
- `Student("Asha", 72)` makes an **object** (an instance).
- `__init__` runs when the object is created and stores its data.
- `self` is the object itself, so `self.name` belongs to that one student.

## Methods and attributes

Variables stored on an object are **attributes** (`asha.marks`). Functions defined in the class are **methods** (`asha.grade()`).

## Inheritance

A class can build on another:

```python
class Topper(Student):
    def grade(self):
        return "Distinction" if self.marks >= 90 else super().grade()

t = Topper("Meena", 95)
print(t.grade())
```

```output
Distinction
```

`Topper` reuses everything from `Student` and changes one method. `super()` calls the parent's version.

## Printing an object

```python
class Student:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f"Student({self.name})"

print(Student("Asha"))
```

```output
Student(Asha)
```

:::tip
Start simple. Use a plain function or dictionary until you notice you are passing the same group of values around everywhere; that is when a class helps.
:::

:::interview
**Interviewers often ask:** "What are the four pillars of OOP?" Encapsulation, abstraction, inheritance and polymorphism. Have one small example ready for each.
:::

:::practice mock-interview
Practise explaining OOP out loud in a Mock Interview.
:::
