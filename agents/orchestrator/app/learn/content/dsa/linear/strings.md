---
title: Strings: common interview patterns
summary: Handle strings with confidence: palindromes, anagrams, reversing and character counting.
takeaways:
- Strings are immutable in Python; build results with lists and join
- Counting characters with a dictionary or Counter solves many problems
- Normalise first (case, spaces) before comparing
---
## Strings basics

A Python string is **immutable**: you cannot change a character in place. `s[0] = "x"` is an error; you create a new string. Slicing: `s[1:4]`, `s[::-1]` (reversed).

## Palindrome check (two pointers)

```python
def is_palindrome(s):
    cleaned = [c.lower() for c in s if c.isalnum()]
    left, right = 0, len(cleaned) - 1
    while left < right:
        if cleaned[left] != cleaned[right]:
            return False
        left += 1
        right -= 1
    return True

print(is_palindrome("A man, a plan, a canal: Panama"), is_palindrome("hello"))
```

```output
True False
```

## Anagrams

Two words are anagrams if they use the same letters the same number of times.

```python
from collections import Counter

def is_anagram(a, b):
    return Counter(a) == Counter(b)

print(is_anagram("listen", "silent"), is_anagram("rat", "car"))
```

```output
True False
```

## First non-repeating character

```python
from collections import Counter

def first_unique(s):
    counts = Counter(s)
    for index, ch in enumerate(s):
        if counts[ch] == 1:
            return index
    return -1

print(first_unique("leetcode"), first_unique("aabb"))
```

```output
0 -1
```

## Longest common prefix

```python
def common_prefix(words):
    if not words:
        return ""
    prefix = words[0]
    for word in words[1:]:
        while not word.startswith(prefix):
            prefix = prefix[:-1]
    return prefix

print(repr(common_prefix(["flower", "flow", "flight"])))
print(repr(common_prefix(["dog", "car"])))
```

```output
'fl'
''
```

## Compress repeated characters

```python
def compress(s):
    if not s:
        return ""
    parts = []
    count = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            count += 1
        else:
            parts.append(s[i - 1] + str(count))
            count = 1
    parts.append(s[-1] + str(count))
    return "".join(parts)

print(compress("aaabbc"))
```

```output
a3b2c1
```

## Useful string tools

| Tool | Use |
| --- | --- |
| `s.split()` / `" ".join(parts)` | words to list and back |
| `s.lower()`, `s.strip()` | normalise |
| `ord("a")` / `chr(97)` | character codes (count letters with `ord(c) - ord("a")`) |
| `s.find(sub)`, `sub in s` | search |

:::tip
For "group by letters" problems, use `"".join(sorted(word))` as a dictionary key. All anagrams share the same sorted key.
:::
