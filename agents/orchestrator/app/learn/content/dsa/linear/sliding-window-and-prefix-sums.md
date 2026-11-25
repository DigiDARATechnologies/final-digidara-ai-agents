---
title: Sliding window and prefix sums
summary: Solve subarray problems in one pass with a moving window, and answer range-sum questions instantly with prefix sums.
takeaways:
- A sliding window reuses work when the window moves by one step
- Fixed windows keep a running total; variable windows grow and shrink
- A prefix-sum array answers any range sum in O(1)
---
## Fixed-size window

Problem: the maximum sum of any **k** consecutive numbers.

The slow way recalculates each window (O(n times k)). The smart way **slides**: add the new number, subtract the one that left.

```python
def max_sum_window(nums, k):
    window = sum(nums[:k])
    best = window
    for i in range(k, len(nums)):
        window += nums[i] - nums[i - k]   # add new, remove old
        best = max(best, window)
    return best

print(max_sum_window([2, 1, 5, 1, 3, 2], 3))
```

```output
9
```

The best window is `5 + 1 + 3 = 9`. Time **O(n)**.

## Variable-size window

Problem: the **longest substring without repeating characters**. Grow the window on the right; when a repeat appears, shrink from the left.

```python
def longest_unique(s):
    seen = {}            # character -> last index
    start = 0
    best = 0
    for end, ch in enumerate(s):
        if ch in seen and seen[ch] >= start:
            start = seen[ch] + 1       # jump past the earlier copy
        seen[ch] = end
        best = max(best, end - start + 1)
    return best

print(longest_unique("abcabcbb"), longest_unique("bbbbb"), longest_unique("pwwkew"))
```

```output
3 1 3
```

## Smallest subarray with sum at least target

```python
def min_length(target, nums):
    start = total = 0
    best = float("inf")
    for end, value in enumerate(nums):
        total += value
        while total >= target:             # shrink while still valid
            best = min(best, end - start + 1)
            total -= nums[start]
            start += 1
    return 0 if best == float("inf") else best

print(min_length(7, [2, 3, 1, 2, 4, 3]))
```

```output
2
```

## Prefix sums

Many questions ask for the sum of a range again and again. Build **prefix sums** once, then each answer is a subtraction.

```python
nums = [3, 1, 4, 1, 5, 9, 2, 6]
prefix = [0]
for x in nums:
    prefix.append(prefix[-1] + x)

def range_sum(left, right):         # inclusive indexes
    return prefix[right + 1] - prefix[left]

print(prefix)
print(range_sum(2, 5))              # 4 + 1 + 5 + 9
```

```output
[0, 3, 4, 8, 9, 14, 23, 25, 31]
19
```

`prefix[i]` is the sum of the first `i` numbers, so the sum from `left` to `right` is `prefix[right + 1] - prefix[left]`. Build in O(n), answer each query in **O(1)**.

## Subarray sum equals k (prefix sums plus a dictionary)

```python
def subarray_sum(nums, k):
    count = 0
    running = 0
    seen = {0: 1}                        # prefix sum -> how many times
    for x in nums:
        running += x
        count += seen.get(running - k, 0)
        seen[running] = seen.get(running, 0) + 1
    return count

print(subarray_sum([1, 2, 3, -2, 2], 3))
```

```output
4
```

If the running sum is `S` and an earlier running sum was `S - k`, then the part between them adds to `k`. This works even with negative numbers, where a sliding window does not.

:::remember
Contiguous subarray or substring + longest, shortest or best? Think sliding window. Many range sums? Think prefix sums.
:::
