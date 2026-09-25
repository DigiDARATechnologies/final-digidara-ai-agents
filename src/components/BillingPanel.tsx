import { useCallback, useEffect, useState } from "react";
import type { User } from "../types";
import {
  createBillingOrder, createTopupOrder, downloadInvoice, fetchBillingPlans, fetchBillingSummary, fetchTokenBalance,
  loadRazorpay, verifyBillingPayment, type BillingPlans, type BillingSummary, type RazorpayOrder,
} from "../lib/billingApi";

interface Props { open: boolean; user: User; onToast: (message: string) => void; }
type CheckoutResponse = { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string };
type RazorpayConstructor = new (options: Record<string, unknown>) => { open: () => void; on: (event: string, callback: (response: { error?: { description?: string } }) => void) => void };

const DEFAULT_CUSTOM_AMOUNT = "500";

/** Fixed grouping (1,200,000), so counts match the plan text the server sends whatever the browser locale. */
const tokens = (count: number) => count.toLocaleString("en-US");

/** Whole rupees on price cards ("₹499"); two decimals where it is a record ("₹10.00"). */
function money(amountMinor: number, currency = "INR", whole = false) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, ...(whole ? { minimumFractionDigits: amountMinor % 100 === 0 ? 0 : 2, maximumFractionDigits: 2 } : {}) }).format(amountMinor / 100);
}

