const RAW_BASE = (import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100");
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

export interface PaymentRecord { id: string; plan_id: string; label: string; amount: number; currency: string; status: string; payment_id: string | null; created_at: string; invoice_available: boolean; }
export interface BillingSummary { plan: string; plan_name: string; plan_expires_at: string | null; payments: PaymentRecord[]; }
/** `payment_page_url`: the plan is paid on DigiDARA's Razorpay payment page
 * (tokens are added by the server once Razorpay confirms), not in-app. */
export interface PlanOffer { id: string; name: string; amount: number; currency: string; period: string; tokens: number; bonus_percent: number; description: string; features: string[]; popular: boolean; payment_page_url?: string | null; }
export interface BillingPlans { plans: PlanOffer[]; }
export interface RazorpayOrder { key_id: string; order_id: string; amount: number; currency: string; name: string; }

function token() { return localStorage.getItem("digidara_token") || ""; }
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}`, ...init?.headers } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "Billing request failed."); }
  return response.json();
}
export const fetchBillingSummary = () => request<BillingSummary>("/billing/summary");
export const fetchBillingPlans = () => request<BillingPlans>("/billing/plans");
export const createBillingOrder = (plan_id: string) => request<RazorpayOrder>("/billing/orders", { method: "POST", body: JSON.stringify({ plan_id }) });
export const verifyBillingPayment = (body: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }) => request<{ verified: boolean; plan: string }>("/billing/verify", { method: "POST", body: JSON.stringify(body) });

export function loadRazorpay(): Promise<void> {
  if ((window as Window & { Razorpay?: unknown }).Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Unable to load Razorpay Checkout."));
    document.head.appendChild(script);
  });
}

export const fetchTokenBalance = () => request<{ balance: number }>("/billing/token-balance");
export interface MonthlyUsage { month_start: string; tokens_used: number; requests: number; balance: number; limit: number; agents: Array<{ agent_name: string; tokens: number; requests: number }>; }
/** This calendar month's billed usage (in the user's own timezone) and the dynamic limit: used + balance left. */
export const fetchMonthlyUsage = () => request<MonthlyUsage>(`/billing/usage-month?offset_minutes=${-new Date().getTimezoneOffset()}`);

/** Downloads a paid payment's PDF invoice. The endpoint needs the bearer
 * token, so this fetches the file and saves it, rather than linking to it. */
export async function downloadInvoice(paymentId: string): Promise<string> {
  const response = await fetch(`${BASE}/billing/invoices/${encodeURIComponent(paymentId)}`, { headers: { Authorization: `Bearer ${token()}` } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "Could not download the invoice."); }
  const filename = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "")?.[1] || "invoice.pdf";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = filename;
  document.body.appendChild(link); link.click(); link.remove();
  URL.revokeObjectURL(url);
  return filename;
}
