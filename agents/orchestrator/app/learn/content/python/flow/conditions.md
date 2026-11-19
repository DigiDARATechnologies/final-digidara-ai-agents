---
title: Conditions: if, elif, else
summary: Make a program choose a path with if, elif, else, and combine tests with and, or, not.
takeaways:
- if runs a block only when its test is True
- Indentation is part of the syntax
- and, or and not combine conditions
---
## Choosing a path

```python
marks = 72

if marks >= 90:
    print("Distinction")
elif marks >= 60:
    print("First class")
else:
    print("Keep practising")
```

```output
First class
```

Python checks the tests from the top and runs the **first** block that is True, then skips the rest.

## Indentation matters

The block under `if` is the lines **indented** by the same amount (4 spaces is the usual choice). There are no braces, so the indentation is what groups the lines.

```python
if marks >= 40:
    print("Pass")
    print("Well done")   # also inside the if
print("Done")             # always runs
```

:::warning
Mixed tabs and spaces cause an `IndentationError`. Let your editor insert 4 spaces when you press Tab.
:::

## Combining conditions

```python
age = 20
has_id = True

if age >= 18 and has_id:
    print("Allowed in")

if age < 13 or age > 65:
    print("Discount")

if not has_id:
    print("Show your ID")
```

## Truthy and falsy

Empty things count as False: `0`, `""`, `[]`, `None`. Everything else is True.

```python
name = ""
if not name:
    print("Please enter your name")
```

## One-line choice

```python
status = "Pass" if marks >= 40 else "Fail"
```

:::interview
**Interviewers often ask:** "What is the difference between `==` and `is`?" `==` compares values; `is` checks whether two names point to the very same object. Use `is` mainly with `None`: `if x is None`.
:::
