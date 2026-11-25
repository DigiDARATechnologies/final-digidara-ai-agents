---
title: Errors and exceptions
summary: Handle problems with try, except, else and finally, and raise your own errors.
takeaways:
- try/except stops an error from ending the program
- Catch specific exceptions, not everything
- finally runs whether or not an error happened
---
## When something goes wrong

```python
number = int("abc")
```

```output
ValueError: invalid literal for int() with base 10: 'abc'
```

Python **raised** a `ValueError`. Without handling it, the program stops. With `try` and `except` you decide what happens instead.

## try and except

```python
try:
    age = int(input("Age: "))
    print("Next year:", age + 1)
except ValueError:
    print("Please type a number.")
```

The `try` block runs. If a `ValueError` happens, Python jumps to `except`.

## Common exceptions

| Exception | Typical cause |
| --- | --- |
| `ValueError` | right type, wrong value: `int("x")` |
| `TypeError` | wrong type: `"a" + 1` |
| `KeyError` | missing dictionary key |
| `IndexError` | list index out of range |
| `ZeroDivisionError` | dividing by zero |
| `FileNotFoundError` | opening a file that is not there |

## else and finally

```python
try:
    file = open("data.txt")
except FileNotFoundError:
    print("No such file")
else:
    print("Opened fine")      # only if no error
    file.close()
finally:
    print("Always runs")      # error or not
```

## Raising your own

```python
def set_age(age):
    if age < 0:
        raise ValueError("age cannot be negative")
    return age
```

:::tip
Catch the **specific** exception you expect. A bare `except:` hides bugs, including ones you did not think of.
:::

:::interview
**Interviewers often ask:** "What is the difference between an error and an exception?" A syntax error stops the program before it runs. An exception happens while it runs, and you can catch it and carry on.
:::
