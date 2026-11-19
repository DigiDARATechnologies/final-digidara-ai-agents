---
title: Strings and text
summary: Work with String methods, understand immutability and the string pool, compare strings correctly and build text efficiently.
takeaways:
- Strings are immutable: methods return a new string and never change the original
- Compare strings with equals(), never ==
- Use StringBuilder to build text in loops, and String.format or text blocks for readable output
---
## Strings are objects

A `String` holds text. It has many useful methods:

```java
String s = "SkillDARA";

System.out.println(s.length());
System.out.println(s.charAt(0));
System.out.println(s.toUpperCase());
System.out.println(s.substring(5));
System.out.println(s.substring(0, 5));
System.out.println(s.indexOf("D"));
System.out.println(s.contains("ill"));
System.out.println(s.replace("A", "a"));
```

```output
9
S
SKILLDARA
DARA
Skill
5
true
SkillDaRa
```

Positions start at **0**. `substring(start, end)` includes `start` but **excludes** `end`.

| Method | Does |
| --- | --- |
| `length()` | number of characters |
| `charAt(i)` | the character at position i |
| `substring(a)` / `substring(a, b)` | part of the string |
| `indexOf("x")` | position of the first match, or -1 |
| `contains("x")`, `startsWith`, `endsWith` | true or false checks |
| `toUpperCase()`, `toLowerCase()` | change case |
| `trim()`, `strip()` | remove spaces at both ends |
| `replace("a", "b")` | replace every match |
| `split(",")` | break into an array |
| `isEmpty()`, `isBlank()` | empty, or empty after trimming |
| `String.join(", ", list)` | join with a separator |
| `repeat(3)` | repeat the text |

## Immutability

A String **never changes** after it is created. Methods that seem to change it actually return a **new** String:

```java
String name = "asha";
name.toUpperCase();                 // result thrown away: name is unchanged
System.out.println(name);
name = name.toUpperCase();          // keep the new string
System.out.println(name);
```

```output
asha
ASHA
```

## Comparing strings: equals, not ==

`==` checks whether two variables point to the **same object**. `.equals()` checks whether the **text** is the same.

```java
String a = "java";
String b = "java";
String c = new String("java");

System.out.println(a == b);           // same literal, shared in the string pool
System.out.println(a == c);           // c is a separate object
System.out.println(a.equals(c));      // same text
System.out.println("JAVA".equalsIgnoreCase(a));
```

```output
true
false
true
true
```

Java keeps one copy of each string literal in a special area called the **string pool**, so `a == b` is true. `new String("java")` makes a separate object, so `a == c` is false although the text is identical.

:::warning
Always compare text with `.equals()`. Comparing with `==` sometimes appears to work (because of the pool) and then breaks in a different situation, which makes it a very hard bug to find. When one side could be `null`, put the literal first: `"admin".equals(role)` never throws a NullPointerException.
:::

To order strings use `compareTo`: it returns a negative number if the first comes before the second, 0 if equal, and a positive number otherwise.

```java
System.out.println("apple".compareTo("banana") < 0);
System.out.println("b".compareTo("a"));
```

```output
true
1
```

## Joining and splitting

```java
String text = "Asha,Ravi,Meena";
String[] names = text.split(",");
System.out.println(names.length);
System.out.println(names[1]);
System.out.println(String.join(" | ", names));
System.out.println("na".repeat(3));
System.out.println("  hello  ".trim() + "!");

System.out.println("a" + 1 + 2);
System.out.println(1 + 2 + "a");
```

```output
3
Ravi
Asha | Ravi | Meena
nanana
hello!
a12
3a
```

The last two lines show how `+` works: evaluated left to right, once a String is involved, every later `+` joins text. `"a" + 1 + 2` is `"a1"` then `"a12"`, but `1 + 2 + "a"` adds the numbers first (3) and then joins `"a"`.

## StringBuilder: building text efficiently

Because strings are immutable, building one inside a loop with `+` creates a new string every time. Use **StringBuilder**, which changes in place:

```java
StringBuilder sb = new StringBuilder();
for (int i = 1; i <= 5; i++) {
    sb.append(i);
    if (i < 5) {
        sb.append(", ");
    }
}
System.out.println(sb.toString());
System.out.println(new StringBuilder("stressed").reverse());
```

```output
1, 2, 3, 4, 5
desserts
```

| Class | Use |
| --- | --- |
| `String` | fixed text |
| `StringBuilder` | building or changing text in a single thread (fast) |
| `StringBuffer` | the same, but thread-safe and slower (rarely needed) |

## Formatting output

```java
String name = "Asha";
double marks = 87.456;
int rank = 3;

System.out.println(String.format("%s scored %.1f", name, marks));
System.out.printf("Rank %03d%n", rank);
System.out.printf("|%-8s|%8s|%n", "left", "right");
```

```output
Asha scored 87.5
Rank 003
|left    |   right|
```

| Code | Meaning |
| --- | --- |
| `%s` | a string |
| `%d` | a whole number (`%5d` pads to width 5, `%05d` pads with zeros) |
| `%.2f` | a decimal with 2 places |
| `%n` | a new line (works on every operating system) |
| `%-8s` | a string, left-aligned in 8 characters |

## Text blocks (Java 15+)

For multi-line text, use three double quotes:

```java
String json = """
        {
          "name": "Asha",
          "marks": 92
        }
        """;
System.out.print(json);
```

```output
{
  "name": "Asha",
  "marks": 92
}
```

The common indentation is removed, and you do not need `\n` or escaped quotes.

:::interview
**Interviewers often ask:** "Why are strings immutable in Java?" It makes them safe to share between threads, lets Java reuse them through the string pool, makes them safe as keys in a HashMap (their hash cannot change), and helps security (a file path or password check cannot be altered after it is validated).
:::
