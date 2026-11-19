---
title: Classes and objects
summary: Model real things with classes, create objects, use fields and methods, understand this, static members and the heap.
takeaways:
- A class is a blueprint; an object is one thing built from it
- Fields hold an object's data; methods define its behaviour
- static members belong to the class itself, not to any single object
---
## Why classes

Imagine storing 500 students with separate variables for names, marks and cities. Instead, describe **a student once**, as a **class**, and create 500 **objects** from it.

| Idea | Real-life example |
| --- | --- |
| **Class** | the blueprint of a house |
| **Object** (instance) | one actual house built from the blueprint |
| **Fields** (attributes) | the colour, the number of rooms |
| **Methods** (behaviour) | open the door, switch on a light |

## Your first class

```java
public class Student {
    String name;
    int marks;

    void introduce() {
        System.out.println("Hi, I am " + name + " and I scored " + marks);
    }

    boolean hasPassed() {
        return marks >= 50;
    }
}
```

This is saved as `Student.java`. Another class uses it:

```java
public class Main {
    public static void main(String[] args) {
        Student asha = new Student();
        asha.name = "Asha";
        asha.marks = 92;

        Student ravi = new Student();
        ravi.name = "Ravi";
        ravi.marks = 48;

        asha.introduce();
        ravi.introduce();
        System.out.println(asha.hasPassed());
        System.out.println(ravi.hasPassed());
    }
}
```

```output
Hi, I am Asha and I scored 92
Hi, I am Ravi and I scored 48
true
false
```

`new Student()` creates an object. Each object has its **own copy** of the fields, so Asha's marks and Ravi's marks are separate. A dot reaches a field or method of an object.

## Where objects live

| Memory area | Holds |
| --- | --- |
| **Stack** | local variables and method calls (small and fast) |
| **Heap** | every object created with `new` |

A variable like `asha` does not contain the object; it holds a **reference** (an address) to the object on the heap. That is why copying an object variable copies only the reference:

```java
Student a = new Student();
a.name = "Asha";
Student b = a;               // b points to the SAME object
b.name = "Changed";
System.out.println(a.name);
```

```output
Changed
```

Both `a` and `b` refer to one object, so a change through `b` is visible through `a`. When no variable refers to an object any more, Java's **garbage collector** frees its memory automatically; you do not delete objects yourself.

## null

A reference that points to no object is `null`. Using a method or field of a `null` reference crashes with a `NullPointerException`:

```java
Student ghost = null;
// ghost.introduce();      // would throw NullPointerException
System.out.println(ghost == null);
```

```output
true
```

:::warning
`NullPointerException` is the most common runtime error in Java. Check for `null` before using a reference that might not be set, or design the code so values are always set.
:::

## this

Inside a method, `this` means "the object this method was called on". It is useful when a parameter has the same name as a field:

```java
public class Counter {
    int count;

    void setCount(int count) {
        this.count = count;        // field = parameter
    }

    Counter increment() {
        count++;
        return this;               // return the same object, so calls can be chained
    }
}
```

```java
Counter c = new Counter();
c.setCount(5);
c.increment().increment();
System.out.println(c.count);
```

```output
7
```

## static: belongs to the class

A `static` field or method belongs to the **class itself**, shared by all objects, and is reached through the class name:

```java
public class Student {
    static int totalStudents = 0;       // one copy, shared by all students
    String name;

    Student(String name) {
        this.name = name;
        totalStudents++;
    }

    static String schoolName() {
        return "SkillDARA Academy";
    }
}
```

```java
new Student("Asha");
new Student("Ravi");
new Student("Meena");
System.out.println(Student.totalStudents);
System.out.println(Student.schoolName());
```

```output
3
SkillDARA Academy
```

A static method cannot use `this` or the non-static fields directly, because it is not tied to one object. `main` is static for that reason: the JVM calls it before any object exists.

| | Instance member | Static member |
| --- | --- | --- |
| belongs to | one object | the class |
| reached with | `object.member` | `ClassName.member` |
| copies | one per object | exactly one |

## toString

Printing an object shows `ClassName@code` unless the class describes itself. Override `toString`:

```java
public class Student {
    String name;
    int marks;

    Student(String name, int marks) {
        this.name = name;
        this.marks = marks;
    }

    @Override
    public String toString() {
        return name + " (" + marks + ")";
    }
}
```

```java
Student s = new Student("Asha", 92);
System.out.println(s);
```

```output
Asha (92)
```

:::interview
**Interviewers often ask:** "What is the difference between a class and an object?" A class is the blueprint that defines fields and methods. An object is an instance of that class, created with `new`, living on the heap with its own copy of the fields. "What does `static` mean?" The member belongs to the class, not to a particular object.
:::
