---
title: Decisions and loops
summary: Make decisions with if and switch, repeat work with for, while and do-while loops, and use break, continue and labels.
takeaways:
- if, else if and else choose between paths; the modern switch expression is clean and safe
- for loops suit a known count, while loops suit an unknown count
- break leaves a loop; continue skips to the next round
---
## if, else if, else

```java
int marks = 72;

if (marks >= 90) {
    System.out.println("Grade A");
} else if (marks >= 75) {
    System.out.println("Grade B");
} else if (marks >= 50) {
    System.out.println("Grade C");
} else {
    System.out.println("Fail");
}
```

```output
Grade C
```

Conditions are checked from the top; the **first** one that is true runs, and the rest are skipped. That is why the highest limit comes first.

:::warning
Always use braces `{ }`, even for a single statement. Without them, only the next line belongs to the `if`, and adding a second line later silently breaks the logic. Also remember that `=` assigns and `==` compares: `if (x = 5)` does not compile in Java for ints, but the mix-up is still common.
:::

## switch

Use `switch` when you compare one value against many fixed options. The modern form (Java 14+) is a **switch expression** with arrows. It needs no `break` and cannot fall through:

```java
int day = 3;
String name = switch (day) {
    case 1 -> "Monday";
    case 2 -> "Tuesday";
    case 3 -> "Wednesday";
    case 6, 7 -> "Weekend";
    default -> "Another weekday";
};
System.out.println(name);
```

```output
Wednesday
```

The older style uses `case 1:` with `break;` after each case. If you forget `break`, execution **falls through** into the next case, which is a classic bug. Prefer the arrow form in new code.

```java
String level = "B";
switch (level) {
    case "A":
        System.out.println("Top");
        break;
    case "B":
        System.out.println("Good");
    case "C":                         // no break above, so execution falls into here too
        System.out.println("Fine");
        break;
    default:
        System.out.println("Other");
}
```

```output
Good
Fine
```

## for loop

Use `for` when you know how many times to repeat:

```java
for (int i = 1; i <= 5; i++) {
    System.out.print(i + " ");
}
System.out.println();

int total = 0;
for (int i = 1; i <= 100; i++) {
    total += i;
}
System.out.println(total);
```

```output
1 2 3 4 5
5050
```

The three parts of `for (start; condition; step)` are: set up a counter, keep going while the condition is true, and update the counter after each round.

## while and do-while

`while` checks the condition **before** each round. `do-while` runs the body **first**, so it always runs at least once:

```java
int n = 1;
while (n < 100) {
    n *= 2;
}
System.out.println(n);

int tries = 10;
do {
    System.out.println("runs once even though the condition is false");
    tries++;
} while (tries < 5);
```

```output
128
runs once even though the condition is false
```

:::warning
A loop whose condition never becomes false runs **forever** (an infinite loop). Always make sure something inside the loop moves it toward the end, such as `i++`.
:::

## Enhanced for (for-each)

To go through every item of an array or a collection:

```java
String[] names = {"Asha", "Ravi", "Meena"};
for (String name : names) {
    System.out.println(name.toUpperCase());
}
```

```output
ASHA
RAVI
MEENA
```

Read it as "for each `name` in `names`". It is shorter and safer than a counter when you do not need the position.

## break and continue

`break` leaves the loop completely. `continue` skips the rest of the current round and moves to the next one.

```java
for (int i = 1; i <= 10; i++) {
    if (i % 2 == 0) {
        continue;          // skip even numbers
    }
    if (i > 7) {
        break;             // stop the whole loop
    }
    System.out.print(i + " ");
}
System.out.println();
```

```output
1 3 5 7
```

## Nested loops

A loop inside a loop. The inner loop runs fully for every round of the outer loop:

```java
for (int row = 1; row <= 4; row++) {
    for (int col = 1; col <= row; col++) {
        System.out.print("* ");
    }
    System.out.println();
}
```

```output
*
* *
* * *
* * * *
```

Pattern printing like this is a favourite warm-up question in interviews and college labs.

## A small program: FizzBuzz

```java
for (int i = 1; i <= 15; i++) {
    if (i % 15 == 0) {
        System.out.println("FizzBuzz");
    } else if (i % 3 == 0) {
        System.out.println("Fizz");
    } else if (i % 5 == 0) {
        System.out.println("Buzz");
    } else {
        System.out.println(i);
    }
}
```

```output
1
2
Fizz
4
Buzz
Fizz
7
8
Fizz
Buzz
11
Fizz
13
14
FizzBuzz
```

The check for `15` must come first, because every multiple of 15 is also a multiple of 3 and 5.

:::interview
**Interviewers often ask:** "What is the difference between `break` and `continue`?" and "while versus do-while?" `break` exits the loop; `continue` skips to the next round. `while` tests first and may never run; `do-while` runs the body at least once.
:::
