import type { AgentStateId } from "./agentStateApi";

export const AGENT_STATE_IDS: AgentStateId[] = [
  "capstone", "codeforge", "aptitude", "communication", "resume_builder", "certificate", "job_fetch",
];

// Where each agent's states used to live in browser storage (one map per learner).
const LEGACY_KEY_PREFIX: Record<AgentStateId, string> = {
  capstone: "digidara_capstone_",
  codeforge: "digidara_codeforge_",
  aptitude: "digidara_aptitude_",
  communication: "digidara_communication_",
  resume_builder: "digidara_resume_builder_",
  certificate: "digidara_certificate_",
  job_fetch: "digidara_job_fetch_",
};

export type StateMap = Record<string, Record<string, unknown>>;

const normalizeEmail = (email: string) => email.trim().toLowerCase();

export const legacyKey = (agentId: AgentStateId, email: string) => `${LEGACY_KEY_PREFIX[agentId]}${normalizeEmail(email)}`;
export const secretsKey = (email: string) => `digidara_agent_secrets_${normalizeEmail(email)}`;

// Agent session credentials that flow states carry. They are short-lived and the
// browser needs them to keep a chat going, but they must never be sent to the database.
export const SECRET_FIELDS = ["sessionToken", "authToken", "token"] as const;

export function splitSecrets(state: Record<string, unknown>): { clean: Record<string, unknown>; secrets: Record<string, string> } {
  const clean: Record<string, unknown> = { ...state };
  const secrets: Record<string, string> = {};
  for (const field of SECRET_FIELDS) {
    if (typeof clean[field] === "string" && clean[field]) secrets[field] = clean[field] as string;
    delete clean[field];
  }
  return { clean, secrets };
}

export function mergeSecrets(state: Record<string, unknown>, secrets: Record<string, string> | undefined): Record<string, unknown> {
  return secrets ? { ...state, ...secrets } : state;
}

export type SecretsStore = Record<string, Record<string, Record<string, string>>>; // agent -> chat -> secrets

export function readSecrets(email: string): SecretsStore {
  try {
    const parsed = JSON.parse(localStorage.getItem(secretsKey(email)) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function writeSecrets(email: string, store: SecretsStore): void {
  try {
    if (Object.values(store).every((chats) => Object.keys(chats).length === 0)) localStorage.removeItem(secretsKey(email));
    else localStorage.setItem(secretsKey(email), JSON.stringify(store));
  } catch {
    // Storage full or blocked: the chat keeps working, it just won't survive a reload.
  }
}

export function readLegacyStates(agentId: AgentStateId, email: string): StateMap {
  try {
    const parsed = JSON.parse(localStorage.getItem(legacyKey(agentId, email)) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function removeLegacyStates(agentId: AgentStateId, email: string): void {
  localStorage.removeItem(legacyKey(agentId, email));
}

export type Snapshot = Record<string, Record<string, string>>; // agent -> chat -> JSON of the last state the server has

export interface Change {
  agentId: AgentStateId;
  chatId: string;
  json: string;
  state: Record<string, unknown>;
}

export interface Removal {
  agentId: AgentStateId;
  chatId: string;
}

export function diffStates(
  snapshot: Snapshot,
  current: Partial<Record<AgentStateId, StateMap>>,
  serialize: (agentId: AgentStateId, state: Record<string, unknown>) => Record<string, unknown>,
): { changes: Change[]; removals: Removal[]; secrets: SecretsStore } {
  const changes: Change[] = [];
  const removals: Removal[] = [];
  const secrets: SecretsStore = {};
  for (const agentId of AGENT_STATE_IDS) {
    const chats = current[agentId] || {};
    const known = snapshot[agentId] || {};
    for (const [chatId, raw] of Object.entries(chats)) {
      if (!raw || typeof raw !== "object") continue;
      const { clean, secrets: chatSecrets } = splitSecrets(serialize(agentId, raw));
      if (Object.keys(chatSecrets).length) (secrets[agentId] ||= {})[chatId] = chatSecrets;
      const json = JSON.stringify(clean);
      if (known[chatId] !== json) changes.push({ agentId, chatId, json, state: clean });
    }
    for (const chatId of Object.keys(known)) {
      if (!(chatId in chats)) removals.push({ agentId, chatId });
    }
  }
  return { changes, removals, secrets };
}
