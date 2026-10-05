import { useEffect, useState } from "react";
import { fetchBillingPlans, type PlanOffer } from "../lib/billingApi";
import { formatPoints } from "../lib/points";

interface Props {
  points: number | null;
  outOfPoints: boolean;
  onBuy: () => void;
  onClose: () => void;
}

function rupees(amountMinor: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(amountMinor / 100);
}

/** Pops up when the balance runs low or out, with the plans on sale and a
 * way straight to checkout. Escape or a click outside closes it. */
export default function LowPointsModal({ points, outOfPoints, onBuy, onClose }: Props) {
  const [plans, setPlans] = useState<PlanOffer[] | null>(null);

  useEffect(() => {
    let active = true;
    fetchBillingPlans().then((catalog) => { if (active) setPlans(catalog.plans); }).catch(() => { if (active) setPlans([]); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const title = outOfPoints ? "You're out of points" : "You're running low on points";
  return (
    <div className="modal-overlay open" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card low-points-card" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className={`low-points-balance${outOfPoints ? " out" : ""}`}>
            <span>Points left</span>
            <strong>{points === null ? "0" : formatPoints(points)}</strong>
          </div>
          <p className="low-points-message">
            {outOfPoints
              ? "Agents can't answer until you top up. Pick a plan to keep going; points never expire."
              : "Top up now so your next test, interview or resume isn't interrupted. Points never expire."}
          </p>
          {plans === null ? <p className="low-points-message">Loading plans…</p> : plans.length > 0 && (
            <ul className="low-points-plans">
              {plans.map((plan) => (
                <li key={plan.id} className={plan.popular ? "popular" : undefined}>
                  <span><b>{plan.name}</b>{plan.popular && <em>Most popular</em>}</span>
                  <span><strong>{formatPoints(plan.points)} points</strong><small>{rupees(plan.amount, plan.currency)}</small></span>
                </li>
              ))}
            </ul>
          )}
          <div className="low-points-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>Later</button>
            <button type="button" className="btn low-points-buy" autoFocus onClick={onBuy}>Buy points</button>
          </div>
        </div>
      </div>
    </div>
  );
}
