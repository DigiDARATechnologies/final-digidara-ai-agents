---
title: What is machine learning?
summary: Machine learning lets a program learn patterns from examples instead of following rules you wrote by hand.
takeaways:
- Traditional code follows rules you write; ML finds the rules from data
- The main types are supervised, unsupervised and reinforcement learning
- Supervised learning predicts either a number (regression) or a category (classification)
---
## Rules versus examples

Suppose you want a program that decides whether an email is spam. You could write rules: "if it says *free money*, it is spam." But spammers change their words every week, and your rules never end.

**Machine learning** takes the opposite route. You show the computer thousands of emails already marked *spam* or *not spam*. It finds the patterns itself, then uses them on new emails.

| | Traditional programming | Machine learning |
| --- | --- | --- |
| You provide | rules and data | data and the answers |
| You get | answers | the rules (a model) |
| Good for | clear, fixed logic | patterns too complex to write down |

## The three main types

| Type | Idea | Example |
| --- | --- | --- |
| **Supervised** | learn from examples that have the right answer | predict a house price; spot spam |
| **Unsupervised** | find structure in data with no answers | group customers who behave alike |
| **Reinforcement** | learn by trial, reward and penalty | a program that learns to play a game |

This course covers the first two, using Python and the **scikit-learn** library.

## Supervised learning: two kinds of answer

If the answer is a **number**, it is **regression**. If it is a **category**, it is **classification**.

| Question | Answer type | Kind |
| --- | --- | --- |
| What will this house sell for? | a number (₹) | regression |
| How many units will we sell next week? | a number | regression |
| Is this email spam? | yes or no | classification |
| Which species is this flower? | one of three | classification |

## Words you will see everywhere

| Word | Meaning |
| --- | --- |
| **Feature** | an input column used to predict (house size, number of rooms) |
| **Label** or **target** | the answer you want to predict (the price) |
| **Sample** | one row of data |
| **Model** | what the algorithm learns: the rules it uses to predict |
| **Training** | showing the model the data so it can learn |

:::note
Machine learning is not magic and not always the answer. If a simple rule works ("orders over ₹500 ship free"), use the rule. ML is for problems where the rule is too hard to write but you have plenty of examples.
:::

:::interview
**Interviewers often ask:** "What is machine learning?" A safe answer: "Machine learning is a way of building systems that learn patterns from data and use them to make predictions, instead of being programmed with explicit rules."
:::
