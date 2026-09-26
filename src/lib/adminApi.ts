/** Client for the orchestrator's platform admin API (`/platform-admin/*`). Every call
 * carries the signed-in account's token; the server refuses anyone who is not an admin. */
const RAW_BASE = (import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100");
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

export interface AgentUsage { agent_id: string; chats: number; users: number; messages: number; last_active: string | null }
export interface Overview {
  generated_at: string;
  users: { total: number; new_7d: number; new_30d: number; admins: number };
  revenue: {
    currency: string; total: number; last_30d: number; last_7d: number; paid_count: number; paying_customers: number;
    by_status: Record<string, number>; by_plan: { plan_id: string; label: string; count: number; amount: number }[];
    daily: { date: string; amount: number; count: number }[];
  };
  tokens: { outstanding_balance: number; credited_by_payments: number; users_out_of_tokens: number };
  activity: { conversations: number; messages: number; active_users_7d: number; by_agent: AgentUsage[] };
  agents: { registered: number; healthy: number };
  recent_signups: { id: string; name: string; email: string; created_at: string | null }[];
  recent_payments: { id: string; email: string; label: string; amount: number; status: string; created_at: string | null }[];
}
export interface AdminUserRow {
  id: string; name: string; email: string; mobile: string; is_admin: boolean; google: boolean; created_at: string | null;
  token_balance: number; paid_total: number; chats: number; agents_used: number; last_active: string | null;
}
export interface UserList { total: number; page: number; limit: number; users: AdminUserRow[] }
export interface UserPayment {
  id: string; label: string; plan_id: string; amount: number; currency: string; status: string; razorpay_order_id: string;
  razorpay_payment_id: string | null; created_at: string | null; paid_at: string | null; tokens: number;
}
export interface UserDetail {
  user: { id: string; name: string; email: string; mobile: string; is_admin: boolean; google: boolean; created_at: string | null; token_balance: number; consent_accepted_at: string | null; consent_policy_version: string | null };
  totals: { paid: number; payments: number; paid_payments: number; tokens_bought: number; conversations: number; messages: number };
  payments: UserPayment[];
  conversations: { id: string; agent_id: string; title: string; messages: number; pinned: boolean; created_at: string | null; updated_at: string | null; deleted: boolean }[];
  agent_progress: { agent_id: string; chat_id: string; step: string | null; updated_at: string | null }[];
}
export interface ConversationView { id: string; agent_id: string; title: string; messages: { role: string; content: string; time: string; created_at: string | null }[] }
export interface PaymentRow {
  id: string; user_id: string; email: string; name: string; label: string; amount: number; currency: string; status: string;
  razorpay_order_id: string; razorpay_payment_id: string | null; created_at: string | null; paid_at: string | null; tokens: number;
}
export interface PaymentList { total: number; page: number; limit: number; summary: Record<string, { count: number; amount: number }>; payments: PaymentRow[] }
export interface RegistryAgent {
  agent_name: string; version: string; endpoint: string; description: string; owner: string; plan_tier: string; status: string;
  last_heartbeat: string | null; heartbeat_age_seconds: number | null; online: boolean; actions: string[];
}
export interface AgentList { agents: RegistryAgent[]; chat_usage: AgentUsage[] }

async function get<T>(path: string, params: Record<string, string | number> = {}): Promise<T> {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== "" && value !== undefined).map(([k, v]) => [k, String(v)])).toString();
  const response = await fetch(`${BASE}/platform-admin${path}${query ? `?${query}` : ""}`, {
    headers: { Authorization: `Bearer ${localStorage.getItem("digidara_token") || ""}` },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "The admin request failed.");
  }
  return response.json();
}

export const fetchOverview = () => get<Overview>("/overview");
export const fetchUsers = (params: { search?: string; sort?: string; page?: number; limit?: number }) => get<UserList>("/users", params as Record<string, string | number>);
export const fetchUserDetail = (id: string) => get<UserDetail>(`/users/${encodeURIComponent(id)}`);
export const fetchConversation = (userId: string, conversationId: string) =>
  get<ConversationView>(`/users/${encodeURIComponent(userId)}/conversations/${encodeURIComponent(conversationId)}`);
export const fetchPayments = (params: { status?: string; search?: string; page?: number; limit?: number }) => get<PaymentList>("/payments", params as Record<string, string | number>);
export const fetchAgents = () => get<AgentList>("/agents");
