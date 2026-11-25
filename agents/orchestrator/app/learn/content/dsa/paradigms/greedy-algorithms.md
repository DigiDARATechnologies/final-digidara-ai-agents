---
title: Greedy algorithms
summary: Make the best local choice at each step, and learn when that is enough to get the best overall answer.
takeaways:
- A greedy algorithm picks the best option now and never reconsiders
- It works only when local choices lead to a global optimum, which you must justify
- Sorting first is a common greedy step
---
## The idea

A **greedy** algorithm builds a solution step by step, always taking the option that looks **best right now**, and never goes back. It is fast and simple, but it is only correct for problems with the right structure. Always ask: "Can I show that the best local choice never hurts?"

## Coin change: when greedy works and when it fails

Make 41 using coins `[25, 10, 5, 1]`. Take the biggest coin that fits each time.

```python
def greedy_coins(amount, coins):
    used = []
    for coin in sorted(coins, reverse=True):
        while amount >= coin:
            amount -= coin
            used.append(coin)
    return used

print(greedy_coins(41, [25, 10, 5, 1]))
print(greedy_coins(6, [4, 3, 1]))
```

```output
[25, 10, 5, 1]
[4, 1, 1]
```

For normal currency greedy gives the fewest coins. But with coins `[4, 3, 1]` and amount 6, greedy gives `4 + 1 + 1` (three coins) while `3 + 3` needs only two. **Greedy fails here**, so we need dynamic programming (next lessons). This is the key warning.

## Activity selection: the classic that works

Given meetings with start and end times, attend the **maximum number** that do not overlap. The greedy rule: always pick the meeting that **ends earliest**, leaving the most room for the rest.

```python
def max_meetings(meetings):
    meetings = sorted(meetings, key=lambda m: m[1])      # by end time
    count, last_end = 0, float("-inf")
    for start, end in meetings:
        if start >= last_end:
            count += 1
            last_end = end
    return count

print(max_meetings([(1, 3), (2, 4), (3, 5), (0, 6), (5, 7), (8, 9), (5, 9)]))
```

```output
4
```

## Jump game

Can you reach the last index if each number is the **maximum jump** from that position? Track the farthest index reachable.

```python
def can_jump(nums):
    farthest = 0
    for i, jump in enumerate(nums):
        if i > farthest:
            return False
        farthest = max(farthest, i + jump)
    return True

print(can_jump([2, 3, 1, 1, 4]), can_jump([3, 2, 1, 0, 4]))
```

```output
True False
```

## Fractional knapsack

You can take **parts** of items. Take items with the highest value per kilo first.

```python
def fractional_knapsack(items, capacity):          # items: (value, weight)
    total = 0.0
    for value, weight in sorted(items, key=lambda x: x[0] / x[1], reverse=True):
        take = min(weight, capacity)
        total += value * take / weight
        capacity -= take
        if capacity == 0:
            break
    return total

print(fractional_knapsack([(60, 10), (100, 20), (120, 30)], 50))
```

```output
240.0
```

If items cannot be split (the **0/1 knapsack**), greedy fails and DP is needed.

## Other greedy classics

- **Merge intervals / minimum arrows / meeting rooms**: sort, then sweep.
- **Huffman coding**: always merge the two least frequent symbols.
- **Minimum spanning tree** (Kruskal, Prim): always add the cheapest safe edge.
- **Dijkstra**: always settle the closest unvisited node.

## How to decide

1. Can a **sort** make the choice obvious?
2. Try a small counterexample. If one exists, greedy is wrong.
3. If choices interact (like coins 4, 3, 1), think DP.

:::interview Greedy vs dynamic programming?
Greedy commits to the best local choice and never revisits it, so it is fast but only valid for some problems. DP considers all choices by combining solutions to overlapping subproblems, so it is correct more often but costs more.
:::
