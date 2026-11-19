---
title: What is Java?
summary: Understand what Java is, how JDK, JRE and JVM fit together, install it on your laptop and run your first program.
takeaways:
- Java is compiled to bytecode that runs on the JVM, so the same program runs on Windows, macOS and Linux
- The JDK is what you install to write programs; it includes the compiler (javac) and the runtime (java)
- Every Java program starts at a main method inside a class
---
## Why Java

Java is one of the most widely used programming languages in the world. Banks, e-commerce sites, Android apps, big data tools and large company systems run on it. It is a popular first language in colleges and a common requirement in job interviews.

| Strength | What it means for you |
| --- | --- |
| **Write once, run anywhere** | the same compiled program runs on any computer that has Java |
| **Strongly typed** | the compiler catches many mistakes before the program runs |
| **Object-oriented** | programs are organised as classes and objects, which keeps big projects tidy |
| **Huge ecosystem** | libraries and frameworks (Spring Boot, Hibernate) for almost any task |
| **Fast and stable** | mature runtime, good performance, strong tooling |
| **Great job market** | many companies hire Java developers all the time |

## How Java runs: source, bytecode, JVM

1. You write **source code** in a `.java` file.
2. The **compiler** (`javac`) turns it into **bytecode** in a `.class` file.
3. The **JVM** (Java Virtual Machine) reads the bytecode and runs it on your computer.

Because the JVM is available for every operating system, the same `.class` file works everywhere. That is the idea behind "write once, run anywhere".

| Term | Meaning |
| --- | --- |
| **JVM** | Java Virtual Machine: runs bytecode |
| **JRE** | Java Runtime Environment: the JVM plus the standard libraries, enough to **run** programs |
| **JDK** | Java Development Kit: the JRE plus tools such as `javac`, enough to **write and run** programs |

As a learner you install the **JDK**.

## Install Java on your laptop

1. Download a recent **LTS** (long-term support) JDK, such as **Java 21**, from Adoptium (Temurin) or Oracle.
2. Run the installer.
3. Open a terminal (Command Prompt, PowerShell or Terminal) and check:

```py
java -version
javac -version
```

Both should print a version number such as 21. If the terminal says the command is not found, the installation folder is not on your system `PATH`; reinstall and tick the option to set it, or add it by hand.

:::tip
A good editor makes learning easier. **IntelliJ IDEA Community Edition** and **VS Code** with the Java extension both work well and are free.
:::

## Your first program

Create a file named `Hello.java`:

```java
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello, Java!");
    }
}
```

Compile and run it from the folder that holds the file:

```py
javac Hello.java      # creates Hello.class
java Hello            # runs it
```

```output
Hello, Java!
```

Since Java 11 you can also run a single file in one step: `java Hello.java`.

## Reading the program

| Part | Meaning |
| --- | --- |
| `public class Hello` | everything in Java lives inside a class; the file name must match the public class name (`Hello.java`) |
| `public static void main(String[] args)` | the **entry point**: the JVM starts here |
| `System.out.println(...)` | prints a line of text to the screen |
| `;` | every statement ends with a semicolon |
| `{ }` | braces group the code that belongs to a class or method |

:::warning
Java is **case-sensitive**: `Hello`, `hello` and `HELLO` are three different names, and `system.out` instead of `System.out` is an error. Most beginner mistakes are a missing semicolon, a wrong capital letter, or a file name that does not match the class name.
:::

## Comments

```java
// a single-line comment

/* a comment that
   spans several lines */

/** a documentation comment, used to generate API docs */
```

## How to try the code in this course

Many examples show only a few lines. Put them **inside a `main` method** of a class, like this:

```java
public class Main {
    public static void main(String[] args) {
        // paste the example lines here
    }
}
```

If the compiler complains about a checked exception (for example in the file and thread lessons), add `throws Exception` after `main(String[] args)`. Lines that start with `import` go at the very top of the file, above the class. Examples that show a whole class (with `public class ...`) can be saved as their own file, named exactly like the class.

## What this course covers

| Part | You will learn |
| --- | --- |
| Basics | variables, operators, strings, decisions, loops, arrays, methods |
| Object-oriented Java | classes, constructors, inheritance, interfaces |
| Everyday tools | exceptions, collections, generics, files |
| Modern Java | lambdas, streams, records, enums, newer language features |
| Beyond | concurrency basics, Maven and testing, interview questions |

Type out every example yourself, compile it and run it. Reading code teaches a little; **typing and running it** teaches a lot.
