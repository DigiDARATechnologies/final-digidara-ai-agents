---
title: Write a README that sells your project
summary: Create a README that explains the problem, shows the result, and tells a visitor how to run it in two minutes, with a template and a checklist.
takeaways:
- The README is the first (often only) thing a recruiter reads
- Show the result early: a screenshot, a GIF or a live link
- Explain what it does, how to run it, what you learned and its limits
---
## The first impression

A recruiter may spend 30 seconds on your repository. In that time they read the **title, the first paragraph, a picture, and maybe the tech list**. A strong README makes them stay; an empty one makes them leave, however good your code is.

## The template

```py
# Project Name

One sentence: what it does and who it is for.

![Screenshot or demo GIF](docs/screenshot.png)

**Live demo:** https://yourproject.onrender.com   |   **Video:** (a short screen recording link)

## Features
- Create, view and complete tasks
- Each user sees only their own data
- JSON API and a web page

## Tech stack
Python, Flask, SQLAlchemy, SQLite/PostgreSQL, pytest, Docker

## How it works (short)
A user registers and logs in; tasks are stored per user in the database;
the same functions power the web pages and the JSON API.

## Run it locally
    git clone https://github.com/yourname/taskflow.git
    cd taskflow
    python -m venv .venv
    .venv\Scripts\activate        # macOS and Linux: source .venv/bin/activate
    pip install -r requirements.txt
    flask --app app run

## Run the tests
    pytest

## What I learned
- Designing a database with a one-to-many relationship
- Keeping each user's data private (and testing it)
- Deploying with Docker and Gunicorn

## Limitations and next steps
- No password reset yet
- Planned: due dates, a React front end
```

## What each part does

| Part | Why it matters |
| --- | --- |
| **Title and one-line summary** | the visitor knows what it is in five seconds |
| **Screenshot or GIF** | people believe what they see; a short demo GIF beats pages of text |
| **Live link** | the strongest proof that it works |
| **Features** | 3 to 6 bullets, in user terms |
| **Tech stack** | helps recruiters and search match your skills to roles |
| **How to run** | proves reproducibility: if they can run it, they respect it |
| **What I learned** | shows reflection and honesty |
| **Limitations** | honesty builds trust; a project with no stated limits looks naive |

## Screenshots and demos

| Tool | Use |
| --- | --- |
| built-in screenshot (Windows: `Win + Shift + S`) | still images |
| **ScreenToGif**, **Kap**, **LICEcap** | short GIFs of the app in use |
| **OBS Studio**, **Loom** | a 1 to 2 minute narrated video |
| a free host (Render, Streamlit Cloud, Hugging Face Spaces, GitHub Pages) | a live demo |

Keep images in a `docs/` folder inside the repository so that links never break.

## Describe the **problem**, not only the tools

| Weak | Strong |
| --- | --- |
| "A Flask app using SQLAlchemy." | "TaskFlow helps students keep separate to-do lists. Each user's tasks are private, and the app has a web page and a JSON API." |
| "ML project on student data." | "Predicts which students are likely to fail so that teachers can offer support early. Compares five models; the final logistic regression reaches 79% accuracy against a 62% baseline." |

State the **result with a number** when you can.

## Checklist

| Check | |
| --- | --- |
| a clear title and a one-sentence purpose | |
| a screenshot, GIF or live link in the first screen | |
| setup steps that work on a fresh computer (test them!) | |
| a `requirements.txt` | |
| no secrets, passwords or personal data | |
| tests and how to run them | |
| limitations and next steps | |
| spelling checked, headings tidy | |

:::tip
The best test: ask a friend who has not seen the project to follow your README on their own computer. Every place they get stuck is a line to fix.
:::

:::practice resume-builder
Use the Resume Builder agent to turn your README's "what it does" and "result" lines into resume bullets.
:::
