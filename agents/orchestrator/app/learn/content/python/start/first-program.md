---
title: Your first program
summary: Run Python, print text, use comments, and read an error message.
takeaways:
- print() shows a value on the screen
- Lines starting with # are comments Python ignores
- An error message names the line and the kind of problem
---
## Two ways to run Python

**1. The interactive shell.** Type `python` (or `python3`) in a terminal. You get a `>>>` prompt. Type a line and see the result at once. It is perfect for trying things.

**2. A file.** Save your code as `hello.py` and run `python hello.py`. This is how real programs run.

## print()

`print()` writes whatever you give it to the screen:

```python
print("Hello")
print(2 + 3)
print("Total:", 2 + 3)
```

```output
Hello
5
Total: 5
```

Text goes inside quotes. Numbers do not need them. Separate several items with commas and Python puts a space between them.

## Comments

A comment is a note for people reading the code. Python skips it:

```python
# Add the two prices
total = 120 + 80   # 200
print(total)
```

:::tip
Comment the *why*, not the *what*. `# convert paise to rupees` helps. `# divide by 100` only repeats the code.
:::

## Reading an error

```python
print("Hello"
```

```output
SyntaxError: '(' was never closed
```

Python tells you the kind of error (`SyntaxError`), the line, and often what is missing. Read the **last line first**: it says what went wrong.

:::warning
Python cares about spelling and capitals. `Print("Hi")` fails because the function is `print`, all lowercase.
:::
