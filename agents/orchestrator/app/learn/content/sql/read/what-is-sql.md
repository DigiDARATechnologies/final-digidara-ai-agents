---
title: What is SQL?
summary: Databases store data in tables, and SQL is the language you use to ask them questions.
takeaways:
- A relational database stores data in tables of rows and columns
- SQL reads and changes that data with short commands
- The sample table in this course is called students
---
## Data that outlives your program

When an app saves your account, your orders or your marks, it puts them in a **database**. The most common kind is a **relational database**: data kept in **tables**, like spreadsheets that can be linked together. MySQL, PostgreSQL, SQL Server and SQLite are all relational databases.

**SQL** (Structured Query Language) is how you talk to them. It is almost the same in every one.

## Tables, rows and columns

Here is a table named `students`:

| id | name | city | marks |
| --- | --- | --- | --- |
| 1 | Asha | Chennai | 92 |
| 2 | Ravi | Madurai | 78 |
| 3 | Meena | Chennai | 85 |
| 4 | Kiran | Coimbatore | 66 |

- Each **column** is one kind of information (`name`).
- Each **row** is one record (one student).
- The `id` column identifies the row. It is the table's **primary key**.

## Your first query

```sql
SELECT name, marks FROM students;
```

| name | marks |
| --- | --- |
| Asha | 92 |
| Ravi | 78 |
| Meena | 85 |
| Kiran | 66 |

`SELECT` says which columns you want and `FROM` says which table.

## All columns

```sql
SELECT * FROM students;
```

`*` means every column. Fine for exploring; in real code ask only for what you need.

## The main families of SQL

| Family | Commands | Purpose |
| --- | --- | --- |
| Reading | `SELECT` | get data |
| Changing | `INSERT`, `UPDATE`, `DELETE` | add, edit and remove rows |
| Designing | `CREATE`, `ALTER`, `DROP` | make and change tables |

:::note
SQL keywords are not case sensitive, but writing them in capitals (`SELECT`, `FROM`) makes queries easier to read. End each statement with a semicolon.
:::
