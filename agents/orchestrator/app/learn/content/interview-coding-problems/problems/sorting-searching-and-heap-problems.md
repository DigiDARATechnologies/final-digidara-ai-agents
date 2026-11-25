---
title: Sorting, searching and heap problems
summary: Sort colours, meeting rooms, find a peak, search a matrix and the first and last position of a value.
takeaways:
- The Dutch national flag sorts three values in one pass
- A min-heap tracks the earliest ending meeting
- Binary search works on any monotonic condition
---
## 1. Sort colours (Dutch national flag)

**Problem.** Sort an array of 0s, 1s and 2s in place in one pass.

```python
def sort_colors(nums):
    low, mid, high = 0, 0, len(nums) - 1
    while mid <= high:
        if nums[mid] == 0:
            nums[low], nums[mid] = nums[mid], nums[low]
            low += 1
            mid += 1
        elif nums[mid] == 1:
            mid += 1
        else:
            nums[mid], nums[high] = nums[high], nums[mid]
            high -= 1
    return nums

print(sort_colors([2, 0, 2, 1, 1, 0]))
```

```output
[0, 0, 1, 1, 2, 2]
```

**O(n)** time, **O(1)** space.

## 2. Meeting rooms II

**Problem.** Given meeting intervals, what is the minimum number of rooms needed?

**Idea.** Sort by start time. Keep a min-heap of end times of meetings in progress; if the earliest ending meeting has finished, reuse its room.

```python
import heapq

def min_rooms(meetings):
    meetings.sort()
    ends = []
    for start, end in meetings:
        if ends and ends[0] <= start:
            heapq.heappop(ends)           # reuse that room
        heapq.heappush(ends, end)
    return len(ends)

print(min_rooms([(0, 30), (5, 10), (15, 20)]), min_rooms([(7, 10), (2, 4)]))
```

```output
2 1
```

Time **O(n log n)**.

## 3. Find a peak element

**Problem.** A peak is greater than its neighbours. Find any peak in O(log n).

**Idea.** If `nums[mid] < nums[mid + 1]`, a peak must exist on the right; otherwise on the left (including mid).

```python
def find_peak(nums):
    low, high = 0, len(nums) - 1
    while low < high:
        mid = (low + high) // 2
        if nums[mid] < nums[mid + 1]:
            low = mid + 1
        else:
            high = mid
    return low

print(find_peak([1, 2, 3, 1]), find_peak([1, 2, 1, 3, 5, 6, 4]))
```

```output
2 5
```

The second array has peaks at indexes 1 and 5; either is valid.

## 4. Search a sorted 2D matrix

**Problem.** Each row is sorted and each row starts after the previous row ends. Treat it as one sorted list.

```python
def search_matrix(matrix, target):
    rows, cols = len(matrix), len(matrix[0])
    low, high = 0, rows * cols - 1
    while low <= high:
        mid = (low + high) // 2
        value = matrix[mid // cols][mid % cols]
        if value == target:
            return True
        if value < target:
            low = mid + 1
        else:
            high = mid - 1
    return False

grid = [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]]
print(search_matrix(grid, 3), search_matrix(grid, 13))
```

```output
True False
```

## 5. First and last position of a value

```python
from bisect import bisect_left, bisect_right

def search_range(nums, target):
    left = bisect_left(nums, target)
    if left == len(nums) or nums[left] != target:
        return [-1, -1]
    return [left, bisect_right(nums, target) - 1]

print(search_range([5, 7, 7, 8, 8, 10], 8), search_range([5, 7, 7, 8, 8, 10], 6))
```

```output
[3, 4] [-1, -1]
```

## 6. Top k frequent elements

```python
import heapq
from collections import Counter

def top_k_frequent(nums, k):
    counts = Counter(nums)
    return heapq.nlargest(k, counts, key=counts.get)

print(top_k_frequent([1, 1, 1, 2, 2, 3], 2))
```

```output
[1, 2]
```

:::remember
When a problem says "sorted" or asks for the smallest value that works, think binary search. When it asks for the best few items, think heap.
:::
