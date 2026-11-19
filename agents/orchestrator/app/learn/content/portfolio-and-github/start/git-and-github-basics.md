---
title: Git and GitHub basics
summary: Save your work with Git, put projects on GitHub, and learn the handful of commands you will use every day.
takeaways:
- Git records the history of your project; GitHub stores it online and is your public portfolio
- Commit small and often, with clear messages
- Never commit passwords, keys or large generated files
---
## Why Git

Git remembers **every version** of your project. You can undo mistakes, try ideas on a branch, and work with others without overwriting each other's files. **GitHub** is a website that hosts Git projects, and recruiters look at your GitHub profile as proof of your work.

## Set up once

```py
git config --global user.name "Priya Nair"
git config --global user.email "priya@example.com"
```

Create a free account at github.com, using a **professional username** (for example `priyanair`, not `cutegirl123`).

## The daily cycle

```py
git init                               # start tracking the project (once)
git status                             # what has changed?
git add .                              # choose all changes for the next snapshot
git commit -m "Add expense report"     # save the snapshot with a message
git log --oneline                      # see the history
```

| Command | Meaning |
| --- | --- |
| `git add file.py` | stage one file |
| `git commit -m "message"` | save a snapshot of everything staged |
| `git diff` | show what changed since the last commit |
| `git restore file.py` | throw away unsaved changes to a file |
| `git switch -c new-feature` | create and move to a new branch |
| `git merge new-feature` | bring a branch back into the current one |

## Put it on GitHub

1. On github.com click **New repository**, give it a name (`expense-tracker`), keep it public, do **not** add a README (you already have one).
2. Connect and upload:

```py
git branch -M main
git remote add origin https://github.com/yourname/expense-tracker.git
git push -u origin main
```

After that, `git push` uploads new commits, and `git pull` downloads changes.

## Write good commit messages

| Weak | Strong |
| --- | --- |
| `update` | `Add monthly summary to the report` |
| `fix` | `Fix crash when the CSV file is missing` |
| `final final 2` | `Validate the amount before saving an expense` |

Rule: start with a verb, describe **what changed and why** in one short line. A readable history shows how you think.

## What must never go on GitHub

| Item | Why | What to do |
| --- | --- | --- |
| passwords, API keys, tokens, `.env` files | anyone can find and misuse them; bots scan GitHub for keys within minutes | keep them in environment variables and list them in `.gitignore` |
| virtual environments (`.venv/`) and `__pycache__/` | huge and unnecessary | `.gitignore` |
| large data files, model files | slow and heavy | use small samples, or Git LFS, or a download link |
| personal or customer data | privacy | use fake or anonymised samples |

A starter `.gitignore` for Python:

```py
.venv/
__pycache__/
*.pyc
.env
*.db
.ipynb_checkpoints/
.DS_Store
```

:::warning
If you ever commit a secret by mistake, **deleting it in a new commit is not enough**, because it stays in the history. Treat the key as leaked: **revoke it** in the service's settings and create a new one.
:::

## A simple branch workflow

For a feature you are unsure about:

```py
git switch -c add-budget-feature       # work safely on a branch
# ...edit, test, commit...
git switch main
git merge add-budget-feature           # bring it in once it works
```

On GitHub, teams use **pull requests**: you push a branch, open a request, someone reviews it, then it is merged. Practising this on your own projects prepares you for a team job.

## Your GitHub profile

| Item | Tip |
| --- | --- |
| **Photo and short bio** | a clear photo; one line about what you do |
| **Pinned repositories** | pin your 4 to 6 best projects |
| **Profile README** | a repository named exactly like your username with a README: introduction, skills, links |
| **Green squares** | consistent small commits look better than one huge upload before the interview |
| **Clean repositories** | each with a README, description and topics (tags) |

Do not leave dozens of empty or half-finished tutorial copies visible. Archive or delete them, and pin your best work.

:::tip
Pair every project with a **good commit history**: recruiters sometimes open the history to see whether you actually built it. A single commit named "upload" with the whole project looks suspicious.
:::
