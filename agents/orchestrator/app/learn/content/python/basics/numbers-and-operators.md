---
title: Numbers and operators
summary: Arithmetic, integer division, remainder, powers and comparison operators.
takeaways:
- / always gives a float, // divides and drops the fraction
- % gives the remainder
- Comparison operators give True or False
---
## Arithmetic

```python
print(7 + 2)    # 9
print(7 - 2)    # 5
print(7 * 2)    # 14
print(7 / 2)    # 3.5
print(7 // 2)   # 3   (floor division)
print(7 % 2)    # 1   (remainder)
print(2 ** 3)   # 8   (power)
```

`/` always gives a float, even for `8 / 2` (it gives `4.0`). Use `//` when you want a whole number of times something fits.

## Remainder is more useful than it looks

```python
number = 14
print(number % 2 == 0)   # True: even numbers leave no remainder
```

Checking for even numbers, wrapping around a list, and splitting seconds into minutes all use `%`.

```python
seconds = 135
print(seconds // 60, "min", seconds % 60, "sec")
```

```output
2 min 15 sec
```

## Order of operations

Python follows the usual rules: brackets first, then powers, then `* /`, then `+ -`.

```python
print(2 + 3 * 4)     # 14
print((2 + 3) * 4)   # 20
```

## Shortcuts

```python
count = 10
count += 1   # same as count = count + 1
count *= 2   # now 22
```

## Comparing values

| Operator | Meaning |
| --- | --- |
| `==` | equal to |
| `!=` | not equal to |
| `<` `>` | less than, greater than |
| `<=` `>=` | less or equal, greater or equal |

```python
print(5 == 5.0)   # True
print(3 != 4)     # True
```

:::warning
Use `==` to compare and `=` to store. Writing `if x = 5:` is an error.
:::

:::remember
Floats can be slightly off: `0.1 + 0.2` gives `0.30000000000000004`. Use `round(value, 2)` when you print money.
:::
