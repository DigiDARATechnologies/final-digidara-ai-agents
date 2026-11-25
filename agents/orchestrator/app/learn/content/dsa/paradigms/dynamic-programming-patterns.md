---
title: Dynamic programming patterns
summary: Recognise the common DP shapes: 0/1 knapsack, subsequences, grids and strings.
takeaways:
- Most DP problems fit a few patterns
- 1D: stairs, robber. 2D: grids, strings, knapsack
- Define dp carefully; the recurrence follows from the definition
---
## Pattern 1: grid paths

A robot moves only right or down from the top-left to the bottom-right of an `m` by `n` grid. How many paths?

`dp[r][c] = dp[r-1][c] + dp[r][c-1]` (arrive from above or from the left).

```python
def grid_paths(rows, cols):
    dp = [[1] * cols for _ in range(rows)]      # first row and column: one way
    for r in range(1, rows):
        for c in range(1, cols):
            dp[r][c] = dp[r - 1][c] + dp[r][c - 1]
    return dp[-1][-1]

print(grid_paths(3, 7), grid_paths(3, 3))
```

```output
28 6
```

A **minimum path sum** is the same shape with `min` and the cell cost.

```python
def min_path_sum(grid):
    rows, cols = len(grid), len(grid[0])
    dp = [row[:] for row in grid]
    for r in range(rows):
        for c in range(cols):
            if r == 0 and c == 0:
                continue
            best = min(dp[r - 1][c] if r else float("inf"),
                       dp[r][c - 1] if c else float("inf"))
            dp[r][c] += best
    return dp[-1][-1]

print(min_path_sum([[1, 3, 1], [1, 5, 1], [4, 2, 1]]))
```

```output
7
```

## Pattern 2: 0/1 knapsack

Each item can be taken **once**. Maximise value within a weight limit. `dp[w]` is the best value with capacity `w`. Loop capacity **backwards** so an item is not used twice.

```python
def knapsack(items, capacity):                 # items: (weight, value)
    dp = [0] * (capacity + 1)
    for weight, value in items:
        for w in range(capacity, weight - 1, -1):
            dp[w] = max(dp[w], dp[w - weight] + value)
    return dp[capacity]

print(knapsack([(1, 1), (3, 4), (4, 5), (5, 7)], 7))
```

```output
9
```

The best is the items with weights 3 and 4, worth 9. Many problems are knapsack in disguise: **subset sum**, **partition into equal halves**, **target sum**.

```python
def can_partition(nums):
    total = sum(nums)
    if total % 2:
        return False
    target = total // 2
    reachable = {0}
    for x in nums:
        reachable |= {r + x for r in reachable if r + x <= target}
    return target in reachable

print(can_partition([1, 5, 11, 5]), can_partition([1, 2, 3, 5]))
```

```output
True False
```

## Pattern 3: longest increasing subsequence (LIS)

`dp[i]` is the length of the longest increasing subsequence **ending at** `i`.

```python
def lis(nums):
    dp = [1] * len(nums)
    for i in range(len(nums)):
        for j in range(i):
            if nums[j] < nums[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)

print(lis([10, 9, 2, 5, 3, 7, 101, 18]))
```

```output
4
```

This is O(n squared). A cleverer method with binary search makes it O(n log n); know that it exists.

## Pattern 4: two strings (LCS and edit distance)

**Longest common subsequence**: `dp[i][j]` for the first `i` letters of `a` and first `j` of `b`. If the letters match, add 1 to the diagonal; otherwise take the better of dropping a letter from either string.

```python
def lcs(a, b):
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[-1][-1]

print(lcs("abcde", "ace"), lcs("abc", "def"))
```

```output
3 0
```

**Edit distance**: the fewest insert, delete or replace operations to turn one word into another (spell checkers, diff tools).

```python
def edit_distance(a, b):
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        dp[i][0] = i                      # delete everything
    for j in range(len(b) + 1):
        dp[0][j] = j                      # insert everything
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j],      # delete
                                   dp[i][j - 1],      # insert
                                   dp[i - 1][j - 1])  # replace
    return dp[-1][-1]

print(edit_distance("horse", "ros"), edit_distance("kitten", "sitting"))
```

```output
3 3
```

## Pattern summary

| Pattern | State | Examples |
| --- | --- | --- |
| 1D linear | `dp[i]` | stairs, robber, coin change, Kadane |
| Grid | `dp[r][c]` | paths, minimum path sum |
| Knapsack | `dp[capacity]` | subset sum, partition |
| Subsequence | `dp[i]` ending at i | LIS |
| Two strings | `dp[i][j]` | LCS, edit distance |

:::remember
DP is about **defining the state clearly**. Write in words what `dp[i]` or `dp[i][j]` means before writing any code.
:::
