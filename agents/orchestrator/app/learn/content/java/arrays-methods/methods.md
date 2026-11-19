---
title: Methods
summary: Write reusable methods with parameters and return values, understand pass-by-value, overloading, varargs and recursion.
takeaways:
- A method groups code under a name so you can reuse it
- Java passes arguments by value: a copy of the variable (for objects, a copy of the reference)
- Overloading lets several methods share a name with different parameters
---
## Defining and calling a method

```java
public class Calculator {

    static int add(int a, int b) {
        return a + b;
    }

    static void greet(String name) {
        System.out.println("Hello, " + name + "!");
    }

    public static void main(String[] args) {
        int sum = add(3, 4);
        System.out.println(sum);
        greet("Asha");
        System.out.println(add(add(1, 2), 10));
    }
}
```

```output
7
Hello, Asha!
13
```

| Part of `static int add(int a, int b)` | Meaning |
| --- | --- |
| `static` | belongs to the class, so `main` can call it without making an object (objects come soon) |
| `int` | the **return type**: the kind of value the method gives back |
| `add` | the method name (camelCase, usually a verb) |
| `(int a, int b)` | the **parameters**: inputs the method needs |
| `return a + b;` | sends the result back and ends the method |

A method that returns nothing uses the return type `void`.

## Methods that make decisions

```java
static String grade(int marks) {
    if (marks >= 90) return "A";
    if (marks >= 75) return "B";
    if (marks >= 50) return "C";
    return "F";
}

static boolean isEven(int n) {
    return n % 2 == 0;
}

static int max(int[] values) {
    int best = values[0];
    for (int v : values) {
        if (v > best) best = v;
    }
    return best;
}
```

```java
System.out.println(grade(82));
System.out.println(isEven(7));
System.out.println(max(new int[]{4, 19, 7}));
```

```output
B
false
19
```

Every path through a method that has a return type must end in a `return`, otherwise the code does not compile.

## Pass by value

Java **always** passes a **copy**. For a primitive, that is a copy of the number, so changing it inside the method does not affect the caller:

```java
static void tryToChange(int x) {
    x = 100;
}

int n = 5;
tryToChange(n);
System.out.println(n);
```

```output
5
```

For objects and arrays, the copy is a copy of the **reference** (the address). The method and the caller then point to the **same object**, so changes to the **object's contents** are visible, but pointing the parameter to a new object is not:

```java
static void changeContents(int[] arr) {
    arr[0] = 99;                  // changes the shared array
}

static void replaceArray(int[] arr) {
    arr = new int[]{7, 7, 7};     // only the local copy of the reference changes
}

int[] data = {1, 2, 3};
changeContents(data);
System.out.println(data[0]);
replaceArray(data);
System.out.println(data[0]);
```

```output
99
99
```

:::interview
**Interviewers often ask:** "Is Java pass by value or pass by reference?" Always **pass by value**. For objects, the value that is copied is the reference, so a method can modify the object it points to but cannot make the caller's variable point to a different object.
:::

## Overloading

Several methods can share a name if their **parameter lists** differ (in number or type):

```java
static int area(int side) {
    return side * side;
}

static int area(int length, int width) {
    return length * width;
}

static double area(double radius) {
    return Math.PI * radius * radius;
}
```

```java
System.out.println(area(4));
System.out.println(area(4, 5));
System.out.println(Math.round(area(2.0) * 100) / 100.0);
```

```output
16
20
12.57
```

Java picks the version that matches the arguments. Changing only the return type is **not** enough to overload.

## Varargs

A method can accept any number of values of one type with `...`:

```java
static int sum(int... numbers) {
    int total = 0;
    for (int n : numbers) {
        total += n;
    }
    return total;
}
```

```java
System.out.println(sum());
System.out.println(sum(5));
System.out.println(sum(1, 2, 3, 4));
```

```output
0
5
10
```

Inside the method, `numbers` is just an `int[]`. A varargs parameter must be the **last** one.

## Recursion

A method that calls **itself**. It needs a **base case** that stops it, and each call must move toward that base case:

```java
static long factorial(int n) {
    if (n <= 1) {
        return 1;              // base case
    }
    return n * factorial(n - 1);
}

static int fibonacci(int n) {
    if (n < 2) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}
```

```java
System.out.println(factorial(5));
System.out.println(factorial(10));
System.out.println(fibonacci(10));
```

```output
120
3628800
55
```

`factorial(5)` becomes `5 * 4 * 3 * 2 * 1`. This simple `fibonacci` repeats a lot of work and becomes very slow for larger numbers.

:::warning
A recursive method with no base case (or one that never reaches it) keeps calling itself until the program crashes with a `StackOverflowError`.
:::

## Good method habits

| Habit | Why |
| --- | --- |
| one method, one job | easier to read, test and reuse |
| a clear verb name: `calculateTotal`, `isValid` | the call reads like a sentence |
| keep it short | if it does not fit on a screen, split it |
| avoid too many parameters | more than 3 or 4 is a hint to group them into an object |
