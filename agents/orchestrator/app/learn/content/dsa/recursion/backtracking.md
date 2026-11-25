---
title: Backtracking
summary: Explore all choices, undo them and try the next: subsets, permutations, combinations and N-Queens style problems.
takeaways:
- Backtracking is choose, explore, undo (unchoose)
- It builds solutions step by step and abandons a path as soon as it cannot work
- Subsets, permutations and combinations all follow the same template
---
## The idea

Imagine searching a maze. At each junction you pick a path. If it is a dead end, you **go back** and try another. That is **backtracking**: build an answer one choice at a time, and **undo** the choice when you return.

## The template

```text
def explore(current_choices):
    if the answer is complete:
        save it
        return
    for each possible next choice:
        make the choice          # choose
        explore(...)             # explore
        undo the choice          # unchoose
```

## Subsets

All subsets of `[1, 2, 3]`. For each number we choose: **include** it or **skip** it.

```python
def subsets(nums):
    result, current = [], []

    def explore(index):
        if index == len(nums):
            result.append(current[:])      # copy the current choice
            return
        current.append(nums[index])        # include
        explore(index + 1)
        current.pop()                      # undo
        explore(index + 1)                 # skip

    explore(0)
    return result

print(subsets([1, 2, 3]))
```

```output
[[1, 2, 3], [1, 2], [1, 3], [1], [2, 3], [2], [3], []]
```

There are 2 to the n subsets, so this is **O(2 to the n)**; nothing can be faster because that many answers must be produced.

Note `current[:]`: we save a **copy**, because `current` keeps changing.

## Permutations

All orderings of `[1, 2, 3]`: at each position try every number not yet used.

```python
def permutations(nums):
    result, current, used = [], [], [False] * len(nums)

    def explore():
        if len(current) == len(nums):
            result.append(current[:])
            return
        for i in range(len(nums)):
            if used[i]:
                continue
            used[i] = True
            current.append(nums[i])
            explore()
            current.pop()
            used[i] = False

    explore()
    return result

print(permutations([1, 2, 3]))
```

```output
[[1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2], [3, 2, 1]]
```

n! results, so **O(n x n!)**.

## Combination sum

Which combinations of numbers (reusable) add up to the target?

```python
def combination_sum(candidates, target):
    result, current = [], []

    def explore(start, remaining):
        if remaining == 0:
            result.append(current[:])
            return
        for i in range(start, len(candidates)):
            if candidates[i] > remaining:
                continue                  # prune: too big
            current.append(candidates[i])
            explore(i, remaining - candidates[i])   # i again: reuse allowed
            current.pop()

    explore(0, target)
    return result

print(combination_sum([2, 3, 6, 7], 7))
```

```output
[[2, 2, 3], [7]]
```

**Pruning** (skipping a branch that cannot work) is what makes backtracking much faster than trying everything.

## Generate parentheses

All valid strings with n pairs of brackets.

```python
def generate_parentheses(n):
    result = []

    def explore(current, opened, closed):
        if len(current) == 2 * n:
            result.append(current)
            return
        if opened < n:
            explore(current + "(", opened + 1, closed)
        if closed < opened:                 # never close more than opened
            explore(current + ")", opened, closed + 1)

    explore("", 0, 0)
    return result

print(generate_parentheses(3))
```

```output
['((()))', '(()())', '(())()', '()(())', '()()()']
```

Only valid choices are made, so no invalid string is ever built.

## N-Queens (the idea)

Place n queens on an n by n board so none attack each other. Place one queen per row; for each column check the column and both diagonals; if no column works, **backtrack** to the previous row and move that queen. It is the classic example of pruning.

:::tip
Draw the decision tree for a tiny input (like 3 numbers). If you can draw the tree, the code follows the choose, explore, undo template.
:::
