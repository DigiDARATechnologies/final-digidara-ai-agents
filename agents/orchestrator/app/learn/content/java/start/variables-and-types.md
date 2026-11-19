---
title: Variables, types and type conversion
summary: Store data in typed variables, know the primitive types and their limits, and convert safely between them.
takeaways:
- Java is statically typed: every variable has a type that cannot change
- There are eight primitive types; String is an object, not a primitive
- Integer division, overflow and floating-point rounding are classic surprises
---
## Variables

A variable is a named place that holds a value. In Java you must say its **type**:

```java
int age = 21;
double price = 499.99;
boolean passed = true;
char grade = 'A';
String name = "Asha";

System.out.println(name + " is " + age);
```

```output
Asha is 21
```

Once declared, a variable keeps its type. `age = "twenty";` is a compile error, because a `String` cannot go into an `int`.

## The eight primitive types

| Type | Size | Holds | Example |
| --- | --- | --- | --- |
| `byte` | 1 byte | -128 to 127 | `byte b = 100;` |
| `short` | 2 bytes | -32,768 to 32,767 | `short s = 3000;` |
| `int` | 4 bytes | about ±2.1 billion | `int n = 42;` |
| `long` | 8 bytes | about ±9.2 × 10^18 | `long big = 3_000_000_000L;` |
| `float` | 4 bytes | decimals (about 7 digits) | `float f = 1.5f;` |
| `double` | 8 bytes | decimals (about 15 digits) | `double d = 3.14;` |
| `char` | 2 bytes | one character | `char c = 'x';` |
| `boolean` | 1 bit of information | `true` or `false` | `boolean ok = true;` |

Use `int` for whole numbers and `double` for decimals by default. A `long` literal needs an `L` at the end, a `float` literal needs an `f`, and underscores in numbers (`3_000_000_000L`) are just for readability.

`String` is **not** a primitive. It is a class, written with a capital S, and string literals use double quotes (`"text"`), while a `char` uses single quotes (`'x'`).

## Naming rules and style

| Rule | Example |
| --- | --- |
| letters, digits, `_` and `$`; cannot start with a digit | `total1`, `_count` are fine; `1total` is not |
| cannot be a reserved word | not `class`, `int`, `new` |
| variables and methods: `camelCase` | `studentName`, `calculateTotal()` |
| classes: `PascalCase` | `Student`, `BankAccount` |
| constants: `UPPER_SNAKE_CASE` | `MAX_MARKS` |

## Constants and var

```java
final double GST_RATE = 0.18;      // final: cannot be changed after it is set
var city = "Chennai";              // var (Java 10+): the compiler works out the type (String)
var count = 10;                    // int
```

`var` only works for local variables that are given a value on the same line. The type is still fixed; it is just written for you.

## Integer division and remainder

When both sides are integers, Java gives an integer result and drops the fraction:

```java
System.out.println(10 / 3);       // integer division
System.out.println(10 % 3);       // remainder
System.out.println(10 / 3.0);     // one side is a double, so the result is a double
System.out.println(-7 / 2);       // truncates toward zero
System.out.println(-7 % 2);       // the remainder takes the sign of the left number
```

```output
3
1
3.3333333333333335
-3
-1
```

:::warning
`double average = total / count;` with two `int`s still divides as integers first. Write `(double) total / count` so at least one side is a decimal **before** the division.
:::

## Casting: converting between types

Going from a smaller type to a bigger one is automatic (**widening**). Going the other way needs an explicit **cast**, and may lose data (**narrowing**):

```java
int a = 5;
double b = a;                 // widening: automatic, b is 5.0
double pi = 3.99;
int c = (int) pi;             // narrowing: the decimal part is cut off, not rounded
long big = 3_000_000_000L;
int small = (int) big;        // too big for an int: the value wraps around
char letter = 'a';
int code = letter;            // a character is a number: 97

System.out.println(b);
System.out.println(c);
System.out.println(small);
System.out.println(code);
System.out.println((char) (letter + 1));
```

```output
5.0
3
-1294967296
97
b
```

`(int) 3.99` is **3**, not 4: casting truncates. Use `Math.round(3.99)` to round (it returns a `long`).

## Overflow and rounding surprises

```java
int max = Integer.MAX_VALUE;
System.out.println(max);
System.out.println(max + 1);              // overflow: wraps to the smallest int, with no error

System.out.println(0.1 + 0.2);            // decimals are binary fractions
System.out.println(0.1 + 0.2 == 0.3);
```

```output
2147483647
-2147483648
0.30000000000000004
false
```

Integers silently wrap around when they overflow. Decimals such as 0.1 cannot be stored exactly in binary, so `0.1 + 0.2` is slightly off. Never compare decimals with `==`; compare the difference with a tiny tolerance instead. For **money**, do not use `double`: use `BigDecimal`, or keep whole paise or cents in a `long`.

## Wrapper classes

Each primitive has an object version used by collections, plus helpful methods:

| Primitive | Wrapper | Useful methods |
| --- | --- | --- |
| `int` | `Integer` | `Integer.parseInt("42")`, `Integer.MAX_VALUE` |
| `double` | `Double` | `Double.parseDouble("3.5")` |
| `boolean` | `Boolean` | `Boolean.parseBoolean("true")` |
| `char` | `Character` | `Character.isDigit('7')`, `Character.toUpperCase('a')` |

Java converts between a primitive and its wrapper automatically (**autoboxing**), which is why `ArrayList<Integer>` can hold `int` values.

:::interview
**Interviewers often ask:** "What is the difference between `int` and `Integer`?" `int` is a primitive that holds a value directly and cannot be `null`. `Integer` is a wrapper class (an object) that can be `null`, can be used in collections and generics, and offers helper methods.
:::
