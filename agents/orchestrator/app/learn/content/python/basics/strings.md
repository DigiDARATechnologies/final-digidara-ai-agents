---
title: Strings
summary: Work with text: indexing, slicing, common methods and f-strings.
takeaways:
- Strings are sequences, so you can index and slice them
- Strings are immutable: methods return a new string
- f-strings put values inside text cleanly
---
## Text in Python

A string is text between quotes. Single or double quotes both work:

```python
city = "Chennai"
word = 'code'
```

## Indexing and slicing

Each character has a position, starting at **0**:

```python
text = "PYTHON"
print(text[0])     # P
print(text[-1])    # N  (last character)
print(text[1:4])   # YTH (start 1, stop before 4)
```

| Index | 0 | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| Character | P | Y | T | H | O | N |

## Useful methods

```python
s = "  Hello World  "
print(s.strip())          # remove spaces at both ends
print(s.lower())          # lowercase
print(s.upper())          # uppercase
print("a,b,c".split(","))  # ['a', 'b', 'c']
print("-".join(["a", "b"]))  # a-b
print("hello".replace("l", "L"))  # heLLo
```

:::warning
Strings are **immutable**. `s.upper()` does not change `s`; it gives back a new string. Store it if you want to keep it: `s = s.upper()`.
:::

## f-strings

Put a value inside text by starting the string with `f` and using braces:

```python
name = "Asha"
score = 92.456
print(f"{name} scored {score:.1f}")
```

```output
Asha scored 92.5
```

`:.1f` means "one digit after the decimal point".

## Checking text

```python
email = "asha@example.com"
print("@" in email)           # True
print(email.startswith("asha"))  # True
print(len(email))             # 16
```

:::interview
**Interviewers often ask:** "How do you reverse a string?" `text[::-1]`. The slice walks the string with a step of -1.
:::

:::practice leetcode
Strings appear in many coding rounds. Try a string problem in Coding Practice.
:::
