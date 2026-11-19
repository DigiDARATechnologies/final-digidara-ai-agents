---
title: Deploy and share your project
summary: Put your project online with free hosting, keep secrets safe, and make a demo link that works when a recruiter clicks it.
takeaways:
- A live link is the strongest proof that your project works
- Free hosts can sleep, so test the link before you share it and have a backup video
- Keep keys and passwords in environment variables, not in the code
---
## Why deploy

A recruiter clicks a link far more often than they clone a repository and install Python. A working URL turns "I built a web app" into "here, try it".

## Which host for which project

| Project type | Good free options |
| --- | --- |
| **Static website** (HTML, CSS, JavaScript, React build) | **GitHub Pages**, Netlify, Vercel, Cloudflare Pages |
| **Python web app or API** (Flask, FastAPI, Django) | **Render**, Railway, Fly.io, PythonAnywhere |
| **Streamlit data app** | **Streamlit Community Cloud**, Hugging Face Spaces |
| **ML demo** | Hugging Face Spaces (Gradio or Streamlit) |
| **Database** | the host's free database, Supabase, Neon (PostgreSQL), MongoDB Atlas |

Free plans, limits and names change, so check each provider's current page before you start.

## The general steps (for a Flask or similar app)

1. **Push the code to GitHub** (without secrets).
2. Make sure there is a **`requirements.txt`** and a start command (`gunicorn wsgi:app`).
3. Create a **new web service** on the host and connect the repository.
4. Set **environment variables**: `SECRET_KEY`, `DATABASE_URL`, API keys.
5. Use a **real database** for anything that must be saved (the free file system of many hosts is erased on restart).
6. Deploy, open the URL and **test everything yourself**: sign up, log in, create data.
7. Put the **live link** in the README, your resume and LinkedIn.

## A static site on GitHub Pages

For a portfolio website made of HTML, CSS and JavaScript:

```py
git add .
git commit -m "Portfolio website"
git push                         # then in the repository: Settings, Pages, choose the main branch
```

Your site appears at `https://yourname.github.io/repository-name/` after a minute or two.

## Environment variables, not secrets in code

```py
import os

SECRET_KEY = os.environ["SECRET_KEY"]                 # fails loudly if it is missing
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.db")
```

On the host, add them in the dashboard (Environment). On your laptop, put them in a `.env` file that is listed in `.gitignore`, and load it with `python-dotenv`.

## Free hosting gotchas

| Problem | What to do |
| --- | --- |
| the app **sleeps** after inactivity and takes about a minute to wake | warn viewers in the README ("first load may take 30 to 60 seconds"), and open it yourself just before an interview |
| the database or uploaded files disappear on restart | use a proper database or object storage |
| it works locally but fails online | read the **deployment logs**; usually a missing package, wrong start command or missing environment variable |
| the app is slow | free plans have little CPU and memory; keep demo data small |
| the free plan ends | keep a **backup video** and screenshots in the README |

## Make it safe to share

| Check | |
| --- | --- |
| no real personal data in the demo | |
| demo accounts with a fake password written in the README (never real passwords) | |
| debug mode off (`DEBUG = False`) | |
| rate limits or a simple guard on forms that send email or use paid APIs | |
| API keys have spending limits | |
| HTTPS (the host provides it) | |

:::warning
If your project calls a **paid API** (for example an AI model), a public demo can run up a bill or exhaust your free quota if strangers use it. Set spending limits, require login, or provide a recorded demo instead.
:::

## A short demo video

Record a **60 to 90 second screen recording** with your voice:

1. What problem it solves (10 seconds).
2. The main flow, step by step (45 seconds).
3. One thing you are proud of (10 seconds).
4. How to find the code (5 seconds).

Upload it to YouTube (unlisted) or Google Drive and link it in the README and LinkedIn. It works even when the live site is asleep.

## Where to share

| Place | How |
| --- | --- |
| **Resume** | project name, one result line, GitHub and live links |
| **LinkedIn** | Featured section and Projects; a short post about what you built and learned |
| **GitHub profile** | pinned repositories and a profile README |
| **Portfolio site** | a simple page listing 3 to 5 projects with pictures and links |
| **College placement cell, clubs, friends** | people often hear about openings through others |

:::practice capstone-project
Ask the Capstone Project agent to help you choose where to host your project and to review your deployment checklist.
:::
