---
title: Recursion
summary: Solve problems by letting a function call itself: base case, recursive case, the call stack and when to avoid it.
takeaways:
- Every recursive function needs a base case that stops it
- Each call must move closer to the base case
- Overlapping calls can explode in cost; memoization fixes that
---
## The idea

**Recursion** means a function solves a problem by calling itself on a **smaller** version of the same problem.

Two parts, always:

1. **Base case**: the simplest version, answered directly (this stops the recursion).
2. **Recursive case**: reduce the problem and call yourself.

## Factorial

`5! = 5 x 4 x 3 x 2 x 1`, and `n! = n x (n - 1)!`

```python
def factorial(n):
    if n <= 1:                 # base case
        return 1
    return n * factorial(n - 1)   # smaller problem

print(factorial(5))
```

```output
120
```

## How the call stack works

```text
factorial(3)
  waits for factorial(2)
      waits for factorial(1) -> returns 1
    returns 2 * 1 = 2
  returns 3 * 2 = 6
```

Each unfinished call sits on the **call stack** until the one below it returns. Without a base case the stack grows until Python raises `RecursionError` (the default limit is about 1000 calls).

## Sum of a list and reverse a string

```python
def total(nums):
    if not nums:
        return 0
    return nums[0] + total(nums[1:])

def reverse(text):
    if len(text) <= 1:
        return text
    return reverse(text[1:]) + text[0]

print(total([1, 2, 3, 4]), reverse("python"))
```

```output
10 nohtyp
```

## Power in O(log n)

Instead of multiplying n times, use `x^n = (x^(n/2))^2`.

```python
def power(x, n):
    if n == 0:
        return 1
    half = power(x, n // 2)
    if n % 2 == 0:
        return half * half
    return half * half * x

print(power(2, 10), power(3, 5))
```

```output
1024 243
```

## The Fibonacci trap and memoization

```python
def fib_slow(n):
    if n < 2:
        return n
    return fib_slow(n - 1) + fib_slow(n - 2)     # repeats the same work

calls = 0
def fib_counted(n):
    global calls
    calls += 1
    if n < 2:
        return n
    return fib_counted(n - 1) + fib_counted(n - 2)

fib_counted(20)
print("calls without memo:", calls)

from functools import lru_cache

@lru_cache(maxsize=None)
def fib_fast(n):
    if n < 2:
        return n
    return fib_fast(n - 1) + fib_fast(n - 2)

print(fib_fast(50))
```

```output
calls without memo: 21891
12586269025
```

`fib(20)` made over 21,000 calls because the same values are recomputed again and again (the cost is exponential). **Memoization** stores each result the first time, so every value is computed once: O(n). This is the seed of **dynamic programming**.

## Recursion vs loops

| Recursion | Loop |
| --- | --- |
| natural for trees, nested data, divide and conquer | simple counting and scanning |
| uses call stack memory | O(1) memory |
| risk of `RecursionError` | no depth limit |

Any recursion can be written with a loop and an explicit stack.

:::remember
1) Write the base case first. 2) Trust that the recursive call works on the smaller problem. 3) Combine its answer into yours.
:::
