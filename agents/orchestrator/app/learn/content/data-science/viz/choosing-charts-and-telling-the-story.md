---
title: Choosing charts and telling the story
summary: Pick the right chart for each question, make charts honest and clear, and turn analysis into a story people act on.
takeaways:
- Choose the chart by the question you are answering
- Keep charts simple, labelled and honest
- A result nobody understands has no value: lead with the finding
---
## One chart per question

Install Matplotlib (`pip install matplotlib`) to draw charts. First decide **what question** the chart should answer:

| Question | Chart | Matplotlib or Pandas |
| --- | --- | --- |
| Compare a few groups | **bar chart** | `plt.bar` or `df.plot.bar()` |
| How does something change over time? | **line chart** | `plt.plot` |
| How are values spread? | **histogram** | `plt.hist` |
| Are there outliers? Compare spread | **box plot** | `plt.boxplot` |
| Do two numbers move together? | **scatter plot** | `plt.scatter` |
| Share of a whole (a few parts) | **pie** or stacked bar | `plt.pie` |

```py
import matplotlib.pyplot as plt
import pandas as pd

df = pd.DataFrame({"dept": ["CSE", "ECE", "IT"], "avg_marks": [88, 75, 80]})

plt.bar(df["dept"], df["avg_marks"], color="#4f46e5")
plt.title("Average marks by department")
plt.ylabel("Marks")
plt.ylim(0, 100)            # honest axis: start at zero for bars
plt.tight_layout()
plt.show()
```

```py
# Spread and relationships
plt.hist(df_marks, bins=10, edgecolor="white")
plt.scatter(df["hours"], df["marks"])
plt.boxplot([group_a, group_b], labels=["A", "B"])
```

## Rules for honest, clear charts

| Do | Avoid |
| --- | --- |
| give a title that states the **finding** ("CSE scores highest") | titles like "Chart 1" |
| label both axes with units | unlabelled axes |
| start bar charts at **zero** | a cut axis that exaggerates small differences |
| use one or two colours with a purpose | rainbow colours with no meaning |
| keep it simple: one message per chart | 3D effects, too many series |
| sort bars by value | random order |

:::warning
A bar chart that starts at 70 instead of 0 can make a 3-mark difference look huge. Misleading charts are a common way to fool an audience, even by accident.
:::

## Telling the story

A data result is only useful if someone **acts** on it. Structure your message like this:

1. **The question:** what were we trying to find out?
2. **The answer first:** one sentence. "Students who attend more than 80% of classes score 15 marks higher on average."
3. **The evidence:** one or two clear charts.
4. **The caveats:** what the data cannot tell us (sample size, correlation, not cause).
5. **The recommendation:** what should be done next.

| Weak | Strong |
| --- | --- |
| "Here is the correlation matrix." | "Attendance is the strongest predictor of marks, so start with attendance support." |
| "p = 0.03" | "The new method raised marks by about 6 points, and it is unlikely to be luck." |

## Know your audience

A manager wants the decision and the risk. An engineer wants the method. A customer wants what changes for them. Prepare the one-sentence answer **for each**, then add detail only for those who ask.

:::tip
Before you share anything, ask a colleague to look at your chart for ten seconds and tell you what it says. If they get it wrong, the chart needs work, not the colleague.
:::

:::practice mock-interview
Practise explaining a result in one sentence, then in two minutes, in a Mock Interview.
:::
