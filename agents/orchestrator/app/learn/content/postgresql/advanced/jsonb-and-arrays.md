---
title: JSONB and arrays
summary: Store flexible data inside a relational table with JSONB and arrays, and query and index it.
takeaways:
- JSONB stores JSON in a fast, indexable binary form
- Use -> and ->> to read values and @> to test containment
- Use JSONB for flexible extras, but keep core fields as normal columns
---
## JSONB columns

Postgres lets one column hold a JSON document. Use **JSONB** (binary, indexable), not plain JSON.

```sql
CREATE TABLE products (
    id    SERIAL PRIMARY KEY,
    name  TEXT NOT NULL,
    attrs JSONB NOT NULL DEFAULT '{}'
);

INSERT INTO products (name, attrs) VALUES
 ('Phone',  '{"brand": "Acme", "ram": 8, "tags": ["5g", "dual-sim"]}'),
 ('Laptop', '{"brand": "Zen",  "ram": 16, "tags": ["gaming"]}');
```

## Reading and filtering

| Operator | Meaning |
| --- | --- |
| `attrs -> 'brand'` | value as JSON |
| `attrs ->> 'brand'` | value as **text** |
| `attrs @> '{"brand":"Acme"}'` | contains this JSON |
| `attrs ? 'ram'` | key exists |

```sql
SELECT name, attrs ->> 'brand' AS brand
FROM products
WHERE (attrs ->> 'ram')::int >= 16;
```

```output
  name  | brand
--------+-------
 Laptop | Zen
(1 row)
```

## Update inside JSON

```sql
UPDATE products
SET attrs = jsonb_set(attrs, '{ram}', '12')
WHERE name = 'Phone';
```

## Index it

```sql
CREATE INDEX idx_products_attrs ON products USING GIN (attrs);
```

A **GIN index** makes `@>` and `?` fast on large tables.

## Arrays

```sql
ALTER TABLE students ADD COLUMN skills TEXT[];
UPDATE students SET skills = ARRAY['python', 'sql'] WHERE name = 'Asha';
SELECT name FROM students WHERE 'sql' = ANY (skills);
```

## When to use which

- Data with a **stable shape** that you filter and join on: normal columns.
- **Flexible or rarely used attributes**: JSONB.
- A real many-to-many relationship (students and courses): a **separate table**, not an array.

:::tip
JSONB gives you some of MongoDB's flexibility inside Postgres. Keep important fields as real columns so you keep types, constraints and joins.
:::
