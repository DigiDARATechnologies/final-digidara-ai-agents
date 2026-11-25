---
title: Linked lists
summary: Understand nodes and pointers, and solve the classic linked list problems: reverse, find the middle, detect a cycle and merge.
takeaways:
- A linked list is a chain of nodes, each pointing to the next
- Insert or delete at a known node is O(1), but reaching a position is O(n)
- Slow and fast pointers and reversal solve most problems
---
## What it is

A list in Python stores items side by side. A **linked list** stores each item in a **node** that also holds a reference to the **next node**.

```text
head -> [3 | *] -> [7 | *] -> [9 | None]
```

| | Array / list | Linked list |
| --- | --- | --- |
| Access item `i` | O(1) | O(n) (walk from the head) |
| Insert / delete at the front | O(n) | **O(1)** |
| Insert after a known node | O(n) | **O(1)** |
| Memory | compact | extra pointer per item |

## Build one

```python
class Node:
    def __init__(self, value, next=None):
        self.value = value
        self.next = next

def from_list(values):
    head = None
    for v in reversed(values):
        head = Node(v, head)
    return head

def to_list(head):
    result = []
    while head:
        result.append(head.value)
        head = head.next
    return result

head = from_list([1, 2, 3, 4, 5])
print(to_list(head))
```

```output
[1, 2, 3, 4, 5]
```

## Reverse a linked list

Walk once, pointing each node backwards. Keep three variables: `previous`, `current` and `next`.

```python
def reverse(head):
    previous = None
    current = head
    while current:
        nxt = current.next      # remember the rest
        current.next = previous # flip the arrow
        previous = current
        current = nxt
    return previous

print(to_list(reverse(from_list([1, 2, 3, 4, 5]))))
```

```output
[5, 4, 3, 2, 1]
```

**O(n)** time, **O(1)** space.

## Slow and fast pointers: the middle

Move `slow` one step and `fast` two steps. When fast reaches the end, slow is in the middle.

```python
def middle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
    return slow.value

print(middle(from_list([1, 2, 3, 4, 5])), middle(from_list([1, 2, 3, 4, 5, 6])))
```

```output
3 4
```

## Detect a cycle (Floyd's algorithm)

If the list loops back on itself, a fast pointer eventually **catches** the slow one, like a faster runner lapping a slower one on a track.

```python
def has_cycle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            return True
    return False

a = from_list([1, 2, 3, 4])
print(has_cycle(a))
tail = a
while tail.next:
    tail = tail.next
tail.next = a.next          # make the last node point back to node 2
print(has_cycle(a))
```

```output
False
True
```

## Merge two sorted lists

```python
def merge(a, b):
    dummy = tail = Node(0)
    while a and b:
        if a.value <= b.value:
            tail.next, a = a, a.next
        else:
            tail.next, b = b, b.next
        tail = tail.next
    tail.next = a or b
    return dummy.next

print(to_list(merge(from_list([1, 4, 6]), from_list([2, 3, 7]))))
```

```output
[1, 2, 3, 4, 6, 7]
```

A **dummy node** at the start avoids special cases for an empty result.

## Tips

- Always check for an **empty list** and a **single node**.
- Draw the arrows on paper before changing pointers.
- Doubly linked lists keep a `prev` pointer too (used by caches and browser history).

:::interview Array vs linked list?
Arrays give fast index access and are cache-friendly; linked lists give fast insertion and deletion at known positions but slow access by position and use more memory.
:::
