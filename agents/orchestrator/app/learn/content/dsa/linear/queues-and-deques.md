---
title: Queues and deques
summary: Process items first-in, first-out with a queue, and use a deque for a sliding window maximum.
takeaways:
- A queue is first in, first out (FIFO)
- Use collections.deque: lists are slow at the front
- BFS, scheduling and sliding windows use queues and deques
---
## The idea

A queue is a line at a ticket counter: the **first** person in is the **first** served (**FIFO**). Add at the back, remove from the front.

Always use `collections.deque` for this. `list.pop(0)` is O(n), `deque.popleft()` is **O(1)**.

```python
from collections import deque

queue = deque()
queue.append("Asha")        # enqueue
queue.append("Ravi")
queue.append("Meena")
print(queue.popleft())      # dequeue -> Asha
print(list(queue))
```

```output
Asha
['Ravi', 'Meena']
```

Uses: print queues, CPU scheduling, messages in order, and **BFS** (the graph lesson).

## Stack with two queues, queue with two stacks

A classic interview question: build a queue using two stacks. Put new items on `inbox`. To remove, if `outbox` is empty move everything over (reversing the order), then pop.

```python
class QueueFromStacks:
    def __init__(self):
        self.inbox, self.outbox = [], []

    def push(self, x):
        self.inbox.append(x)

    def pop(self):
        if not self.outbox:
            while self.inbox:
                self.outbox.append(self.inbox.pop())
        return self.outbox.pop()

q = QueueFromStacks()
for x in [1, 2, 3]:
    q.push(x)
print(q.pop(), q.pop())
q.push(4)
print(q.pop(), q.pop())
```

```output
1 2
3 4
```

Each item moves at most twice, so operations are **O(1) on average**.

## Circular queue (idea)

A fixed-size buffer where the end wraps around to the start, using `index % size`. Useful when memory is limited.

## Deque for sliding window maximum

Problem: the maximum of every window of size k. Keep a deque of **indexes** whose values are in decreasing order; the front is always the maximum.

```python
from collections import deque

def window_max(nums, k):
    dq, result = deque(), []                  # dq holds indexes
    for i, value in enumerate(nums):
        while dq and nums[dq[-1]] <= value:   # smaller ones can never be the max
            dq.pop()
        dq.append(i)
        if dq[0] <= i - k:                    # front left the window
            dq.popleft()
        if i >= k - 1:
            result.append(nums[dq[0]])
    return result

print(window_max([1, 3, -1, -3, 5, 3, 6, 7], 3))
```

```output
[3, 3, 5, 5, 6, 7]
```

Each index enters and leaves the deque once: **O(n)**.

## Priority queue

A queue where the **most important** item leaves first, not the oldest. Covered in the heaps lesson.

:::tip
In Python write `from collections import deque`. A queue made with a plain list will pass small tests and then be too slow on large inputs.
:::
