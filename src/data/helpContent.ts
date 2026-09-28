export interface FaqItem {
  q: string;
  a: string;
  topic: "Getting started" | "Agents" | "Files & uploads" | "Chats" | "Appearance" | "Account & privacy";
}

export const SUPPORT_EMAIL = "support@digidaraaiagents.com";

export const FAQ: FaqItem[] = [
  {
    topic: "Getting started",
    q: "What is DigiDARA Agents?",
    a: "DigiDARA Agents is a workspace of specialised AI agents. Each agent is built for one kind of job, such as practising coding problems, preparing for interviews, building a resume or planning a career, so you get focused help instead of a one-size-fits-all chat.",
  },
  {
    topic: "Getting started",
    q: "How do I start using an agent?",
    a: "Click New chat in the sidebar and type what you need, or open My agents to browse every agent and pick one. Each agent opens its own workspace with a welcome message.",
  },
  {
    topic: "Getting started",
    q: "What is the difference between DigiDARA Agents and My agents?",
    a: "DigiDARA Agents is your home screen with the main chat box. My agents is the full catalogue where you can search and filter agents by category.",
  },
  {
    topic: "Getting started",
    q: "How do I get back to the home screen?",
    a: "Click DigiDARA Agents at the top of the sidebar menu, or click New chat. The arrow beside the logo collapses the sidebar when you want more room.",
  },
  {
    topic: "Agents",
    q: "How do I find the right agent for my goal?",
    a: "Open My agents and use the search box or the category tabs (Top Picks, Career, Programming, Research & Analysis, Writing, Productivity, Education and Business). You can also read the descriptions in the Meet the agents section on this page.",
  },
  {
    topic: "Agents",
    q: "Can I use more than one agent in the same day?",
    a: "Yes. Every conversation is separate, so you can start a chat with one agent, then click New chat and open another. All of your conversations stay in History.",
  },
  {
    topic: "Agents",
    q: "Which agents help with getting a job?",
    a: "The Career Guidance Agent maps your path, the Resume Builder Agent creates ATS-friendly resumes, the Job Fetching Agent finds and ranks matching roles, and the Mock Interview Agent lets you practise interviews. The Aptitude Trainer and Communication Coach agents help you prepare for tests and speak with confidence.",
  },
  {
    topic: "Agents",
    q: "Which agents help me learn and practise?",
    a: "The LeetCode / DSA Agent for coding practice, the Aptitude Trainer Agent for timed practice sets, the Communication Coach Agent for pronunciation, speaking and writing, the Capstone Project Agent for a guided project, and the AI Certification Agent for exams and certificates.",
  },
  {
    topic: "Files & uploads",
    q: "Can I upload files to an agent?",
    a: "Some agents accept files. Use the plus button in the message box once you are chatting with the agent. Capstone Project accepts .docx and .zip files, Resume Builder accepts .pdf, .doc, .docx and .txt files, and Job Fetching accepts .pdf, .doc and .docx files.",
  },
  {
    topic: "Files & uploads",
    q: "Why does the plus button ask me to start a chat first?",
    a: "Attachments only work inside a chat with an agent that supports them. Open one of those agents, then use the plus button again.",
  },
  {
    topic: "Chats",
    q: "Where are my previous conversations?",
    a: "They are listed under History in the left sidebar, newest first. Click any conversation to reopen it.",
  },
  {
    topic: "Chats",
    q: "How do I rename, pin or delete a conversation?",
    a: "Hover a conversation in History and click the three dots. You can rename it, pin it to the top, or delete it.",
  },
  {
    topic: "Chats",
    q: "Can I speak instead of typing?",
    a: "Yes. Use the microphone button in the message box to dictate your message. Your browser will ask for microphone permission the first time.",
  },
  {
    topic: "Chats",
    q: "How can I get better answers from an agent?",
    a: "Be specific about your goal, your current level and what you want back, for example the role you are targeting or the topic you want to practise. If an answer is not quite right, send a follow-up message to refine it.",
  },
  {
    topic: "Appearance",
    q: "How do I switch between dark and light theme?",
    a: "Click the sun or moon icon in the top bar. Your choice is remembered on this device.",
  },
  {
    topic: "Appearance",
    q: "What is the moving strip of agents in the top bar?",
    a: "It shows every available agent as they glide past. Hover over it to pause the strip.",
  },
  {
    topic: "Account & privacy",
    q: "Where can I read the Terms of Service and Privacy Policy?",
    a: "Open your profile menu at the bottom of the sidebar, hover Help, and choose Terms of Service or Privacy Policy.",
  },
  {
    topic: "Account & privacy",
    q: "How do I manage my account and data?",
    a: "Open your profile menu and choose Profile or Settings. For requests that are not available in Settings, email privacy@digidaraaiagents.com.",
  },
  {
    topic: "Account & privacy",
    q: "I forgot my password. What should I do?",
    a: "On the login page choose Forgot password? and send us the pre-filled email. Our team will help you reset it.",
  },
  {
    topic: "Account & privacy",
    q: "How do I log out?",
    a: "Open your profile menu at the bottom of the sidebar and choose Log out.",
  },
];

