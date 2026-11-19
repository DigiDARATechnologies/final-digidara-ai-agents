---
title: Abstract classes and interfaces
summary: Define contracts with interfaces and abstract classes, use default methods, and know when to choose which.
takeaways:
- An interface is a contract of methods a class promises to provide
- An abstract class can mix finished methods with ones children must write
- A class can implement many interfaces but extend only one class
---
## Abstract classes

An **abstract class** is incomplete on purpose. You cannot create objects from it; you extend it. It may contain **abstract methods** (no body) that every subclass must implement, and normal methods that are shared.

```java
public abstract class Shape {
    private final String name;

    protected Shape(String name) {
        this.name = name;
    }

    public abstract double area();               // no body: children must provide it

    public String describe() {                   // shared, finished behaviour
        return name + " with area " + String.format("%.2f", area());
    }
}

public class Circle extends Shape {
    private final double radius;

    public Circle(double radius) {
        super("Circle");
        this.radius = radius;
    }

    @Override
    public double area() {
        return Math.PI * radius * radius;
    }
}

public class Rectangle extends Shape {
    private final double width, height;

    public Rectangle(double width, double height) {
        super("Rectangle");
        this.width = width;
        this.height = height;
    }

    @Override
    public double area() {
        return width * height;
    }
}
```

```java
Shape[] shapes = { new Circle(2), new Rectangle(3, 4) };
for (Shape s : shapes) {
    System.out.println(s.describe());
}
// new Shape("x");      // compile error: Shape is abstract
```

```output
Circle with area 12.57
Rectangle with area 12.00
```

## Interfaces

An **interface** describes **what** a class can do, without saying how. A class that `implements` it must provide every method.

```java
public interface Payable {
    double amountDue();                      // implicitly public and abstract
}

public interface Printable {
    void print();
}

public class Invoice implements Payable, Printable {
    private final double amount;

    public Invoice(double amount) {
        this.amount = amount;
    }

    @Override
    public double amountDue() {
        return amount * 1.18;                // add 18% tax
    }

    @Override
    public void print() {
        System.out.println("Invoice, due: " + amountDue());
    }
}
```

```java
Invoice invoice = new Invoice(1000);
invoice.print();

Payable p = invoice;                         // use it through the interface type
System.out.println(p.amountDue() > 1000);
```

```output
Invoice, due: 1180.0
true
```

A class can implement **many** interfaces, which is how Java gets the benefits of multiple inheritance safely.

## Default and static methods in interfaces

Since Java 8, interfaces can include finished methods:

```java
public interface Greeter {
    String name();

    default String greet() {                 // a ready-made method children can use or override
        return "Hello, " + name() + "!";
    }

    static Greeter of(String n) {            // a static helper
        return () -> n;
    }
}
```

```java
Greeter g = Greeter.of("Asha");
System.out.println(g.greet());
```

```output
Hello, Asha!
```

An interface with exactly **one** abstract method is a **functional interface**. It can be written as a lambda (like `() -> n` above), which is the doorway to streams in a later lesson.

## Abstract class or interface?

| | Abstract class | Interface |
| --- | --- | --- |
| Can have fields with state | yes | only constants |
| Can have constructors | yes | no |
| A class can use | only one (`extends`) | many (`implements`) |
| Best for | a family of closely related classes sharing code | a capability that unrelated classes can have |
| Example | `Shape` with `Circle` and `Rectangle` | `Comparable`, `Runnable`, `Payable` |

## Interfaces you will meet constantly

| Interface | Purpose |
| --- | --- |
| `Comparable<T>` | gives a class a natural order (`compareTo`) |
| `Comparator<T>` | an external way to order objects |
| `Runnable` | a task to run on a thread |
| `List`, `Set`, `Map` | the collection types (many classes implement them) |
| `AutoCloseable` | something that can be closed in try-with-resources |

## Programming to an interface

Declare variables with the interface type and create the concrete class on the right:

```java
List<String> names = new ArrayList<>();       // the left side says what it is, the right side how
```

If you later switch to `LinkedList`, only one word changes and no other code breaks.

## Sealed types (Java 17+)

A `sealed` class or interface lists exactly which classes may extend it, giving you a closed set of cases the compiler can check:

```java
public sealed interface Vehicle permits Car, Bike { }
public record Car(int seats) implements Vehicle { }
public record Bike(boolean electric) implements Vehicle { }
```

:::interview
**Interviewers often ask:** "Abstract class versus interface?" An abstract class can hold state and constructors and is for closely related classes; a class extends only one. An interface defines a capability, a class can implement many, and since Java 8 it can have default and static methods. "Can you create an object of an abstract class?" No, only of a concrete subclass.
:::
