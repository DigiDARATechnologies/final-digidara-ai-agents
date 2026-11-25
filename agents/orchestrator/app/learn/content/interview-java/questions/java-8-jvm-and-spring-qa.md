---
title: Java 8 features, JVM and Spring questions
summary: Lambdas, streams, Optional, garbage collection, memory areas and Spring Boot basics.
kind: qa
takeaways:
- Be able to write a lambda and a stream pipeline
- Know the JVM memory areas and what garbage collection does
- Explain dependency injection and what Spring Boot adds
---
### Q [Easy] What are lambda expressions?
A short way to write an anonymous function, mainly for **functional interfaces** (one abstract method). Example: `list.forEach(x -> System.out.println(x));`

### Q [Medium] What is a functional interface?
An interface with **exactly one abstract method** (such as `Runnable`, `Comparator`, `Function`). It can have default and static methods. It is the target type for lambdas.

### Q [Medium] What is the Stream API?
A way to process collections with a pipeline: **source**, **intermediate operations** (`filter`, `map`, `sorted`; lazy) and a **terminal operation** (`collect`, `count`, `forEach`).

```java
List<String> names = students.stream()
    .filter(s -> s.getMarks() >= 75)
    .map(Student::getName)
    .sorted()
    .collect(Collectors.toList());
```

### Q [Medium] What is `Optional` used for?
A container that may or may not hold a value, used to avoid `NullPointerException` and make absence explicit: `Optional.ofNullable(x).orElse(defaultValue)`.

### Q [Medium] What are default methods in interfaces?
Methods with a body in an interface (marked `default`), added in Java 8 so interfaces can evolve without breaking existing classes.

### Q [Medium] Describe the JVM memory areas.
**Heap**: objects (shared, garbage collected). **Stack**: one per thread, holds method frames and local variables. **Method area / Metaspace**: class metadata and static data. **PC register** and **native method stack** per thread.

### Q [Medium] What is garbage collection?
The JVM automatically frees memory of objects that are no longer **reachable**. You cannot force it; `System.gc()` is only a request. Common collectors include G1 (default in modern Java) and ZGC.

### Q [Hard] What causes a memory leak in Java if there is garbage collection?
Objects that are still **referenced** but no longer needed: unbounded static collections, caches without eviction, unclosed resources and listeners that are never removed.

### Q [Hard] Difference between stack and heap?
Stack: small, fast, per thread, holds primitives and references, freed automatically when the method ends. Heap: large, shared, holds objects, cleaned by the garbage collector.

### Q [Medium] What is Spring and what is dependency injection?
Spring is a framework for building Java applications. **Dependency injection (DI)** means a class receives the objects it depends on from outside (the Spring container) instead of creating them, which makes code loosely coupled and easier to test.

### Q [Medium] What does Spring Boot add?
Auto-configuration, embedded servers (Tomcat), starter dependencies and production features, so you can create a running application with little configuration.

### Q [Medium] Explain common Spring annotations.
`@Component`, `@Service`, `@Repository`: beans managed by Spring. `@Autowired`: inject a dependency. `@RestController`: a controller returning JSON. `@GetMapping` / `@PostMapping`: map HTTP requests. `@SpringBootApplication`: entry point with auto-configuration.

### Q [Hard] What is the difference between `@Component`, `@Service` and `@Repository`?
All register a bean. `@Service` marks business logic and `@Repository` marks data access (and translates database exceptions). They are specialisations that make the code's intent clear.
