---
title: Records, enums and modern Java
summary: Write compact data classes with records, model fixed choices with enums, and use modern features: var, switch patterns, sealed types and virtual threads.
takeaways:
- A record is a short, immutable data class with equals, hashCode and toString written for you
- An enum is a fixed set of named constants and can have fields and methods
- Java 17 and 21 added pattern matching, sealed types and virtual threads
---
## Records (Java 16+)

A class that only carries data usually needs a constructor, getters, `equals`, `hashCode` and `toString`: dozens of lines. A **record** writes all of it for you:

```java
public record Student(String name, int marks) { }
```

```java
Student s = new Student("Asha", 92);
System.out.println(s);
System.out.println(s.name());
System.out.println(s.marks());
System.out.println(s.equals(new Student("Asha", 92)));
```

```output
Student[name=Asha, marks=92]
Asha
92
true
```

| A record gives you | |
| --- | --- |
| a constructor | `new Student("Asha", 92)` |
| accessor methods | `name()` and `marks()` (not `getName`) |
| `toString`, `equals`, `hashCode` | based on all the fields |
| immutability | the fields are `private final`; there are no setters |

You can still add validation and methods:

```java
public record Student(String name, int marks) {

    public Student {                                  // compact constructor: runs before the fields are set
        if (marks < 0 || marks > 100) {
            throw new IllegalArgumentException("Marks must be 0 to 100");
        }
    }

    public boolean passed() {
        return marks >= 50;
    }

    public static Student of(String name) {
        return new Student(name, 0);
    }
}
```

Records are ideal for results, messages, coordinates, API responses and map keys.

## Enums

An **enum** is a type with a fixed set of named values. It is safer than using strings or numbers for choices such as days, levels or order states:

```java
public enum Level {
    BEGINNER, INTERMEDIATE, ADVANCED
}
```

```java
Level level = Level.INTERMEDIATE;
System.out.println(level);
System.out.println(level.ordinal());
System.out.println(Level.valueOf("ADVANCED"));
System.out.println(Level.values().length);

for (Level l : Level.values()) {
    System.out.print(l + " ");
}
System.out.println();
```

```output
INTERMEDIATE
1
ADVANCED
3
BEGINNER INTERMEDIATE ADVANCED
```

A typo like `Level.BEGINER` is a compile error, while the string `"BEGINER"` would be a hidden bug. Enums with data and behaviour:

```java
public enum Plan {
    FREE(0, 1), PRO(499, 5), TEAM(1999, 25);

    private final int monthlyPrice;
    private final int seats;

    Plan(int monthlyPrice, int seats) {
        this.monthlyPrice = monthlyPrice;
        this.seats = seats;
    }

    public int yearlyPrice() {
        return monthlyPrice * 10;            // two months free
    }

    public int seats() {
        return seats;
    }
}
```

```java
System.out.println(Plan.PRO.yearlyPrice());
System.out.println(Plan.TEAM.seats());
System.out.println(Plan.valueOf("FREE").yearlyPrice());
```

```output
4990
25
0
```

## switch with enums and patterns

```java
Level level = Level.ADVANCED;

String advice = switch (level) {
    case BEGINNER -> "Start with the basics";
    case INTERMEDIATE -> "Build small projects";
    case ADVANCED -> "Read other people's code";
};
System.out.println(advice);
```

```output
Read other people's code
```

A switch **expression** over an enum must cover every constant (or have a default), so adding a new constant later makes the compiler point at every switch you must update.

Since Java 21, switch can test the **type** of an object (**pattern matching**), which works beautifully with records and sealed types:

```java
sealed interface Shape permits Circle, Square { }
record Circle(double radius) implements Shape { }
record Square(double side) implements Shape { }

static double area(Shape shape) {
    return switch (shape) {
        case Circle c -> Math.PI * c.radius() * c.radius();
        case Square s -> s.side() * s.side();
    };
}
```

```java
System.out.println(area(new Square(4)));
System.out.println(Math.round(area(new Circle(1)) * 100) / 100.0);
```

```output
16.0
3.14
```

Because `Shape` is sealed to `Circle` and `Square`, the compiler knows the switch is complete without a `default`.

## Other modern features

| Feature | Since | Example |
| --- | --- | --- |
| `var` for local variables | 10 | `var list = new ArrayList<String>();` |
| text blocks | 15 | `"""` multi-line text `"""` |
| `instanceof` pattern | 16 | `if (obj instanceof String s) { ... }` |
| records | 16 | `record Point(int x, int y) { }` |
| sealed classes | 17 | `sealed interface Shape permits ...` |
| switch expressions | 14 | `String x = switch (n) { case 1 -> "one"; default -> "many"; };` |
| pattern matching for switch | 21 | `case Circle c -> ...` |
| record patterns | 21 | `case Point(int x, int y) -> ...` |
| virtual threads | 21 | `Thread.startVirtualThread(task)` |
| sequenced collections | 21 | `list.getFirst()`, `list.getLast()`, `list.reversed()` |

```java
import java.util.*;

var numbers = new ArrayList<>(List.of(1, 2, 3));
System.out.println(numbers.getFirst());
System.out.println(numbers.getLast());
System.out.println(numbers.reversed());

Object value = "hello";
if (value instanceof String text && text.length() > 3) {
    System.out.println(text.toUpperCase());
}
```

```output
1
3
[3, 2, 1]
HELLO
```

(`getFirst`, `getLast` and `reversed` on a list need Java 21 or later.)

## Which Java version should I learn on?

Java releases every six months, but companies use **LTS** (long-term support) versions: **8, 11, 17 and 21** (and later ones). A good plan for learners today is **Java 21**. Most of this course works on Java 17 as well. Older projects you may join at work often use 8 or 11, so it helps to know that lambdas and streams (Java 8) are the big dividing line.

:::interview
**Interviewers often ask:** "What are the new features in Java 17 or 21?" Records, sealed classes, text blocks, switch expressions, `instanceof` and switch pattern matching, and virtual threads (21). "What is a record?" A compact immutable data class whose constructor, accessors, `equals`, `hashCode` and `toString` are generated.
:::