export interface ReleaseSection {
  label: "New" | "Improved" | "Fixed";
  items: string[];
}

export interface ReleaseNote {
  date: string;
  title: string;
  summary: string;
  sections: ReleaseSection[];
}

export const RELEASES: ReleaseNote[] = [
  {
    date: "September 25, 2026",
    title: "A brand new look and feel",
    summary:
      "We redesigned the whole DigiDARA Agents experience: a sharper dark theme, a clean light theme, a new login, and a friendlier sidebar. Everything you already use works exactly as before.",
    sections: [
      {
        label: "New",
        items: [
          "Dark and light themes. Switch any time with the sun or moon button in the top bar. Your choice is remembered on this device.",
          "A pure black dark theme designed to be easy on the eyes during long sessions.",
          "A live agent strip in the top bar that glides across all available agents.",
          "A Help menu in your profile with a searchable Help center, Release notes, Contact support, Report a bug, Terms of Service and Privacy Policy.",
          "Contact support and Report a bug pages. Bug reports automatically include your browser, screen size and theme so we can fix issues faster.",
          "An animated glowing border around the message box that follows you into every chat.",
        ],
      },
      {
        label: "Improved",
        items: [
          "A redesigned login and sign-up page with the DigiDARA blue and gold branding.",
          "A cleaner sidebar with crisp line icons, brighter text and a larger DigiDARA logo that matches your theme.",
          "Your profile now sits at the bottom of the sidebar, and its menu shows your name, plan, Profile, Settings, Help and Log out.",
          "A modern, consistent typeface across the whole app for easier reading.",
          "Chat conversations, buttons, cards and forms restyled so they look right in both themes.",
          "A tidier top bar. The connection badge now only appears when something needs your attention.",
        ],
      },
      {
        label: "Fixed",
        items: [
          "Sidebar text, including your name and the selected chat, is now clearly visible in the light theme.",
          "Selected text on the login page is now readable instead of fading out.",
          "The sidebar logo is no longer squeezed to a tiny size.",
        ],
      },
    ],
  },
];

export interface WorkflowStep { title: string; body: string }
export interface AgentWorkflow { summary: string; steps: WorkflowStep[]; tips: string[] }

