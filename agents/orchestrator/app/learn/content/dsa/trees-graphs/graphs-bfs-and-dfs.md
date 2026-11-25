---
title: Graphs, BFS and DFS
summary: Model connections with graphs and explore them with breadth-first and depth-first search.
takeaways:
- A graph is nodes (vertices) connected by edges; store it as an adjacency list
- BFS explores level by level with a queue and finds the fewest steps
- DFS goes deep first with recursion or a stack and finds connected components, paths and cycles
---
## What is a graph?

A **graph** is a set of **nodes** (vertices) joined by **edges**. Roads between cities, friends on a social network, links between web pages: all graphs.

- **Directed**: edges have a direction (follow someone). **Undirected**: both ways (friends).
- **Weighted**: edges carry a cost (distance).

## Adjacency list

Store, for each node, the list of its neighbours. It is compact and what interviews expect.

```python
edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("D", "E")]

graph = {}
for a, b in edges:
    graph.setdefault(a, []).append(b)
    graph.setdefault(b, []).append(a)      # undirected: add both ways

print(graph)
```

```output
{'A': ['B', 'C'], 'B': ['A', 'D'], 'C': ['A', 'D'], 'D': ['B', 'C', 'E'], 'E': ['D']}
```

Space is O(V + E): V vertices, E edges.

## Breadth-first search (BFS)

Explore all neighbours first, then their neighbours: **level by level**, using a **queue**. BFS finds the **shortest path in an unweighted graph**.

```python
from collections import deque

def bfs_distance(graph, start, goal):
    queue = deque([(start, 0)])
    visited = {start}
    while queue:
        node, distance = queue.popleft()
        if node == goal:
            return distance
        for neighbour in graph[node]:
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append((neighbour, distance + 1))
    return -1

print(bfs_distance(graph, "A", "E"))
```

```output
3
```

The **visited set** is essential. Without it a graph with a cycle would loop forever. Time **O(V + E)**.

## Depth-first search (DFS)

Go as deep as possible along one path, then backtrack. Use **recursion** (or a stack).

```python
def dfs(graph, node, visited=None):
    visited = visited if visited is not None else set()
    visited.add(node)
    order = [node]
    for neighbour in graph[node]:
        if neighbour not in visited:
            order += dfs(graph, neighbour, visited)
    return order

print(dfs(graph, "A"))
```

```output
['A', 'B', 'D', 'C', 'E']
```

## Which to use?

| Problem | Use |
| --- | --- |
| shortest path (fewest edges) | **BFS** |
| is there a path? connected components? | DFS or BFS |
| explore all possibilities, cycles, topological order | **DFS** |

## Number of islands (grid as a graph)

A grid of land (`1`) and water (`0`) is a graph: each cell connects to its four neighbours.

```python
def count_islands(grid):
    rows, cols = len(grid), len(grid[0])
    seen = set()

    def sink(r, c):
        if r < 0 or c < 0 or r >= rows or c >= cols:
            return
        if grid[r][c] == "0" or (r, c) in seen:
            return
        seen.add((r, c))
        sink(r + 1, c); sink(r - 1, c); sink(r, c + 1); sink(r, c - 1)

    islands = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == "1" and (r, c) not in seen:
                islands += 1
                sink(r, c)
    return islands

grid = ["11000",
        "11000",
        "00100",
        "00011"]
print(count_islands(grid))
```

```output
3
```

## Detect a cycle in an undirected graph

```python
def has_cycle(graph):
    visited = set()

    def visit(node, parent):
        visited.add(node)
        for neighbour in graph[node]:
            if neighbour == parent:
                continue
            if neighbour in visited or visit(neighbour, node):
                return True
        return False

    return any(visit(n, None) for n in graph if n not in visited)

print(has_cycle(graph))
print(has_cycle({"A": ["B"], "B": ["A", "C"], "C": ["B"]}))
```

```output
True
False
```

:::remember
Graph questions often hide in other shapes: grids, word ladders, courses and prerequisites, networks. Spot the nodes and edges, then choose BFS or DFS.
:::
