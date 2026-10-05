"""What the general chat may tell a learner about DigiDARA: each live agent's
purpose and the steps a learner takes to use it.

This is the assistant's only source of facts about the platform, written from
the learner's side of the screen: what to click, what to type, what comes
back. It deliberately says nothing about how anything works inside (models,
code execution, grading, storage), and the router prompt forbids explaining
that. Keep it in step with the agents' own flows in src/lib/*Flow.ts when a
flow changes.
"""

PLATFORM_GUIDE = """
DIGIDARA AI AGENTS (digidaraaiagents.com)
A learning and career platform with specialised AI agents. Open an agent from the Store, or ask the DigiDARA Assistant to connect you. Every chat is saved in the sidebar. The microphone button lets you speak instead of typing.

POINTS AND PLANS
- Agents use points. Every new account starts with 25 free points. Points never expire.
- Plans (one-time payments): Basic Rs 399 = 250 points; Standard Rs 799 = 500 points; Premium Rs 999 = 750 points. The Standard and Premium pages show the price plus GST.
- Buy points: Settings -> Billing -> choose a plan. When points run low, a "Buy points" popup appears.
- See points used per agent: Settings -> Usage.

LIVE AGENTS

1. Capstone Project Agent
Purpose: complete a real capstone project end to end and earn a certificate.
Steps:
  1. Open the agent and answer its first question.
  2. Tell it the language, role or topic you want your project in (for example "Python data analysis").
  3. Pick one of the two project options it offers (A or B). Once chosen, the project is locked.
  4. Read the project requirements. Download the example report and example project if you want a reference.
  5. Click "Start 7-day timer" when you are ready. The timer cannot be paused.
  6. Build the project. You can ask the agent questions about your project at any time while you work.
  7. Before the deadline, attach your .docx project report and your .zip source code with the paperclip button and send them.
  8. Answer the viva questions in the chat. You get more than one viva attempt.
  9. When both your project score and the viva pass, check how your name is spelled and get your certificate and the final report (PDF). If you do not pass, improve the project and resubmit.

2. LeetCode Agent (CodeForge coding practice)
Purpose: practise coding problems course by course and topic by topic.
Steps:
  1. Choose a course, then a topic, then a problem.
  2. Read the problem and write your solution in the code editor.
  3. Click Run to try your code, then Submit to check it against the tests.
  4. Stuck? Use "Explain this error" or ask the tutor for a hint.
  5. Use "Code Playground" to write and run any code freely, or "Choose another problem" to continue.

3. Aptitude Trainer Agent
Purpose: practise quantitative aptitude, logical reasoning and verbal ability with timed tests.
Steps:
  1. Choose "Category Practice" (one area) or "Mixed Test" (a mix of areas) and pick how many questions you want.
  2. Answer each question before its timer runs out. Type "hint" if you need a nudge.
  3. Review your score and the explanations at the end, and download the PDF report.
  4. Open the dashboard to see your history and progress by topic.

4. Mock Interview Agent
Purpose: practise real interviews and get scored feedback on every answer.
Steps:
  1. Choose "Technical interview" or "HR interview".
  2. For a technical interview, pick a job role (for example Python Fullstack Developer, Data Analyst, AI Engineer) or a custom topic.
  3. Choose a level (Beginner 60 seconds, Intermediate 90 seconds or Advanced 120 seconds per answer) and the number of questions (5, 10 or 15).
  4. Answer each question by speaking or typing within the time limit.
  5. Read your feedback and final report, then practise your weak topics or start another interview.

5. Communication Coach Agent
Purpose: improve spoken and written English.
Steps:
  1. Choose Pronunciation Practice, Speaking Practice or Writing Practice, or start the recommended practice.
  2. Pronunciation: pick Word or Sentence and a level (Easy, Medium, Hard), then say it aloud.
  3. Speaking: chat with the AI by voice on a topic.
  4. Writing: write about the given topic and get corrections.
  5. Each activity is scored out of 10. Track progress and daily challenges on the dashboard, and download a PDF report.

6. Resume Builder Agent
Purpose: create or improve an ATS-friendly resume.
Steps:
  1. Choose "Create a resume" or upload an existing resume.
  2. Say whether you are a fresher/student or an experienced professional.
  3. Fill in each section as the agent asks: education, experience, projects, skills, certifications, achievements and links.
  4. Use "Edit with AI" or "Enhance summary" to improve the wording.
  5. Review the resume, then "Choose template & download" to get the PDF.

7. AI Certification Agent
Purpose: take a certification exam on a topic and earn a certificate.
Steps:
  1. Click "Take Certification Exam" and choose a topic.
  2. Answer the exam questions in the chat.
  3. Score 70% or more to pass and earn the certificate.
  4. Download the PDF certificate and the exam report, or email the certificate. Use "My Certificates" to see all of them.

8. Job Fetching Agent
Purpose: find jobs that match your skills, with a fit score for each.
Steps:
  1. Set up your profile: skills, experience, preferred locations and work mode (Remote, Hybrid, Office or Any). Uploading a resume is optional.
  2. Browse your matched jobs, or ask for more, such as fresher jobs or jobs in a city.
  3. Ask about a job's salary and role details, or hide jobs you do not want.
  4. Click "Apply now" to open the employer's application page.
  5. A free daily number of jobs and messages is included; after that it uses points.

COMING SOON (not available yet; do not connect to these)
Career Guidance Agent, Research Agent, Content Writer Agent, Data Analyst Agent, Video AI Agent, Business Strategy Agent, Coding Assistant Agent.
""".strip()
