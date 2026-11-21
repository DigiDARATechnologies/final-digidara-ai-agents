---
title: Project: Loan approval prediction (classification)
summary: Predict whether a loan should be approved, choose the right metric and threshold, and check the model for unfair differences between groups.
takeaways:
- Classification projects need the right metric: precision, recall and AUC, not only accuracy
- The decision threshold is a business choice about which mistake costs more
- Always check results by group, and keep a human in the loop for decisions about people
---
## The problem

A small finance company wants help deciding which loan applications to approve. The target is **approved or not**, so this is **classification**. This kind of model affects real people, so responsibility is part of the project.

## The data

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(5)
n = 1500
income = rng.lognormal(10.4, 0.45, n).round(-2)                         # monthly income, rupees
credit_score = np.clip(rng.normal(680, 70, n), 300, 850).round(0)
loan_amount = np.clip(income * rng.uniform(3, 20, n), 50000, 3000000).round(-3)
years_employed = np.clip(rng.normal(6, 4, n), 0, 30).round(1)
existing_loans = rng.integers(0, 5, n)
group = rng.choice(["A", "B"], n, p=[0.6, 0.4])                          # a group label kept only for checking fairness

burden = loan_amount / (income * 12)
raw = (0.012 * (credit_score - 680) + 0.00002 * (income - 35000) - 1.5 * (burden - 0.6) + 0.06 * (years_employed - 6) - 0.35 * (existing_loans - 2))
logit = 0.8 + 1.6 * raw
approved = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

loans = pd.DataFrame({"income": income, "credit_score": credit_score, "loan_amount": loan_amount, "years_employed": years_employed,
                      "existing_loans": existing_loans, "group": group, "approved": approved})
print(loans.shape)
print("approval rate:", round(loans["approved"].mean(), 3))
print(loans.groupby("approved")[["income", "credit_score", "existing_loans"]].mean().round(1).to_string())
```

```output
(1500, 7)
approval rate: 0.498
           income  credit_score  existing_loans
approved
0         33321.2         651.3             2.4
1         39639.8         712.4             1.7
```

Approved applicants have a higher income and credit score, and fewer existing loans, as we would expect. The `group` column is **not** used to make the decision. We keep it aside only to **audit** the model.

## Train and compare

```python
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

features = ["income", "credit_score", "loan_amount", "years_employed", "existing_loans"]
X_train, X_test, y_train, y_test, g_train, g_test = train_test_split(loans[features], loans["approved"], loans["group"], test_size=0.3, random_state=0, stratify=loans["approved"])

models = {
    "logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
    "gradient boosting": HistGradientBoostingClassifier(random_state=0),
}
print(f"{'model':<22}{'accuracy':>10}{'precision':>11}{'recall':>8}{'AUC':>7}")
for name, model in models.items():
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    print(f"{name:<22}{accuracy_score(y_test, pred):>10.2f}{precision_score(y_test, pred):>11.2f}{recall_score(y_test, pred):>8.2f}{roc_auc_score(y_test, proba):>7.2f}")
print("baseline accuracy (always the majority class):", round(max(y_test.mean(), 1 - y_test.mean()), 2))
```

```output
model                   accuracy  precision  recall    AUC
logistic regression         0.77       0.79    0.74   0.86
gradient boosting           0.75       0.75    0.74   0.83
baseline accuracy (always the majority class): 0.5
```

| Metric | In this project |
| --- | --- |
| **precision** | of the loans we approve, how many are good applicants |
| **recall** | of the good applicants, how many we approve |
| **AUC** | how well the model ranks good above bad, across every threshold |

Logistic regression is as good as the boosting model and far easier to explain to a customer or a regulator.

## Choose the threshold from the cost of mistakes

The model gives a probability. Approving a loan that defaults loses money; rejecting a good applicant loses a customer. Suppose a wrong approval costs 5 times as much as a wrong rejection:

```python
logistic = models["logistic regression"]
proba = logistic.predict_proba(X_test)[:, 1]

print("approve above   approved   wrong approvals   wrong rejections   total cost")
for threshold in (0.4, 0.5, 0.6, 0.7, 0.8):
    approve = proba >= threshold
    wrong_approvals = int((approve & (y_test == 0)).sum())
    wrong_rejections = int((~approve & (y_test == 1)).sum())
    cost = 5 * wrong_approvals + 1 * wrong_rejections
    print(f"{threshold:>13}   {int(approve.sum()):>8}   {wrong_approvals:>15}   {wrong_rejections:>16}   {cost:>10}")
```

```output
approve above   approved   wrong approvals   wrong rejections   total cost
          0.4        247                61                 38          343
          0.5        210                44                 58          278
          0.6        173                27                 78          213
          0.7        137                17                104          189
          0.8        102                 9                131          176
```

The cheapest threshold is **not** 0.5. With these costs, a stricter cut-off saves money: the total cost falls from 278 at 0.5 to 176 at 0.8. But look at what it means: at 0.8 the company approves only 102 of 450 applicants and turns away 131 good ones. Cost is only one side; growth and customer goodwill matter too. The threshold is a **business decision**, written down and reviewed.

## Check for unfair differences between groups

A model can be accurate overall and still treat groups differently. Compare approval rates and error rates:

```python
approve = proba >= 0.5
audit = pd.DataFrame({"group": g_test.to_numpy(), "actual": y_test.to_numpy(), "approved_by_model": approve.astype(int)})

summary = audit.groupby("group").apply(lambda d: pd.Series({
    "applicants": len(d),
    "real approval rate": d["actual"].mean(),
    "model approval rate": d["approved_by_model"].mean(),
    "good applicants rejected (rate)": ((d["approved_by_model"] == 0) & (d["actual"] == 1)).sum() / max((d["actual"] == 1).sum(), 1),
}), include_groups=False).round(2)
print(summary.to_string())
```

```output
       applicants  real approval rate  model approval rate  good applicants rejected (rate)
group
A           277.0                0.51                 0.45                             0.26
B           173.0                0.49                 0.49                             0.25
```

Compare the two rows. The groups are close: the model wrongly rejects about 26% of good applicants in group A and 25% in group B. The approval rates differ by four points (45% against 49%), which is small but still worth a question. The group did not affect how we generated this data, so a small gap is expected. **With real data this check often shows large gaps**, because past decisions and income gaps carry history into the data. If the rates differ a lot, find out why, and do not launch the model until you understand and can defend it.

## Responsible use

| Rule | Why |
| --- | --- |
| never use a protected attribute (religion, caste, gender) as a feature | it is unfair, and often illegal |
| beware of **proxies** (pin code, surname, school) that stand in for those attributes | the model can learn them indirectly |
| explain each decision (top factors) and allow appeals | people deserve a reason |
| keep a **human reviewer** for borderline and high-value cases | the model supports, a person decides |
| monitor approval rates and defaults over time | drift and unfair patterns can appear later |
| follow the law (for example RBI guidelines on digital lending) | compliance |

:::warning
Never launch an automated approve-or-reject system that affects people's money, jobs or health without fairness checks, explanations, human oversight and legal review. A good score on a practice dataset does not make a model safe to use.
:::
