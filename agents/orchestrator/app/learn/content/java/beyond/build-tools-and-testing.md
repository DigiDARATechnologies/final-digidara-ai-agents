---
title: Maven, JUnit and professional habits
summary: Organise a real project with Maven, write unit tests with JUnit, and learn the habits and tools that professional Java teams use.
takeaways:
- Maven (or Gradle) builds the project and downloads libraries from the pom.xml description
- JUnit tests check that your code behaves as promised, every time you change it
- Packages, naming and small classes keep a project readable as it grows
---
## Packages

A **package** groups related classes into a folder structure and avoids name clashes. By convention the name is your reversed domain:

```java
package com.skilldara.students;

public class Student { }
```

The file sits in the folder `com/skilldara/students/Student.java`. Other packages bring it in with `import com.skilldara.students.Student;`. Classes in `java.lang` (like `String` and `Math`) are imported automatically.

## A typical project layout

```py
my-app/
  pom.xml                              # the Maven build file
  src/
    main/
      java/com/skilldara/app/App.java  # your code
      resources/                       # config files, templates
    test/
      java/com/skilldara/app/AppTest.java   # your tests
  target/                              # build output (do not commit this)
```

## Maven

Real projects use libraries (for JSON, databases, logging) and need a repeatable build. **Maven** reads a `pom.xml` file that lists your project and its **dependencies**, downloads them automatically, compiles, tests and packages the result. **Gradle** is the other popular build tool and does the same job.

```py
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.skilldara</groupId>
  <artifactId>my-app</artifactId>
  <version>1.0.0</version>

  <properties>
    <maven.compiler.release>21</maven.compiler.release>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>5.10.2</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

| Command | Does |
| --- | --- |
| `mvn compile` | compile the code |
| `mvn test` | compile and run the tests |
| `mvn package` | build a `.jar` file in `target/` |
| `mvn clean` | delete the `target` folder |
| `mvn clean install` | a full clean build, then store the result in your local repository |

A dependency is identified by three parts (`groupId`, `artifactId`, `version`). Search for libraries at **Maven Central** (search.maven.org).

## JUnit: automated tests

A **unit test** is a small piece of code that checks one behaviour of your code. Run all of them after every change, and you will notice at once if something broke.

The class under test:

```java
public class Grader {

    public static String grade(int marks) {
        if (marks < 0 || marks > 100) {
            throw new IllegalArgumentException("Marks must be 0 to 100");
        }
        if (marks >= 90) return "A";
        if (marks >= 75) return "B";
        if (marks >= 50) return "C";
        return "F";
    }
}
```

Its tests, in `src/test/java`:

```java
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class GraderTest {

    @Test
    void topMarksGetA() {
        assertEquals("A", Grader.grade(92));
    }

    @Test
    void boundariesBelongToTheHigherGrade() {
        assertEquals("B", Grader.grade(75));
        assertEquals("C", Grader.grade(50));
        assertEquals("F", Grader.grade(49));
    }

    @Test
    void invalidMarksAreRejected() {
        assertThrows(IllegalArgumentException.class, () -> Grader.grade(101));
        assertThrows(IllegalArgumentException.class, () -> Grader.grade(-1));
    }
}
```

Run them with `mvn test` (or the green arrow in your IDE). If all pass, Maven prints something like `Tests run: 3, Failures: 0`.

| Assertion | Checks |
| --- | --- |
| `assertEquals(expected, actual)` | the values are equal (the expected value goes first) |
| `assertTrue(condition)`, `assertFalse(...)` | a condition |
| `assertNull(x)`, `assertNotNull(x)` | null checks |
| `assertThrows(Type.class, () -> ...)` | the code throws that exception |
| `assertAll(...)` | check several things and report every failure |

Good tests are **small**, **fast**, **independent** of each other, and named for the behaviour they check (`boundariesBelongToTheHigherGrade`). Test the normal case, the boundaries, and the invalid inputs.

### Mocking

When the class under test needs a database or a web service, replace that part with a **mock** so the test stays fast and does not need the real thing. **Mockito** is the standard library for this:

```java
Repo repo = mock(Repo.class);
when(repo.findById(1)).thenReturn(new Student("Asha", 92));
```

## Logging, not printing

`System.out.println` is for learning. Real programs use a logging library (SLF4J with Logback) so messages have levels and can be turned up or down without changing code:

```java
private static final Logger log = LoggerFactory.getLogger(OrderService.class);

log.info("Order {} created for {}", orderId, customer);
log.error("Payment failed for order {}", orderId, exception);
```

## Frameworks you will meet

| Tool | Used for |
| --- | --- |
| **Spring Boot** | building web applications, REST APIs and microservices (the most common Java framework in jobs) |
| **Hibernate / JPA** | mapping classes to database tables (an ORM) |
| **JDBC** | the low-level API for talking to a database |
| **Jackson** | converting objects to and from JSON |
| **Lombok** | removing boilerplate such as getters (records now do part of this) |
| **JUnit and Mockito** | testing |
| **Maven / Gradle** | building |
| **Git** | version control (always) |

A good learning path after this course: build a small console project, then a REST API with **Spring Boot** and a database (MySQL or PostgreSQL), add tests, and put the code on GitHub.

## Habits of professional Java developers

| Habit | Why |
| --- | --- |
| small classes and methods with one job | readable and testable |
| meaningful names, no abbreviations | the code explains itself |
| program to interfaces | easy to change and to test |
| prefer immutable objects and `final` | fewer bugs, especially with threads |
| handle exceptions properly, never swallow them | failures stay visible |
| write tests for every important behaviour | safe changes |
| use a formatter and a linter | one consistent style |
| read other people's code and review code | the fastest way to improve |

:::interview
**Interviewers often ask:** "What is Maven?" A build and dependency-management tool: you describe the project and its libraries in `pom.xml`, and Maven downloads them and compiles, tests and packages the project. "What is a unit test?" A small automated test of one unit of behaviour (a method or class), run repeatedly to catch regressions, typically with JUnit.
:::
