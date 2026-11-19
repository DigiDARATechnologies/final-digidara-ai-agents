---
title: Generics, Optional and useful classes
summary: Write type-safe code with generics, avoid null with Optional, and use Math, LocalDate, Random and other everyday utilities.
takeaways:
- Generics let one class or method work with many types, safely
- Optional makes "might be missing" explicit, and reduces NullPointerExceptions
- java.time (LocalDate and friends) replaces the old Date and Calendar
---
## Why generics

Before generics, a list held plain `Object`s, and you had to cast every item you took out, with no protection against putting in the wrong type. **Generics** let you say what a container holds, and the compiler checks it.

```java
List<String> names = new ArrayList<>();
names.add("Asha");
// names.add(42);            // compile error: an int is not a String
String first = names.get(0); // no cast needed
```

## Writing a generic class

```java
public class Box<T> {
    private T content;

    public Box(T content) {
        this.content = content;
    }

    public T get() {
        return content;
    }

    public void set(T content) {
        this.content = content;
    }
}
```

```java
Box<String> word = new Box<>("hello");
Box<Integer> number = new Box<>(42);

System.out.println(word.get().toUpperCase());
System.out.println(number.get() + 1);
```

```output
HELLO
43
```

`T` is a **type parameter**: a placeholder for the real type, filled in when you use the class. One `Box` class now works for strings, numbers and anything else, with full type checking.

## Generic methods and bounds

```java
static <T> void printAll(List<T> items) {
    for (T item : items) {
        System.out.print(item + " ");
    }
    System.out.println();
}

static <T extends Comparable<T>> T biggest(List<T> items) {      // T must be comparable
    T best = items.get(0);
    for (T item : items) {
        if (item.compareTo(best) > 0) {
            best = item;
        }
    }
    return best;
}
```

```java
printAll(List.of(1, 2, 3));
System.out.println(biggest(List.of(4, 19, 7)));
System.out.println(biggest(List.of("pear", "apple", "zebra")));
```

```output
1 2 3
19
zebra
```

`T extends Comparable<T>` is a **bound**: the method accepts any type that can be compared, and can therefore call `compareTo`.

:::note
Generics exist only at compile time. The compiler removes the type information afterwards (**type erasure**), so at run time a `List<String>` and a `List<Integer>` are both just a `List`. This is why you cannot write `new T()` or `instanceof List<String>`.
:::

## Wildcards (a short look)

| Syntax | Meaning |
| --- | --- |
| `List<?>` | a list of some unknown type (read only) |
| `List<? extends Number>` | a list of `Number` or any subclass (you can read from it) |
| `List<? super Integer>` | a list of `Integer` or any parent (you can add to it) |

A `List<Integer>` is **not** a `List<Number>`, even though `Integer` is a `Number`; wildcards are how a method accepts the related types.

## Optional: avoiding null

A method that might have no answer can return `null`, but callers forget to check. `Optional<T>` makes the "maybe" visible in the type:

```java
import java.util.*;

static Optional<String> findCity(Map<String, String> cities, String name) {
    return Optional.ofNullable(cities.get(name));
}
```

```java
Map<String, String> cities = Map.of("Asha", "Chennai", "Ravi", "Madurai");

System.out.println(findCity(cities, "Asha").isPresent());
System.out.println(findCity(cities, "Zoya").isPresent());
System.out.println(findCity(cities, "Zoya").orElse("unknown"));
System.out.println(findCity(cities, "Ravi").map(String::toUpperCase).orElse("unknown"));

findCity(cities, "Asha").ifPresent(c -> System.out.println("Found " + c));
```

```output
true
false
unknown
MADURAI
Found Chennai
```

| Method | Use |
| --- | --- |
| `Optional.of(x)` | a value that is definitely not null |
| `Optional.ofNullable(x)` | might be null |
| `Optional.empty()` | no value |
| `isPresent()`, `isEmpty()` | check |
| `orElse(default)`, `orElseGet(supplier)` | the value, or a fallback |
| `orElseThrow()` | the value, or an exception |
| `map(...)`, `ifPresent(...)` | work on the value only if there is one |

Use `Optional` for **return values**. Do not use it for fields or parameters, and do not call `get()` without checking first.

## Math

```java
System.out.println(Math.max(7, 12));
System.out.println(Math.min(7, 12));
System.out.println(Math.abs(-9));
System.out.println(Math.pow(2, 10));
System.out.println(Math.sqrt(144));
System.out.println(Math.round(4.5));
System.out.println(Math.round(4.4));
System.out.println(Math.ceil(4.1));
System.out.println(Math.floor(4.9));
```

```output
12
7
9
1024.0
12.0
5
4
5.0
4.0
```

`Math.pow`, `sqrt`, `ceil` and `floor` return `double`. `Math.round` returns a whole number.

## Dates and time

Use the `java.time` package (Java 8 and later):

```java
import java.time.*;
import java.time.temporal.ChronoUnit;

LocalDate start = LocalDate.of(2026, 3, 1);
LocalDate end = LocalDate.of(2026, 3, 10);

System.out.println(start);
System.out.println(start.plusDays(30));
System.out.println(start.getDayOfWeek());
System.out.println(ChronoUnit.DAYS.between(start, end));
System.out.println(start.isBefore(end));
System.out.println(Period.between(LocalDate.of(2020, 1, 15), end));
System.out.println(LocalTime.of(9, 30).plusMinutes(45));
System.out.println(LocalDate.of(2026, 2, 1).lengthOfMonth());
```

```output
2026-03-01
2026-03-31
SUNDAY
9
true
P6Y1M23D
10:15
28
```

| Class | Holds |
| --- | --- |
| `LocalDate` | a date, no time (2026-03-01) |
| `LocalTime` | a time, no date |
| `LocalDateTime` | date and time, no time zone |
| `ZonedDateTime` | date, time and time zone |
| `Duration`, `Period` | an amount of time (hours and minutes, or years months days) |
| `DateTimeFormatter` | turns dates into text and back |

All of them are **immutable**: `plusDays` returns a new object.

## Random numbers

```java
import java.util.Random;

Random random = new Random(42);              // a fixed seed gives a repeatable sequence
int dice = random.nextInt(6) + 1;            // 1 to 6
System.out.println(dice >= 1 && dice <= 6);

double d = Math.random();                    // between 0.0 (included) and 1.0 (excluded)
System.out.println(d >= 0.0 && d < 1.0);
```

```output
true
true
```

For anything security-related (tokens, passwords) use `SecureRandom`, not `Random`.

## Scanner: reading input from the keyboard

```java
import java.util.Scanner;

Scanner in = new Scanner(System.in);
System.out.print("Enter your name: ");
String name = in.nextLine();
System.out.print("Enter your age: ");
int age = in.nextInt();
System.out.println("Hello " + name + ", next year you will be " + (age + 1));
in.close();
```

Run this on your own laptop and type the answers. `nextLine()` reads a whole line, `nextInt()` an integer, and `nextDouble()` a decimal.

:::interview
**Interviewers often ask:** "What are generics and why use them?" They let classes and methods work with a type chosen by the caller, giving compile-time type safety and removing casts. And: "What is type erasure?" The compiler removes generic type information after checking, so it does not exist at run time.
:::
