---
title: SQL query practice with real output
summary: Seven classic query questions on one table, with the query and its real result.
kind: qa
takeaways:
- Practise the patterns: second highest, top per group, self join, duplicates, ranking
- Explain the plan before you write
- Check ties and NULLs
---
Practice with this table, `employees(id, name, dept, salary, manager_id)`:

| id | name | dept | salary | manager_id |
| --- | --- | --- | --- | --- |
| 1 | Asha | IT | 70000 | NULL |
| 2 | Ravi | IT | 50000 | 1 |
| 3 | Meena | HR | 45000 | 1 |
| 4 | Kiran | HR | 45000 | 3 |
| 5 | Lata | Sales | 60000 | 1 |
| 6 | Nisha | Sales | 80000 | 5 |
| 7 | Arun | IT | 50000 | 1 |

Each query below was run on this data and the output is the real result.

### Q [Medium] Second highest salary
```sql
SELECT MAX(salary) AS second_highest
FROM employees
WHERE salary < (SELECT MAX(salary) FROM employees);
```

```output
second_highest
70000
```

### Q [Medium] Average salary by department, highest first
```sql
SELECT dept, ROUND(AVG(salary), 2) AS avg_salary
FROM employees
GROUP BY dept
ORDER BY avg_salary DESC;
```

```output
dept | avg_salary
Sales | 70000.00
IT | 56666.67
HR | 45000.00
```

### Q [Medium] Employees who earn more than their manager
```sql
SELECT e.name, e.salary, m.name AS manager, m.salary AS manager_salary
FROM employees e
JOIN employees m ON e.manager_id = m.id
WHERE e.salary > m.salary;
```

```output
name | salary | manager | manager_salary
Nisha | 80000 | Lata | 60000
```

### Q [Medium] Salaries that appear more than once
```sql
SELECT salary, COUNT(*) AS people
FROM employees
GROUP BY salary
HAVING COUNT(*) > 1
ORDER BY salary;
```

```output
salary | people
45000 | 2
50000 | 2
```

### Q [Medium] Highest paid employee in each department
```sql
SELECT dept, name, salary
FROM (
    SELECT dept, name, salary,
           ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC, id) AS rn
    FROM employees
) ranked
WHERE rn = 1
ORDER BY dept;
```

```output
dept | name | salary
HR | Meena | 45000
IT | Asha | 70000
Sales | Nisha | 80000
```

### Q [Medium] Rank salaries without gaps (DENSE_RANK)
```sql
SELECT name, salary,
       DENSE_RANK() OVER (ORDER BY salary DESC) AS salary_rank
FROM employees
ORDER BY salary_rank, name;
```

```output
name | salary | salary_rank
Nisha | 80000 | 1
Asha | 70000 | 2
Lata | 60000 | 3
Arun | 50000 | 4
Ravi | 50000 | 4
Kiran | 45000 | 5
Meena | 45000 | 5
```

### Q [Medium] Employees with no one reporting to them
```sql
SELECT name
FROM employees e
WHERE NOT EXISTS (SELECT 1 FROM employees x WHERE x.manager_id = e.id)
ORDER BY name;
```

```output
name
Arun
Kiran
Nisha
Ravi
```


Notes: the second query uses `ROUND` for readable averages; ties in the "highest paid" query are broken by `id` so the result is predictable.

:::tip
In an interview, say your plan first ("group by department, then take the maximum") and then write the query. Check edge cases: ties, NULLs and empty groups.
:::
