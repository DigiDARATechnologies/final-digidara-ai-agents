---
title: Shortest paths, topological sort and union-find
summary: Use Dijkstra for weighted shortest paths, topological sort for ordering tasks, and union-find for connected groups.
takeaways:
- Dijkstra finds shortest paths with non-negative weights using a min-heap
- Topological sort orders tasks that depend on each other (a directed acyclic graph)
- Union-find quickly merges and checks groups
---
## Dijkstra: shortest path with weights

BFS counts edges. When edges have **costs** (km, minutes), use **Dijkstra**: always expand the node with the **smallest known distance** next, using a min-heap.

```python
import heapq

def dijkstra(graph, start):
    distance = {node: float("inf") for node in graph}
    distance[start] = 0
    heap = [(0, start)]
    while heap:
        current, node = heapq.heappop(heap)
        if current > distance[node]:
            continue                          # outdated entry
        for neighbour, weight in graph[node]:
            candidate = current + weight
            if candidate < distance[neighbour]:
                distance[neighbour] = candidate
                heapq.heappush(heap, (candidate, neighbour))
    return distance

roads = {
    "A": [("B", 4), ("C", 1)],
    "B": [("D", 1)],
    "C": [("B", 2), ("D", 5)],
    "D": [],
}
print(dijkstra(roads, "A"))
```

```output
{'A': 0, 'B': 3, 'C': 1, 'D': 4}
```

The direct road A to B costs 4, but A to C to B costs only 1 + 2 = 3, and Dijkstra finds it. Time **O((V + E) log V)**.

:::warning
Dijkstra does **not** work with negative edge weights. (Bellman-Ford handles those.)
:::

## Topological sort: ordering by dependencies

Courses have prerequisites. A valid study order puts every course **after** its prerequisites. This works only if there is **no cycle**. Method (Kahn's algorithm): repeatedly take nodes with **no remaining prerequisites**.

```python
from collections import deque

def course_order(count, prerequisites):
    graph = {i: [] for i in range(count)}
    needs = [0] * count                     # number of unmet prerequisites
    for course, before in prerequisites:
        graph[before].append(course)
        needs[course] += 1

    queue = deque(i for i in range(count) if needs[i] == 0)
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in graph[node]:
            needs[nxt] -= 1
            if needs[nxt] == 0:
                queue.append(nxt)
    return order if len(order) == count else []     # empty means a cycle

print(course_order(4, [(1, 0), (2, 0), (3, 1), (3, 2)]))
print(course_order(2, [(0, 1), (1, 0)]))
```

```output
[0, 1, 2, 3]
[]
```

If the result has fewer nodes than expected, a **cycle** exists and the courses can never be finished. Uses: build systems, task schedulers, course planning.

## Union-find (disjoint set)

Keeps track of which items belong to the same group. Two operations: **find** (which group?) and **union** (merge two groups).

```python
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]   # path compression
            x = self.parent[x]
        return x

    def union(self, a, b):
        root_a, root_b = self.find(a), self.find(b)
        if root_a == root_b:
            return False                 # already together
        self.parent[root_a] = root_b
        return True

uf = UnionFind(6)
for a, b in [(0, 1), (1, 2), (3, 4)]:
    uf.union(a, b)

print(uf.find(0) == uf.find(2), uf.find(0) == uf.find(3))
groups = len({uf.find(i) for i in range(6)})
print("groups:", groups)
```

```output
True False
groups: 3
```

With path compression, each operation is almost **O(1)**. Uses: number of connected groups, detecting a cycle when adding edges, Kruskal's minimum spanning tree.

## Choosing the tool

| Need | Algorithm |
| --- | --- |
| fewest edges | BFS |
| cheapest path, non-negative costs | Dijkstra |
| order with dependencies | topological sort |
| groups and "are these connected?" | union-find |
