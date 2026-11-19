---
title: Reading and writing files
summary: Open files with the with statement, read lines, write and append text.
takeaways:
- Use with open(...) so the file closes by itself
- Modes: r read, w write (overwrites), a append
- Loop over a file to read it line by line
---
## Open a file safely

```python
with open("notes.txt", "w") as f:
    f.write("Line one\n")
    f.write("Line two\n")
```

`with` closes the file for you when the block ends, even if an error happens. This is the standard way to open files.

## Modes

| Mode | What it does |
| --- | --- |
| `"r"` | read (default); the file must exist |
| `"w"` | write; **erases** an existing file |
| `"a"` | append to the end |

## Reading

```python
with open("notes.txt") as f:
    content = f.read()        # the whole file as one string
print(content)
```

For large files read line by line:

```python
with open("notes.txt") as f:
    for line in f:
        print(line.strip())
```

```output
Line one
Line two
```

`strip()` removes the newline at the end of each line.

## Appending

```python
with open("notes.txt", "a") as f:
    f.write("Line three\n")
```

## A practical example

Count the lines that contain a word:

```python
count = 0
with open("notes.txt") as f:
    for line in f:
        if "Line" in line:
            count += 1
print(count)
```

:::warning
Opening a file with `"w"` deletes what was in it. Use `"a"` if you want to keep the old content.
:::

:::remember
Handle `FileNotFoundError` when the file may not exist. See the lesson on errors.
:::
