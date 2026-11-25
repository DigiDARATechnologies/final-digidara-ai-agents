---
title: Security, backup and Python
summary: Create roles and permissions, back up and restore a database, and connect from Python safely.
takeaways:
- Give each application its own role with only the permissions it needs
- pg_dump and pg_restore back up and restore a database
- Use parameterised queries from Python, never string formatting
---
## Roles and permissions

In Postgres, users and groups are **roles**.

```sql
CREATE ROLE app_user LOGIN PASSWORD 'use-a-strong-secret';
GRANT CONNECT ON DATABASE college TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE ON students TO app_user;
```

Give your application **only what it needs** (least privilege). It should not be a superuser. Never commit the password to Git; read it from an environment variable.

## Backup and restore

```bash
# back up one database to a file
pg_dump -U postgres -Fc college > college.dump

# restore into a new database
createdb -U postgres college_copy
pg_restore -U postgres -d college_copy college.dump
```

Back up on a **schedule**, store copies **away from the server**, and **test a restore** sometimes. A backup you have never restored is only a hope. Managed services (RDS, Supabase, Neon) offer automatic backups and point-in-time recovery.

## Connecting from Python

```python
import os
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])

with conn:                       # commits on success, rolls back on error
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name, marks FROM students WHERE marks >= %s ORDER BY marks DESC",
            (70,),
        )
        for name, marks in cur.fetchall():
            print(name, marks)
conn.close()
```

The `%s` placeholder with a tuple of values is the **safe** way. Never build SQL with f-strings or `+`: that allows **SQL injection**, where a user types SQL as their input.

```python
# DANGEROUS: do not do this
cur.execute(f"SELECT * FROM students WHERE name = '{user_input}'")
```

In real apps you will use an ORM such as SQLAlchemy or Django, which also use parameters for you.

## Connection pooling

Opening a database connection is slow. Web apps keep a **pool** of connections and reuse them (SQLAlchemy does this; PgBouncer is a pooling server).

:::warning
Never expose the database port to the whole internet. Allow connections only from your application servers.
:::
