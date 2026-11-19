---
title: Data science interview questions
summary: The questions fresher data science and analyst interviews keep asking, with short answers.
kind: qa
takeaways:
- Know the workflow and be able to describe a project you did
- Explain statistics ideas in plain words, with an example
- Be ready for the outliers, p-value and correlation questions
---
### Q [Easy] What is data science?
The practice of extracting insight from data using programming, statistics and domain knowledge, to answer questions and support decisions.

### Q [Easy] What are the steps of a data science project?
Define the problem, collect data, clean it, explore it, build and evaluate a model, then communicate the results and deploy or act on them. It is iterative: later steps often send you back.

### Q [Easy] What is the difference between a data analyst and a data scientist?
An analyst answers questions from existing data with SQL, Excel and visualisation. A data scientist also builds statistical and machine learning models to predict or find patterns.

### Q [Medium] What is EDA and why does it matter?
Exploratory data analysis is looking at the data (shape, types, missing values, distributions, relationships) **before** modelling. It catches errors, shows what is normal, and guides which models and features to try.

### Q [Medium] How do you handle missing data?
Find out why it is missing, then drop rows or columns if few are affected, or fill with the mean, median, mode or a model's estimate. State the choice, because it can change the results.

### Q [Medium] How do you detect and handle outliers?
Detect them with box plots, the IQR rule or z-scores. Check whether they are errors or real. Fix or remove errors; for real extremes use the median, capping or a transformation, and document it.

### Q [Easy] What is the difference between mean and median? When do you prefer the median?
The mean is the average and the median is the middle value. The median is better for skewed data or data with outliers, such as salaries.

### Q [Medium] What is standard deviation?
A measure of how spread out the values are around the mean, in the same units as the data. A small value means the values are close to the mean.

### Q [Medium] What is correlation? Does it imply causation?
Correlation measures how strongly two variables move together, from -1 to 1. It does not imply causation: a third factor may drive both (ice cream and drowning both rise in summer). Causation needs a controlled experiment.

### Q [Medium] What is a p-value?
The probability of getting a result at least as extreme as the one observed, if the null hypothesis were true. A small p-value (below 0.05) is evidence against the null. It is not the probability that your hypothesis is correct.

### Q [Medium] What are Type I and Type II errors?
Type I is a false positive: rejecting a true null hypothesis. Type II is a false negative: failing to reject a false null hypothesis.

### Q [Medium] What is the central limit theorem?
The averages of many random samples tend to follow a normal distribution, whatever the shape of the original data, and their spread shrinks as the sample size grows. It is why many statistical tests work.

### Q [Medium] What is an A/B test?
A randomised experiment comparing two versions (A and B) on a chosen measure, followed by a hypothesis test to decide whether the difference is real.

### Q [Medium] What is the difference between a population and a sample?
The population is everything you want to know about. A sample is the part you actually measure. A good (random) sample lets you estimate population values.

### Q [Hard] Your model has 99% accuracy on a fraud dataset. Is it good?
Not necessarily. If only 1% of transactions are fraud, a model that always says "not fraud" is 99% accurate. Check precision, recall, F1 and the confusion matrix on the fraud class.

### Q [Medium] How would you explain a result to a non-technical manager?
Lead with the answer in one sentence and what it means for the decision, show one clear chart, state the main limitation, and give a recommendation. Leave the method for those who ask.

:::practice mock-interview
Practise describing a project you did, from question to result, in a Mock Interview.
:::
