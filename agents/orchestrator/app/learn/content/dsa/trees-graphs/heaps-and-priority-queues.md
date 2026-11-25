---
title: Heaps and priority queues
summary: Get the smallest or largest item fast with a heap, and solve top-k and merge problems.
takeaways:
- A heap gives the minimum (or maximum) in O(1) and inserts or removes in O(log n)
- Python's heapq is a min-heap; negate numbers for a max-heap
- Top-k problems use a heap of size k
---
## The idea

A **priority queue** hands out the **most important** item first, not the oldest. A **heap** is the usual way to build it: a tree stored in a list where every parent is **smaller** than its children (min-heap), so the smallest item is always at the top.

| Operation | Cost |
| --- | --- |
| see the minimum | O(1) |
| push | O(log n) |
| pop the minimum | O(log n) |
| build from a list (`heapify`) | O(n) |

## Using heapq

```python
import heapq

heap = []
for number in [5, 1, 8, 3, 2]:
    heapq.heappush(heap, number)

print(heap[0])                  # smallest, without removing
print([heapq.heappop(heap) for _ in range(len(heap))])   # sorted order
```

```output
1
[1, 2, 3, 5, 8]
```

For a **max-heap**, push the negative of each number and negate again when popping.

```python
import heapq

nums = [5, 1, 8, 3, 2]
max_heap = [-x for x in nums]
heapq.heapify(max_heap)
print(-heapq.heappop(max_heap))
```

```output
8
```

## Kth largest element

Keep a **min-heap of size k**. Its top is the kth largest seen so far.

```python
import heapq

def kth_largest(nums, k):
    heap = []
    for x in nums:
        heapq.heappush(heap, x)
        if len(heap) > k:
            heapq.heappop(heap)       # drop the smallest
    return heap[0]

print(kth_largest([3, 2, 1, 5, 6, 4], 2))
```

```output
5
```

Time **O(n log k)**, which beats sorting everything (O(n log n)) when k is small. Python also has `heapq.nlargest(k, nums)`.

## Top k frequent words

```python
import heapq
from collections import Counter

def top_k_frequent(words, k):
    counts = Counter(words)
    return [word for word, _ in heapq.nlargest(k, counts.items(), key=lambda item: item[1])]

print(top_k_frequent(["a", "b", "a", "c", "b", "a", "d"], 2))
```

```output
['a', 'b']
```

## Merge k sorted lists

Put the first item of each list in a heap; pop the smallest and push the next item from the same list.

```python
import heapq

def merge_sorted(lists):
    heap = [(lst[0], i, 0) for i, lst in enumerate(lists) if lst]
    heapq.heapify(heap)
    result = []
    while heap:
        value, which, position = heapq.heappop(heap)
        result.append(value)
        if position + 1 < len(lists[which]):
            heapq.heappush(heap, (lists[which][position + 1], which, position + 1))
    return result

print(merge_sorted([[1, 4, 7], [2, 5, 8], [3, 6, 9]]))
```

```output
[1, 2, 3, 4, 5, 6, 7, 8, 9]
```

## Running median (two heaps)

A **max-heap** holds the smaller half and a **min-heap** the larger half. The median is at the tops. This gives the median of a stream in O(log n) per number.

## Where heaps are used

Dijkstra's shortest path, task schedulers, "k nearest", merging sorted data, and keeping the top scorers on a leaderboard.

:::tip
"Top k", "kth largest", "smallest k", "keep the best so far while streaming data"? Think heap.
:::
