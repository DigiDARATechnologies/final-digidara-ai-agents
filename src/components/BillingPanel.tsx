import { useCallback, useEffect, useState } from "react";
import type { User } from "../types";
import {
  createBillingOrder, downloadInvoice, fetchBillingPlans, fetchBillingSummary, fetchTokenBalance,
  loadRazorpay, verifyBillingPayment, type BillingPlans, type BillingSummary, type PlanOffer, type RazorpayOrder,
} from "../lib/billingApi";
import { formatPoints } from "../lib/points";

interface Props { open: boolean; user: User; onToast: (message: string) => void; }
type CheckoutResponse = { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string };
type RazorpayConstructor = new (options: Record<string, unknown>) => { open: () => void; on: (event: string, callback: (response: { error?: { description?: string } }) => void) => void };

/** Whole rupees on price cards ("₹499"); two decimals where it is a record ("₹10.00"). */
function money(amountMinor: number, currency = "INR", whole = false) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, ...(whole ? { minimumFractionDigits: amountMinor % 100 === 0 ? 0 : 2, maximumFractionDigits: 2 } : {}) }).format(amountMinor / 100);
}

// Same rule as the server (billing/routes.py GSTIN_PATTERN).
const GSTIN_PATTERN = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

export default function BillingPanel({ open, user, onToast }: Props) {
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [catalog, setCatalog] = useState<BillingPlans | null>(null);
  const [pointsBalance, setPointsBalance] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [invoiceBusy, setInvoiceBusy] = useState<string | null>(null);
  const [pagePlan, setPagePlan] = useState<PlanOffer | null>(null);
  const [gstin, setGstin] = useState("");
  const gstinValue = gstin.replace(/\s+/g, "").toUpperCase();
  const gstinError = gstinValue && !GSTIN_PATTERN.test(gstinValue) ? "Enter a valid 15-character GSTIN, e.g. 33ABCDE1234F1Z5, or leave it empty." : "";

  const refresh = useCallback(async () => {
    const [summary, balance] = await Promise.all([
      fetchBillingSummary().catch(() => ({ plan: "free", plan_name: "Free", plan_expires_at: null, payments: [] }) as BillingSummary),
      fetchTokenBalance().then((result) => result.points).catch(() => null),
    ]);
    setBilling(summary);
    setPointsBalance(balance);
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
    fetchBillingPlans().then(setCatalog).catch(() => setCatalog(null));
  }, [open, refresh]);

  // A payment-page purchase finishes in another tab; pick up the new balance
  // and history when the learner comes back.
  useEffect(() => {
    if (!open || !pagePlan) return;
    const onFocus = () => { void refresh(); window.dispatchEvent(new Event("digidara:billing-updated")); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [open, pagePlan, refresh]);

  async function pay(createOrder: () => Promise<RazorpayOrder>, description: (order: RazorpayOrder) => string, pointsAdded: () => number | undefined) {
    setBusy(true);
    try {
      const order = await createOrder();
      await loadRazorpay();
      const Razorpay = (window as unknown as { Razorpay: RazorpayConstructor }).Razorpay;
      const checkout = new Razorpay({
        key: order.key_id, amount: order.amount, currency: order.currency, name: "DigiDARA", description: description(order), order_id: order.order_id,
        // The server sends this account's own details; the email is locked so
        // the payment is always made as this account.
        prefill: order.prefill ?? { name: user.name, email: user.email, contact: user.mobile },
        readonly: order.readonly ?? { email: true }, theme: { color: "#365f91" },
        handler: async (response: CheckoutResponse) => {
          try {
            await verifyBillingPayment(response);
            window.dispatchEvent(new Event("digidara:billing-updated"));
            await refresh();
            const added = pointsAdded();
            onToast(added ? `Payment verified. ${formatPoints(added)} points added.` : "Payment verified.");
          } catch (error) { onToast((error as Error).message); } finally { setBusy(false); }
        },
        modal: { ondismiss: () => setBusy(false) },
      });
      checkout.on("payment.failed", (response) => { onToast(response.error?.description || "Payment failed."); setBusy(false); });
      checkout.open();
    } catch (error) { onToast((error as Error).message); setBusy(false); }
  }

  const buyPlan = (plan: PlanOffer) => {
    if (plan.payment_page_url) {
      // Paid on DigiDARA's Razorpay page; the server credits the account whose
      // email is entered there, once Razorpay confirms the payment.
      window.open(plan.payment_page_url, "_blank", "noopener,noreferrer");
      setPagePlan(plan);
      return;
    }
    if (gstinError) { onToast(gstinError); return; }
    void pay(() => createBillingOrder(plan.id, gstinValue || undefined), (order) => order.name, () => plan.points);
  };

  async function saveInvoice(paymentId: string) {
    setInvoiceBusy(paymentId);
    try { await downloadInvoice(paymentId); } catch (error) { onToast((error as Error).message); } finally { setInvoiceBusy(null); }
  }

  const hasPlan = !!billing && billing.plan !== "free";
  const expires = billing?.plan_expires_at ? new Date(billing.plan_expires_at).toLocaleDateString() : null;

  return (
    <>
      <h2>Billing</h2>
      <div className="current-plan">
        <div>
          <small>Current Plan</small>
          <strong>{hasPlan ? `DigiDARA ${billing?.plan_name}` : "DigiDARA Free"}</strong>
          <span>{hasPlan ? `Active until ${expires}. Plans are one-time payments; buy again to renew.` : "Pick a plan below for more points."}</span>
        </div>
        <span className="plan-badge">{hasPlan ? "Active" : "Free"}</span>
      </div>

      <h3 className="settings-title">Points Balance</h3>
      <div className="current-plan"><div><small>Available Points</small><strong>{pointsBalance === null ? "-" : formatPoints(pointsBalance)}</strong><span>Each agent request uses a few points. Points never expire.</span></div></div>

      <h3 className="settings-title">Choose a Plan</h3>
      <p className="billing-account-note">Paying as <b>{user.email}</b>. Points are added to this account.</p>
      <label className="billing-gstin">
        <span>GSTIN (optional, for a business tax invoice)</span>
        <input value={gstin} onChange={(event) => setGstin(event.target.value)} placeholder="e.g. 33ABCDE1234F1Z5" maxLength={20} autoComplete="off" aria-invalid={!!gstinError} />
        {gstinError && <small role="alert">{gstinError}</small>}
      </label>
      {!catalog ? <p>Loading plans...</p> : (
        <div className="plan-grid">
          {catalog.plans.map((plan) => (
            <article key={plan.id} className={plan.popular ? "recommended" : undefined} data-plan={plan.id}>
              {plan.popular && <span>Most Popular</span>}
              <h3>{plan.name}</h3>
              <strong>{money(plan.amount, plan.currency, true)} <small>one-time</small></strong>
              {plan.amount_with_gst && plan.amount_with_gst !== plan.amount && <small className="plan-gst">{money(plan.amount_with_gst, plan.currency)} incl. {plan.gst_percent || 18}% GST</small>}
              <p>{plan.description}</p>
              <ul className="plan-features">{plan.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
              {plan.payment_page_url && <p className="plan-page-note">Opens Razorpay in a new tab. Pay with <b>{user.email}</b> so the points reach this account.</p>}
              <button disabled={busy} onClick={() => buyPlan(plan)}>Buy {plan.name}</button>
            </article>
          ))}
        </div>
      )}
      {pagePlan && (
        <p className="plan-page-status" role="status">
          Finish the {money(pagePlan.amount, pagePlan.currency, true)} payment in the Razorpay tab using {user.email}. Your {formatPoints(pagePlan.points)} points appear here once Razorpay confirms it.{" "}
          <button type="button" className="invoice-btn" onClick={() => void refresh()}>Refresh balance</button>
        </p>
      )}

      <h3 className="settings-title">Transaction History</h3>
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
