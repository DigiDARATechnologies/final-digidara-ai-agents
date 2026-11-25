---
title: Machine learning basics questions
summary: Types of learning, bias and variance, overfitting, regularisation, common algorithms and feature engineering.
kind: qa
takeaways:
- Explain supervised, unsupervised and reinforcement learning with examples
- Describe overfitting and three ways to reduce it
- Compare common algorithms and when to use each
---
### Q [Easy] What is machine learning?
Teaching computers to learn patterns from data so they can make predictions or decisions without being explicitly programmed with rules.

### Q [Easy] Supervised vs unsupervised vs reinforcement learning?
**Supervised**: learn from labelled examples (spam or not spam; house price). **Unsupervised**: find structure in unlabelled data (customer clusters). **Reinforcement**: an agent learns by trial and reward (game playing, robotics).

### Q [Easy] Classification vs regression?
Classification predicts a **category** (pass or fail). Regression predicts a **number** (marks, price).

### Q [Easy] What are training, validation and test sets?
**Training**: the model learns from it. **Validation**: used to tune settings and choose models. **Test**: touched only once at the end to estimate real performance.

### Q [Medium] What is overfitting and how do you reduce it?
The model memorises the training data (very high training score, much lower test score). Reduce it with **more data**, a **simpler model**, **regularisation**, **cross-validation**, **early stopping**, **dropout** (neural networks) and **feature selection**.

### Q [Medium] What is underfitting?
The model is too simple to capture the pattern, so it performs poorly on both training and test data. Fix with a more complex model, better features or less regularisation.

### Q [Medium] Explain the bias-variance trade-off.
**Bias** is error from overly simple assumptions (underfitting). **Variance** is error from sensitivity to the training data (overfitting). Making the model more complex lowers bias but raises variance; the goal is the sweet spot with the lowest total error.

### Q [Medium] What is regularisation? L1 vs L2?
A penalty added to the loss to keep weights small and reduce overfitting. **L1 (Lasso)** can shrink some weights to exactly zero (feature selection). **L2 (Ridge)** shrinks weights smoothly but rarely to zero.

### Q [Medium] What is cross-validation?
Splitting the data into k folds, training on k-1 and testing on the remaining fold, k times, then averaging the scores. It gives a more reliable estimate than one split.

### Q [Medium] Explain how a decision tree works. What are its weaknesses?
It splits data by asking yes or no questions on features, choosing splits that best separate the classes (using Gini impurity or entropy). It is easy to interpret but **overfits easily** and is unstable.

### Q [Medium] Random forest vs gradient boosting?
Both are ensembles of trees. A **random forest** trains many trees independently on random samples and averages them (reduces variance). **Gradient boosting** trains trees one after another, each correcting the previous errors (reduces bias), and often gives higher accuracy but needs careful tuning.

### Q [Medium] How does k-means clustering work?
Choose k, place k centres, assign each point to the nearest centre, move each centre to the mean of its points, and repeat until it stops changing. Choose k with the elbow method or silhouette score.

### Q [Medium] How do you handle missing values?
Remove rows or columns if few or useless, or **impute**: mean or median for numbers, most frequent for categories, or a model-based method. Add a "was missing" flag when missingness itself is informative.

### Q [Medium] How do you encode categorical variables?
**One-hot encoding** for categories without order, **ordinal encoding** for ordered categories, and target or frequency encoding for high-cardinality columns.

### Q [Medium] Why do we scale features?
Algorithms that use distances or gradients (k-NN, SVM, neural networks, gradient descent) are sensitive to feature ranges. Standardisation (mean 0, std 1) or min-max scaling puts features on a comparable scale. Tree models do not need it.

### Q [Hard] What is data leakage?
Information from outside the training data (often from the test set or the future) leaks into the model, giving unrealistically good results. Examples: scaling or imputing before splitting, or using a feature that is only known after the outcome. Always split first and fit preprocessing on the training set only.

### Q [Hard] How do you deal with an imbalanced dataset?
Do not trust accuracy. Use precision, recall, F1 or PR-AUC; resample (oversample the minority, SMOTE, or undersample); use **class weights**; and choose a sensible decision threshold.
