---
title: Trees and binary search trees
summary: Understand binary trees, the traversals (DFS and BFS), height, and how a binary search tree keeps data ordered.
takeaways:
- A tree is nodes connected in a hierarchy; a binary tree has at most two children per node
- Traversals: preorder, inorder, postorder (depth-first) and level order (breadth-first)
- In a binary search tree, left is smaller and right is larger, so search is O(height)
---
## What is a tree?

A **tree** is a hierarchy of **nodes**: a **root** at the top, **children** below, and **leaves** with no children. Folders on your computer and the HTML of a web page are trees.

A **binary tree** gives each node at most two children: **left** and **right**.

```text
        8
      /   \
     3     10
    / \      \
   1   6      14
```

Terms: **height** is the longest path from root to a leaf; **depth** is a node's distance from the root.

## Build and traverse

```python
class TreeNode:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

root = TreeNode(8,
        TreeNode(3, TreeNode(1), TreeNode(6)),
        TreeNode(10, None, TreeNode(14)))

def preorder(node):                  # root, left, right
    return [] if not node else [node.value] + preorder(node.left) + preorder(node.right)

def inorder(node):                   # left, root, right
    return [] if not node else inorder(node.left) + [node.value] + inorder(node.right)

def postorder(node):                 # left, right, root
    return [] if not node else postorder(node.left) + postorder(node.right) + [node.value]

print(preorder(root))
print(inorder(root))
print(postorder(root))
```

```output
[8, 3, 1, 6, 10, 14]
[1, 3, 6, 8, 10, 14]
[1, 6, 3, 14, 10, 8]
```

These three are **depth-first** (DFS). Notice that **inorder** on this tree gives sorted numbers; that is a key property of binary search trees.

## Level order (breadth-first)

Visit the tree level by level using a **queue**.

```python
from collections import deque

def level_order(root):
    if not root:
        return []
    levels, queue = [], deque([root])
    while queue:
        level = []
        for _ in range(len(queue)):          # exactly one level
            node = queue.popleft()
            level.append(node.value)
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        levels.append(level)
    return levels

print(level_order(root))
```

```output
[[8], [3, 10], [1, 6, 14]]
```

## Height, size and checks

```python
def height(node):
    if not node:
        return 0
    return 1 + max(height(node.left), height(node.right))

def count(node):
    return 0 if not node else 1 + count(node.left) + count(node.right)

def is_symmetric(a, b):
    if not a and not b:
        return True
    if not a or not b or a.value != b.value:
        return False
    return is_symmetric(a.left, b.right) and is_symmetric(a.right, b.left)

print(height(root), count(root), is_symmetric(root, root))
```

```output
3 6 False
```

Most tree problems follow one recursive pattern: **answer for the node = combine the answers for the left and right subtrees**.

## Binary search tree (BST)

In a **BST**, for every node: everything in the left subtree is **smaller**, everything in the right subtree is **larger**. Search, insert and delete follow one path from the root.

```python
def insert(node, value):
    if not node:
        return TreeNode(value)
    if value < node.value:
        node.left = insert(node.left, value)
    elif value > node.value:
        node.right = insert(node.right, value)
    return node

def search(node, value):
    while node:
        if value == node.value:
            return True
        node = node.left if value < node.value else node.right
    return False

bst = None
for v in [8, 3, 10, 1, 6, 14, 4, 7]:
    bst = insert(bst, v)

print(inorder(bst))
print(search(bst, 6), search(bst, 5))
```

```output
[1, 3, 4, 6, 7, 8, 10, 14]
True False
```

Cost is **O(height)**. A balanced tree has height about log n, so O(log n). If you insert already-sorted data the tree becomes a **line** (height n, O(n)). Balanced trees (AVL, red-black) fix this automatically.

## Validate a BST

Checking only each node against its direct children is wrong. Pass down allowed **limits**.

```python
def is_bst(node, low=float("-inf"), high=float("inf")):
    if not node:
        return True
    if not (low < node.value < high):
        return False
    return is_bst(node.left, low, node.value) and is_bst(node.right, node.value, high)

print(is_bst(bst), is_bst(TreeNode(5, TreeNode(1), TreeNode(4, TreeNode(3), TreeNode(6)))))
```

```output
True False
```

:::remember
Trees are recursive. For any tree question ask: what do I need from the left subtree, from the right subtree, and how do I combine them at this node?
:::
