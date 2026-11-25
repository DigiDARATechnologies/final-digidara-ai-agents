---
title: Sorting algorithms
summary: Learn how bubble, insertion, merge and quick sort work, their costs, and which one Python uses.
takeaways:
- Simple sorts (bubble, insertion, selection) are O(n squared)
- Merge sort and quick sort are O(n log n) using divide and conquer
- In real code use sorted() and list.sort(), which are O(n log n) and stable
---
## Why sorting matters

Sorted data enables binary search, two pointers, and quick duplicate detection. Interviewers like sorting because it shows how you think about cost.

## Insertion sort: O(n squared)

Like sorting playing cards in your hand: take each card and insert it in the right place among those already sorted.

```python
def insertion_sort(nums):
    nums = nums[:]
    for i in range(1, len(nums)):
        current = nums[i]
        j = i - 1
        while j >= 0 and nums[j] > current:
            nums[j + 1] = nums[j]      # shift bigger items right
            j -= 1
        nums[j + 1] = current
    return nums

print(insertion_sort([5, 2, 9, 1, 5, 6]))
```

```output
[1, 2, 5, 5, 6, 9]
```

It is simple and fast on **small or almost-sorted** lists. Bubble sort and selection sort are similar O(n squared) sorts used mainly for teaching.

## Merge sort: O(n log n)

**Divide and conquer**: split in half, sort each half, then **merge** the two sorted halves.

```python
def merge_sort(nums):
    if len(nums) <= 1:
        return nums
    mid = len(nums) // 2
    left = merge_sort(nums[:mid])
    right = merge_sort(nums[mid:])
    merged, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i]); i += 1
        else:
            merged.append(right[j]); j += 1
    return merged + left[i:] + right[j:]

print(merge_sort([38, 27, 43, 3, 9, 82, 10]))
```

```output
[3, 9, 10, 27, 38, 43, 82]
```

The list is halved about log n times, and each level does n work to merge, so **O(n log n)** always. It needs O(n) extra space and is **stable** (equal items keep their order).

## Quick sort: O(n log n) on average

Pick a **pivot**, put smaller items on the left and larger on the right, then sort each side.

```python
def quick_sort(nums):
    if len(nums) <= 1:
        return nums
    pivot = nums[len(nums) // 2]
    smaller = [x for x in nums if x < pivot]
    equal   = [x for x in nums if x == pivot]
    larger  = [x for x in nums if x > pivot]
    return quick_sort(smaller) + equal + quick_sort(larger)

print(quick_sort([38, 27, 43, 3, 9, 82, 10]))
```

```output
[3, 9, 10, 27, 38, 43, 82]
```

Average **O(n log n)**; the worst case is **O(n squared)** if pivots are chosen badly (for example always the smallest item on sorted data). Real implementations are in place and pick pivots carefully.

## Comparison

| Algorithm | Best | Average | Worst | Extra space | Stable |
| --- | --- | --- | --- | --- | --- |
| Bubble / selection | O(n) / O(n squared) | O(n squared) | O(n squared) | O(1) | bubble yes |
| Insertion | O(n) | O(n squared) | O(n squared) | O(1) | yes |
| Merge | O(n log n) | O(n log n) | O(n log n) | O(n) | yes |
| Quick | O(n log n) | O(n log n) | O(n squared) | O(log n) | no |
| Heap | O(n log n) | O(n log n) | O(n log n) | O(1) | no |
| Counting | O(n + k) | O(n + k) | O(n + k) | O(k) | yes |

A general comparison sort can never beat **O(n log n)**. Counting sort beats it only for small integer ranges because it does not compare items.

## What Python uses

`sorted()` and `list.sort()` use **Timsort**, a hybrid of merge and insertion sort. It is O(n log n), **stable**, and very fast on partly sorted data.

```python
people = [("Ravi", 25), ("Asha", 25), ("Meena", 22)]
print(sorted(people, key=lambda p: p[1]))        # stable: Ravi stays before Asha
```

```output
[('Meena', 22), ('Ravi', 25), ('Asha', 25)]
```

## Sorting problems

- **Merge intervals**: sort by start, then merge overlaps.
- **Kth largest**: sort, or use a heap (better).
- **Sort colours (0, 1, 2)**: counting or the Dutch national flag, O(n).

```python
def merge_intervals(intervals):
    intervals = sorted(intervals)
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged

print(merge_intervals([[1, 3], [8, 10], [2, 6], [15, 18]]))
```

```output
[[1, 6], [8, 10], [15, 18]]
```

:::interview Which sorting algorithm is best?
It depends. Merge sort has guaranteed O(n log n) and is stable; quick sort is usually fastest in practice; insertion sort is best for tiny or nearly sorted data. In Python just use `sorted()`.
:::
