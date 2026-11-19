---
title: Inheritance and polymorphism
summary: Reuse code with extends, override methods, call super, and let one reference type work with many object types through polymorphism.
takeaways:
- A subclass extends a superclass and inherits its fields and methods
- Overriding replaces a method; the version that runs depends on the real object type
- Polymorphism lets code written for the parent work with every child
---
## Inheritance

When classes share common features, put them in a **superclass** and let others **extend** it. The child classes (**subclasses**) inherit the fields and methods.

```java
public class Person {
    protected String name;

    public Person(String name) {
        this.name = name;
    }

    public String describe() {
        return "Person: " + name;
    }
}

public class Student extends Person {
    private int marks;

    public Student(String name, int marks) {
        super(name);                 // call the parent constructor first
        this.marks = marks;
    }

    @Override
    public String describe() {
        return "Student: " + name + " (" + marks + ")";
    }
}

public class Teacher extends Person {
    private String subject;

    public Teacher(String name, String subject) {
        super(name);
        this.subject = subject;
    }

    @Override
    public String describe() {
        return "Teacher: " + name + " teaches " + subject;
    }
}
```

| Keyword | Meaning |
| --- | --- |
| `extends` | this class inherits from another (an "is-a" relationship: a Student **is a** Person) |
| `super(...)` | call the parent's constructor; it must be the **first** line |
| `super.method()` | call the parent's version of a method |
| `@Override` | tells the compiler "I mean to replace a parent method" (it catches typos) |
| `protected` | visible to subclasses |

Java allows only **one** superclass for a class (single inheritance); multiple abilities come from interfaces.

## Polymorphism

*Poly-morph* means "many forms". A variable of the **parent type** can hold any **child object**, and a call to an overridden method runs the **child's** version:

```java
Person[] people = {
    new Person("Kiran"),
    new Student("Asha", 92),
    new Teacher("Mr. Rao", "Java")
};

for (Person p : people) {
    System.out.println(p.describe());
}
```

```output
Person: Kiran
Student: Asha (92)
Teacher: Mr. Rao teaches Java
```

The loop is written once for `Person`, yet each object behaves according to its **real type**. Java decides which `describe()` to run when the program runs (**dynamic dispatch**), not when it compiles. Adding a new kind of person later does not require changing this loop.

## Using super

```java
public class Employee {
    protected double baseSalary;

    public Employee(double baseSalary) {
        this.baseSalary = baseSalary;
    }

    public double salary() {
        return baseSalary;
    }
}

public class Manager extends Employee {
    public Manager(double baseSalary) {
        super(baseSalary);
    }

    @Override
    public double salary() {
        return super.salary() + 10000;       // parent's pay plus a bonus
    }
}
```

```java
Employee e = new Employee(30000);
Employee m = new Manager(50000);
System.out.println(e.salary());
System.out.println(m.salary());
```

```output
30000.0
60000.0
```

`m` is declared as an `Employee`, but it is a `Manager` object, so `salary()` adds the bonus.

## Overriding versus overloading

| | Overloading | Overriding |
| --- | --- | --- |
| Where | the same class | a subclass |
| Method name | the same | the same |
| Parameters | **different** | **the same** |
| Chosen | at compile time | at run time, by the real object type |

## Casting and instanceof

You can treat a child as its parent automatically (**upcasting**). To use a child-only method, check the type and cast down:

```java
Person p = new Student("Asha", 92);

if (p instanceof Student s) {              // Java 16+: test and name in one step
    System.out.println("Marks are visible here: " + s.describe());
}

Person t = new Teacher("Mr. Rao", "Java");
System.out.println(t instanceof Student);
```

```output
Marks are visible here: Student: Asha (92)
false
```

A wrong cast (`(Student) t` when `t` is a Teacher) throws `ClassCastException`, so test with `instanceof` first.

## final classes and methods

`final class X` cannot be extended (`String` is final). `final` on a method prevents overriding. The `Object` class sits at the top: **every** class extends `Object` and inherits methods such as `toString()`, `equals()` and `hashCode()`.

## Inheritance or composition?

Inheritance means "is-a". Often "has-a" is a better fit: a `Car` **has an** `Engine`; it is not an engine. Holding another object in a field is called **composition**, and is more flexible because it avoids deep chains of classes.

:::tip
"Favour composition over inheritance" is common advice. Use inheritance when there is a genuine "is-a" relationship and the child can be used **anywhere** the parent is expected; otherwise hold the other object as a field.
:::

:::interview
**Interviewers often ask:** "What is polymorphism?" The ability of one reference type to refer to objects of many classes, with the right overridden method chosen at run time. "Overloading versus overriding?" Overloading: same name, different parameters, in one class, resolved at compile time. Overriding: a subclass replaces a parent's method with the same signature, resolved at run time.
:::
