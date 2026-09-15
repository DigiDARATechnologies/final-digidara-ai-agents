import type { Agent } from "../types";

export const CATEGORIES = [
  "Top Picks",
  "Career",
  "Programming",
  "Research & Analysis",
  "Writing",
  "Productivity",
  "Education",
  "Business",
];

export const AGENTS: Agent[] = [
  {
    id: "career-guide", name: "Career Guidance Agent", icon: "🧭", color: "#22c55e", author: "DigiDARA", rating: 4.9,
    category: ["Top Picks", "Career"], featured: true,
    desc: "Maps your ideal career roadmap, identifies skill gaps and recommends the fastest path to your target role.",
    greeting: "Hi! I'm your Career Guidance Agent. Tell me your current role and where you'd like to be in 2 years, and I'll sketch a roadmap for you.",
  },
  {
    id: "leetcode", name: "LeetCode / DSA Agent", icon: "⌨️", color: "#eab308", author: "DigiDARA", rating: 4.7,
    category: ["Top Picks", "Programming", "Education"], featured: true, kind: "codeforge", backendAgentName: "codeforge_agent",
    desc: "Practice real coding problems by course and topic, run and submit against sandboxed tests, and get AI tutor guidance when you're stuck.",
    greeting: "Ready to practice? Connecting you now…",
  },
  {
    id: "job-fetch", name: "Job Fetching Agent", icon: "🔎", color: "#3b82f6", author: "DigiDARA", rating: 4.6,
    category: ["Career", "Productivity"], featured: false, kind: "job-fetch", backendAgentName: "job_agent",
    desc: "Continuously scans job boards for roles matching your profile and ranks them by an explainable fit score.",
    greeting: "Connecting you to the Job Fetching Agent…",
  },
  {
    id: "research", name: "Research Agent", icon: "📚", color: "#06b6d4", author: "DigiDARA", rating: 4.8,
    category: ["Research & Analysis", "Top Picks"], featured: false,
    desc: "Digs through papers, articles and data to produce well-cited summaries on any topic you throw at it.",
    greeting: "What topic should I research for you today? I can summarize papers, compare viewpoints or fact-check claims.",
  },
  {
    id: "content-writer", name: "Content Writer Agent", icon: "✍️", color: "#ec4899", author: "DigiDARA", rating: 4.7,
    category: ["Writing"], featured: false,
    desc: "Drafts blog posts, social copy and email campaigns in your brand voice, ready to publish.",
    greeting: "What are we writing today — a blog post, a LinkedIn post, or marketing copy? Give me the topic and tone.",
  },
  {
    id: "data-analyst", name: "Data Analyst Agent", icon: "📊", color: "#14b8a6", author: "DigiDARA", rating: 4.6,
    category: ["Research & Analysis", "Business"], featured: false,
    desc: "Analyzes spreadsheets and datasets, surfaces trends, and builds clear charts and summaries.",
    greeting: "Share your data or describe the dataset, and tell me what question you're trying to answer.",
  },
  {
    id: "aptitude", name: "Aptitude Trainer Agent", icon: "🧮", color: "#f97316", author: "DigiDARA", rating: 4.5,
    category: ["Top Picks", "Education"], featured: true, kind: "aptitude", backendAgentName: "aptitude_agent",
    desc: "Drills quantitative aptitude, logical reasoning and verbal ability with timed practice sets.",
    greeting: "Let's practice! Pick a topic: quantitative aptitude, logical reasoning, or verbal ability.",
  },
  {
    id: "video-ai", name: "Video AI Agent", icon: "🎬", color: "#6366f1", author: "DigiDARA", rating: 4.4,
    category: ["Productivity"], featured: false,
    desc: "Generates and edits short-form videos from a script or prompt, complete with captions and voiceover.",
    greeting: "Describe the video you want — topic, length and style — and I'll put together a first cut.",
  },
  {
    id: "biz-strategy", name: "Business Strategy Agent", icon: "🤝", color: "#0ea5e9", author: "DigiDARA", rating: 4.6,
    category: ["Business"], featured: false,
    desc: "Helps evaluate business ideas, build go-to-market plans and model pricing strategy.",
    greeting: "What business problem are we tackling — a new product idea, GTM plan, or pricing strategy?",
  },
  {
    id: "code-assist", name: "Coding Assistant Agent", icon: "💻", color: "#7c3aed", author: "DigiDARA", rating: 4.9,
    category: ["Programming", "Top Picks"], featured: false,
    desc: "Writes, reviews and debugs code across languages, with clear explanations for every change.",
    greeting: "What are you building? Paste your code or describe the bug and I'll help you work through it.",
  },
  {
    id: "capstone-project", name: "Capstone Project Agent", icon: "🎓", color: "#16a34a", author: "DigiDARA", rating: 4.9,
    category: ["Top Picks", "Education"], featured: true, kind: "capstone", backendAgentName: "capstone_project_agent",
    desc: "Runs your capstone project end-to-end: eligibility check, topic pick, 7-day timer, and graded submission review.",
    greeting: "Hi! I'm the Capstone Project Agent. Let's check your eligibility first — what's your full name?",
  },
  {
    id: "communication-coach", name: "Communication Coach Agent", icon: "🗣️", color: "#f43f5e", author: "DigiDARA", rating: 4.8,
    category: ["Top Picks", "Education"], featured: true, kind: "communication", backendAgentName: "communication_agent",
    desc: "Coaches Pronunciation, Speaking and Writing through AI-scored practice loops, daily challenges, and a progress dashboard.",
    greeting: "Ready to practice? Connecting you now…",
  },
];

