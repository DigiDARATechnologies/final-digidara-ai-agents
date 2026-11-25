---
title: Collections, exceptions and multithreading questions
summary: ArrayList, LinkedList, HashMap internals, exceptions, threads, synchronization and the concurrency tools.
kind: qa
takeaways:
- Know when to choose ArrayList, LinkedList, HashMap, TreeMap and HashSet
- Explain checked versus unchecked exceptions
- Understand thread safety, synchronized and the executor framework
---
### Q [Easy] ArrayList vs LinkedList?
`ArrayList` is backed by an array: fast random access O(1), slow insertion or deletion in the middle O(n). `LinkedList` is a doubly linked list: fast insertion or deletion at known positions, slow access by index O(n). ArrayList is the default choice.

### Q [Easy] List vs Set vs Map?
A **List** is ordered and allows duplicates. A **Set** has unique elements. A **Map** stores key-value pairs with unique keys.

### Q [Medium] How does HashMap work internally?
It uses an array of **buckets**. The key's `hashCode()` decides the bucket; keys that land in the same bucket form a linked list (or a balanced tree when long, since Java 8). `get` and `put` are O(1) on average. It allows one null key and is **not thread safe**.

### Q [Medium] HashMap vs Hashtable vs ConcurrentHashMap?
`HashMap`: unsynchronized, allows nulls, fastest in single-threaded code. `Hashtable`: legacy, synchronized on every method, no nulls. `ConcurrentHashMap`: thread safe with fine-grained locking, better throughput, no null keys or values.

### Q [Medium] HashSet vs TreeSet vs LinkedHashSet?
`HashSet`: no order, O(1). `LinkedHashSet`: keeps insertion order. `TreeSet`: sorted order, O(log n).

### Q [Medium] Comparable vs Comparator?
`Comparable` defines the **natural order** inside the class (`compareTo`). `Comparator` is a **separate** object defining another ordering (`compare`), so you can sort the same class several ways.

### Q [Medium] Checked vs unchecked exceptions?
**Checked** exceptions (such as `IOException`) must be caught or declared with `throws`; the compiler checks. **Unchecked** exceptions (`RuntimeException` and subclasses, such as `NullPointerException`) need not be handled. `Error` (such as `OutOfMemoryError`) is for serious problems.

### Q [Medium] What is the use of `finally`? Does it always run?
It runs after `try` and `catch` for clean-up (closing resources). It runs even if an exception occurs, except when the JVM exits (`System.exit`) or crashes. Prefer **try-with-resources** for closing.

### Q [Medium] `throw` vs `throws`?
`throw` actually throws an exception object. `throws` in a method signature declares which exceptions the method may throw.

### Q [Medium] What is a thread and how do you create one?
A thread is a path of execution. Create by extending `Thread`, or (better) implementing `Runnable` or `Callable` and passing it to a thread or an executor.

### Q [Hard] What does `synchronized` do?
It lets only one thread at a time execute a block or method guarded by the same lock, preventing race conditions on shared data. It also guarantees visibility of changes between threads.

### Q [Hard] `volatile` vs `synchronized`?
`volatile` guarantees visibility of a variable's latest value across threads but **not atomicity** of compound actions (such as `count++`). `synchronized` gives both mutual exclusion and visibility.

### Q [Hard] What is a deadlock and how can you avoid it?
Two or more threads wait forever for locks held by each other. Avoid by acquiring locks in a **consistent order**, holding locks for a short time, using timeouts (`tryLock`) and avoiding nested locks.

### Q [Hard] What is the Executor framework and why use it?
It manages a **pool of threads** and a queue of tasks (`ExecutorService`), so you do not create a thread per task. It reuses threads, limits resources and offers `Future` for results.

### Q [Hard] `wait()` vs `sleep()`?
`sleep(ms)` pauses the thread and **keeps** its locks. `wait()` releases the lock and waits until another thread calls `notify()` or `notifyAll()`, so it is used for thread coordination.
