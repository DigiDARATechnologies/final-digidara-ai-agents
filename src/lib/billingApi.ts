const RAW_BASE = (import.meta.env.VITE_GATEWAY_API_URL !== undefined ? import.meta.env.VITE_GATEWAY_API_URL : "http://127.0.0.1:8100");
const BASE = RAW_BASE.endsWith("/") ? RAW_BASE.slice(0, -1) : RAW_BASE;

export interface PaymentRecord { id: string; plan_id: string; amount: number; currency: string; status: string; payment_id: string | null; created_at: string; }
export interface BillingSummary { plan: string; payments: PaymentRecord[]; }
export interface RazorpayOrder { key_id: string; order_id: string; amount: number; currency: string; name: string; }

function token() { return localStorage.getItem("digidara_token") || ""; }
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}`, ...init?.headers } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "Billing request failed."); }
  return response.json();
}
export const fetchBillingSummary = () => request<BillingSummary>("/billing/summary");
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

export interface TopupOrder extends RazorpayOrder { tokens: number }
export const fetchTokenBalance = () => request<{ balance: number }>("/billing/token-balance");
export const createTopupOrder = (amount_inr: number) => request<TopupOrder>("/billing/topup-order", { method: "POST", body: JSON.stringify({ amount_inr }) });
