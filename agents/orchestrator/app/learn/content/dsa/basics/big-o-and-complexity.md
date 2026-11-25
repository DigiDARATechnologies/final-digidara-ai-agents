---
title: Big-O and complexity
summary: Measure how an algorithm grows with input size, and learn to read and compare time and space complexity.
takeaways:
- Big-O describes how the work grows as the input grows, ignoring small details
- Common growth rates: O(1), O(log n), O(n), O(n log n), O(n squared), O(2 to the n)
- Always consider both time and extra memory (space)
---
## The idea

We do not measure seconds (they depend on the computer). We count **how many steps** an algorithm takes as the input size **n** grows. **Big-O** is that growth rate, keeping only the biggest term.

- `3n + 10` steps is **O(n)**
- `n * n + 5n` steps is **O(n squared)**

## The common growth rates

| Big-O | Name | Example | 1,000 items |
| --- | --- | --- | --- |
| **O(1)** | constant | read `list[5]`, dictionary lookup | 1 step |
| **O(log n)** | logarithmic | binary search | about 10 steps |
| **O(n)** | linear | loop through a list | 1,000 steps |
| **O(n log n)** | linearithmic | good sorting | about 10,000 steps |
| **O(n squared)** | quadratic | nested loops | 1,000,000 steps |
| **O(2 to the n)** | exponential | all subsets | impossibly many |

## Seeing it in code

```python
def first_item(items):          # O(1): one step, however long the list
    return items[0]

def total(items):               # O(n): one pass
    result = 0
    for x in items:
        result += x
    return result

def has_duplicate_slow(items):  # O(n squared): compare every pair
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j]:
                return True
    return False

def has_duplicate_fast(items):  # O(n): remember what we have seen
    seen = set()
    for x in items:
        if x in seen:
            return True
        seen.add(x)
    return False

data = [4, 8, 15, 16, 23, 42, 8]
print(first_item(data), total(data), has_duplicate_slow(data), has_duplicate_fast(data))
```

```output
4 116 True True
```

Both duplicate checkers give the same answer, but for a million items the quadratic one would need about a trillion comparisons while the set version needs a million.

## How to find the complexity

1. **One loop over n items**: O(n).
2. **A loop inside a loop** (both over n): O(n squared).
3. **Halving the problem each step**: O(log n).
4. **Steps one after another**: add them, keep the biggest. `O(n) + O(n squared)` is O(n squared).
5. **Drop constants**: `O(2n)` is O(n).

## Space complexity

Space is the **extra memory** the algorithm needs (not counting the input). `has_duplicate_fast` uses a set that can grow to n items, so its space is **O(n)**, while the slow version uses **O(1)** extra space. This is a **trade-off**: we spend memory to save time.

## Best, average and worst case

Searching a list for a value: best case is the first item (O(1)), worst case is the last or missing (O(n)). Unless told otherwise, quote the **worst case**.

:::remember
If n is about 100,000 and you need to finish in a second, aim for O(n log n) or better. O(n squared) is about 10 billion steps and will be too slow.
:::
