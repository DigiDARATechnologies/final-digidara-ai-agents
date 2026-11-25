---
title: Advanced Python concepts
summary: Iterators, generators, decorators, context managers, dunder methods, memory, MRO and dataclasses.
kind: qa
takeaways:
- Explain decorators, generators and context managers with a tiny example
- Know how Python manages memory and copies objects
- Use dunder methods, properties and dataclasses
---
### Q [Medium] What is the difference between an iterator and an iterable?
An **iterable** can be looped over (list, string, dict): it has `__iter__`. An **iterator** produces items one at a time with `__next__` and remembers its position. `iter(list)` gives an iterator, and a `for` loop does this for you.

### Q [Medium] What is a generator and how is it different from a list comprehension?
A generator produces values **lazily** with `yield` (or a generator expression `(x for x in data)`), so it uses almost no memory and can be endless. A list comprehension builds the whole list in memory at once.

### Q [Medium] How do decorators work?
A decorator takes a function and returns a new function that wraps it. `@timer` above `def work()` means `work = timer(work)`. Use `functools.wraps` so the wrapped function keeps its name and docstring.

```python
import functools, time

def timer(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        print(f"{fn.__name__} took {time.perf_counter() - start:.4f}s")
        return result
    return wrapper
```

### Q [Medium] What is a context manager and the `with` statement?
An object that sets something up and always cleans it up (closing a file, releasing a lock). It implements `__enter__` and `__exit__`, or you write one with `contextlib.contextmanager`. `with open("a.txt") as f:` closes the file even if an error occurs.

### Q [Medium] What are `*args` and `**kwargs`?
`*args` collects extra **positional** arguments into a tuple. `**kwargs` collects extra **keyword** arguments into a dict. They let a function accept any number of arguments and are used to pass arguments through.

### Q [Medium] What are dunder (magic) methods? Give examples.
Methods with double underscores that Python calls for special syntax: `__init__` (constructor), `__str__` and `__repr__` (text form), `__len__` (`len(x)`), `__eq__` (`==`), `__add__` (`+`), `__getitem__` (`x[i]`).

### Q [Medium] `__str__` vs `__repr__`?
`__str__` is the readable form for users (`print`). `__repr__` is the unambiguous form for developers (and is used if `__str__` is missing).

### Q [Medium] What is `@property`?
It turns a method into an attribute that is calculated on access, with optional setter validation, keeping a clean interface: `circle.area` instead of `circle.area()`.

### Q [Medium] Shallow copy vs deep copy?
A **shallow copy** (`copy.copy`) copies the outer container but shares the inner objects. A **deep copy** (`copy.deepcopy`) copies everything recursively. With nested lists, changing an inner list through a shallow copy changes the original too.

### Q [Medium] How does Python manage memory?
Objects live on a private heap. **Reference counting** frees an object when nothing refers to it, and a **cyclic garbage collector** cleans up reference cycles. You do not free memory manually.

### Q [Medium] What is the difference between a module and a package?
A **module** is a single `.py` file. A **package** is a folder of modules (with an `__init__.py` file) that you import together.

### Q [Medium] What does `if __name__ == "__main__":` do?
It runs the code only when the file is executed directly, not when it is imported as a module. It keeps test or demo code from running on import.

### Q [Hard] What is method resolution order (MRO)?
The order in which Python searches classes for a method in multiple inheritance. It uses the **C3 linearisation**; see it with `ClassName.__mro__`. `super()` follows this order.

### Q [Medium] What is a dataclass?
A decorator (`@dataclass`) that generates `__init__`, `__repr__` and `__eq__` for a class that mostly holds data, so you write only the fields.

### Q [Hard] `async`/`await` vs threads?
`async` code runs many I/O-bound tasks on **one thread** by switching at each `await`; it is lightweight and good for thousands of network waits. Threads run in parallel for blocking calls but share memory and are limited by the GIL for CPU work. For CPU-heavy tasks use multiprocessing.
