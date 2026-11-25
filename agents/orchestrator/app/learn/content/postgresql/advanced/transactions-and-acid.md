---
title: Transactions and ACID
summary: Group several changes into one all-or-nothing unit, and understand ACID, isolation and locks.
takeaways:
- A transaction makes many statements succeed or fail together
- ACID: Atomicity, Consistency, Isolation, Durability
- Higher isolation prevents anomalies but can cause more waiting or retries
---
## The bank transfer problem

Moving 500 rupees from Asha to Ravi takes two updates. If the server fails between them, money disappears. A **transaction** groups them.

```sql
BEGIN;
UPDATE accounts SET balance = balance - 500 WHERE owner = 'Asha';
UPDATE accounts SET balance = balance + 500 WHERE owner = 'Ravi';
COMMIT;
```

If something goes wrong, run `ROLLBACK;` and **neither** change is kept. Postgres also rolls back automatically if the connection drops.

## ACID

| Letter | Promise |
| --- | --- |
| **A**tomicity | all statements happen, or none |
| **C**onsistency | constraints stay true after the transaction |
| **I**solation | concurrent transactions do not see each other's half-done work |
| **D**urability | once committed, it survives a crash |

## Isolation levels

When two users work at once, strange things can happen. Isolation levels choose how strict Postgres is:

| Level | Behaviour |
| --- | --- |
| **Read Committed** (default) | each statement sees only committed data |
| **Repeatable Read** | the transaction sees one consistent snapshot |
| **Serializable** | acts as if transactions ran one after another; may ask you to retry |

Postgres uses **MVCC** (multi-version concurrency control): readers do not block writers and writers do not block readers, because each sees its own version of the rows.

## Locks

To stop two people changing the same row, lock it when you read it:

```sql
BEGIN;
SELECT balance FROM accounts WHERE owner = 'Asha' FOR UPDATE;
-- other transactions wanting this row now wait
UPDATE accounts SET balance = balance - 500 WHERE owner = 'Asha';
COMMIT;
```

**Deadlock**: A waits for B while B waits for A. Postgres detects it and cancels one. Reduce the risk by always updating rows in the **same order** and keeping transactions short.

:::remember
Keep transactions short. Long ones hold locks and slow everyone down.
:::
