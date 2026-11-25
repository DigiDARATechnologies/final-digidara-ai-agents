---
title: Dynamic programming: the basics
summary: Learn to spot overlapping subproblems and solve them once with memoization or a table.
takeaways:
- DP applies when a problem has overlapping subproblems and optimal substructure
- Top-down: recursion plus memoization. Bottom-up: fill a table
- Steps: define the state, write the recurrence, set the base cases, choose the order
---
## When to think DP

DP is **recursion that remembers**. Use it when:

1. The problem breaks into **smaller versions of itself** (optimal substructure).
2. The **same subproblems repeat** (overlapping subproblems).
3. You are asked for a **count, the minimum, the maximum, or whether it is possible**.

## Four steps

1. **State**: what do I need to know? (`dp[i]` means ...)
2. **Recurrence**: how does `dp[i]` come from smaller states?
3. **Base cases**: the smallest answers.
4. **Order / answer**: compute from small to large; where is the final answer?

## Climbing stairs

You can climb 1 or 2 steps at a time. How many ways to reach step n?

- To reach step `n`, you came from `n - 1` or `n - 2`, so `ways(n) = ways(n-1) + ways(n-2)`.

**Top-down (memoization):**

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def ways(n):
    if n <= 2:
        return n               # 1 way to reach 1, 2 ways to reach 2
    return ways(n - 1) + ways(n - 2)

print([ways(n) for n in range(1, 9)], ways(40))
```

```output
[1, 2, 3, 5, 8, 13, 21, 34] 165580141
```

**Bottom-up (table):**

```python
def ways_table(n):
    if n <= 2:
        return n
    dp = [0] * (n + 1)
    dp[1], dp[2] = 1, 2
    for i in range(3, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n]

print(ways_table(40))
```

```output
165580141
```

Both are **O(n)**. Because we only need the last two values, space can drop to **O(1)** with two variables.

## House robber

Houses with money in a row; you cannot rob two **adjacent** houses. Maximum money?

At house `i`: skip it (keep the best up to `i-1`) or rob it (its money plus the best up to `i-2`).

```python
def rob(nums):
    take, skip = 0, 0
    for money in nums:
        take, skip = skip + money, max(take, skip)
    return max(take, skip)

print(rob([2, 7, 9, 3, 1]), rob([1, 2, 3, 1]))
```

```output
12 4
```

## Coin change (minimum coins)

Fixes the greedy failure from the last lesson. `dp[a]` is the fewest coins to make amount `a`.

```python
def min_coins(coins, amount):
    INF = float("inf")
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        for coin in coins:
            if coin <= a:
                dp[a] = min(dp[a], dp[a - coin] + 1)
    return dp[amount] if dp[amount] != INF else -1

print(min_coins([4, 3, 1], 6), min_coins([2], 3), min_coins([1, 2, 5], 11))
```

```output
2 -1 3
```

For `[4, 3, 1]` and 6 the answer is 2 (3 + 3), the case greedy got wrong. Time **O(amount x coins)**.

## Maximum subarray (Kadane's algorithm)

The best sum of a contiguous subarray. At each number, either **extend** the previous subarray or **start fresh**.

```python
def max_subarray(nums):
    best = current = nums[0]
    for x in nums[1:]:
        current = max(x, current + x)
        best = max(best, current)
    return best

print(max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]))
```

```output
6
```

The best subarray is `4, -1, 2, 1`. One pass, O(n), O(1) space.

## Memoization vs tabulation

| | Top-down (memo) | Bottom-up (table) |
| --- | --- | --- |
| Style | recursion plus cache | loops filling a table |
| Computes | only the needed states | all states |
| Risk | recursion depth | none |
| Easier to | write first | optimise space |

:::tip
Start by writing the plain recursion. If it repeats work, add `@lru_cache`. That alone solves many interview DP problems.
:::