export default function BillingPanel({ open, user, onToast }: Props) {
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [catalog, setCatalog] = useState<BillingPlans | null>(null);
  const [tokenBalance, setTokenBalance] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [invoiceBusy, setInvoiceBusy] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState(DEFAULT_CUSTOM_AMOUNT);

  const refresh = useCallback(async () => {
    const [summary, balance] = await Promise.all([
      fetchBillingSummary().catch(() => ({ plan: "free", plan_name: "Free", plan_expires_at: null, payments: [] }) as BillingSummary),
      fetchTokenBalance().then((result) => result.balance).catch(() => null),
    ]);
    setBilling(summary);
    setTokenBalance(balance);
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
    fetchBillingPlans().then(setCatalog).catch(() => setCatalog(null));
  }, [open, refresh]);

  async function pay(createOrder: () => Promise<RazorpayOrder & { tokens?: number }>, description: (order: RazorpayOrder) => string, tokensAdded: (order: RazorpayOrder & { tokens?: number }) => number | undefined) {
    setBusy(true);
    try {
      const order = await createOrder();
      await loadRazorpay();
      const Razorpay = (window as unknown as { Razorpay: RazorpayConstructor }).Razorpay;
      const checkout = new Razorpay({
        key: order.key_id, amount: order.amount, currency: order.currency, name: "DigiDARA", description: description(order), order_id: order.order_id,
        prefill: { name: user.name, email: user.email, contact: user.mobile }, theme: { color: "#365f91" },
        handler: async (response: CheckoutResponse) => {
          try {
            await verifyBillingPayment(response);
            window.dispatchEvent(new Event("digidara:billing-updated"));
            await refresh();
            const added = tokensAdded(order);
            onToast(added ? `Payment verified. ${tokens(added)} tokens added.` : "Payment verified.");
          } catch (error) { onToast((error as Error).message); } finally { setBusy(false); }
        },
        modal: { ondismiss: () => setBusy(false) },
      });
      checkout.on("payment.failed", (response) => { onToast(response.error?.description || "Payment failed."); setBusy(false); });
      checkout.open();
    } catch (error) { onToast((error as Error).message); setBusy(false); }
  }

  const buyPlan = (planId: string) => pay(() => createBillingOrder(planId), (order) => order.name, () => catalog?.plans.find((plan) => plan.id === planId)?.tokens);
  const payCustom = () => pay(() => createTopupOrder(Math.max(catalog?.custom.min_amount_inr ?? 1, Math.floor(Number(customInput)) || 0)), (order) => `${order.name} top-up`, (order) => order.tokens);

  async function saveInvoice(paymentId: string) {
    setInvoiceBusy(paymentId);
    try { await downloadInvoice(paymentId); } catch (error) { onToast((error as Error).message); } finally { setInvoiceBusy(null); }
  }

  const custom = catalog?.custom;
  const rate = custom?.tokens_per_rupee ?? 1000;
  // Keep the raw text so the field can be cleared and retyped; the amount is derived from it.
  const customAmount = Math.max(custom?.min_amount_inr ?? 1, Math.floor(Number(customInput)) || 0);
  const hasPlan = !!billing && billing.plan !== "free";
  const expires = billing?.plan_expires_at ? new Date(billing.plan_expires_at).toLocaleDateString() : null;

  return (
    <>
      <h2>Billing</h2>
      <div className="current-plan">
        <div>
          <small>Current plan</small>
          <strong>{hasPlan ? `DigiDARA ${billing?.plan_name}` : "DigiDARA Free"}</strong>
          <span>{hasPlan ? `Active until ${expires}. Plans are one-time payments; buy again to renew.` : "Pick a plan below for more tokens, or pay any amount you like."}</span>
        </div>
        <span className="plan-badge">{hasPlan ? "Active" : "Free"}</span>
      </div>

      <h3 className="settings-title">Token balance</h3>
      <div className="current-plan"><div><small>Available tokens</small><strong>{tokenBalance === null ? "-" : tokens(tokenBalance)}</strong><span>Each agent request costs a small number of tokens. Tokens never expire.</span></div></div>

      <h3 className="settings-title">Choose a plan</h3>
      {!catalog ? <p>Loading plans...</p> : (
        <div className="plan-grid">
          {catalog.plans.map((plan) => (
            <article key={plan.id} className={plan.popular ? "recommended" : undefined} data-plan={plan.id}>
              {plan.popular && <span>Most popular</span>}
              <h3>{plan.name}</h3>
              <strong>{money(plan.amount, plan.currency, true)} <small>one-time</small></strong>
              <p>{plan.description}</p>
              <ul className="plan-features">{plan.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
              <button disabled={busy} onClick={() => void buyPlan(plan.id)}>Buy {plan.name}</button>
            </article>
          ))}
          {custom && (
            <article data-plan="custom">
              <h3>{custom.name}</h3>
              <strong>{money(customAmount * 100, "INR", true)} <small>you choose</small></strong>
              <p>{custom.description}</p>
              <label className="custom-amount">Amount (INR)
                <input type="number" inputMode="numeric" min={custom.min_amount_inr} step={1} value={customInput} onChange={(event) => setCustomInput(event.target.value)} />
              </label>
              <ul className="plan-features"><li>{`${tokens(customAmount * rate)} tokens credited instantly`}</li><li>{`INR 1 = ${tokens(rate)} tokens`}</li></ul>
              <button disabled={busy} onClick={() => void payCustom()}>Pay {money(customAmount * 100, "INR", true)}</button>
            </article>
          )}
        </div>
      )}

      <h3 className="settings-title">Transaction history</h3>
      <div className="transaction-list with-invoice">
        {billing?.payments.length ? billing.payments.map((payment) => (
          <div key={payment.id}>
            <span><b>{payment.label}</b><small>{new Date(payment.created_at).toLocaleDateString()}</small></span>
            <span className={`payment-status ${payment.status}`}>{payment.status}</span>
            <strong>{money(payment.amount, payment.currency)}</strong>
            {payment.invoice_available
              ? <button type="button" className="invoice-btn" disabled={invoiceBusy === payment.id} onClick={() => void saveInvoice(payment.id)} aria-label={`Download invoice for ${payment.label}`}>{invoiceBusy === payment.id ? "..." : "Invoice"}</button>
              : <span className="invoice-placeholder" />}
          </div>
        )) : <p>No transactions yet.</p>}
      </div>
      <p className="secure-payment">Payments are securely processed by Razorpay. Card or UPI details never pass through DigiDARA servers.</p>
    </>
  );
}
