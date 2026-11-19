---
title: Python basics
summary: Core Python questions on types, memory, equality and style.
kind: qa
takeaways:
- Know mutable versus immutable and == versus is
- Python is compiled to bytecode, then interpreted
- Be ready to explain in one or two sentences, with a tiny example
---
### Q [Easy] What are the key features of Python?
Python is interpreted, dynamically typed, easy to read, and comes with a large standard library. It supports several styles (procedural, object-oriented, functional) and manages memory automatically.

### Q [Easy] Is Python compiled or interpreted?
Both, in a sense. Python source is first compiled to **bytecode** (the `.pyc` files), and the Python virtual machine then runs that bytecode. In everyday talk we call it interpreted.

### Q [Easy] What is the difference between `==` and `is`?
`==` compares **values**. `is` checks whether two names point to the **same object** in memory.

```python
a = [1, 2]
b = [1, 2]
print(a == b)   # True: equal values
print(a is b)   # False: two different lists
```

Use `is` mainly for `None`: `if x is None`.

### Q [Easy] What are mutable and immutable types?
A **mutable** object can change after it is created: list, dict, set. An **immutable** one cannot: int, float, str, tuple, bool, frozenset. "Changing" an immutable value really creates a new object.

### Q [Medium] What is the difference between `/` and `//`?
`/` is true division and always gives a float (`7 / 2` is `3.5`). `//` is floor division and rounds down (`7 // 2` is `3`).

### Q [Medium] How does Python manage memory?
Objects live in a private heap. Python counts the **references** to each object and frees it when the count reaches zero. A **cyclic garbage collector** also finds groups of objects that only refer to each other.

### Q [Easy] What is PEP 8?
The official style guide: 4 spaces for indentation, `snake_case` for variables and functions, `CapWords` for classes, and lines of about 79 characters. Following it makes code consistent.

### Q [Medium] What is dynamic typing?
You do not declare a variable's type. The **value** carries the type, and a name can point to a different type later. It is flexible, but mistakes appear at run time, so tests and type hints help.

### Q [Easy] What is a docstring?
A string written as the first statement of a module, function or class that describes it. It is available through `help()` and the `__doc__` attribute.

```python
def area(w, h):
    """Return the area of a rectangle."""
    return w * h
```

### Q [Medium] What does `if __name__ == "__main__":` do?
It runs the code below it only when the file is **run directly**, not when it is imported by another file. It lets one file work as both a script and a module.

:::practice mock-interview
Explain these answers aloud in a Mock Interview, not just in your head.
:::
