---
title: Text and dates
summary: Clean text with the str methods, change types with astype, and work with dates using to_datetime and dt.
takeaways:
- The .str accessor applies string methods to a whole column
- astype changes a column's type; pd.to_numeric handles bad values
- to_datetime makes real dates, and .dt reads their parts
---
## Cleaning text

Text from forms and files is often messy: extra spaces, mixed capitals. The `.str` accessor applies a string method to every value in a column.

```python
import pandas as pd

df = pd.DataFrame({"name": ["  asha K ", "RAVI", "meena s"], "email": ["asha@x.com", "RAVI@Y.COM", "meena@x.com"]})
df["name"] = df["name"].str.strip().str.title()
df["email"] = df["email"].str.lower()
df["domain"] = df["email"].str.split("@").str[1]
print(df)
```

```output
      name        email domain
0   Asha K   asha@x.com  x.com
1     Ravi   ravi@y.com  y.com
2  Meena S  meena@x.com  x.com
```

| Method | What it does |
| --- | --- |
| `str.strip()` | removes spaces at both ends |
| `str.lower()`, `str.upper()`, `str.title()` | changes capitals |
| `str.replace("a", "b")` | replaces text |
| `str.contains("abc")` | True where the text contains it |
| `str.split(",")` | splits into pieces |
| `str.len()` | the length of each text |

## Changing types

A column of numbers can arrive as text, and then you cannot calculate with it.

```python
raw = pd.DataFrame({"marks": ["92", "78", "85"]})
print(raw["marks"].dtype)
raw["marks"] = raw["marks"].astype(int)
print(raw["marks"].dtype, raw["marks"].sum())
```

```output
object
int32 255
```

If some values are not numbers, `astype` fails. Use `to_numeric` and turn the bad values into NaN:

```python
messy = pd.Series(["10", "20", "n/a", "40"])
print(pd.to_numeric(messy, errors="coerce"))
```

```output
0    10.0
1    20.0
2     NaN
3    40.0
dtype: float64
```

## Dates

```python
orders = pd.DataFrame({"when": ["2026-01-15", "2026-02-03", "2026-02-20"], "amount": [500, 300, 450]})
orders["when"] = pd.to_datetime(orders["when"])
print(orders.dtypes)
```

```output
when      datetime64[ns]
amount             int64
dtype: object
```

Once a column is a real date, the `.dt` accessor reads its parts:

```python
orders["month"] = orders["when"].dt.month
orders["day"] = orders["when"].dt.day_name()
print(orders)
print(orders["when"].max() - orders["when"].min())
```

```output
        when  amount  month       day
0 2026-01-15     500      1  Thursday
1 2026-02-03     300      2   Tuesday
2 2026-02-20     450      2    Friday
36 days 00:00:00
```

:::tip
When a column holds dates, convert it with `to_datetime` as soon as you load the file (or use `parse_dates` in `read_csv`). Dates stored as text sort and compare wrongly.
:::
