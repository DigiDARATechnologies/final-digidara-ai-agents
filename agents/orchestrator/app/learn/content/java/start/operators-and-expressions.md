---
title: Operators and expressions
summary: Calculate with arithmetic, comparison, logical and assignment operators, and understand precedence and short-circuiting.
takeaways:
- Arithmetic, comparison and logical operators combine into expressions
- ++ and -- come in prefix and postfix forms that behave differently
- && and || stop early (short-circuit), which can prevent errors
---
## Arithmetic

| Operator | Meaning | Example | Result |
| --- | --- | --- | --- |
| `+` | add (and join strings) | `7 + 2` | 9 |
| `-` | subtract | `7 - 2` | 5 |
| `*` | multiply | `7 * 2` | 14 |
| `/` | divide | `7 / 2` | 3 (integers) |
| `%` | remainder | `7 % 2` | 1 |

```java
int a = 17, b = 5;
System.out.println(a + b);
System.out.println(a / b);
System.out.println(a % b);
System.out.println(a / (double) b);
System.out.println(2 + 3 * 4);
System.out.println((2 + 3) * 4);
```

```output
22
3
2
3.4
14
20
```

Multiplication and division happen before addition and subtraction. Use brackets when you want a different order, or whenever it makes the code clearer.

## Assignment operators

```java
int x = 10;
x += 5;      // x = x + 5   -> 15
x -= 3;      // x = x - 3   -> 12
x *= 2;      // x = x * 2   -> 24
x /= 5;      // x = x / 5   -> 4  (integer division)
x %= 3;      // x = x % 3   -> 1
System.out.println(x);
```

```output
1
```

## Increment and decrement

`++` adds one, `--` subtracts one. Written **before** the variable (prefix) it changes the value first; **after** (postfix) it uses the old value first:

```java
int i = 5;
int j = i++;      // j gets 5, then i becomes 6
int k = ++i;      // i becomes 7, then k gets 7
System.out.println(i + " " + j + " " + k);
```

```output
7 5 7
```

:::tip
Use `++` and `--` on their own line (`count++;`). Mixing them into bigger expressions is a common source of confusion, and interviewers love to ask about it.
:::

## Comparison operators

They produce a `boolean`:

| Operator | Meaning |
| --- | --- |
| `==` | equal to |
| `!=` | not equal to |
| `>`, `<` | greater than, less than |
| `>=`, `<=` | greater than or equal, less than or equal |

```java
int marks = 72;
System.out.println(marks >= 50);
System.out.println(marks == 100);
System.out.println(marks != 72);
```

```output
true
false
false
```

## Logical operators

| Operator | Meaning | Example |
| --- | --- | --- |
| `&&` | AND: both true | `marks >= 50 && attendance >= 75` |
| `\|\|` | OR: at least one true | `isAdmin \|\| isOwner` |
| `!` | NOT: reverses | `!passed` |

`&&` and `||` are **short-circuit** operators: if the left side already decides the answer, the right side is not evaluated at all.

```java
int[] items = {};
boolean safe = items.length > 0 && items[0] > 10;    // the right side never runs when the array is empty
System.out.println(safe);

int n = 0;
boolean result = (n != 0) && (100 / n > 5);          // no divide-by-zero, because n != 0 is false
System.out.println(result);
```

```output
false
false
```

Without short-circuiting, `items[0]` on an empty array would throw an exception, and `100 / n` would divide by zero. Putting the safety check **first** is a standard Java habit.

## The ternary operator

A short way to choose between two values:

```java
int marks = 48;
String result = marks >= 50 ? "Pass" : "Fail";
System.out.println(result);
```

```output
Fail
```

Read it as: *condition ? value if true : value if false*.

## Operator precedence

From highest to lowest (simplified):

| Order | Operators |
| --- | --- |
| 1 | `()` brackets, `++`, `--`, `!` |
| 2 | `*`, `/`, `%` |
| 3 | `+`, `-` |
| 4 | `<`, `<=`, `>`, `>=` |
| 5 | `==`, `!=` |
| 6 | `&&` |
| 7 | `\|\|` |
| 8 | `?:`, then assignment (`=`, `+=`...) |

When in doubt, add brackets.

## Bitwise operators (a quick look)

| Operator | Meaning | Example (`5` is `101`, `3` is `011`) |
| --- | --- | --- |
| `&` | AND | `5 & 3` is 1 |
| `\|` | OR | `5 \| 3` is 7 |
| `^` | XOR | `5 ^ 3` is 6 |
| `<<` | shift left | `5 << 1` is 10 |
| `>>` | shift right | `5 >> 1` is 2 |

```java
System.out.println(5 & 3);
System.out.println(5 | 3);
System.out.println(5 ^ 3);
System.out.println(5 << 1);
System.out.println(5 >> 1);
```

```output
1
7
6
10
2
```

Shifting left by one doubles a number and shifting right halves it. Bitwise operators appear in puzzles and low-level code more than in everyday programs.

:::interview
**Interviewers often ask:** "What is the difference between `==` and `.equals()`?" and "What is the output of `int i = 5; int j = i++ + ++i;`?" For the second: `i++` gives 5 (then i is 6), `++i` makes i 7 and gives 7, so `j` is **12**.
:::
