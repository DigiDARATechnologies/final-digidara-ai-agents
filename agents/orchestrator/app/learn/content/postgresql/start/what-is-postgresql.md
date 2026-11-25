---
title: What is PostgreSQL?
summary: Meet PostgreSQL, the open-source relational database used by many companies, and run your first commands in psql.
takeaways:
- PostgreSQL stores data in tables with strict types and relationships
- It follows SQL standards and adds powerful extras such as JSONB and window functions
- psql is the command line tool to connect, create databases and run queries
---
## What it is

**PostgreSQL** (often "Postgres") is a free, open-source **relational database**. Data lives in **tables** (rows and columns), tables are linked with keys, and you talk to it with **SQL**. It is known for being reliable, correct and feature-rich, which is why startups and large companies both use it.

| Compared with | Postgres |
| --- | --- |
| SQLite | a real server for many users at once, far more features |
| MySQL | similar, but stricter and with more advanced features (JSONB, window functions, rich types) |
| MongoDB | tables with a fixed structure and strong guarantees, instead of flexible documents |

If you know basic SQL from the SQL course, everything you learned works here.

## Install and connect

Install from postgresql.org (or use Docker). Then open the terminal tool **psql**:

```bash
psql -U postgres
```

Useful psql commands (they start with a backslash and are not SQL):

| Command | Meaning |
| --- | --- |
| `\l` | list databases |
| `\c shop` | connect to the database `shop` |
| `\dt` | list tables |
| `\d students` | describe a table |
| `\q` | quit |

## Your first database

```sql
CREATE DATABASE college;
\c college

CREATE TABLE students (
    id    SERIAL PRIMARY KEY,
    name  TEXT NOT NULL,
    marks INTEGER
);

INSERT INTO students (name, marks) VALUES ('Asha', 82), ('Ravi', 67);

SELECT * FROM students;
```

```output
 id | name | marks
----+------+-------
  1 | Asha |    82
  2 | Ravi |    67
(2 rows)
```

`SERIAL` creates a number that counts up automatically, so you do not choose the `id` yourself.

## Server, database, schema, table

- A **server** can hold many **databases**.
- A database holds **schemas** (folders for tables; the default one is `public`).
- A schema holds **tables**, views, functions and more.

:::tip
End every SQL statement with a semicolon in psql. If the prompt changes to `-#`, psql is waiting for the rest of your statement.
:::