/** Step-by-step "how it works" for each live agent, keyed by agent id. */
export const AGENT_WORKFLOWS: Record<string, AgentWorkflow> = {
  aptitude: {
    summary: "Timed practice for quantitative aptitude, logical reasoning and verbal ability.",
    steps: [
      { title: "Pick a topic and level", body: "Choose the section you want to drill (quantitative, logical or verbal) and how hard the set should be." },
      { title: "Start a timed set", body: "Questions appear one at a time in the chat with a running timer, like a real placement test." },
      { title: "Answer and move around", body: "Select an option for each question. You can jump between questions and change an answer before you submit." },
      { title: "Submit and review", body: "Get your score, see which answers were right or wrong, and read the explanation for each one." },
      { title: "Repeat on weak areas", body: "Start another set on the topics you missed until your accuracy improves." },
    ],
    tips: ["Try to answer within the time limit, because speed is part of aptitude tests.", "Review the explanations even for questions you got right."],
  },
  "certificate-agent": {
    summary: "Generates a certification exam, assesses you in chat, and issues a PDF certificate when you pass.",
    steps: [
      { title: "Choose a certification", body: "Pick the subject or skill you want to be certified in." },
      { title: "Take the exam", body: "The agent generates a fresh exam and asks the questions in an interactive chat assessment." },
      { title: "Get scored", body: "Your answers are graded as soon as you finish, with a pass or fail result." },
      { title: "Download your certificate", body: "If you pass, a PDF certificate is issued that you can download and share." },
      { title: "Check the leaderboard", body: "See how your score ranks against other learners." },
    ],
    tips: ["Find past attempts and certificates under My Certificates in your history.", "You can retake an exam to improve your score."],
  },
  leetcode: {
    summary: "Practice real coding problems with a sandboxed runner and an AI tutor.",
    steps: [
      { title: "Choose a course and topic", body: "Pick a language or subject, then a topic such as SQL, JavaScript or CSS." },
      { title: "Open a problem", body: "Read the problem statement, examples and constraints. Coding and multiple-choice problems are both supported." },
      { title: "Write and run your code", body: "Run your solution against sample tests in a safe sandbox and see the output or errors straight away." },
      { title: "Submit for grading", body: "Submit to run the full set of tests and see which ones pass." },
      { title: "Ask the AI tutor", body: "If you are stuck, ask for a hint or an explanation without being handed the whole answer." },
    ],
    tips: ["Run often: small steps make bugs easier to find.", "Use the tutor for hints first, then the full explanation."],
  },
  "communication-coach": {
    summary: "Coaches pronunciation, speaking and writing with AI-scored practice.",
    steps: [
      { title: "Pick a skill", body: "Choose Pronunciation, Speaking or Writing practice." },
      { title: "Do a practice round", body: "Read, speak or write to the prompt. Use the mic button to record your voice." },
      { title: "Get AI scoring", body: "Your attempt is scored and you get specific feedback on what to improve." },
      { title: "Repeat the loop", body: "Try again with the feedback in mind. Each attempt is saved." },
      { title: "Track your progress", body: "Open the dashboard to see your scores, daily challenges and progress over time." },
    ],
    tips: ["Allow microphone access in your browser for speaking practice.", "A short daily session beats one long one."],
  },
  "job-fetch": {
    summary: "Finds job openings that match your profile and ranks them by how well they fit you.",
    steps: [
      { title: "Tell it about you", body: "Share your role, skills, experience and preferred location in a short onboarding chat." },
      { title: "Search job boards", body: "The agent scans job boards for roles that match what you asked for." },
      { title: "See a fit score", body: "Each job is ranked with an explainable fit score, so you know why it matched." },
      { title: "Refine your search", body: "Ask for a different location, seniority or skill and the list updates." },
      { title: "Apply", body: "Open the listings you like and apply from the original posting." },
    ],
    tips: ["The more specific your skills, the better the matches.", "Ask why a job scored low to see what is missing."],
  },
  "mock-interview": {
    summary: "AI-driven technical and HR mock interviews with scores and feedback.",
    steps: [
      { title: "Set up the interview", body: "Choose the role and whether you want a technical or HR interview." },
      { title: "Answer the questions", body: "Questions are asked one at a time. Type your answer or use the mic button." },
      { title: "Get feedback on each answer", body: "Every answer is scored, with notes on strengths and what to improve." },
      { title: "See your report", body: "At the end you get a full report with overall scores you can review later." },
      { title: "Practise again", body: "Retake the interview and compare against your previous attempt." },
    ],
    tips: ["Answer out loud first, then type it. It builds fluency.", "Use the report to pick what to work on next."],
  },
  "capstone-project": {
    summary: "Runs your capstone project end to end, from topic selection to a graded review.",
    steps: [
      { title: "Eligibility check", body: "The agent confirms you are eligible to start a capstone project." },
      { title: "Pick your topic", body: "Choose a project topic and confirm the requirements." },
      { title: "Build within the timer", body: "You get a 7-day window to build the project and prepare your files." },
      { title: "Submit your work", body: "Upload your report and files, including the required screenshots, in the chat." },
      { title: "Review and viva", body: "Your submission is reviewed and graded, with a viva Q&A. If it is not accepted, you get clear revision notes and can resubmit." },
      { title: "Get certified", body: "On passing, you receive your capstone certificate." },
    ],
    tips: ["Read the example files the agent shares before you start.", "Keep your screenshots clear, because they are checked during review."],
  },
  "resume-builder": {
    summary: "Create, import, analyse, improve and export ATS-friendly resumes.",
    steps: [
      { title: "Create or import", body: "Start a new resume from scratch, or upload your existing one." },
      { title: "Analyse it", body: "The agent checks structure, wording and ATS compatibility and points out gaps." },
      { title: "Improve the content", body: "Accept suggested rewrites for summaries, bullet points and skills." },
      { title: "Preview", body: "See exactly how the finished resume will look before you save it." },
      { title: "Export", body: "Download the final, ATS-friendly resume ready to send." },
    ],
    tips: ["Tailor the resume to each job by pasting the job description.", "Keep bullet points short and results-focused."],
  },
};
