---
title: Java interview questions
summary: Java questions from basic to advanced, with short answers you can say aloud, covering the language, OOP, collections, exceptions, strings, memory and concurrency.
kind: qa
takeaways:
- Be able to explain OOP concepts with a small example for each
- Know equals versus ==, String immutability, the collections and how HashMap works
- Understand the JVM, memory areas, exceptions and the basics of threads
---
### Q [Easy] What is Java and why is it called platform independent?
A high-level, object-oriented, class-based language. Source code compiles to bytecode, which runs on the Java Virtual Machine (JVM). Because a JVM exists for each operating system, the same bytecode runs anywhere: "write once, run anywhere".

### Q [Easy] What is the difference between JDK, JRE and JVM?
The JVM runs bytecode. The JRE is the JVM plus the standard libraries needed to run programs. The JDK is the JRE plus development tools such as the compiler `javac`. Developers install the JDK.

### Q [Easy] What are the primitive data types in Java?
`byte`, `short`, `int`, `long`, `float`, `double`, `char` and `boolean`. Everything else, including `String` and arrays, is a reference type (an object).

### Q [Easy] What is the difference between `==` and `.equals()`?
`==` compares primitives by value and objects by **reference** (whether they are the same object). `.equals()` compares the **content** when a class overrides it, as `String` does. Use `.equals()` to compare strings.

