---
title: Model evaluation and statistics questions
summary: Confusion matrix, precision and recall, ROC-AUC, p-values, hypothesis testing, distributions and A/B tests.
kind: qa
takeaways:
- Compute and explain precision, recall and F1 from a confusion matrix
- Explain p-value and confidence interval in plain words
- Know the basic distributions and the central limit theorem
---
### Q [Easy] What is a confusion matrix?
A table of actual versus predicted classes showing true positives (TP), false positives (FP), true negatives (TN) and false negatives (FN).

### Q [Medium] Explain precision, recall, accuracy and F1.
**Accuracy** = (TP + TN) / all. **Precision** = TP / (TP + FP), of those predicted positive how many were right. **Recall** = TP / (TP + FN), of all real positives how many were found. **F1** is the harmonic mean of precision and recall.

### Q [Medium] When is recall more important than precision?
When a miss is costly: cancer screening, fraud detection. Precision matters more when a false alarm is costly: spam filtering of important email, recommending only trusted content.

### Q [Medium] What is the ROC curve and AUC?
The ROC curve plots the true positive rate against the false positive rate at all thresholds. **AUC** is the area under it (0.5 means random, 1.0 means perfect) and measures how well the model ranks positives above negatives.

### Q [Medium] Which metrics do you use for regression?
**MAE** (average absolute error), **MSE** and **RMSE** (penalise large errors, RMSE has the target's units), and **R squared** (share of variance explained).

### Q [Easy] Mean vs median vs mode? When is median better?
Mean is the average, median is the middle value, mode is the most frequent. Use the **median** when there are outliers or skewed data (such as income).

### Q [Medium] What is standard deviation and variance?
Variance is the average squared distance from the mean; standard deviation is its square root and is in the original units. They measure spread.

### Q [Medium] What is the normal distribution and the 68-95-99.7 rule?
A symmetric bell-shaped distribution. About 68% of values lie within 1 standard deviation of the mean, 95% within 2 and 99.7% within 3.

### Q [Medium] What is the central limit theorem?
The distribution of sample means approaches a normal distribution as the sample size grows, whatever the shape of the original data (given finite variance). It is why many statistical tests work.

### Q [Medium] What is a p-value?
The probability of seeing results at least as extreme as ours **if the null hypothesis were true**. A small p-value (commonly below 0.05) is evidence against the null. It is **not** the probability that the null is true.

### Q [Medium] What are Type I and Type II errors?
**Type I** (false positive): rejecting a true null hypothesis. **Type II** (false negative): failing to reject a false null.

### Q [Medium] What is a confidence interval?
A range that, if the procedure were repeated many times, would contain the true value a stated share (such as 95%) of the time.

### Q [Medium] Correlation vs causation?
Correlation means two variables move together. It does not prove one causes the other; there may be a third factor or coincidence. Experiments (A/B tests) help establish causation.

### Q [Hard] How would you design an A/B test?
Define the metric and hypothesis, choose the sample size beforehand (power analysis), randomly split users into control and treatment, run for a full period (include weekdays and weekends), avoid peeking, then test significance and check practical impact and guardrail metrics.

### Q [Hard] What is multicollinearity and why is it a problem?
Features that are highly correlated with each other. In linear models it makes coefficients unstable and hard to interpret. Detect with correlation or VIF; fix by dropping or combining features, or using regularisation.
