---
title: Creating tables and keys
summary: Design a table with CREATE TABLE, data types, primary and foreign keys and constraints.
takeaways:
- CREATE TABLE defines columns and their types
- A primary key identifies each row; a foreign key links tables
- Constraints stop bad data getting in
---
## CREATE TABLE

```sql
CREATE TABLE students (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(150) UNIQUE,
  city VARCHAR(60),
  marks INT CHECK (marks BETWEEN 0 AND 100),
  joined DATE
);
```

## Common data types

| Type | Holds |
| --- | --- |
| `INT` | whole numbers |
| `DECIMAL(10,2)` | exact decimals, ideal for money |
| `VARCHAR(n)` | text up to n characters |
| `TEXT` | long text |
| `DATE`, `DATETIME` | dates and times |
| `BOOLEAN` | true or false |

## Constraints

| Constraint | Rule |
| --- | --- |
| `PRIMARY KEY` | unique and not null; identifies the row |
| `NOT NULL` | a value is required |
| `UNIQUE` | no two rows can share this value |
| `DEFAULT` | a value used when none is given |
| `CHECK` | a condition that must hold |
| `FOREIGN KEY` | must match a row in another table |

## Foreign keys

```sql
CREATE TABLE enrolments (
  id INT PRIMARY KEY AUTO_INCREMENT,
  student_id INT NOT NULL,
  course VARCHAR(60) NOT NULL,
  FOREIGN KEY (student_id) REFERENCES students(id)
);
```

The database now refuses an enrolment for a student that does not exist.

## Changing a table

```sql
ALTER TABLE students ADD COLUMN phone VARCHAR(15);
ALTER TABLE students DROP COLUMN phone;
DROP TABLE enrolments;
```

## Indexes

An index makes searching a column fast, like the index at the back of a book:

```sql
CREATE INDEX idx_students_city ON students(city);
```

Add indexes on columns you search or join on often. Too many slow down inserts.

:::interview
**Interviewers often ask:** "Primary key versus unique key?" A table has one primary key, which cannot be null. It can have many unique keys, and in most databases they may allow a null.
:::
