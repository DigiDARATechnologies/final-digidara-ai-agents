import { useState, type FormEvent } from "react";
import { sendEnterpriseEnquiry, type EnterpriseEnquiry as Enquiry } from "../lib/billingApi";

const TYPES: { id: Enquiry["organization_type"]; label: string }[] = [
  { id: "college", label: "College / university" },
  { id: "training_institute", label: "Training institute" },
  { id: "company", label: "Company" },
  { id: "other", label: "Other" },
];

/** The Enterprise plan card: an organization sends its details, which are
 * emailed to SkillDARA support, who get back to it. */
export default function EnterpriseEnquiry({ name, email, supportEmail, onToast }: {
  name: string; email: string; supportEmail: string; onToast: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [form, setForm] = useState({
    organization: "", organization_type: "college" as Enquiry["organization_type"], contact_name: name, email, phone: "",
    learners: "", city: "", message: "",
  });
  const set = (field: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [field]: event.target.value });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const learners = Number.parseInt(form.learners, 10);
      await sendEnterpriseEnquiry({ ...form, learners: Number.isFinite(learners) && learners > 0 ? learners : null });
      setSent(true);
      onToast("Thanks! Our team will contact you soon.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="enterprise-plan">
      <div className="enterprise-head">
        <div>
          <h3>Enterprise</h3>
          <strong>Custom pricing</strong>
          <p>For colleges, training institutes and companies: points for every learner, an organization dashboard,
            staff logins, student list upload, proctored assessments and priority support.</p>
        </div>
        {!open && !sent && <button type="button" onClick={() => setOpen(true)}>Contact sales</button>}
      </div>
      {sent ? (
        <p className="enterprise-sent" role="status">Thanks! We have sent your details to <b>{supportEmail}</b>. Our team will contact you at <b>{form.email}</b>.</p>
      ) : open && (
        <form className="enterprise-form" onSubmit={submit}>
          <label className="field"><span>Organization name *</span>
            <input required minLength={2} maxLength={255} value={form.organization} onChange={set("organization")} placeholder="e.g. Anna University" />
          </label>
          <label className="field"><span>Type</span>
            <select value={form.organization_type} onChange={set("organization_type")}>
              {TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
            </select>
          </label>
          <label className="field"><span>Contact person *</span>
            <input required minLength={2} maxLength={255} value={form.contact_name} onChange={set("contact_name")} />
          </label>
          <label className="field"><span>Email *</span>
            <input required type="email" maxLength={255} value={form.email} onChange={set("email")} />
          </label>
          <label className="field"><span>Phone *</span>
            <input required type="tel" minLength={8} maxLength={32} value={form.phone} onChange={set("phone")} placeholder="+91 98765 43210" />
          </label>
          <label className="field"><span>Number of learners</span>
            <input type="number" min={1} max={1000000} value={form.learners} onChange={set("learners")} placeholder="e.g. 500" />
          </label>
          <label className="field"><span>City</span>
            <input maxLength={120} value={form.city} onChange={set("city")} />
          </label>
          <label className="field enterprise-wide"><span>What do you need?</span>
            <textarea rows={3} maxLength={2000} value={form.message} onChange={set("message")}
              placeholder="Courses, batch size, start date, anything else" />
          </label>
          {error && <p className="form-error enterprise-wide" role="alert">{error}</p>}
          <div className="enterprise-actions enterprise-wide">
            <button type="submit" disabled={busy}>{busy ? "Sending…" : "Send to SkillDARA"}</button>
            <button type="button" className="link-btn" onClick={() => setOpen(false)}>Cancel</button>
            <small>Sent to {supportEmail}</small>
          </div>
        </form>
      )}
    </article>
  );
}
