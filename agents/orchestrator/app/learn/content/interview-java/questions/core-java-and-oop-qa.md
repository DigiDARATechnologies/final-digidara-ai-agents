---
title: Core Java and OOP questions
summary: JDK, JRE and JVM, data types, strings, the four OOP pillars, abstract classes and interfaces.
kind: qa
takeaways:
- Explain JDK, JRE and JVM clearly
- Know the four OOP pillars with a real example each
- Separate abstract class from interface, overloading from overriding
---
### Q [Easy] What is the difference between JDK, JRE and JVM?
The **JVM** runs Java bytecode and makes Java platform independent. The **JRE** is the JVM plus the standard libraries needed to run programs. The **JDK** is the JRE plus development tools such as the compiler (`javac`) and debugger.

### Q [Easy] Why is Java called platform independent?
Source code compiles to **bytecode**, not machine code. Any machine with a JVM can run the same bytecode ("write once, run anywhere"). The JVM itself is platform specific.

### Q [Easy] What are the primitive data types in Java?
`byte`, `short`, `int`, `long`, `float`, `double`, `char` and `boolean`. Everything else (such as `String` and arrays) is a reference type.

### Q [Easy] What is the difference between `==` and `.equals()`?
`==` compares **references** for objects (are they the same object?) and values for primitives. `.equals()` compares **content** when the class overrides it, as `String` does.

### Q [Medium] Why is `String` immutable? What are the benefits?
Once created, a String cannot change; operations make a new String. Benefits: thread safety, safe use as keys in a HashMap (the hash code does not change), security (file names, network addresses) and the String pool saves memory. Use `StringBuilder` for many changes.

### Q [Medium] StringBuilder vs StringBuffer?
Both are mutable. `StringBuffer` is **synchronized** (thread safe but slower). `StringBuilder` is not synchronized and is faster; use it when only one thread uses it.

### Q [Medium] Explain the four pillars of OOP.
**Encapsulation**: bundle data with methods and hide it using `private` fields and getters or setters. **Inheritance**: a class reuses another's members (`extends`). **Polymorphism**: one interface, many behaviours (overloading, overriding). **Abstraction**: expose what an object does and hide how (abstract classes, interfaces).

### Q [Medium] Method overloading vs overriding?
**Overloading**: same method name, different parameters, in the same class; resolved at **compile time**. **Overriding**: a subclass gives its own version of a parent method with the same signature; resolved at **run time**.

### Q [Medium] Abstract class vs interface?
An **abstract class** can have state (fields), constructors and both abstract and concrete methods, and a class can extend only **one**. An **interface** defines a contract (with default and static methods since Java 8) and a class can implement **many**. Use an interface for capabilities (`Comparable`), an abstract class for a shared base.

### Q [Medium] What is the `static` keyword?
A static member belongs to the **class**, not to an object. Static methods cannot use instance fields directly. Static blocks run once when the class loads.

### Q [Medium] What does the `final` keyword do?
A `final` variable cannot be reassigned, a `final` method cannot be overridden and a `final` class cannot be extended (like `String`).

### Q [Medium] What is a constructor? Can it be overloaded or inherited?
A constructor initialises a new object and has the class name with no return type. It can be **overloaded**, but is **not inherited**. A subclass constructor calls the parent's with `super(...)`.

### Q [Hard] What is the difference between `this` and `super`?
`this` refers to the current object (used to separate a field from a parameter, or call another constructor). `super` refers to the parent class (call a parent constructor or method).

### Q [Hard] What is the diamond problem and how does Java avoid it?
If a class could inherit from two classes with the same method, which one to use is ambiguous. Java forbids multiple inheritance of classes. With interfaces' default methods, the class must **override** the method to resolve the conflict.

### Q [Hard] Explain `hashCode()` and `equals()` contract.
Equal objects must have equal hash codes. If you override `equals`, you must override `hashCode`, or hash-based collections (HashMap, HashSet) will behave wrongly. Unequal objects may share a hash code (a collision).
