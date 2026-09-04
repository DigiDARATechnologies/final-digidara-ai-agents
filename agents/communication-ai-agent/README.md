# Communication Module (LMS)

A self-contained Communication practice module: **Dashboard, Speaking, Writing, History, Profile**.

- Frontend: React (Vite) + Tailwind CSS
- Backend: Flask (Python)
- Database: MySQL (use MySQL Workbench)
- AI: Groq API (LLM for conversation questions + scoring)

---

## How the Speaking page works (clarified)

1. Two sections/tabs: **Topic-wise** (pick a subject, AI also scores your *knowledge* of it) and
   **Daily Conversation** (casual everyday chat, no knowledge score).
2. Pick a **difficulty** (Easy / Medium / Hard).
3. Click **Start Conversation**.
4. The AI asks a question and **speaks it out loud** (browser text-to-speech).
5. As soon as the AI finishes speaking, the app **automatically starts listening** (browser speech-to-text) —
   no button needed to start recording.
6. When you stop talking (or press "I'm done answering"), your speech is transcribed and sent to the backend,
   which asks Groq to score it: **Confidence, Fluency, Grammar**, and (topic-wise only) **Knowledge**.
7. This repeats for 5 questions, then you get a full session summary and it's saved to your History and Dashboard.

The **Writing page** follows the exact same flow (topic-wise / daily, difficulty, Start Conversation, 5 prompts,
scored, summary) but you **type** your answer instead of speaking — no voice involved. Scores are
**Grammar, Vocabulary, Clarity**, and (topic-wise only) **Knowledge**.

Voice features use the browser's built-in **Web Speech API** (`SpeechSynthesis` + `SpeechRecognition`) — no
extra API key needed for voice. It works best in Chrome or Edge. If the browser doesn't support speech
recognition, the page will show a clear message.

---

## 1. Database setup (MySQL Workbench)

1. Open MySQL Workbench and connect to your local MySQL server.
2. Either run `backend/schema.sql` directly (creates the database + all tables), **or** just create the
   database and let Flask create the tables for you:
   ```sql
   CREATE DATABASE communication_module CHARACTER SET utf8mb4;
   ```

## 2. Backend setup (Flask)

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
cp .env.example .env         # then edit .env with your MySQL password + Groq API key
```

Edit `.env`:
```
DATABASE_URL=mysql+pymysql://root:yourpassword@localhost:3306/communication_module
GROQ_API_KEY=your-groq-api-key
```

Create tables and seed starter topics (skip `init-db` if you already ran `schema.sql`):
```bash
set FLASK_APP=run.py        # Windows: use `set`, macOS/Linux: use `export`
flask init-db
flask seed-topics
```

Run the API:
```bash
python run.py
```
The API runs at `http://localhost:5001/api`.

## 3. Frontend setup (React)

```bash
cd frontend
npm install
npm run dev
```
Opens at `http://localhost:5173`. It talks to the backend at `http://localhost:5001/api` by default
(change with a `VITE_API_URL` env var if needed).

## 4. Getting a Groq API key

Sign up at https://console.groq.com, create an API key, and put it in `backend/.env` as `GROQ_API_KEY`.

---

## Project structure

```
communication-module/
  backend/
    app/
      routes/        auth, dashboard, speaking, writing, history, profile
      services/       groq_service.py  (all AI calls: questions + scoring + summaries) The last one of three just okay did you see a false
      models.py       SQLAlchemy models (User, SpeakingSession/Turn, WritingSession/Turn, Topic)
      config.py
      commands.py     `flask init-db`, `flask seed-topics`
    schema.sql        manual MySQL schema (optional, mirrors models.py)
    requirements.txt
    run.py
  frontend/
    src/
      pages/          Dashboard, Speaking, Writing, History, Profile, Login
      components/     AppLayout (sidebar), ScoreRing, ModeTabs, DifficultySelector, TopicGrid
      context/        AuthContext.jsx
      api/client.js
```

## Notes for integrating into a bigger LMS

- Auth here is a minimal JWT register/login so the module runs standalone. If your main LMS already has auth,
  swap `routes/auth.py` for your existing login and just keep issuing/accepting the same JWT shape
  (`flask_jwt_extended`), or drop in your LMS's user id into the `users` table.
- All communication-module tables are self-contained (`users`, `topics`, `speaking_sessions`,
  `speaking_turns`, `writing_sessions`, `writing_turns`) so they can be merged into a larger LMS schema —
  just point `user_id` at your existing users table if you already have one.
