---
title: What are data structures and algorithms?
summary: Understand why DSA matters for interviews and real software, and the roadmap you will follow in this course.
takeaways:
- A data structure organises data; an algorithm is the steps to solve a problem with it
- The right structure can make a program thousands of times faster
- Learn patterns, not memorised answers
---
## The two words

- A **data structure** is a way to store and organise data so it can be used efficiently: a list, a dictionary, a tree.
- An **algorithm** is a clear sequence of steps that solves a problem: search a name, sort marks, find the shortest route.

Together they decide how **fast** and how **memory-friendly** your program is.

## Why it matters: a quick experiment

Find whether a number is in a collection of 200,000 numbers, 200 times. First with a **list**, then with a **set**.

```python
import time

numbers = list(range(200_000))
as_set = set(numbers)
targets = [199_999] * 200

start = time.perf_counter()
for t in targets:
    t in numbers            # list: checks one by one
list_time = time.perf_counter() - start

start = time.perf_counter()
for t in targets:
    t in as_set             # set: jumps straight to it
set_time = time.perf_counter() - start

print("set is faster by more than 100 times:", list_time / set_time > 100)
```

```output
set is faster by more than 100 times: True
```

Same data, same question, completely different speed. Choosing the right structure is the whole skill.

## Why companies test it

- It shows you can **think clearly** about problems.
- It shows you know the cost of your code. At small scale anything works; at a million users it does not.
- Most product company interviews (and many service company tests) ask DSA questions.

## The roadmap in this course

| Stage | Topics |
| --- | --- |
| **Foundations** | Big-O, how to solve problems |
| **Linear structures** | arrays, strings, hash maps, linked lists, stacks, queues |
| **Search and sort** | binary search, sorting |
| **Recursion** | recursion, backtracking |
| **Trees and graphs** | trees, heaps, tries, graphs, shortest paths |
| **Paradigms** | greedy, dynamic programming, bits |
| **Interview** | patterns and questions |

## How to study

1. Understand the idea in plain words and draw it on paper.
2. Code it yourself without looking.
3. Solve 3 to 5 problems on it (LeetCode, HackerRank, GeeksforGeeks).
4. Write down the **pattern** and the **complexity** in a notebook.
5. Revisit after a week.

:::tip
Do not memorise solutions. If you recognise the **pattern** (two pointers, sliding window, BFS, DP), you can solve problems you have never seen.
:::
