---
title: Joins, grouping and query writing
summary: The queries interviewers ask you to write: joins, second highest, duplicates and window functions.
kind: qa
takeaways:
- Explain the four joins with a tiny example
- Memorise the patterns for second highest and duplicates
- A window function adds a rank or total without collapsing rows
---
Questions below use these tables: `employees(id, name, salary, dept_id, manager_id)` and `departments(id, name)`.

### Q [Medium] Explain INNER, LEFT, RIGHT and FULL joins.
**INNER:** only rows that match in both tables. **LEFT:** all rows from the left table, with `NULL` where there is no match. **RIGHT:** the same for the right table. **FULL:** all rows from both, matched where possible.

### Q [Medium] Find the second highest salary.
```sql
SELECT MAX(salary)
FROM employees
WHERE salary < (SELECT MAX(salary) FROM employees);
```

Or `SELECT DISTINCT salary FROM employees ORDER BY salary DESC LIMIT 1 OFFSET 1;`

### Q [Medium] Find duplicate email addresses.
```sql
SELECT email, COUNT(*) AS times
FROM users
GROUP BY email
HAVING COUNT(*) > 1;
```

### Q [Medium] Find employees who earn more than their manager.
Join the table to itself:

```sql
SELECT e.name
FROM employees e
JOIN employees m ON e.manager_id = m.id
WHERE e.salary > m.salary;
```

### Q [Medium] Which departments have more than 5 employees?
```sql
SELECT d.name, COUNT(*) AS staff
FROM departments d
JOIN employees e ON e.dept_id = d.id
GROUP BY d.name
HAVING COUNT(*) > 5;
```

### Q [Easy] What is the difference between COUNT(*) and COUNT(column)?
`COUNT(*)` counts every row. `COUNT(column)` counts only rows where that column is **not NULL**.

### Q [Medium] How do you find departments with no employees?
```sql
SELECT d.name
FROM departments d
LEFT JOIN employees e ON e.dept_id = d.id
WHERE e.id IS NULL;
```

### Q [Hard] How do you delete duplicate rows but keep one?
```sql
DELETE u1
FROM users u1
JOIN users u2 ON u1.email = u2.email AND u1.id > u2.id;
```

This keeps the row with the smallest `id` for each email. (The syntax shown is MySQL's.)

### Q [Hard] What is a window function?
A function that works over a set of rows **without collapsing them** into one, unlike `GROUP BY`.

```sql
SELECT name, salary,
       RANK() OVER (ORDER BY salary DESC) AS salary_rank
FROM employees;
```

`ROW_NUMBER()`, `RANK()` and `DENSE_RANK()` number the rows; they differ in how they treat ties.

:::interview
**Tip:** when asked to write a query, say your plan first ("I will join the tables on the department id, group by department, then filter with HAVING"). It shows how you think, even if you slip on the syntax.
:::

:::practice mock-interview
Practise writing and explaining queries in a Mock Interview.
:::
