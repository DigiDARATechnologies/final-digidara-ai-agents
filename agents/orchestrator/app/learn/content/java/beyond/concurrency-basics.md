---
title: Threads and concurrency basics
summary: Run tasks in parallel with threads and executors, see why shared data is dangerous, and protect it with synchronized and atomic classes.
takeaways:
- A thread is an independent path of execution; use an ExecutorService instead of creating threads by hand
- Two threads changing the same data without protection give wrong results (a race condition)
- synchronized, locks and atomic classes make shared updates safe
---
## Why concurrency

A program that waits for a slow network call or a disk read wastes time. A server must handle many users at once. **Threads** let one program do several things at the same time. Modern computers have several CPU cores, so threads can truly run in parallel.

## Starting a thread

```java
public class ThreadDemo {
    public static void main(String[] args) throws InterruptedException {
        Thread worker = new Thread(() -> System.out.println("Running in " + Thread.currentThread().getName()));
        worker.setName("worker-1");
        worker.start();             // start() runs the task on a NEW thread
        worker.join();              // wait until it finishes
        System.out.println("Back in " + Thread.currentThread().getName());
    }
}
```

```output
Running in worker-1
Back in main
```

Call `start()`, not `run()`: calling `run()` just runs the code on the **current** thread, with no concurrency at all. `join()` makes one thread wait for another.

## The problem: a race condition

Two threads updating the same variable can overwrite each other's changes, because `count++` is really three steps (read, add, write):

```java
public class Counter {
    private int count = 0;

    public void increment() {
        count++;                    // NOT safe when called from several threads
    }

    public int get() {
        return count;
    }
}
```

```java
Counter counter = new Counter();
Runnable task = () -> {
    for (int i = 0; i < 100_000; i++) {
        counter.increment();
    }
};

Thread t1 = new Thread(task);
Thread t2 = new Thread(task);
t1.start();
t2.start();
t1.join();
t2.join();
System.out.println(counter.get());     // expected 200000
```

On most runs the printed number is **less than 200,000**, and it is different from run to run, because some increments are lost. Run it yourself a few times to see it. This is called a **race condition**, and it is one of the hardest kinds of bug to find, because the program usually works when you test it.

## Fix 1: synchronized

`synchronized` allows **one thread at a time** into a method or block:

```java
public class SafeCounter {
    private int count = 0;

    public synchronized void increment() {
        count++;
    }

    public synchronized int get() {
        return count;
    }
}
```

With `SafeCounter`, the same two-thread test always prints **200000**.

## Fix 2: atomic classes

For simple counters, `java.util.concurrent.atomic` is faster and simpler:

```java
import java.util.concurrent.atomic.AtomicInteger;

AtomicInteger count = new AtomicInteger();
count.incrementAndGet();
count.addAndGet(5);
System.out.println(count.get());
```

```output
6
```

`incrementAndGet()` reads, adds and writes as **one indivisible step**, so it is safe from many threads.

## ExecutorService: thread pools

Creating a new thread for every task is wasteful. A **thread pool** keeps a few threads and gives them tasks:

```java
import java.util.*;
import java.util.concurrent.*;

ExecutorService pool = Executors.newFixedThreadPool(4);

List<Future<Integer>> results = new ArrayList<>();
for (int n = 1; n <= 3; n++) {
    final int number = n;
    results.add(pool.submit(() -> number * number));       // runs on a pool thread, gives back a Future
}

for (Future<Integer> f : results) {
    System.out.println(f.get());                           // waits for the result
}
pool.shutdown();                                           // always shut the pool down
```

```output
1
4
9
```

A `Future` is a promise of a result that may not be ready yet. `get()` waits for it. Always call `shutdown()`, or the program may never exit.

## CompletableFuture

For chaining asynchronous steps:

```java
CompletableFuture<String> greeting = CompletableFuture
        .supplyAsync(() -> "Asha")
        .thenApply(name -> "Hello, " + name)
        .thenApply(String::toUpperCase);

System.out.println(greeting.get());
```

```output
HELLO, ASHA
```

## Thread-safe collections

| Instead of | Use |
| --- | --- |
| `HashMap` shared by threads | `ConcurrentHashMap` |
| `ArrayList` shared by threads | `CopyOnWriteArrayList`, or a synchronized wrapper |
| a hand-written queue | `LinkedBlockingQueue`, `ArrayBlockingQueue` |
| a plain `int` counter | `AtomicInteger`, `LongAdder` |

## Virtual threads (Java 21)

Ordinary threads are heavy: a server can hold only thousands. **Virtual threads** are lightweight threads managed by the JVM, so a program can use hundreds of thousands, which is ideal for code that mostly waits on the network or a database:

```java
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    for (int i = 0; i < 10_000; i++) {
        executor.submit(() -> {
            Thread.sleep(100);        // waiting is cheap on a virtual thread
            return "done";
        });
    }
}
```

## Deadlock and other dangers

| Problem | Meaning |
| --- | --- |
| **Race condition** | the result depends on the timing of threads |
| **Deadlock** | two threads each hold a lock the other needs, so both wait forever |
| **Visibility** | one thread does not see another thread's change (fix with `volatile`, locks or atomics) |
| **Starvation** | a thread never gets its turn |

Reduce the risk: share as little changeable data as possible, prefer **immutable** objects, use the high-level `java.util.concurrent` tools instead of raw `synchronized` and `wait`/`notify`, and always take locks in the same order.

:::warning
Concurrency bugs often do not show up in testing, then appear in production under load. If you do not need threads, do not use them. When you do, use the higher-level tools (`ExecutorService`, `ConcurrentHashMap`, atomics).
:::

:::interview
**Interviewers often ask:** "What is a race condition and how do you avoid it?" Two threads access shared data and at least one changes it, so the result depends on timing. Avoid it with `synchronized`, locks, atomic variables, thread-safe collections or immutable data. And: "`start()` versus `run()`?" `start()` creates a new thread that runs the task; `run()` is a normal method call on the current thread.
:::
