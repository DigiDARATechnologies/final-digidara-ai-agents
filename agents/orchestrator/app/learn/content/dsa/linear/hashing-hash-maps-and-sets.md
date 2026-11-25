---
title: Hash maps and sets
summary: Use dictionaries and sets to look things up in constant time: the most useful tool in coding interviews.
takeaways:
- A hash map stores key-value pairs with O(1) average lookup
- A set stores unique items with O(1) membership tests
- Trading memory for speed with a hash map turns many O(n squared) solutions into O(n)
---
## How hashing works

A **hash function** turns a key (like `"asha"`) into a number, and that number decides which **bucket** stores it. To find the key later, hash it again and go straight to the bucket. That is why lookups are O(1) on average.

Two keys can land in the same bucket (a **collision**); the structure handles it (for example with a small list per bucket), and it stays fast as long as buckets are not overloaded.

Only **hashable** (unchangeable) keys work: strings, numbers, tuples. Lists cannot be keys.

## Two Sum: the classic

Find two numbers that add up to a target. Brute force checks all pairs (O(n squared)). With a dictionary we need one pass.

```python
def two_sum(nums, target):
    seen = {}                       # value -> index
    for index, value in enumerate(nums):
        need = target - value
        if need in seen:
            return seen[need], index
        seen[value] = index
    return None

print(two_sum([2, 7, 11, 15], 9))
print(two_sum([3, 2, 4], 6))
```

```output
(0, 1)
(1, 2)
```

At each number we ask "have I already seen the partner I need?" in O(1). Total **O(n)** time and O(n) space.

## Frequency counting

```python
def most_common_word(text):
    counts = {}
    for word in text.lower().split():
        counts[word] = counts.get(word, 0) + 1
    return max(counts, key=counts.get), counts

print(most_common_word("the cat and the hat and the bat"))
```

```output
('the', {'the': 3, 'cat': 1, 'and': 2, 'hat': 1, 'bat': 1})
```

## Group anagrams

```python
def group_anagrams(words):
    groups = {}
    for w in words:
        groups.setdefault("".join(sorted(w)), []).append(w)
    return list(groups.values())

print(group_anagrams(["eat", "tea", "tan", "ate", "nat", "bat"]))
```

```output
[['eat', 'tea', 'ate'], ['tan', 'nat'], ['bat']]
```

## Sets: uniqueness and membership

```python
a = {1, 2, 3, 4}
b = {3, 4, 5}
print(a & b, a | b, a - b)

def longest_consecutive(nums):
    values = set(nums)
    best = 0
    for n in values:
        if n - 1 not in values:           # start of a run
            length = 1
            while n + length in values:
                length += 1
            best = max(best, length)
    return best

print(longest_consecutive([100, 4, 200, 1, 3, 2]))
```

```output
{3, 4} {1, 2, 3, 4, 5} {1, 2}
4
```

The longest consecutive sequence is `1, 2, 3, 4`. We only start counting at the **start** of a run, so every number is visited a constant number of times: O(n).

## When to reach for a hash map

- "Have I seen this before?" (a set)
- "How many times?" (a counter)
- "Find a partner / complement" (Two Sum)
- "Group by something" (anagrams)
- "Remember a result so I do not recompute it" (caching, DP)

:::remember
Hash map = **memory for speed**. If a nested loop is only searching for something, a dictionary can usually replace the inner loop.
:::
