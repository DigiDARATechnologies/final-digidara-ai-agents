---
title: Pipelines and saving a model
summary: Chain preparation and model into one Pipeline, avoid leakage, and save the trained model with joblib.
takeaways:
- A Pipeline runs scaling and the model as one object
- A pipeline fitted on training data cannot leak test data
- joblib saves a trained model so you can reload it later
---
## Why pipelines

Real models have several steps: fill gaps, encode, scale, predict. Doing them by hand invites mistakes (such as scaling before splitting). A **Pipeline** chains the steps into one object that you `fit` and `predict` like a normal model.

```python
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

df = pd.DataFrame({
    "age": [25, 32, None, 41, 29, 52, 38, 45, 23, 36, 48, 30],
    "salary": [30000, 52000, 41000, None, 38000, 90000, 61000, 75000, 28000, 58000, 80000, 45000],
    "city": ["Chennai", "Madurai", "Chennai", "Salem", "Madurai", "Chennai", "Salem", "Chennai", "Madurai", "Salem", "Chennai", "Madurai"],
    "bought": [0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 0],
})
X, y = df.drop(columns="bought"), df["bought"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=2, stratify=y)

numbers = Pipeline([("fill", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
prepare = ColumnTransformer([
    ("numbers", numbers, ["age", "salary"]),
    ("category", OneHotEncoder(handle_unknown="ignore"), ["city"]),
])

model = Pipeline([("prepare", prepare), ("forest", RandomForestClassifier(n_estimators=100, random_state=2))])
model.fit(X_train, y_train)
print("test accuracy:", round(model.score(X_test, y_test), 3))
```

```output
test accuracy: 1.0
```

Here a `ColumnTransformer` applies one set of steps to the number columns and another to the text column, then the forest learns from the result.

## Predicting with raw data

The pipeline accepts **raw** rows. It does the filling, encoding and scaling for you, using only what it learned from the training data:

```python
new_customers = pd.DataFrame({"age": [34, None], "salary": [55000, 33000], "city": ["Chennai", "Trichy"]})
print(model.predict(new_customers))
```

```output
[1 0]
```

The second customer lives in "Trichy", a city never seen in training. `handle_unknown="ignore"` keeps the model from failing.

## Saving a model

Training can take minutes or hours, so save the result and reload it in your app. `joblib` does this:

```python
import io
import joblib

buffer = io.BytesIO()                 # a real program would use a file name: "model.joblib"
joblib.dump(model, buffer)
buffer.seek(0)

loaded = joblib.load(buffer)
print(loaded.predict(new_customers))
print("size in bytes > 0:", buffer.getbuffer().nbytes > 0)
```

```output
[1 0]
size in bytes > 0: True
```

With a file it looks like this:

```py
joblib.dump(model, "model.joblib")     # save once, after training
model = joblib.load("model.joblib")    # load in your web app
```

:::warning
Only load model files you made yourself or fully trust. A joblib or pickle file can run code when it is loaded.
:::

## From model to product

| Step | Tool |
| --- | --- |
| Train and save | scikit-learn, joblib |
| Serve predictions | a Flask or FastAPI endpoint that loads the model |
| Keep the same versions | note your library versions (`pip freeze`) |
| Watch it over time | compare new data with training data; retrain when it drifts |

:::interview
**Interviewers often ask:** "Why use a pipeline?" It keeps preparation and the model together, makes the work repeatable, prevents data leakage (steps are fitted on training data only), and lets you tune and save everything as one object.
:::
