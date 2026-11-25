---
title: Stacks
summary: Use a last-in, first-out stack to solve matching brackets, undo, and next-greater-element problems.
takeaways:
- A stack is last in, first out (LIFO): push and pop at one end
- A Python list works as a stack with append and pop
- A monotonic stack finds the next greater or smaller element in O(n)
---
## The idea

Think of a pile of plates: you add and remove from the **top**. The last item pushed is the first popped (**LIFO**).

| Operation | Python | Cost |
| --- | --- | --- |
| push | `stack.append(x)` | O(1) |
| pop | `stack.pop()` | O(1) |
| peek | `stack[-1]` | O(1) |
| empty? | `not stack` | O(1) |

Real uses: the **undo** button, browser **back**, function **call stack**, parsing expressions.

## Balanced brackets

Push every opening bracket. For a closing bracket, the top of the stack must be its partner.

```python
def is_balanced(text):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for ch in text:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack

print(is_balanced("{[()]}"), is_balanced("([)]"), is_balanced("(("))
```

```output
True False False
```

## Evaluate a postfix expression

In postfix, `3 4 + 2 *` means `(3 + 4) * 2`.

```python
def eval_postfix(tokens):
    stack = []
    for token in tokens:
        if token in "+-*/":
            b, a = stack.pop(), stack.pop()
            stack.append({"+": a + b, "-": a - b, "*": a * b, "/": a / b}[token])
        else:
            stack.append(float(token))
    return stack[0]

print(eval_postfix(["3", "4", "+", "2", "*"]))
```

```output
14.0
```

## Monotonic stack: next greater element

For each day's temperature, how many days until a **warmer** day? Keep a stack of indexes of days still waiting for a warmer day.

```python
def days_until_warmer(temps):
    answer = [0] * len(temps)
    stack = []                              # indexes waiting
    for i, t in enumerate(temps):
        while stack and temps[stack[-1]] < t:
            j = stack.pop()
            answer[j] = i - j
        stack.append(i)
    return answer

print(days_until_warmer([73, 74, 75, 71, 69, 72, 76, 73]))
```

```output
[1, 1, 4, 2, 1, 1, 0, 0]
```

Each index is pushed once and popped once, so it is **O(n)**, not O(n squared).

## Min stack: get the minimum in O(1)

Store, with each value, the smallest value so far.

```python
class MinStack:
    def __init__(self):
        self.items = []                 # pairs: (value, minimum so far)

    def push(self, x):
        current_min = min(x, self.items[-1][1]) if self.items else x
        self.items.append((x, current_min))

    def pop(self):
        return self.items.pop()[0]

    def minimum(self):
        return self.items[-1][1]

s = MinStack()
for v in [5, 3, 7, 2]:
    s.push(v)
print(s.minimum())
s.pop()
print(s.minimum())
```

```output
2
3
```

:::remember
Matching pairs, nested structures, "undo", or "next greater/smaller"? Think **stack**.
:::
