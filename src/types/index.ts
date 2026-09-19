export interface Agent {
  id: string;
  name: string;
  icon: string;
  color: string;
  author?: string;
  rating?: number;
  category?: string[];
  featured?: boolean;
  desc?: string;
  greeting: string;
  /**
   * "capstone" routes chat turns through the Capstone FastAPI backend.
   * "codeforge" routes chat turns through the CodeForge Flask backend.
   * "communication" routes chat turns through the Communication Coach Flask
   * backend. All go through the same orchestrator gateway; absent means
   * canned replies.
   */
  kind?: "capstone" | "codeforge" | "aptitude" | "communication" | "resume-builder" | "certificate" | "job-fetch" | "mock-interview";
  /** This agent's registry name on the orchestrator (manifest.json's
   * `agent_name`) — lets the general chat's LLM router hand a matched
   * message off to this agent's dedicated flow. Absent for agents with no
   * `kind` (nothing to hand off to yet). */
  backendAgentName?: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  mobile: string;
  initial: string;
  isAdmin?: boolean;
}

export interface ChatOption {
  label: string;
  value: string;
  description?: string;
}

export interface ChatMessage {
  role: "user" | "agent";
  text: string;
  time: string;
  options?: ChatOption[];
  /** Only set on user messages in a flow-driven chat (Capstone/CodeForge/
   * Communication): a reference to that agent's flow state exactly as it
   * stood right before this message was processed. Editing this message
   * later resumes the flow from here with the edited text, instead of from
   * whatever the flow has advanced to since — e.g. editing a Capstone
   * topic-request message regenerates topics from the new wording, rather
   * than the conversation just breaking. Flow-state setters always produce
   * a new object (never mutate in place), so holding a reference here stays
   * valid indefinitely — no cloning needed. */
  stateSnapshot?: unknown;
}

export interface Chat {
  id: string;
  agentId: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
  pinned?: boolean;
}

export type View = "store" | "chat" | "admin";
