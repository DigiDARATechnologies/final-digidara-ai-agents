---
title: Binary search
summary: Find items in sorted data in O(log n), and use the same idea to search for answers, not just values.
takeaways:
- Binary search halves the search range each step, giving O(log n)
- It needs sorted data or a yes/no condition that changes only once
- Binary search on the answer solves many 'minimum possible' problems
---
## The idea

Guess a number between 1 and 1,000,000. Always guess the **middle** and ask "higher or lower?". You need at most **20 guesses**, because each guess halves what is left. That is **O(log n)**.

It only works on **sorted** data.

## The standard code

```python
def binary_search(nums, target):
    low, high = 0, len(nums) - 1
    while low <= high:
        mid = (low + high) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1

data = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
print(binary_search(data, 23), binary_search(data, 7))
```

```output
5 -1
```

Each loop throws away half the numbers. A million items need about 20 steps, a billion only about 30.

## Python's built-in: bisect

```python
from bisect import bisect_left, bisect_right

data = [1, 2, 2, 2, 3, 5]
print(bisect_left(data, 2), bisect_right(data, 2))   # first and one past the last 2
print(bisect_right(data, 2) - bisect_left(data, 2), "copies of 2")
```

```output
1 4
3 copies of 2
```

## First position that meets a condition

Many problems are "find the **first** index where something becomes true". The pattern: keep `high` as a possible answer.

```python
def first_true(low, high, condition):
    while low < high:
        mid = (low + high) // 2
        if condition(mid):
            high = mid          # mid could be the answer, look left
        else:
            low = mid + 1       # too small, look right
    return low

# first number whose square is at least 50
print(first_true(0, 100, lambda x: x * x >= 50))
```

```output
8
```

## Binary search on the answer

Problem: **Koko eats bananas.** Piles `[3, 6, 7, 11]`, you have `h = 8` hours. Each hour she eats up to `k` bananas from one pile. What is the **smallest speed k** that finishes in time?

Speeds go from 1 to the biggest pile. If speed `k` works, any faster speed works too, so the answers look like `no no no yes yes yes`. Binary search finds the first `yes`.

```python
import math

def min_eating_speed(piles, h):
    def can_finish(k):
        return sum(math.ceil(p / k) for p in piles) <= h
    low, high = 1, max(piles)
    while low < high:
        mid = (low + high) // 2
        if can_finish(mid):
            high = mid
        else:
            low = mid + 1
    return low

print(min_eating_speed([3, 6, 7, 11], 8))
```

```output
4
```

## Rotated sorted array

`[4, 5, 6, 7, 0, 1, 2]` was sorted and then rotated. One half is always still sorted; check if the target lies in the sorted half.

```python
def search_rotated(nums, target):
    low, high = 0, len(nums) - 1
    while low <= high:
        mid = (low + high) // 2
        if nums[mid] == target:
            return mid
        if nums[low] <= nums[mid]:                 # left half sorted
            if nums[low] <= target < nums[mid]:
                high = mid - 1
            else:
                low = mid + 1
        else:                                      # right half sorted
            if nums[mid] < target <= nums[high]:
                low = mid + 1
            else:
                high = mid - 1
    return -1

print(search_rotated([4, 5, 6, 7, 0, 1, 2], 0), search_rotated([4, 5, 6, 7, 0, 1, 2], 3))
```

```output
4 -1
```

:::warning
Common bugs: using `<` instead of `<=` in the loop, and an infinite loop when `low` and `high` never move. Test with an array of one and two items.
:::
