---
title: Project: Fraud and anomaly detection
summary: Find suspicious transactions among thousands of normal ones, compare an unsupervised detector with a supervised model, and judge them by the alerts a team can review.
takeaways:
- Fraud is rare, so accuracy is useless and precision and recall matter
- Isolation Forest finds unusual transactions without labels; a supervised model does better when you have labels
- Judge a detector by how many real frauds are in the top alerts a team can review
---
## The problem

Out of every 100 transactions, perhaps one is fraud. The bank wants a short **list of alerts** that analysts can review each day. The challenge: fraud is rare, changing, and often **unlabelled**.

## The data

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(8)
n = 5000
amount = np.exp(rng.normal(6.0, 0.8, n)).round(0)                    # typical spend, mostly small
hour = np.clip(rng.normal(14, 4, n), 0, 23).round(0)
distance_from_home = np.abs(rng.normal(8, 6, n)).round(1)
transactions_last_hour = rng.poisson(0.4, n)
is_fraud = np.zeros(n, dtype=int)

fraud_ids = rng.choice(n, 60, replace=False)                        # 1.2% fraud
amount[fraud_ids] = np.exp(rng.normal(8.0, 0.7, 60)).round(0)
hour[fraud_ids] = rng.choice([1, 2, 3, 4, 23], 60)
distance_from_home[fraud_ids] = np.abs(rng.normal(120, 60, 60)).round(1)
transactions_last_hour[fraud_ids] = rng.poisson(3, 60)
is_fraud[fraud_ids] = 1

tx = pd.DataFrame({"amount": amount, "hour": hour, "distance_from_home": distance_from_home, "transactions_last_hour": transactions_last_hour, "fraud": is_fraud})
print(tx.shape, "| fraud rate:", round(tx["fraud"].mean(), 4))
print(tx.groupby("fraud").mean().round(1).to_string())
```

```output
(5000, 5) | fraud rate: 0.012
       amount  hour  distance_from_home  transactions_last_hour
fraud
0       558.1  13.9                 8.6                     0.4
1      3749.3   5.4               120.3                     3.2
```

Fraudulent transactions are bigger, at odd hours, far from home and in quick succession, so they should look different from normal ones.

## The accuracy trap

```python
print("accuracy of a detector that never flags anything:", round(1 - tx["fraud"].mean(), 3))
```

```output
accuracy of a detector that never flags anything: 0.988
```

A model that **never** raises an alert is about 99% accurate and completely useless. We need better questions: **of the alerts, how many are real (precision)? of all frauds, how many did we catch (recall)?**

## Approach 1: Isolation Forest (no labels needed)

```python
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

features = ["amount", "hour", "distance_from_home", "transactions_last_hour"]
scaled = StandardScaler().fit_transform(np.log1p(tx[features].clip(lower=0)))

forest = IsolationForest(n_estimators=300, contamination=0.012, random_state=0).fit(scaled)
tx["anomaly_score"] = -forest.score_samples(scaled)               # higher means more unusual

alerts = 60                                                       # a team can review 60 transactions
top = tx.sort_values("anomaly_score", ascending=False).head(alerts)
print(f"reviewed the {alerts} most unusual transactions:")
print("  real frauds among them:", int(top["fraud"].sum()), f"(precision {top['fraud'].mean():.0%})")
print("  share of all fraud caught (recall):", f"{top['fraud'].sum() / tx['fraud'].sum():.0%}")
```

```output
reviewed the 60 most unusual transactions:
  real frauds among them: 58 (precision 97%)
  share of all fraud caught (recall): 97%
```

Without a single label, reviewing just the top 60 alerts finds most of the fraud. A random review of 60 transactions would find less than one fraud on average (60 × 1.2%).

## Approach 2: a supervised model (when you have labels)

If past cases were labelled by investigators, a supervised model can learn the exact pattern of fraud:

```python
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score

X_train, X_test, y_train, y_test = train_test_split(tx[features], tx["fraud"], test_size=0.3, random_state=0, stratify=tx["fraud"])
supervised = HistGradientBoostingClassifier(class_weight="balanced", random_state=0).fit(X_train, y_train)
scores = supervised.predict_proba(X_test)[:, 1]

alerts_test = 18
order = np.argsort(scores)[::-1][:alerts_test]
print(f"among the top {alerts_test} alerts on unseen data:")
print("  real frauds:", int(y_test.to_numpy()[order].sum()), "of", alerts_test)
print("  share of all fraud in the test set caught:", f"{y_test.to_numpy()[order].sum() / y_test.sum():.0%}")
print("  average precision (PR-AUC):", round(average_precision_score(y_test, scores), 2))
```

```output
among the top 18 alerts on unseen data:
  real frauds: 16 of 18
  share of all fraud in the test set caught: 89%
  average precision (PR-AUC): 0.94
```

Both approaches work well here because the planted fraud is very different from normal behaviour (real fraud is much subtler). Do not read the two numbers as a contest: the first was measured on all the data, the second on an unseen test set. On real data, a supervised model usually becomes the stronger one once you have enough labels, because it learns your actual fraud patterns. But fraud labels are often **late and incomplete** (a fraud is confirmed weeks later), so many teams use **both**: a supervised model for known patterns plus an anomaly detector for new kinds.

## Run it like a real system

| Piece | Practice |
| --- | --- |
| **score every transaction** | the model gives a risk score, not a verdict |
| **decide by cost** | block above a high score, send medium scores for review, allow the rest |
| **limit alerts to what a team can review** | an overwhelmed team ignores alerts |
| **feedback loop** | analysts mark each alert real or false; retrain with the new labels |
| **monitor drift** | fraudsters change tactics, so performance decays |
| **explain the alert** | "amount 12 times the usual, 3 transactions in 10 minutes" |

## Cautions

:::warning
A fraud score is a **suspicion**, not proof. Blocking a genuine customer's card at a wedding or while travelling is costly and upsetting, so use friendly checks (an OTP, a call) before declining, check for unfair patterns across customer groups, and keep a person responsible for final decisions.
:::

:::practice capstone-project
Pick one of the four ML projects, share your plan with the Capstone Project agent, and ask it to challenge your metric and your threshold.
:::
