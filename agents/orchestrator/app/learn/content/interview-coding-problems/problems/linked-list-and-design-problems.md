---
title: Linked list and design problems
summary: Remove the nth node from the end, check a palindrome list, and design an LRU cache.
takeaways:
- Two pointers with a gap find the nth node from the end in one pass
- A dummy node removes special cases at the head
- An LRU cache combines a hash map with an ordering of use
---
Helper used in the examples:

```python
class Node:
    def __init__(self, value, next=None):
        self.value = value
        self.next = next

def build(values):
    head = None
    for v in reversed(values):
        head = Node(v, head)
    return head

def to_list(head):
    out = []
    while head:
        out.append(head.value)
        head = head.next
    return out

print(to_list(build([1, 2, 3])))
```

```output
[1, 2, 3]
```

## 1. Remove the nth node from the end

**Idea.** Move `fast` n steps ahead. Then move `fast` and `slow` together; when `fast` reaches the end, `slow` is just before the node to remove. A **dummy node** handles removing the head.

```python
def remove_nth_from_end(head, n):
    dummy = Node(0, head)
    fast = slow = dummy
    for _ in range(n):
        fast = fast.next
    while fast.next:
        fast = fast.next
        slow = slow.next
    slow.next = slow.next.next
    return dummy.next

print(to_list(remove_nth_from_end(build([1, 2, 3, 4, 5]), 2)))
print(to_list(remove_nth_from_end(build([1]), 1)))
```

```output
[1, 2, 3, 5]
[]
```

One pass, **O(n)** time, **O(1)** space.

## 2. Palindrome linked list

**Idea.** Find the middle with slow and fast pointers, reverse the second half, then compare both halves.

```python
def is_palindrome(head):
    slow = fast = head
    while fast and fast.next:
        slow, fast = slow.next, fast.next.next
    previous = None
    while slow:                       # reverse the second half
        slow.next, previous, slow = previous, slow, slow.next
    left, right = head, previous
    while right:
        if left.value != right.value:
            return False
        left, right = left.next, right.next
    return True

print(is_palindrome(build([1, 2, 2, 1])), is_palindrome(build([1, 2, 3])))
```

```output
True False
```

**O(n)** time, **O(1)** space.

## 3. LRU cache

**Problem.** A cache with a fixed capacity. `get` and `put` must be O(1). When full, remove the **least recently used** item.

**Idea.** An `OrderedDict` keeps order of use; move an item to the end when it is used, and remove from the front when full.

```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.items = OrderedDict()

    def get(self, key):
        if key not in self.items:
            return -1
        self.items.move_to_end(key)           # now the most recently used
        return self.items[key]

    def put(self, key, value):
        if key in self.items:
            self.items.move_to_end(key)
        self.items[key] = value
        if len(self.items) > self.capacity:
            self.items.popitem(last=False)    # drop the least recently used

cache = LRUCache(2)
cache.put(1, "one")
cache.put(2, "two")
print(cache.get(1))
cache.put(3, "three")        # evicts key 2
print(cache.get(2), cache.get(3))
```

```output
one
-1 three
```

If asked to build it **without** `OrderedDict`, use a hash map from key to node plus a **doubly linked list**; moving a node and removing the tail are both O(1).

## 4. Detect and find the start of a cycle

```python
def cycle_start(head):
    slow = fast = head
    while fast and fast.next:
        slow, fast = slow.next, fast.next.next
        if slow is fast:
            slow = head
            while slow is not fast:
                slow, fast = slow.next, fast.next
            return slow.value
    return None

a = build([3, 2, 0, -4])
tail = a
while tail.next:
    tail = tail.next
tail.next = a.next                 # the tail points back to the node with value 2
print(cycle_start(a))
```

```output
2
```

After the pointers meet, restart one from the head; moving both one step at a time, they meet at the **start of the cycle**.
