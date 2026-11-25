---
title: Generative AI portfolio projects
summary: Project ideas with a clear plan, the skills each shows, and how to present them to recruiters.
takeaways:
- Pick one project and finish it end to end rather than starting many
- Show evaluation, cost and limits, not only a demo
- A working link and a clear README impress more than complex code
---
## What recruiters like to see

A working app they can **try**, a **README** explaining the idea and design, some **evidence it works** (a small evaluation), and honest notes on limits. Finish one good project before starting another.

## Project 1: chat with your PDFs (RAG)

**What**: upload documents, ask questions, get answers with citations.
**Build**: chunk and embed, store in Chroma or pgvector, retrieve, answer with a grounded prompt.
**Show**: citations, an "I do not know" answer when the text has no answer, and a hit-rate table from a test set of 30 questions.

## Project 2: college assistant

**What**: answers student questions from the handbook, fee rules and timetable.
**Add**: metadata filters (by department), a feedback button, and a fallback to "contact the office".

## Project 3: resume analyser

**What**: compare a resume with a job description and give a match score and suggestions.
**Build**: structured output (JSON with skills found and missing), embeddings for similarity.
**Show**: how you avoid inventing skills, and privacy handling for personal data.

## Project 4: SQL assistant

**What**: ask a question in English, get a SQL query and the result.
**Safety**: read-only database user, validate and limit queries, show the query before running.

## Project 5: support ticket triage

**What**: classify, prioritise and draft a reply for incoming tickets.
**Build**: structured output with categories, a human-approval step before sending.
**Show**: precision and recall per category against labelled tickets.

## Project 6: multimodal notes helper

**What**: upload a photo of notes or a lecture recording, get clean notes and quiz questions.
**Build**: a vision or speech model for input, an LLM for summary, structured output for questions.

## How to build any of them

1. **Define** one user and one problem.
2. Build the **simplest working version** first.
3. Make a **test set** of real questions and score it.
4. Improve one thing at a time (chunking, prompt, model) and record the numbers.
5. Add **safety**: input limits, no secrets in the prompt, source citations.
6. **Deploy** it (Streamlit, Gradio, or a Flask or FastAPI app) and write the README.

## README checklist

- Problem and who it is for
- A screenshot or short video and the live link
- Architecture diagram (documents, embeddings, vector store, LLM)
- How you tested it, and the results table
- Cost per question and speed
- Limits and what you would improve next

:::practice capstone-project
Take your chosen idea to the Capstone Project agent for guided planning and review.
:::
