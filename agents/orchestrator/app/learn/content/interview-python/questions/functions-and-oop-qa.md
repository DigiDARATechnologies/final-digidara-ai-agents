---
title: Functions and OOP
summary: Questions on arguments, decorators, generators, classes, inheritance and the GIL.
kind: qa
takeaways:
- Know *args, **kwargs, lambdas and decorators
- Explain inheritance and polymorphism with a small example
- Be able to describe generators and the GIL in two sentences
---
### Q [Easy] What is the difference between a function and a method?
A function stands alone. A **method** is a function defined inside a class and is called on an object, with the object passed as `self`.

### Q [Medium] What are `*args` and `**kwargs`?
`*args` collects extra positional arguments into a tuple. `**kwargs` collects extra named arguments into a dictionary. They let a function accept any number of arguments.

### Q [Medium] What is a lambda function?
A small anonymous function written on one line: `square = lambda n: n * n`. It is handy as a short key function, for example in `sorted(items, key=lambda x: x[1])`.

### Q [Hard] What is the mutable default argument problem?
A default value is created **once**, when the function is defined. If it is a list, every call shares it.

```python
def add(item, items=[]):   # bug
    items.append(item)
    return items

def add_fixed(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### Q [Medium] What are `__init__` and `self`?
`__init__` is the **initialiser**: it runs when an object is created and sets up its data. `self` is the object the method is acting on, passed automatically as the first argument.

### Q [Medium] Explain inheritance and polymorphism.
**Inheritance:** a class reuses the attributes and methods of a parent class. **Polymorphism:** different classes can have a method with the same name and behave in their own way, so code can call it without caring which class it is.

```python
class Animal:
    def speak(self): return "..."
class Dog(Animal):
    def speak(self): return "Woof"
for a in (Animal(), Dog()):
    print(a.speak())
```

### Q [Medium] What is the difference between `@staticmethod` and `@classmethod`?
A static method gets no automatic first argument and behaves like a plain function inside the class. A class method receives the **class** (`cls`) and is often used for alternate constructors.

### Q [Medium] What is a decorator?
A function that takes a function and returns a new one, adding behaviour around it (logging, timing, checking permissions). The `@name` syntax above a function applies it.

```python
def shout(fn):
    def wrapper(*a, **k):
        return fn(*a, **k).upper()
    return wrapper

@shout
def hello():
    return "hello"
```

### Q [Hard] What is a generator and why use `yield`?
A generator function uses `yield` to produce values **one at a time** instead of building a whole list. It keeps its state between values, so it uses very little memory, which is useful for large or endless data.

### Q [Hard] What is the GIL?
The **Global Interpreter Lock** in CPython lets only one thread run Python bytecode at a time. Threads therefore do not speed up CPU-heavy work; use the `multiprocessing` module for that. Threads still help with waiting tasks such as network calls.

:::practice mock-interview
Rehearse explaining decorators and generators in a Mock Interview.
:::
