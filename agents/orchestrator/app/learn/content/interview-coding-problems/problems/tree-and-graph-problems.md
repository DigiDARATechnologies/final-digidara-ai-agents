---
title: Tree and graph problems
summary: Depth, inversion, lowest common ancestor, diameter, path sum and a BFS grid problem.
takeaways:
- Tree problems: combine the answers from the left and right subtrees
- BST problems use the ordering to choose a side
- Shortest steps on a grid or graph means BFS
---
```python
class TreeNode:
    def __init__(self, value, left=None, right=None):
        self.value, self.left, self.right = value, left, right

root = TreeNode(3, TreeNode(9), TreeNode(20, TreeNode(15), TreeNode(7)))
print(root.value, root.left.value, root.right.value)
```

```output
3 9 20
```

## 1. Maximum depth

```python
def max_depth(node):
    if not node:
        return 0
    return 1 + max(max_depth(node.left), max_depth(node.right))

print(max_depth(root))
```

```output
3
```

## 2. Invert a binary tree

Swap the left and right child of every node.

```python
def invert(node):
    if node:
        node.left, node.right = invert(node.right), invert(node.left)
    return node

def inorder(node):
    return [] if not node else inorder(node.left) + [node.value] + inorder(node.right)

print(inorder(root))
invert(root)
print(inorder(root))
```

```output
[9, 3, 15, 20, 7]
[7, 20, 15, 3, 9]
```

## 3. Lowest common ancestor in a BST

**Idea.** If both values are smaller than the node, go left; if both are larger, go right; otherwise the node is the answer.

```python
def lca_bst(node, p, q):
    while node:
        if p < node.value and q < node.value:
            node = node.left
        elif p > node.value and q > node.value:
            node = node.right
        else:
            return node.value

bst = TreeNode(6, TreeNode(2, TreeNode(0), TreeNode(4, TreeNode(3), TreeNode(5))), TreeNode(8, TreeNode(7), TreeNode(9)))
print(lca_bst(bst, 2, 8), lca_bst(bst, 3, 5))
```

```output
6 4
```

**O(height)**.

## 4. Diameter of a binary tree

The longest path (in edges) between any two nodes. At each node, the best path through it is `left depth + right depth`.

```python
def diameter(root):
    best = 0
    def depth(node):
        nonlocal best
        if not node:
            return 0
        left, right = depth(node.left), depth(node.right)
        best = max(best, left + right)
        return 1 + max(left, right)
    depth(root)
    return best

tree = TreeNode(1, TreeNode(2, TreeNode(4), TreeNode(5)), TreeNode(3))
print(diameter(tree))
```

```output
3
```

## 5. Path sum

Does a root-to-leaf path add up to the target?

```python
def has_path_sum(node, target):
    if not node:
        return False
    if not node.left and not node.right:
        return node.value == target
    return has_path_sum(node.left, target - node.value) or has_path_sum(node.right, target - node.value)

t = TreeNode(5, TreeNode(4, TreeNode(11, TreeNode(7), TreeNode(2))), TreeNode(8, TreeNode(13), TreeNode(4, None, TreeNode(1))))
print(has_path_sum(t, 22), has_path_sum(t, 100))
```

```output
True False
```

## 6. Rotting oranges (multi-source BFS)

**Problem.** In a grid, `2` is a rotten orange, `1` fresh, `0` empty. Each minute rotten oranges rot their four neighbours. How many minutes until none is fresh (or -1 if impossible)?

**Idea.** Start BFS from **all** rotten oranges at once; each BFS level is one minute.

```python
from collections import deque

def oranges_rotting(grid):
    rows, cols = len(grid), len(grid[0])
    queue = deque((r, c) for r in range(rows) for c in range(cols) if grid[r][c] == 2)
    fresh = sum(row.count(1) for row in grid)
    minutes = 0
    while queue and fresh:
        for _ in range(len(queue)):
            r, c = queue.popleft()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                    grid[nr][nc] = 2
                    fresh -= 1
                    queue.append((nr, nc))
        minutes += 1
    return minutes if fresh == 0 else -1

print(oranges_rotting([[2, 1, 1], [1, 1, 0], [0, 1, 1]]))
print(oranges_rotting([[2, 1, 1], [0, 1, 1], [1, 0, 1]]))
```

```output
4
-1
```

The second grid has a fresh orange in the bottom-left corner that can never be reached, so the answer is -1. Time **O(rows x cols)**.
