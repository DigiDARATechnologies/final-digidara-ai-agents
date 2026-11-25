---
title: Variables and types
summary: Store values with names, and meet integers, floats, strings and booleans.
takeaways:
- A variable is a name that points to a value
- The four basic types are int, float, str and bool
- type() tells you what a value is
---
## A variable is a labelled box

```python
name = "Asha"
age = 21
height = 1.62
is_student = True
```

Each line stores a value under a name. `=` here means "store", not "equals".

You can use the name later and change what it holds:

```python
age = 21
age = age + 1
print(age)
```

```output
22
```

## The basic types

| Type | Meaning | Example |
| --- | --- | --- |
| `int` | whole number | `42`, `-7` |
| `float` | number with a decimal point | `3.14` |
| `str` | text | `"hello"` |
| `bool` | true or false | `True`, `False` |

Ask Python which type a value has:

```python
print(type(42), type(3.14), type("hi"), type(True))
```

```output
<class 'int'> <class 'float'> <class 'str'> <class 'bool'>
```

## Naming rules

- Use letters, digits and `_`, and do not start with a digit.
- Names are case sensitive: `Score` and `score` are different.
- Use lowercase with underscores: `total_marks`, not `TotalMarks`.

:::remember
`"5"` (text) and `5` (number) are different. `"5" + "5"` is `"55"`, while `5 + 5` is `10`.
:::

## Converting between types

```python
marks = "85"          # text, maybe from user input
total = int(marks) + 5
print(total)
```

```output
90
```

`int()`, `float()` and `str()` convert a value. If the text is not a number, `int("abc")` raises a `ValueError`.

:::interview
**Interviewers often ask:** "Is Python statically or dynamically typed?" Dynamically: you do not declare a type, the value carries it, and a name can later point to a value of another type.
:::