### Q [Easy] What are the four pillars of OOP?
Encapsulation (hiding data behind methods), inheritance (a class reusing a parent's code), polymorphism (one type, many forms, with the right method chosen at run time) and abstraction (exposing what something does, not how, through abstract classes and interfaces).

### Q [Medium] Why is `String` immutable and what is the string pool?
Immutability makes strings thread-safe, safe as HashMap keys, cacheable and more secure. The string pool is a memory area where identical string literals share one object, which saves memory. `new String("a")` creates a separate object outside the shared literal.

### Q [Medium] Difference between `String`, `StringBuilder` and `StringBuffer`?
`String` is immutable. `StringBuilder` is mutable and fast but not thread-safe. `StringBuffer` is mutable and thread-safe (synchronized) but slower. Use `StringBuilder` to build text in loops.

### Q [Medium] What is the difference between method overloading and overriding?
Overloading: the same method name with different parameters in the same class, resolved at compile time. Overriding: a subclass provides its own version of a parent's method with the same signature, resolved at run time (dynamic dispatch).

### Q [Medium] Abstract class versus interface?
An abstract class can have fields, constructors and both abstract and concrete methods, and a class can extend only one. An interface defines a contract (with default and static methods since Java 8), has only constants as fields, and a class can implement many. Use an abstract class for closely related classes sharing code, an interface for a capability.

### Q [Medium] What does the `static` keyword mean?
A static member belongs to the class rather than to any object, so it is shared and is accessed through the class name. Static methods cannot use `this` or instance members directly. Static blocks run once when the class is loaded.

### Q [Medium] What does `final` mean for a variable, method and class?
A final variable cannot be reassigned (for objects the reference is fixed, though the object can still change). A final method cannot be overridden. A final class cannot be extended, as with `String`.

### Q [Medium] What is the difference between checked and unchecked exceptions?
Checked exceptions (subclasses of `Exception` other than `RuntimeException`, such as `IOException`) must be caught or declared with `throws`. Unchecked exceptions (`RuntimeException` and its subclasses, such as `NullPointerException`) need not be, and usually indicate bugs.

### Q [Medium] Explain `try`, `catch`, `finally` and try-with-resources.
`try` holds code that may fail, `catch` handles a specific exception, and `finally` always runs for clean-up. Try-with-resources automatically closes any `AutoCloseable` resource (files, connections) when the block ends, even after an exception.

### Q [Medium] Is Java pass by value or pass by reference?
Always pass by value. For objects, the value passed is a copy of the reference, so a method can change the object's state but cannot change which object the caller's variable points to.

### Q [Medium] ArrayList versus LinkedList?
`ArrayList` is array-backed, so it has fast random access and is the default choice. `LinkedList` is a doubly linked list with fast insertion and removal at the ends but slow access by index and more memory use per element.

### Q [Medium] What is the difference between `HashMap`, `LinkedHashMap` and `TreeMap`?
`HashMap` gives fast lookups with no order. `LinkedHashMap` keeps insertion order. `TreeMap` keeps keys sorted (and uses `compareTo`), with slower O(log n) operations.

### Q [Hard] How does `HashMap` work internally?
It stores entries in an array of buckets. The key's `hashCode()` decides the bucket, and `equals()` finds the exact key within it. Collisions in a bucket are kept in a linked list, which turns into a balanced tree when it grows large (Java 8+). When the map gets too full it resizes and rehashes.

### Q [Hard] What is the contract between `equals()` and `hashCode()`?
If two objects are equal by `equals()`, they must return the same `hashCode()`. Objects with the same hash code are not necessarily equal. Break the contract and hash-based collections misbehave. Override both together, using the same fields.

### Q [Medium] What is a lambda and what is a functional interface?
A lambda is a short anonymous function, `(a, b) -> a + b`. It implements a functional interface: an interface with exactly one abstract method such as `Runnable`, `Comparator` or `Predicate`.

### Q [Medium] What is the Stream API?
A way to process collections as a pipeline of operations: a source, lazy intermediate operations (`filter`, `map`, `sorted`) and a terminal operation (`collect`, `count`, `sum`). Streams do not modify their source and can be consumed only once.

### Q [Medium] What is `Optional`?
A container that may or may not hold a value, used as a return type to make "no result" explicit and reduce `NullPointerException`s. Use `map`, `orElse` and `ifPresent` instead of calling `get()` blindly.

### Q [Medium] What is a record?
A concise, immutable data class (Java 16+) where the compiler generates the constructor, accessors, `equals`, `hashCode` and `toString` from the declared components.

### Q [Hard] Explain the JVM memory areas.
The **heap** stores objects and is managed by the garbage collector. The **stack** holds a frame per method call with local variables and references (one stack per thread). **Metaspace** stores class metadata. There is also a program counter per thread and native method stacks.

### Q [Hard] What is garbage collection?
The JVM automatically frees memory of objects that are no longer reachable from any live reference. You cannot force it (`System.gc()` is only a hint). Memory leaks still happen in Java when objects are kept reachable by mistake, for example in a static collection that is never cleared.

### Q [Hard] What is the difference between a process and a thread, and how do you create a thread?
A process is an independent program with its own memory; threads are lightweight paths of execution inside a process that share its memory. Create one with `new Thread(runnable).start()`, or better, submit tasks to an `ExecutorService`. Call `start()`, not `run()`.

### Q [Hard] What is a race condition and how do you prevent it?
When several threads access shared mutable data and the result depends on timing, for instance with `count++`. Prevent it with `synchronized`, locks, atomic classes (`AtomicInteger`), thread-safe collections (`ConcurrentHashMap`) or immutable objects.

### Q [Hard] What is the difference between `synchronized` and `volatile`?
`synchronized` gives mutual exclusion (one thread at a time) and also makes changes visible to other threads. `volatile` only guarantees **visibility** of a variable's latest value; it does not make compound actions like `count++` atomic.

### Q [Hard] What is a deadlock?
Two or more threads each hold a lock the other needs and wait forever. Avoid it by locking in a consistent order, holding locks for as short a time as possible, using timeouts (`tryLock`), or using higher-level concurrency tools.

### Q [Medium] What are generics and what is type erasure?
Generics let classes and methods operate on types specified by the caller, with compile-time type safety and no casts. Type erasure means the compiler removes the generic type information after checking, so at run time `List<String>` and `List<Integer>` are both just `List`.

### Q [Medium] Why does `Integer a = 127, b = 127; a == b` give true but 128 gives false?
Autoboxing uses `Integer.valueOf`, which caches objects for values from -128 to 127. Within that range both variables point to the same cached object; outside it, new objects are created, and `==` compares references. Compare wrapper objects with `.equals()`.

:::practice mock-interview
Practise explaining OOP, `equals` versus `==`, how HashMap works and what a race condition is aloud in a Mock Interview.
:::
