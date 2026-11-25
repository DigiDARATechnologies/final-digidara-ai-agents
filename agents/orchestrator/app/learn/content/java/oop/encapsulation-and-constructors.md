---
title: Constructors and encapsulation
summary: Set up objects with constructors, protect their data with private fields and getters, and make safe, immutable classes.
takeaways:
- A constructor runs when an object is created and sets its starting state
- Make fields private and expose behaviour through methods (encapsulation)
- Validation inside setters and constructors keeps objects always valid
---
## Constructors

A **constructor** is a special method with the **same name as the class** and no return type. It runs automatically when you use `new`.

```java
public class Student {
    String name;
    int marks;

    Student(String name, int marks) {       // constructor
        this.name = name;
        this.marks = marks;
    }

    Student(String name) {                  // another constructor (overloaded)
        this(name, 0);                      // call the first one
    }
}
```

```java
Student a = new Student("Asha", 92);
Student b = new Student("Ravi");
System.out.println(a.name + " " + a.marks);
System.out.println(b.name + " " + b.marks);
```

```output
Asha 92
Ravi 0
```

`this(...)` calls another constructor of the same class, which avoids repeating code. If you write **no** constructor, Java gives the class an empty **default constructor**. As soon as you write one of your own, the default one disappears.

## The problem with open fields

If fields are open to everyone, any code can break the object:

```java
Student s = new Student("Asha", 92);
s.marks = -500;          // nothing stops this nonsense
```

## Encapsulation: private fields, public methods

**Encapsulation** means hiding the inner data (`private`) and letting the outside world use it only through methods you control. The class then guards its own rules.

| Access modifier | Visible to |
| --- | --- |
| `private` | only inside the same class |
| (nothing, "package-private") | classes in the same package |
| `protected` | the same package and subclasses |
| `public` | everyone |

```java
public class BankAccount {
    private double balance;
    private final String owner;

    public BankAccount(String owner, double openingBalance) {
        if (openingBalance < 0) {
            throw new IllegalArgumentException("Opening balance cannot be negative");
        }
        this.owner = owner;
        this.balance = openingBalance;
    }

    public void deposit(double amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("Deposit must be positive");
        }
        balance += amount;
    }

    public boolean withdraw(double amount) {
        if (amount <= 0 || amount > balance) {
            return false;
        }
        balance -= amount;
        return true;
    }

    public double getBalance() {
        return balance;
    }

    public String getOwner() {
        return owner;
    }
}
```

```java
BankAccount acc = new BankAccount("Asha", 1000);
acc.deposit(500);
System.out.println(acc.withdraw(2000));
System.out.println(acc.withdraw(300));
System.out.println(acc.getBalance());
// acc.balance = 1_000_000;    // compile error: balance is private
```

```output
false
true
1200.0
```

The balance can only change through `deposit` and `withdraw`, which check the rules. It is impossible to end up with a negative deposit or an overdraft by accident.

## Getters and setters

| Method | Convention | Example |
| --- | --- | --- |
| **getter** | `getName()` (or `isActive()` for booleans) | returns the field |
| **setter** | `setName(String name)` | changes the field, usually with a check |

Do not create a setter for every field automatically. If a value should never change after the object is created (like the `owner` above, which is `final`), provide **no setter**.

## Immutable classes

An **immutable** object cannot change after creation. They are simpler and safe to share between threads. `String` is immutable. To build your own:

1. Make the class `final`.
2. Make all fields `private final`.
3. Set them only in the constructor.
4. Provide no setters; return copies of any mutable fields.

```java
public final class Money {
    private final long paise;

    public Money(long paise) {
        this.paise = paise;
    }

    public Money plus(Money other) {
        return new Money(this.paise + other.paise);      // returns a NEW object
    }

    public long getPaise() {
        return paise;
    }
}
```

```java
Money a = new Money(5000);
Money b = a.plus(new Money(2500));
System.out.println(a.getPaise());
System.out.println(b.getPaise());
```

```output
5000
7500
```

`a` was not changed by `plus`; a new `Money` was created instead.

## Initialisation order (a quick reference)

When you create an object: static parts of the class run once when the class is first used; then, for each object, the fields get default values, then field initialisers and instance blocks run, and finally the constructor body runs.

:::tip
A good rule of thumb: **make everything as private as possible, and as final as possible.** Open things up only when something else genuinely needs them.
:::

:::interview
**Interviewers often ask:** "What is encapsulation and why use it?" Bundling data with the methods that work on it and hiding the internals with `private`. It protects the object's rules (validation), lets you change the inside later without breaking other code, and reduces bugs.
:::
