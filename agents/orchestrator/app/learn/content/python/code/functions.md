---
title: Functions
summary: Package code with def, parameters, return values and default arguments.
takeaways:
- def creates a function; return sends a value back
- Parameters are inputs; defaults make them optional
- A function without return gives back None
---
## Why functions

When the same steps appear twice, give them a name and reuse them.

```python
def greet(name):
    return f"Hello, {name}!"

print(greet("Asha"))
print(greet("Ravi"))
```

```output
Hello, Asha!
Hello, Ravi!
```

`def` defines the function, `name` is a **parameter**, and `return` sends a result back.

## Parameters and defaults

```python
def area(width, height=1):
    return width * height

print(area(4, 5))      # 20
print(area(4))         # 4
print(area(height=3, width=2))  # 6, named arguments
```

## Returning several values

```python
def min_max(numbers):
    return min(numbers), max(numbers)

low, high = min_max([4, 9, 2])
print(low, high)   # 2 9
```

Python returns a tuple, which you unpack into two names.

## print versus return

```python
def add_print(a, b):
    print(a + b)       # shows it, returns None

def add_return(a, b):
    return a + b       # gives the value back

total = add_return(2, 3) + 10   # 15
```

:::remember
`print` is for people to read. `return` is for the rest of your program to use.
:::

## Scope

A variable created inside a function exists only there:

```python
def f():
    x = 5

f()
print(x)    # NameError
```

## *args and **kwargs

```python
def total(*numbers):
    return sum(numbers)

print(total(1, 2, 3))   # 6
```

`*numbers` collects extra positional arguments into a tuple. `**options` collects extra named arguments into a dictionary.

:::warning
Never use a list as a default value (`def f(items=[])`). The same list is shared between calls. Use `None` and create the list inside.
:::

:::interview
**Interviewers often ask:** "What is a lambda?" A small one-line unnamed function: `square = lambda n: n * n`. Handy with `sorted(key=...)` and `map`.
:::
