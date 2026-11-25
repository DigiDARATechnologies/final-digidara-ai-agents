---
title: Problem-solving patterns cheat sheet
summary: A map from the wording of a problem to the technique that usually solves it, plus how to approach any question in an interview.
takeaways:
- Match the clue in the question to a pattern
- Start with brute force, state its cost, then improve it
- Say your thinking aloud and test with small examples
---
## The five-step approach

1. **Understand**: repeat the problem. Ask about the input size, duplicates, negative numbers, empty input, sorted or not.
2. **Examples**: work a small example by hand, including an edge case.
3. **Brute force**: say the simple solution and its cost, even if it is slow.
4. **Improve**: find the repeated work or the clue that points to a pattern (below).
5. **Code and test**: write clean code, then run through your example, the empty case and one tricky case. State the final time and space complexity.

## Clue to technique

| If the problem says... | Think |
| --- | --- |
| sorted array, find pair, in-place | **two pointers** |
| contiguous subarray or substring, longest or shortest | **sliding window** |
| many range sum queries | **prefix sums** |
| seen before, count, group, complement | **hash map or set** |
| sorted and search, or "minimum value that works" | **binary search** |
| matching brackets, nested, undo, next greater | **stack** |
| level by level, shortest path (unweighted) | **BFS** |
| all combinations, permutations, subsets | **backtracking** |
| tree problem | **recursion** (left, right, combine) |
| top k, kth largest, stream | **heap** |
| shortest path with weights | **Dijkstra** |
| ordering with dependencies | **topological sort** |
| connected groups, "are these linked?" | **union-find** or DFS |
| count ways, min or max over choices, repeating subproblems | **dynamic programming** |
| best local choice, intervals, sort first | **greedy** |
| one unique number, no extra space | **XOR / bits** |
| linked list middle or cycle | **slow and fast pointers** |

## Complexity targets

| Input size n | Aim for |
| --- | --- |
| up to 10 | O(n!) or O(2 to the n) may be fine (backtracking) |
| up to 1,000 | O(n squared) |
| up to 100,000 | O(n log n) |
| up to 1,000,000 or more | O(n) or O(log n) |

## Edge cases to always test

- empty input, a single element
- duplicates and all elements equal
- negative numbers and zero
- already sorted, reverse sorted
- very large input (does it time out?)

## Communicating

- Think aloud: "Brute force is O(n squared). I notice we search for a partner, so a hash map could make it O(n)."
- If stuck, simplify the problem or try a smaller example.
- Name your variables clearly and keep the code tidy.

## A practice plan

| Weeks | Focus |
| --- | --- |
| 1 | arrays, strings, hash maps (about 25 problems) |
| 2 | two pointers, sliding window, stacks, linked lists |
| 3 | binary search, sorting, recursion, backtracking |
| 4 | trees, graphs, heaps |
| 5 | dynamic programming and greedy |
| 6 | mixed practice and mock interviews |

Use LeetCode (Easy first), HackerRank and GeeksforGeeks. Solve, then **re-solve** the ones you struggled with after a week.

:::practice mock-interview
Practise explaining a solution aloud with the Mock Interview agent. Explaining clearly is half the interview.
:::
