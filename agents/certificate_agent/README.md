# ⚡ CertifyAI: Intelligent Certification Platform 🎓

CertifyAI is an advanced, production-ready AI certification agent that dynamically generates exams, strictly evaluates answers using Large Language Models (LLMs), and issues visually stunning PDF certificates for passing candidates. 

It is designed with a sleek, Glassmorphism-inspired dark UI and backed by a robust, secure FastAPI backend.

---

## ✨ Features

- **🧠 Dynamic AI Exam Generation:** Leverages Groq (`llama-3.3-70b-versatile`) and LangChain to dynamically generate custom multiple-choice questions ranging from beginner to advanced based on any topic.
- **🛡️ Secure Authentication:** JWT-based stateless authentication with `bcrypt` password hashing.
- **📊 Interactive Dashboard:** Track exam history, view performance statistics, and download earned certificates.
- **👩‍🏫 Strict AI Evaluation:** Answers are evaluated purely on correctness (0 or 1 point) with detailed feedback from the AI evaluation agent.
- **🏆 Production-Grade Certificates:** Automatically generates and saves beautiful, responsive PDF certificates for passing candidates using `ReportLab`.
- **⚙️ Configurable Architecture:** Environment variables (`.env`) for database connections, JWT secrets, LLM parameters, and exam policies.
- **🗄️ Connection Pooling:** Robust MySQL database schema with connection pooling for performance.

---

## 🛠️ Technology Stack

*   **Backend:** FastAPI, Python, Uvicorn
*   **AI Integration:** LangChain, LangGraph, Groq (`llama-3.3-70b-versatile`)
*   **Database:** MySQL (mysql-connector-python)
*   **Authentication:** JWT (python-jose), bcrypt
*   **Frontend:** Vanilla JS, HTML5, CSS3 (Glassmorphism & CSS Animations)
*   **PDF Generation:** ReportLab
*   **Configuration:** Pydantic Settings

---

## 🚀 Setup & Installation

### 1. Prerequisites
- **Python 3.10+**
- **MySQL Server** (running locally or remotely)
- **Groq Developer Account** (for API Key)

### 2. Clone the Repository
```bash
git clone <your-repository-url>
cd certificate_agent
```

### 3. Setup Virtual Environment
Create and activate a Python virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\activate
```
*(On macOS/Linux use `source venv/bin/activate`)*

### 4. Install Dependencies  
Install all required production packages:
```powershell
pip install -r requirements.txt
```

### 5. Setup the Database
Log into your MySQL instance and create the database:
```sql
CREATE DATABASE certification_db;
```

### 6. Configure Environment Variables
Ensure your `.env` file exists in the root directory (`d:\certificate_agent\.env`) with the correct details:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_db_password_here
DB_NAME=career_agent_db

SECRET_KEY=your_random_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

PASS_SCORE=70
MAX_ATTEMPTS=3
CERTIFICATES_DIR=certificates
```
*(Note: Change the `DB_PASSWORD` if yours is different)*

---

## 💻 Running the Application

Once your virtual environment is active and MySQL database is configured, you can start the FastAPI server:

```powershell
# Ensure you are inside the virtual environment
python run.py
```

*   The server will start on **`http://localhost:8000`**
*   The API Documentation (Swagger UI) is available at **`http://localhost:8000/docs`**

---

## 📘 How to Use

1. **Register:** Navigate to `http://localhost:8000`, click the **Register** tab, and create a new account.
2. **Dashboard:** Upon login, you'll see your dashboard where you can track "Total Exams", "Exams Passed", and view your "Exam History".
3. **Start an Exam:** Type a topic (e.g., *Python, Docker, React*) into the "Start a New Exam" input and click **Start Exam ⚡**.
4. **Take the Test:** The AI will build a personalized exam. Answer the questions and use the navigation points at the top to skip around. 
5. **Submit & Evaluate:** Submit the exam. The AI evaluation agent will grade your answers.
6. **Get Certified:** If your score is above the `PASS_SCORE` (default 70%), you will earn a production-grade PDF certificate that can be downloaded straight from the results page!

---

## 📁 Project Structure

```
d:\certificate_agent\
├── .env                          ← Configuration
├── requirements.txt              ← Dependencies
├── run.py                        ← Server Entry Point
└── app\
    ├── main.py                   ← FastAPI setup
    ├── config.py                 ← Pydantic Settings
    ├── api\                      ← API Routes
    │   ├── auth.py             
    │   ├── exam.py             
    │   └── certificate.py       
    ├── agents\                   ← AI Agents
    │   ├── question_agent.py     
    │   ├── evaluation_agent.py   
    │   └── exam_graph.py         
    ├── services\                 ← Core Logic
    │   ├── auth_service.py       
    │   ├── exam_service.py       
    │   └── certificate_generator.py 
    ├── db\                       ← Database
    │   └── database.py           
    ├── schemas\                  ← Pydantic Models
    │   ├── user.py 
    │   └── exam.py    
    └── ui\                       ← Frontend
        ├── index.html            
        ├── dashboard.html        
        ├── exam.html             
        ├── result.html           
        └── static\css\styles.css 
```
