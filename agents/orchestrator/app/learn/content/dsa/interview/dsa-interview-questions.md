---
title: DSA interview questions
summary: Frequently asked DSA concept questions with short answers, from arrays and hashing to graphs and dynamic programming.
takeaways:
- Know definitions, costs and trade-offs, not just code
- Always mention time and space complexity
- Give a small example with each answer
kind: qa
---
### Q [Easy] What is the difference between an array and a linked list?
An array stores items contiguously with O(1) access by index but O(n) insertion in the middle. A linked list stores nodes with pointers, giving O(1) insertion at a known node but O(n) access by position, and extra memory for pointers.

### Q [Easy] What is Big-O notation?
A way to describe how the running time or memory of an algorithm grows with the input size n, ignoring constants and smaller terms. For example, one loop is O(n) and two nested loops are O(n squared).

### Q [Easy] Stack vs queue?
A stack is last-in, first-out (undo, bracket matching, DFS). A queue is first-in, first-out (scheduling, BFS).

### Q [Easy] How does a hash map work and what is its cost?
A hash function maps a key to a bucket so get, set and delete are O(1) on average. Collisions are handled with chaining or probing, and the worst case is O(n).

### Q [Easy] What is recursion? What are its two parts?
A function calling itself on a smaller problem. It needs a base case to stop and a recursive case that moves toward it.

### Q [Medium] Compare merge sort and quick sort.
Both are divide and conquer. Merge sort is always O(n log n), stable, but needs O(n) extra space. Quick sort is O(n log n) on average with O(log n) space and usually faster in practice, but its worst case is O(n squared).

### Q [Medium] What is binary search and its requirement?
Search a sorted collection by repeatedly halving the range. It takes O(log n). The data must be sorted (or the condition monotonic).

### Q [Medium] How do you detect a cycle in a linked list?
Floyd's algorithm: move a slow pointer by one and a fast pointer by two. If they meet, there is a cycle. O(n) time, O(1) space.

### Q [Medium] BFS vs DFS?
BFS uses a queue and explores level by level, giving the shortest path in an unweighted graph. DFS uses recursion or a stack and goes deep first, useful for components, cycles and topological order. Both are O(V + E).

### Q [Medium] What is a binary search tree and its complexity?
A binary tree where left values are smaller and right values are larger. Search, insert and delete are O(height): O(log n) if balanced, O(n) if skewed.

### Q [Medium] When would you use a heap?
When you repeatedly need the smallest or largest item: top-k, kth largest, merging sorted lists, scheduling, Dijkstra. Push and pop are O(log n).

### Q [Medium] How do you find two numbers that add to a target?
In one pass with a hash map storing seen values: for each number check whether `target - number` was seen. O(n) time, O(n) space. On a sorted array, two pointers give O(1) space.

### Q [Medium] What is a trie and when is it used?
A tree where each node is a character, so words with a shared prefix share a path. Used for autocomplete and prefix search in O(length of word).

### Q [Hard] What is dynamic programming?
Solving a problem by combining solutions to overlapping subproblems, storing each result so it is computed once (memoization or tabulation). It applies when there is optimal substructure and repeated subproblems.

### Q [Hard] Greedy vs dynamic programming?
Greedy takes the best local choice and never revisits it, which is fast but valid only when local choices lead to a global optimum (activity selection). DP considers all options via subproblems (coin change with arbitrary coins, 0/1 knapsack).

### Q [Hard] How does Dijkstra's algorithm work and what are its limits?
It repeatedly takes the unvisited node with the smallest known distance from a min-heap and relaxes its edges. O((V + E) log V). It fails with negative edge weights (use Bellman-Ford).

### Q [Hard] What is topological sorting?
An ordering of a directed acyclic graph where every node comes after the nodes it depends on. Use Kahn's algorithm with in-degrees or DFS. If not all nodes are output, there is a cycle.

### Q [Hard] How would you find the median of a data stream?
Keep a max-heap for the smaller half and a min-heap for the larger half, balanced in size. The median is at the heap tops. Each insert is O(log n).

### Q [Hard] Explain the difference between memoization and tabulation.
Memoization is top-down recursion with a cache and computes only needed states. Tabulation is bottom-up iteration over a table; it avoids recursion depth and often allows space optimisation.

### Q [Hard] How do you detect and handle a cycle when ordering course prerequisites?
Build a directed graph and run a topological sort. If fewer nodes than courses are produced, a cycle exists and all courses cannot be completed.
