---
title: OOP concepts questions
summary: Classes, objects, the four pillars, SOLID principles and common design patterns, language independent.
kind: qa
takeaways:
- Explain OOP concepts with simple real-life examples
- Know the five SOLID principles
- Name and describe a few design patterns
---
### Q [Easy] What is object-oriented programming?
A style that organises code into **objects**: bundles of data (attributes) and behaviour (methods), created from **classes**. It models real-world things and helps reuse and maintain code.

### Q [Easy] Class vs object?
A **class** is a blueprint; an **object** is an instance built from it. "Car" is a class; my red Swift is an object.

### Q [Easy] Explain the four pillars with an example.
**Encapsulation**: a bank account hides its balance and exposes `deposit()` and `withdraw()`. **Inheritance**: `SavingsAccount` extends `Account`. **Polymorphism**: `area()` behaves differently for `Circle` and `Square`. **Abstraction**: you use `drive()` without knowing how the engine works.

### Q [Medium] Compile-time vs run-time polymorphism?
**Compile-time** (static): method overloading and operator overloading. **Run-time** (dynamic): method overriding through a parent reference calling the child's version.

### Q [Medium] Composition vs inheritance?
Inheritance is an "is-a" relationship (a Dog is an Animal). Composition is a "has-a" relationship (a Car has an Engine). Prefer **composition** for flexibility; use inheritance for real "is-a" cases.

### Q [Medium] What is coupling and cohesion?
**Coupling**: how much one module depends on another (aim for low). **Cohesion**: how closely the parts of a module belong together (aim for high).

### Q [Medium] Explain the SOLID principles.
**S**ingle responsibility: a class has one reason to change. **O**pen/closed: open for extension, closed for modification. **L**iskov substitution: a subclass must be usable wherever its parent is. **I**nterface segregation: many small interfaces beat one large one. **D**ependency inversion: depend on abstractions, not concrete classes.

### Q [Medium] What is the Singleton pattern?
Ensures a class has **only one instance** and gives global access to it (for example a configuration or logging object). Be careful with thread safety and testing.

### Q [Medium] What is the Factory pattern?
A method or class that creates objects without exposing the exact class, so the caller asks for "a payment processor" and the factory decides which one.

### Q [Medium] What is the Observer pattern?
Objects (observers) subscribe to another (the subject) and are notified when it changes, like subscribers to a newsletter or event listeners in the UI.

### Q [Medium] What is the difference between an abstract class and an interface?
An abstract class can hold state and partial implementation and is for closely related classes. An interface only defines a contract (behaviour) that unrelated classes can implement.

### Q [Hard] What is the MVC architecture?
**Model** (data and rules), **View** (what the user sees), **Controller** (handles input and connects the two). It separates concerns so each part can change independently.

### Q [Hard] What is dependency injection?
Providing an object's dependencies from outside rather than creating them inside. It reduces coupling and makes testing easy by letting you pass in a fake dependency.
