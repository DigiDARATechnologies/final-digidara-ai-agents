---
title: Lambdas and streams
summary: Write short functions with lambdas, use functional interfaces and method references, and process data with the Stream API.
takeaways:
- A lambda is a short anonymous function: (parameters) -> expression
- Streams process data as a pipeline: source, then filter and map, then a final collecting step
- Streams are lazy and do not change the original collection
---
## Lambdas

A **lambda** is a small function written inline, without a name. It is used wherever Java expects a **functional interface** (an interface with one abstract method).

```java
import java.util.*;

List<String> names = new ArrayList<>(List.of("Meena", "Asha", "Ravi"));

// the long way: an anonymous class
names.sort(new Comparator<String>() {
    @Override
    public int compare(String a, String b) {
        return a.compareTo(b);
    }
});

// the short way: a lambda
names.sort((a, b) -> b.compareTo(a));
System.out.println(names);
```

```output
[Ravi, Meena, Asha]
```

The shape is `(parameters) -> body`. For one expression, no braces or `return` are needed. With a block body use braces and `return`:

```java
Comparator<Integer> byLastDigit = (a, b) -> {
    int x = a % 10;
    int y = b % 10;
    return Integer.compare(x, y);
};
```

## Common functional interfaces

Java provides ready-made ones in `java.util.function`:

| Interface | Method | Takes and returns | Example |
| --- | --- | --- | --- |
| `Predicate<T>` | `test` | T, gives boolean | `s -> s.isEmpty()` |
| `Function<T, R>` | `apply` | T, gives R | `s -> s.length()` |
| `Consumer<T>` | `accept` | T, gives nothing | `s -> System.out.println(s)` |
| `Supplier<T>` | `get` | nothing, gives T | `() -> "hello"` |
| `BiFunction<T, U, R>` | `apply` | T and U, gives R | `(a, b) -> a + b` |
| `UnaryOperator<T>` | `apply` | T, gives T | `s -> s.trim()` |

```java
import java.util.function.*;

Predicate<Integer> isEven = n -> n % 2 == 0;
Function<String, Integer> length = s -> s.length();
BiFunction<Integer, Integer, Integer> add = (a, b) -> a + b;
Supplier<String> greeting = () -> "Hello";

System.out.println(isEven.test(10));
System.out.println(length.apply("SkillDARA"));
System.out.println(add.apply(3, 4));
System.out.println(greeting.get());
System.out.println(isEven.negate().test(10));
```

```output
true
9
7
Hello
false
```

## Method references

When a lambda only calls an existing method, write it shorter with `::`:

| Lambda | Method reference |
| --- | --- |
| `s -> s.length()` | `String::length` |
| `s -> System.out.println(s)` | `System.out::println` |
| `(a, b) -> Integer.compare(a, b)` | `Integer::compare` |
| `() -> new ArrayList<>()` | `ArrayList::new` |

## Streams

A **stream** processes a sequence of data as a **pipeline**:

1. a **source** (a list, an array, a range of numbers),
2. zero or more **intermediate** steps (`filter`, `map`, `sorted`, `distinct`, `limit`),
3. one **terminal** step that produces the result (`collect`, `toList`, `count`, `sum`, `forEach`).

```java
import java.util.*;
import java.util.stream.*;

List<Integer> marks = List.of(92, 48, 85, 71, 64, 55);

List<Integer> passed = marks.stream()
        .filter(m -> m >= 60)
        .sorted()
        .toList();
System.out.println(passed);

System.out.println(marks.stream().mapToInt(Integer::intValue).sum());
System.out.println(marks.stream().filter(m -> m >= 50).count());
System.out.println(marks.stream().mapToInt(Integer::intValue).max().getAsInt());
System.out.println(marks.stream().mapToInt(Integer::intValue).average().getAsDouble());
```

```output
[64, 71, 85, 92]
415
5
92
69.16666666666667
```

The original `marks` list is **not changed**: a stream produces new results. Nothing happens until the terminal step runs (streams are **lazy**).

## map and collect

`map` transforms every item:

```java
List<String> names = List.of("asha", "ravi", "meena");

List<String> upper = names.stream().map(String::toUpperCase).toList();
System.out.println(upper);

List<Integer> lengths = names.stream().map(String::length).toList();
System.out.println(lengths);

String joined = names.stream().map(n -> n.substring(0, 1).toUpperCase() + n.substring(1)).collect(Collectors.joining(", "));
System.out.println(joined);

System.out.println(IntStream.rangeClosed(1, 5).map(n -> n * n).boxed().toList());
System.out.println(IntStream.rangeClosed(1, 5).sum());
```

```output
[ASHA, RAVI, MEENA]
[4, 4, 5]
Asha, Ravi, Meena
[1, 4, 9, 16, 25]
15
```

## Grouping with Collectors

Group a list into a map, like SQL's GROUP BY. Using a `TreeMap` keeps the output in key order:

```java
record Student(String name, String dept, int marks) { }

List<Student> students = List.of(
        new Student("Asha", "CSE", 92),
        new Student("Ravi", "ECE", 48),
        new Student("Meena", "CSE", 85),
        new Student("Arun", "ECE", 71),
        new Student("Divya", "IT", 64));

Map<String, Long> countByDept = students.stream()
        .collect(Collectors.groupingBy(Student::dept, TreeMap::new, Collectors.counting()));
System.out.println(countByDept);

Map<String, Double> averageByDept = students.stream()
        .collect(Collectors.groupingBy(Student::dept, TreeMap::new, Collectors.averagingInt(Student::marks)));
System.out.println(averageByDept);

Optional<Student> topper = students.stream().max(Comparator.comparingInt(Student::marks));
System.out.println(topper.get().name());

System.out.println(students.stream().anyMatch(s -> s.marks() < 50));
System.out.println(students.stream().allMatch(s -> s.marks() >= 50));
```

```output
{CSE=2, ECE=2, IT=1}
{CSE=88.5, ECE=59.5, IT=64.0}
Asha
true
false
```

## Useful stream operations

| Operation | Does |
| --- | --- |
| `filter(predicate)` | keeps items that match |
| `map(function)` | transforms each item |
| `flatMap(...)` | turns each item into a stream and joins them all (a list of lists into one list) |
| `sorted()`, `sorted(comparator)` | sorts |
| `distinct()` | removes duplicates |
| `limit(n)`, `skip(n)` | takes or drops items |
| `reduce(identity, combiner)` | folds all items into one value |
| `collect(...)`, `toList()` | gathers the result |
| `count()`, `sum()`, `average()`, `min()`, `max()` | summaries |
| `anyMatch`, `allMatch`, `noneMatch` | true or false checks |
| `parallelStream()` | runs the pipeline on several threads (use only when you have measured a benefit) |

## A stream can be used only once

```java
var stream = List.of(1, 2, 3).stream();
System.out.println(stream.count());
// stream.count();       // IllegalStateException: the stream has already been used
```

```output
3
```

:::warning
Keep stream pipelines **free of side effects**: do not change outside variables from inside `map` or `filter`. And do not use a stream when a simple loop is clearer; long, deeply nested pipelines are hard to read.
:::

:::interview
**Interviewers often ask:** "What is a functional interface?" An interface with exactly one abstract method (such as `Runnable`, `Comparator`, `Predicate`), which a lambda or method reference can implement. "Intermediate versus terminal operations?" Intermediate ones (`filter`, `map`) return another stream and are lazy; a terminal one (`collect`, `count`) triggers the whole pipeline and produces a result.
:::
