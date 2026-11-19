---
title: Collections: List, Set and Map
summary: Store and organise groups of objects with ArrayList, HashSet, TreeSet and HashMap, and choose the right collection.
takeaways:
- List keeps order and allows duplicates; Set rejects duplicates; Map stores key-value pairs
- Declare with the interface type (List, Set, Map) and create with a class (ArrayList, HashSet, HashMap)
- Collections hold objects, so primitives use wrappers such as Integer
---
## The collections framework

Arrays have a fixed size. The **Collections Framework** (in `java.util`) gives you growable, ready-made containers:

| Interface | Idea | Main classes |
| --- | --- | --- |
| `List` | an ordered list; duplicates allowed; access by position | `ArrayList`, `LinkedList` |
| `Set` | no duplicates | `HashSet`, `LinkedHashSet`, `TreeSet` |
| `Map` | key to value pairs; keys are unique | `HashMap`, `LinkedHashMap`, `TreeMap` |
| `Queue`, `Deque` | first-in-first-out (and both ends) | `ArrayDeque`, `PriorityQueue` |

## ArrayList

```java
import java.util.*;

List<String> names = new ArrayList<>();
names.add("Asha");
names.add("Ravi");
names.add("Meena");
names.add(1, "Kiran");                    // insert at position 1

System.out.println(names);
System.out.println(names.size());
System.out.println(names.get(2));
System.out.println(names.contains("Ravi"));
System.out.println(names.indexOf("Meena"));

names.remove("Ravi");                     // remove by value
names.remove(0);                          // remove by position
System.out.println(names);

Collections.sort(names);
System.out.println(names);
```

```output
[Asha, Kiran, Ravi, Meena]
4
Ravi
true
3
[Kiran, Meena]
[Kiran, Meena]
```

`<String>` is a **generic** type that says what the list holds, so the compiler rejects anything else. The `<>` on the right is filled in for you (the "diamond").

:::warning
For a `List<Integer>`, `list.remove(1)` removes the item at **position** 1, but `list.remove(Integer.valueOf(1))` removes the **value** 1. This surprises almost everyone once.
:::

## Looping over a list

```java
List<Integer> marks = new ArrayList<>(List.of(92, 48, 85));

for (int m : marks) {
    System.out.print(m + " ");
}
System.out.println();

marks.removeIf(m -> m < 50);              // remove every item that matches (a lambda, covered soon)
System.out.println(marks);

int sum = 0;
for (int m : marks) {
    sum += m;
}
System.out.println(sum);
```

```output
92 48 85
[92, 85]
177
```

`List.of(...)` creates a small **immutable** list that cannot be changed (adding to it throws `UnsupportedOperationException`); wrap it in `new ArrayList<>(...)` when you need to change it.

:::warning
Removing items from a list **inside a for-each loop** throws `ConcurrentModificationException`. Use `removeIf`, or an `Iterator`.
:::

## HashSet and TreeSet: no duplicates

```java
Set<String> cities = new HashSet<>();
System.out.println(cities.add("Chennai"));
System.out.println(cities.add("Madurai"));
System.out.println(cities.add("Chennai"));       // already there
System.out.println(cities.size());

Set<Integer> sorted = new TreeSet<>(List.of(5, 3, 9, 3, 1));
System.out.println(sorted);
```

```output
true
true
false
2
[1, 3, 5, 9]
```

`add` returns `false` when the item was already present. A `HashSet` does not promise any order. A `TreeSet` keeps its items **sorted**, and a `LinkedHashSet` keeps **insertion order**. Sets are perfect for removing duplicates and for fast "is it in here?" checks.

## HashMap: key and value

```java
Map<String, Integer> marks = new HashMap<>();
marks.put("Asha", 92);
marks.put("Ravi", 48);
marks.put("Meena", 85);
marks.put("Ravi", 58);                           // same key: the value is replaced

System.out.println(marks.get("Asha"));
System.out.println(marks.get("Ravi"));
System.out.println(marks.get("Zoya"));           // missing key gives null
System.out.println(marks.getOrDefault("Zoya", 0));
System.out.println(marks.containsKey("Meena"));
System.out.println(marks.size());
marks.remove("Meena");
System.out.println(marks.size());
```

```output
92
58
null
0
true
3
2
```

A `HashMap` is very fast at finding a value by its key, but it makes **no promise about the order** of its entries.

## Looping over a Map

```java
Map<String, Integer> marks = new TreeMap<>();      // TreeMap keeps keys sorted
marks.put("Meena", 85);
marks.put("Asha", 92);
marks.put("Ravi", 58);

for (Map.Entry<String, Integer> entry : marks.entrySet()) {
    System.out.println(entry.getKey() + " -> " + entry.getValue());
}
System.out.println(marks.keySet());
System.out.println(marks.values());
```

```output
Asha -> 92
Meena -> 85
Ravi -> 58
[Asha, Meena, Ravi]
[92, 85, 58]
```

## Counting with a Map: word frequency

The most common map pattern:

```java
String text = "to be or not to be";
Map<String, Integer> counts = new TreeMap<>();

for (String word : text.split(" ")) {
    counts.merge(word, 1, Integer::sum);          // add 1, or start at 1 if the word is new
}
System.out.println(counts);
```

```output
{be=2, not=1, or=1, to=2}
```

`merge(key, 1, Integer::sum)` says: "if the key is missing, store 1; otherwise add 1 to the existing value".

## Choosing a collection

| You need | Use |
| --- | --- |
| an ordered list, access by position | `ArrayList` (the default choice) |
| lots of inserts or removals at the ends | `ArrayDeque` or `LinkedList` |
| no duplicates, fast contains | `HashSet` |
| no duplicates, always sorted | `TreeSet` |
| look up by key | `HashMap` |
| key lookup in sorted or insertion order | `TreeMap` or `LinkedHashMap` |
| a priority queue (always get the smallest first) | `PriorityQueue` |

## Sorting and comparing

```java
List<String> words = new ArrayList<>(List.of("pear", "fig", "banana", "kiwi"));

Collections.sort(words);                                           // natural (alphabetical) order
System.out.println(words);

words.sort(Comparator.comparing(String::length));                  // by length; ties keep their order
System.out.println(words);

words.sort(Comparator.comparing(String::length).reversed());
System.out.println(words);
```

```output
[banana, fig, kiwi, pear]
[fig, kiwi, pear, banana]
[banana, kiwi, pear, fig]
```

Your own classes can define a natural order by implementing `Comparable<T>`, or you can pass a `Comparator` whenever you sort.

## equals and hashCode

`HashSet` and `HashMap` use `equals()` and `hashCode()` to decide whether two objects are the same. If you use your own class as a key, override **both**, using the same fields:

```java
import java.util.Objects;

public class Student {
    private final int id;
    private final String name;

    public Student(int id, String name) {
        this.id = id;
        this.name = name;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Student other)) return false;
        return id == other.id && Objects.equals(name, other.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, name);
    }
}
```

:::warning
If two objects are `equals`, they **must** have the same `hashCode`. Break this rule and a `HashSet` may keep "duplicates" or a `HashMap` may fail to find a key that is clearly there. A `record` (a later lesson) writes both methods for you.
:::

:::interview
**Interviewers often ask:** "ArrayList versus LinkedList?" `ArrayList` is backed by an array: fast access by position, slower inserts in the middle. `LinkedList` links nodes: fast inserts and removals at the ends but slow access by position. In practice `ArrayList` is nearly always the better choice. Also: "How does HashMap work?" It computes the key's `hashCode` to choose a bucket, then uses `equals` to find the exact key inside that bucket.
:::
