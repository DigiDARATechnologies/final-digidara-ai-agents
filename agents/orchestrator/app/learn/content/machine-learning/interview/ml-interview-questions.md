---
title: Machine learning interview questions
summary: The ML questions fresher interviews keep asking, with short answers you can say in your own words.
kind: qa
takeaways:
- Be able to define overfitting, bias and variance, and data leakage
- Know when to use which metric
- Explain with a simple example, not only a definition
---
### Q [Easy] What is machine learning?
A way of building systems that **learn patterns from data** and use them to make predictions, instead of being programmed with explicit rules.

### Q [Easy] What are supervised and unsupervised learning?
**Supervised** learning trains on data with the right answers (labels) to predict them for new data, as in spam detection or price prediction. **Unsupervised** learning has no labels and looks for structure, such as grouping customers.

### Q [Easy] What is the difference between regression and classification?
Regression predicts a **number** (a house price). Classification predicts a **category** (spam or not spam).

### Q [Easy] What are features and labels?
Features are the input columns used to make a prediction. The label (or target) is the answer you want to predict.

### Q [Medium] What is overfitting, and how do you prevent it?
The model memorises the training data and does badly on new data: a high training score and a much lower test score. Prevent it with more data, a simpler model, regularisation, limits such as `max_depth`, cross-validation, and ensembles.

### Q [Medium] What is underfitting?
The model is too simple to capture the pattern, so it does badly on both training and test data. Fix it with a more flexible model or better features.

### Q [Medium] Explain the bias-variance trade-off.
**Bias** is error from too simple assumptions (underfitting). **Variance** is error from being too sensitive to the training data (overfitting). Making a model more complex lowers bias but raises variance. The goal is the balance with the lowest total error on new data.

### Q [Medium] Why do we split data into training and test sets?
To measure how the model performs on **data it has never seen**. A score on the training data only shows how well it memorised.

### Q [Medium] What is cross-validation?
Splitting the data into k parts and training k times, each time using a different part as the validation set, then averaging the scores. It gives a more reliable estimate than one split.

### Q [Medium] What is data leakage?
When information from outside the training set (such as the test data or the future) influences the model, which makes the evaluation unrealistically good. Avoid it by fitting scalers and imputers on training data only, ideally inside a Pipeline.

### Q [Medium] Why is accuracy not always a good metric? Which metrics would you use?
With unbalanced classes, a model that always predicts the majority class can have high accuracy but be useless. Use the confusion matrix, **precision**, **recall**, **F1**, and ROC-AUC. For regression use MAE, RMSE and R².

### Q [Medium] What are precision and recall?
Precision is TP / (TP + FP): when the model says yes, how often it is right. Recall is TP / (TP + FN): of all the real yes cases, how many it found.

### Q [Hard] How would you handle an imbalanced dataset?
Choose better metrics (F1, recall, PR curve), use **stratified** splits, set `class_weight="balanced"`, **resample** (oversample the small class or undersample the large one), or collect more examples of the rare class.

### Q [Medium] What is regularisation?
A penalty added to the model's training objective that discourages large coefficients, so the model stays simpler and overfits less. Common types are L1 (Lasso, which can remove features) and L2 (Ridge).

### Q [Medium] Why do we scale features?
Many models use distances or gradient steps (KNN, K-means, SVM, linear models), so a feature with large numbers can dominate the others. Scaling puts features on a similar range. Tree-based models do not need it.

### Q [Hard] How does a random forest work?
It builds many decision trees, each on a random sample of the rows and a random subset of features, and combines their predictions by vote (or average). This reduces the variance of a single tree.

### Q [Medium] What is the difference between bagging and boosting?
**Bagging** trains models independently on random samples and averages them (random forest). **Boosting** trains models one after another, each one focusing on the mistakes of the previous (gradient boosting, XGBoost).

### Q [Medium] How do you choose k in K-means?
Try several values and use the elbow method on inertia and the silhouette score, then check that the clusters are meaningful.

### Q [Medium] What is data leakage and how do you prevent it?
When information that would not be available at prediction time reaches the model during training, such as a column created after the outcome, or a scaler fitted on the whole dataset before splitting. Scores look excellent and then collapse in production. Prevent it by asking "would I have this value at prediction time?", putting every transformation inside a Pipeline, splitting by group or time where needed, and being suspicious of results that look too good.

### Q [Medium] Explain the bias-variance trade-off.
Bias is error from a model too simple to capture the pattern (underfitting). Variance is error from a model so flexible that it fits noise and changes a lot with different training samples (overfitting). More complexity lowers bias and raises variance, so test error is U-shaped; we look for the balance using validation, regularisation, more data or simpler models.

### Q [Medium] L1 versus L2 regularisation?
Both penalise large weights. L2 (Ridge) shrinks weights smoothly toward zero. L1 (Lasso) can set some weights exactly to zero, so it performs feature selection. Elastic Net mixes both. Scale the features first.

### Q [Hard] How does gradient boosting work, and how does it differ from a random forest?
It builds shallow trees sequentially. Each new tree is trained on the errors (residuals, or gradients of the loss) of the current ensemble, and a fraction of its output (the learning rate) is added. A random forest builds deep trees independently and averages them. Boosting mainly reduces bias and usually reaches higher accuracy on tabular data, but needs a small learning rate, limited depth and early stopping to avoid overfitting.

### Q [Medium] How do you handle an imbalanced dataset?
Use stratified splits and judge with precision, recall, F1 and PR-AUC instead of accuracy. Try class weights first, then resampling such as SMOTE (only on training data, inside the pipeline), and tune the decision threshold for the business cost of each type of error. Consider anomaly detection or collecting more positive examples.

### Q [Medium] When would you use PCA, and what are its drawbacks?
To reduce many correlated features to a few uncorrelated components that keep most of the variance, which speeds training, reduces noise and allows visualisation. Scale first and fit it on training data only. Drawbacks: it is linear, and the components are mixtures of the original features, so they are harder to explain.

### Q [Hard] How do you interpret a black-box model?
Globally, use permutation importance (shuffle a feature on held-out data and measure the drop in score) and partial dependence plots. For a single prediction use SHAP or LIME. Be careful with correlated features, and remember that importance shows what the model uses, not what causes the outcome.

### Q [Hard] How do you validate a time-series model?
Never shuffle. Train on earlier data and test on later data, using a forward split or TimeSeriesSplit, and compare with a naive baseline such as "same as last week". Build features only from information known at prediction time, for example lags and rolling statistics shifted by one step.

### Q [Hard] What is model drift and how do you detect it?
Data drift is a change in the distribution of the inputs; concept drift is a change in the relationship between inputs and the target. Detect them by comparing recent feature and prediction distributions with the training data (KS test, PSI), tracking real performance once outcomes are known, and retraining when metrics fall.

:::practice mock-interview
Practise explaining these aloud in a Mock Interview. Use a small example for each answer.
:::
