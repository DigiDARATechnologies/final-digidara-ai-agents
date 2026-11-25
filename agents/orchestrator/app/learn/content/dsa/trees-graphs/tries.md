---
title: Tries (prefix trees)
summary: Store words in a trie to autocomplete and check prefixes in time proportional to the word length.
takeaways:
- A trie stores strings character by character along a path
- Prefix search costs O(length of the prefix), regardless of how many words exist
- Used for autocomplete, spell checking and dictionary problems
---
## The idea

A **trie** (say "try") stores words as paths. Each node is a character; words that share a beginning share the path. A flag marks where a word **ends**.

```text
       root
      /    \
     c      d
     |      |
     a      o
    / \     |
   t*  r*   g*      words: cat, car, dog
```

## Build one

```python
class Trie:
    def __init__(self):
        self.root = {}

    def insert(self, word):
        node = self.root
        for ch in word:
            node = node.setdefault(ch, {})
        node["#"] = True                    # end of a word

    def _walk(self, text):
        node = self.root
        for ch in text:
            if ch not in node:
                return None
            node = node[ch]
        return node

    def search(self, word):
        node = self._walk(word)
        return bool(node and "#" in node)

    def starts_with(self, prefix):
        return self._walk(prefix) is not None

trie = Trie()
for w in ["cat", "car", "card", "dog"]:
    trie.insert(w)

print(trie.search("car"), trie.search("ca"), trie.starts_with("ca"), trie.starts_with("x"))
```

```output
True False True False
```

`search("ca")` is False because "ca" is only a prefix, not a stored word.

## Autocomplete

Walk to the end of the prefix, then collect every word below it.

```python
def autocomplete(trie, prefix):
    node = trie._walk(prefix)
    if node is None:
        return []
    results = []

    def collect(current, path):
        for key, child in sorted(current.items()):
            if key == "#":
                results.append(prefix + path)
            else:
                collect(child, path + key)

    collect(node, "")
    return results

print(autocomplete(trie, "ca"))
print(autocomplete(trie, "do"))
```

```output
['car', 'card', 'cat']
['dog']
```

## Cost

| Operation | Time |
| --- | --- |
| insert, search, prefix check | **O(L)**, L is the word length |
| space | up to O(total characters) |

A hash set also finds a whole word in O(L), but it **cannot** answer "which words start with `ca`?" quickly. A trie can.

## Typical problems

- Autocomplete and search suggestions
- Spell checkers
- Longest common prefix of many words
- Word search on a grid (stop early when no word has this prefix)

:::note
For interviews, know the idea and be able to write insert and search. A dictionary of dictionaries, as above, is the quickest way in Python.
:::
