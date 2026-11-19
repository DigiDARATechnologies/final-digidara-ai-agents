---
title: Exception handling
summary: Handle errors with try, catch and finally, understand checked and unchecked exceptions, use try-with-resources and write your own exceptions.
takeaways:
- An exception is an object describing a problem; try and catch let the program recover
- Checked exceptions must be handled or declared; unchecked ones (RuntimeException) need not be
- try-with-resources closes files and connections automatically
---
## When things go wrong

A program can fail at run time: divide by zero, read a missing file, use `null`. Java reports the problem by **throwing an exception**. If nothing catches it, the program stops and prints a stack trace.

```java
int[] values = {1, 2, 3};
System.out.println(values[5]);        // ArrayIndexOutOfBoundsException: the program crashes here
```

## try and catch

```java
try {
    int result = 10 / 0;
    System.out.println("never printed");
} catch (ArithmeticException e) {
    System.out.println("Caught: " + e.getMessage());
}
System.out.println("The program continues");
```

```output
Caught: / by zero
The program continues
```

When the exception happens, Java jumps out of the `try` block to the matching `catch`. The code after the whole structure carries on normally.

## Several catches and finally

```java
static void test(String text, int[] data, int index) {
    try {
        int number = Integer.parseInt(text);
        System.out.println(data[index] / number);
    } catch (NumberFormatException e) {
        System.out.println("not a number: " + text);
    } catch (ArithmeticException e) {
        System.out.println("cannot divide by zero");
    } catch (ArrayIndexOutOfBoundsException e) {
        System.out.println("bad position " + index);
    } finally {
        System.out.println("finished");       // runs whether or not there was an exception
    }
}
```

```java
int[] data = {100, 50};
test("5", data, 0);
test("abc", data, 0);
test("0", data, 1);
test("2", data, 9);
```

```output
20
finished
not a number: abc
finished
cannot divide by zero
finished
bad position 9
finished
```

`finally` always runs, which makes it the right place for clean-up such as closing a file. Catch the **specific** exceptions first. Catching a general `Exception` hides bugs.

## The exception family

| Group | Examples | Rule |
| --- | --- | --- |
| **Checked** exceptions (extend `Exception`) | `IOException`, `SQLException` | the compiler **forces** you to catch them or declare `throws` |
| **Unchecked** exceptions (extend `RuntimeException`) | `NullPointerException`, `IllegalArgumentException`, `ArrayIndexOutOfBoundsException` | usually programming mistakes; handling is optional |
| **Errors** (extend `Error`) | `OutOfMemoryError`, `StackOverflowError` | serious problems; do not try to catch them |

Checked exceptions are about problems outside your control (a file is missing, the network drops). Unchecked ones are mostly bugs you should fix in the code.

## throw and throws

You can **throw** an exception yourself when a rule is broken. A method that might throw a checked exception **declares** it with `throws`:

```java
static void setAge(int age) {
    if (age < 0 || age > 150) {
        throw new IllegalArgumentException("Age must be between 0 and 150, got " + age);
    }
    System.out.println("Age set to " + age);
}

static String readFirstLine(String path) throws java.io.IOException {
    return java.nio.file.Files.readAllLines(java.nio.file.Path.of(path)).get(0);
}
```

```java
setAge(30);
try {
    setAge(-5);
} catch (IllegalArgumentException e) {
    System.out.println("Rejected: " + e.getMessage());
}
```

```output
Age set to 30
Rejected: Age must be between 0 and 150, got -5
```

## try-with-resources

Files, database connections and network streams must be closed. **try-with-resources** closes them automatically, even when an exception happens:

```java
import java.io.*;

try (BufferedReader reader = new BufferedReader(new FileReader("notes.txt"))) {
    String line;
    while ((line = reader.readLine()) != null) {
        System.out.println(line);
    }
} catch (IOException e) {
    System.out.println("Could not read the file: " + e.getMessage());
}
// the reader is closed here, whatever happened above
```

Anything that implements `AutoCloseable` can go in the brackets. This replaces the old pattern of closing inside `finally`.

## Custom exceptions

Make your own exception to describe problems in your application:

```java
public class InsufficientFundsException extends Exception {
    private final double shortBy;

    public InsufficientFundsException(double shortBy) {
        super("Not enough balance, short by " + shortBy);
        this.shortBy = shortBy;
    }

    public double getShortBy() {
        return shortBy;
    }
}
```

```java
static void withdraw(double balance, double amount) throws InsufficientFundsException {
    if (amount > balance) {
        throw new InsufficientFundsException(amount - balance);
    }
    System.out.println("Withdrawn " + amount);
}
```

```java
try {
    withdraw(1000, 400);
    withdraw(1000, 1500);
} catch (InsufficientFundsException e) {
    System.out.println(e.getMessage());
}
```

```output
Withdrawn 400.0
Not enough balance, short by 500.0
```

Extend `Exception` for a problem callers must handle (checked), or `RuntimeException` for a programming error (unchecked).

## Good exception habits

| Do | Avoid |
| --- | --- |
| catch **specific** exceptions | `catch (Exception e)` everywhere |
| give a useful message (what failed, with which value) | an empty message |
| log the exception, or rethrow it | an **empty catch block** that silently hides the problem |
| use try-with-resources for anything closable | forgetting to close files and connections |
| validate arguments early and throw `IllegalArgumentException` | letting bad data travel deep into the program |
| never use exceptions for normal flow | using exceptions as a replacement for `if` |

:::warning
An empty `catch` block (`catch (Exception e) { }`) is one of the worst habits in programming: the program fails and nobody can tell why. At the very least, print or log the exception.
:::

:::interview
**Interviewers often ask:** "Checked versus unchecked exceptions?" Checked exceptions (subclasses of `Exception` but not `RuntimeException`) must be caught or declared; they represent recoverable external problems. Unchecked ones (`RuntimeException` and `Error`) need no declaration and usually signal bugs. Also: "Does `finally` always run?" Almost always: it runs after the try and catch parts, even after a `return`, unless the JVM exits (for example `System.exit`) or crashes.
:::
