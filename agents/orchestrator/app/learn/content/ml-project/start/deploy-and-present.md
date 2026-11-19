---
title: Deploy, present and know the limits
summary: Serve the model through a small API, test it, describe the project honestly with its limits, and present it on your resume and in interviews.
takeaways:
- A model is only useful when others can use it: wrap it in an API or a small app
- State the limits, fairness concerns and the right way to use the predictions
- Be ready to explain every choice: the metric, the baseline, the threshold
---
## Serve it with Flask

The model is saved. Now let people use it through a small web API. Load the model **once** when the app starts.

```python
import joblib
import pandas as pd
from flask import Flask, jsonify, request

model = joblib.load("student_model.joblib")
FIELDS = ["attendance_pct", "study_hours", "previous_score", "sleep_hours", "assignments_done", "phone_hours"]
LIMITS = {"attendance_pct": (0, 100), "study_hours": (0, 16), "previous_score": (0, 100),
          "sleep_hours": (0, 16), "assignments_done": (0, 10), "phone_hours": (0, 16)}

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.post("/predict")
def predict():
    data = request.get_json(silent=True) or {}
    errors = {}
    for name in FIELDS:
        value = data.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors[name] = "A number is required"
        elif not LIMITS[name][0] <= value <= LIMITS[name][1]:
            errors[name] = f"Must be between {LIMITS[name][0]} and {LIMITS[name][1]}"
    if errors:
        return jsonify(error="Invalid input", details=errors), 422
    chance = float(model.predict_proba(pd.DataFrame([data])[FIELDS])[0, 1])
    return jsonify(chance_of_passing=round(chance, 2), at_risk=chance < 0.6)

client = app.test_client()
good = {"attendance_pct": 92, "study_hours": 4.5, "previous_score": 78, "sleep_hours": 7.5, "assignments_done": 9, "phone_hours": 2}
bad = {"attendance_pct": 250, "study_hours": "lots"}

print(client.get("/health").get_json())
print(client.post("/predict", json=good).get_json())
response = client.post("/predict", json=bad)
print(response.status_code, response.get_json())
```

```output
{'status': 'ok'}
{'at_risk': False, 'chance_of_passing': 0.99}
422 {'details': {'assignments_done': 'A number is required', 'attendance_pct': 'Must be between 0 and 100', 'phone_hours': 'A number is required', 'previous_score': 'A number is required', 'sleep_hours': 'A number is required', 'study_hours': 'A number is required'}, 'error': 'Invalid input'}
```

The API refuses nonsense input with clear messages and answers sensible input with a probability. In production you would run it with Gunicorn behind HTTPS, as in the Flask web project.

## Other ways to share it

| Option | Good for |
| --- | --- |
| **Streamlit** app | a quick interactive demo with sliders for each feature (the easiest for portfolios) |
| **Flask or FastAPI** API | when other software needs to call the model |
| **Hugging Face Spaces, Render, Streamlit Cloud** | free places to host a demo |
| a **notebook** with a clear story | recruiters who want to read your reasoning |

A Streamlit version is only a few lines:

```py
import joblib
import pandas as pd
import streamlit as st

model = joblib.load("student_model.joblib")
st.title("Student pass predictor")
record = {
    "attendance_pct": st.slider("Attendance (%)", 0, 100, 75),
    "study_hours": st.slider("Study hours per day", 0.0, 10.0, 3.0),
    "previous_score": st.slider("Previous score", 0, 100, 60),
    "sleep_hours": st.slider("Sleep hours", 3.0, 10.0, 7.0),
    "assignments_done": st.slider("Assignments done (of 10)", 0, 10, 7),
    "phone_hours": st.slider("Phone hours per day", 0.0, 12.0, 4.0),
}
chance = model.predict_proba(pd.DataFrame([record]))[0, 1]
st.metric("Chance of passing", f"{chance:.0%}")
if chance < 0.6:
    st.warning("This student may benefit from extra support.")
```

## Limits and responsible use

A good project states what it **cannot** do. Be honest about these:

| Limit | What to write |
| --- | --- |
| **Practice data** | trained on generated data; real results would need real, consented, anonymised records |
| **Moderate accuracy** | the model is right about four times in five (79% on the test set); it supports human judgement and never replaces it |
| **Correlation, not cause** | "phone hours" being linked to failure does not mean phones cause it; do not use the model to blame students |
| **Fairness** | check performance for different groups (gender, region, background). A model can be less accurate for some groups and make unfair decisions |
| **Privacy** | student data is sensitive: collect the minimum, store it safely, follow the law and the college policy |
| **Feedback loops** | if flagged students get less opportunity rather than more help, the system causes harm; the aim is **support** |
| **Drift** | habits and courses change; monitor accuracy and retrain |

:::warning
Never use a model like this to **decide** something about a person on its own (grades, admission, scholarships). Use it to start a conversation: a teacher checks in with the student. A human stays responsible.
:::

## Your project README

```py
# Student Pass Predictor

Predicts whether a student is likely to pass from attendance, study habits and previous score,
so that teachers can offer support early.

**Result:** 79% accuracy on a held-out test set (baseline: 62%). Logistic regression, chosen for being
as accurate as the complex models and easy to explain.

## Approach
1. Defined the target, metric and baseline.   2. Cleaned and explored the data.
3. Compared 5 models with 5-fold cross-validation.   4. Tuned and tested once on a locked test set.
5. Explained the model (coefficients, permutation importance).   6. Served it with Flask.

## Limits
Practice data; moderate accuracy; shows association, not cause; needs a fairness check before real use.

## Run it
    pip install -r requirements.txt
    python train.py            # trains and saves student_model.joblib
    flask --app app run
```

(Replace the numbers with your own results if you change the data or the model.)

## Resume bullets

:::example Resume entry
**Student Pass Predictor** (Python, scikit-learn, pandas, Flask)
- Built an end-to-end classification project: defined the problem and metric, compared five models with cross-validation, and selected logistic regression, which matched the complex models and was easy to explain.
- Chose the decision threshold for the cost of missing at-risk students (recall) and documented the precision trade-off.
- Deployed the model through a validated Flask API with automated tests; documented limits and fairness concerns. GitHub: github.com/yourname/student-pass-predictor
:::

## Interview questions about this project

| Question | Your answer should cover |
| --- | --- |
| "Why did you choose logistic regression?" | it matched the complex models in cross-validation and is explainable to teachers |
| "How do you know it is not overfitting?" | cross-validation and a test score close to it |
| "What does 79% accuracy mean here?" | compare with the 62% baseline, and explain the confusion matrix |
| "Which error matters more?" | missing a failing student; so the threshold favours recall |
| "How did you avoid data leakage?" | split first, the scaler inside the pipeline, the test set used once |
| "What would you do with more time or data?" | real data, fairness checks, more features, monitoring |
| "How would this go wrong in real life?" | drift, unfair outcomes, using it to punish rather than support |

:::interview
**Interviewers often ask:** "Your model is 79% accurate; is that good?" It depends on the baseline and the cost of mistakes. Here 62% is the do-nothing baseline, so it adds value, but the real question is how many at-risk students it catches at a threshold the college can handle, and whether it is fair across groups.
:::

:::practice capstone-project
Ask the Capstone Project agent to review your README against the limits table and to suggest one fairness check for your own data.
:::
