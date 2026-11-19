---
title: Plotting and saving results
summary: Make quick charts straight from a DataFrame, and save the cleaned data back to a file.
takeaways:
- df.plot and Series.plot draw charts with Matplotlib behind the scenes
- Pick the chart by the question: bar to compare, line over time, hist for spread
- to_csv saves a result; use index=False to leave out the row numbers
---
## Quick charts

Pandas can draw a chart directly from a DataFrame. It uses **Matplotlib** (`pip install matplotlib`), so install that first.

```py
import pandas as pd
import matplotlib.pyplot as plt

df = pd.DataFrame({
    "name": ["Asha", "Ravi", "Meena", "Kiran", "Divya", "Arun"],
    "dept": ["CSE", "ECE", "CSE", "IT", "CSE", "ECE"],
    "marks": [92, 78, 85, 66, 88, 71],
})

df.groupby("dept")["marks"].mean().plot(kind="bar", title="Average marks by department")
plt.ylabel("Marks")
plt.show()
```

## Which chart for which question

| Question | Chart | Code |
| --- | --- | --- |
| Compare groups | bar | `plot(kind="bar")` |
| How does it change over time? | line | `plot(kind="line")` |
| How are the values spread? | histogram | `plot(kind="hist")` |
| Do two numbers move together? | scatter | `plot.scatter(x="a", y="b")` |
| Share of a whole (few parts) | pie | `plot(kind="pie")` |

```py
df["marks"].plot(kind="hist", bins=5)         # the spread of marks
df.plot.scatter(x="marks", y="attendance")    # two numbers together
```

:::tip
Always give a chart a title and label the axes. A chart without them makes the reader guess what they are looking at.
:::

## Saving your work

After cleaning, save the result so you do not repeat the work:

```python
import pandas as pd

df = pd.DataFrame({"name": ["Asha", "Ravi"], "marks": [92, 78]})
print(df.to_csv(index=False))
```

```output
name,marks
Asha,92
Ravi,78
```

With a real file name this writes the file:

```py
df.to_csv("clean_students.csv", index=False)
df.to_excel("clean_students.xlsx", index=False)   # needs: pip install openpyxl
df.to_json("clean_students.json", orient="records")
```

`index=False` leaves out the row numbers (0, 1, 2…), which you normally do not want in the file.

## A typical Pandas workflow

1. **Load:** `read_csv`
2. **Inspect:** `head`, `info`, `describe`
3. **Clean:** missing values, types, duplicates
4. **Transform:** new columns, filters
5. **Summarise:** `groupby`, `pivot_table`
6. **Show or save:** a chart, or `to_csv`

:::practice leetcode
Practise the Python behind this in Coding Practice, then come back and apply it to a real dataset.
:::
