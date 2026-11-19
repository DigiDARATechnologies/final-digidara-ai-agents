---
title: Loops: for and while
summary: Repeat work with for and while, use range, break and continue.
takeaways:
- for walks through a sequence; while repeats until a test fails
- range(n) gives 0 up to n-1
- break leaves a loop; continue skips to the next round
---
## for: do something for each item

```python
for fruit in ["apple", "mango", "banana"]:
    print(fruit)
```

`for` takes the items one at a time and runs the indented block for each.

## range

`range` makes a sequence of numbers:

```python
for i in range(3):         # 0, 1, 2
    print(i)

for n in range(1, 6):      # 1 to 5
    print(n)

for n in range(10, 0, -3): # 10, 7, 4, 1
    print(n)
```

`range(start, stop, step)` stops **before** `stop`.

## while: repeat until a condition fails

```python
count = 3
while count > 0:
    print(count)
    count -= 1
print("Go!")
```

```output
3
2
1
Go!
```

:::warning
If nothing inside a `while` loop changes the condition, it never ends. Forgetting `count -= 1` above would loop forever. Press Ctrl+C to stop a runaway program.
:::

## break and continue

```python
for n in range(1, 10):
    if n % 2 == 0:
        continue      # skip even numbers
    if n > 7:
        break         # stop completely
    print(n)
```

```output
1
3
5
7
```

## A useful pattern: accumulate

```python
total = 0
for price in [120, 80, 45]:
    total += price
print("Total:", total)
```

```output
Total: 245
```

:::tip
Need the position as well as the item? Use `enumerate`: `for i, item in enumerate(items):`.
:::

:::practice leetcode
Loops are in almost every beginner coding problem. Try one in Coding Practice.
:::