// Strategy F Resume Builder: the React app calls it only via the registry gateway.
AGENTS.push({
  id: "resume-builder", name: "Resume Builder Agent", icon: "📄", color: "#0f766e", author: "DigiDARA", rating: 4.9,
  category: ["Top Picks", "Career", "Writing"], featured: true, kind: "resume-builder", backendAgentName: "resume_builder_agent",
  desc: "Create, import, analyze, improve, preview, and export ATS-friendly resumes through a guided workflow.",
  greeting: "Connecting you to Resume Builder...",
});

// Strategy F Certificate Agent: the React app calls it only via the registry gateway.
AGENTS.push({
  id: "certificate-agent", name: "AI Certification Agent", icon: "📜", color: "#8b5cf6", author: "DigiDARA", rating: 4.9,
  category: ["Top Picks", "Education"], featured: true, kind: "certificate", backendAgentName: "certificate_agent",
  desc: "AI-powered certification exam generator, interactive chat assessment, leaderboard, and PDF certificate issuing system.",
  greeting: "Connecting you to AI Certification Agent...",
});



export const DEFAULT_AGENT: Agent = {
  id: "digidara-assistant",
  name: "DigiDARA Assistant",
  icon: "⚡",
  color: "#0e7490",
  greeting: "Hi, I'm your DigiDARA Assistant. Ask me anything, or open a specialized agent from the store for focused help.",
};

export const CANNED_REPLIES = [
  "Got it — here's a quick take: break this into smaller steps first, then I can go deeper on whichever part matters most.",
  "Great question. Based on what you shared, I'd suggest starting with the highest-impact step and iterating from there.",
  "Here's a suggestion: let's define the goal clearly first, then I'll tailor the next steps to get you there faster.",
  "I can help with that. Could you share a bit more detail so I can give you a precise, actionable answer?",
  "Noted! I've factored that in — here's what I'd recommend as your next move.",
];

export function findAgent(id: string): Agent | undefined {
  if (id === DEFAULT_AGENT.id) return DEFAULT_AGENT;
  return AGENTS.find((a) => a.id === id);
}

/** Maps the orchestrator router's chosen `agent_name` (manifest.json's
 * registry identity) back to the matching store card, for the general
 * chat's LLM-routed handoff. */
export function findAgentByBackendName(agentName: string): Agent | undefined {
  return AGENTS.find((a) => a.backendAgentName === agentName);
}
