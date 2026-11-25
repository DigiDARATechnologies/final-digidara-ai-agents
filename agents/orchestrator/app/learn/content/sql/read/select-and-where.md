---
title: SELECT, WHERE and filtering
summary: Pick columns, filter rows with WHERE, and combine conditions with AND, OR, IN, BETWEEN and LIKE.
takeaways:
- WHERE keeps only the rows that match a condition
- Combine conditions with AND, OR and NOT
- LIKE matches text patterns; % is any run of characters
---
## Filtering rows

```sql
SELECT name, marks
FROM students
WHERE marks >= 80;
```

| name | marks |
| --- | --- |
| Asha | 92 |
| Meena | 85 |

`WHERE` keeps only the rows where the condition is true.

## Comparison operators

| Operator | Meaning |
| --- | --- |
| `=` | equal (one equals sign in SQL) |
| `<>` or `!=` | not equal |
| `<` `>` `<=` `>=` | comparisons |

## Combining conditions

```sql
SELECT name FROM students
WHERE city = 'Chennai' AND marks > 90;
```

```sql
SELECT name FROM students
WHERE city = 'Madurai' OR city = 'Coimbatore';
```

Use brackets when mixing `AND` and `OR`, because `AND` is applied first.

## IN and BETWEEN

```sql
SELECT name FROM students WHERE city IN ('Madurai', 'Coimbatore');
SELECT name FROM students WHERE marks BETWEEN 70 AND 90;
```

`BETWEEN` includes both ends.

## Searching text with LIKE

```sql
SELECT name FROM students WHERE name LIKE 'A%';   -- starts with A
SELECT name FROM students WHERE name LIKE '%a';   -- ends with a
SELECT name FROM students WHERE name LIKE '%in%'; -- contains "in"
```

`%` stands for any number of characters, and `_` for exactly one.

## Missing values

```sql
SELECT name FROM students WHERE city IS NULL;
SELECT name FROM students WHERE city IS NOT NULL;
```

:::warning
`NULL` means "unknown". It is never equal to anything, not even to another `NULL`, so `city = NULL` finds nothing. Use `IS NULL`.
:::

:::interview
**Interviewers often ask:** "What is the difference between WHERE and HAVING?" `WHERE` filters rows before grouping. `HAVING` filters groups after `GROUP BY`. You will meet it in the next lesson.
:::
