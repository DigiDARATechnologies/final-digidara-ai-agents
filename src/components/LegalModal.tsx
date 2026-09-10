import { useState } from "react";

interface Props {
  open: boolean;
  initialTab: "terms" | "privacy";
  onClose: () => void;
}

const EFFECTIVE_DATE = "September 10, 2026";

export default function LegalModal({ open, initialTab, onClose }: Props) {
  const [tab, setTab] = useState<"terms" | "privacy">(initialTab);
  if (!open) return null;

  return (
    <div className="modal-overlay open" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card legal-shell">
        <div className="modal-head">
          <div className="auth-tabs" role="tablist">
            <button type="button" className={tab === "terms" ? "active" : ""} onClick={() => setTab("terms")}>Terms of Service</button>
            <button type="button" className={tab === "privacy" ? "active" : ""} onClick={() => setTab("privacy")}>Privacy Policy</button>
          </div>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body legal-body">
          {tab === "terms" ? <TermsContent /> : <PrivacyContent />}
        </div>
      </div>
    </div>
  );
}

function TermsContent() {
  return (
    <article className="legal-doc">
      <h2>DigiDARA Terms of Service</h2>
      <p className="legal-meta">Effective date: {EFFECTIVE_DATE}</p>

      <h3>1. Acceptance of terms</h3>
      <p>
        By creating an account or using any DigiDARA agent (Capstone Project,
        CodeForge, Communication Coach, Aptitude Trainer, Resume Builder, or
        Certificate agent), you agree to these Terms of Service and the
        accompanying Privacy Policy. If you do not agree, do not use the
        platform.
      </p>

      <h3>2. Your account</h3>
      <p>
        You're responsible for the accuracy of the name, email, and mobile
        number you provide at signup, and for keeping your login credentials
        confidential. Course/certificate eligibility checks (Capstone) and
        session bridging (CodeForge, Communication Coach, Aptitude Trainer)
        rely on this information matching our records.
      </p>

      <h3>3. Acceptable use</h3>
      <ul>
        <li>No attempting to bypass an agent's rate limits, session/auth checks, or sandboxed code execution boundaries.</li>
        <li>No submitting malicious code to CodeForge's execution environment.</li>
        <li>No sharing hidden test cases, tutor guidance, or generated certificates/exam content obtained through the platform.</li>
        <li>No using the platform to generate content that is unlawful, infringing, or abusive.</li>
      </ul>

      <h3>4. AI-generated content</h3>
      <p>
        Project topics, feedback, scoring, tutor guidance, exam questions,
        and resume suggestions are generated or evaluated by third-party AI
        providers configured per agent. This content is provided "as is" and
        may be inaccurate or incomplete — it does not constitute professional,
        legal, or career advice. Always use your own judgment before acting
        on AI-generated output.
      </p>

      <h3>5. Payments</h3>
      <p>
        Paid plans and token top-ups are processed via Razorpay. Fees are
        described at the time of purchase; refunds, where applicable, follow
        the policy shown at checkout.
      </p>

      <h3>6. Service availability</h3>
      <p>
        Individual agents may be temporarily unavailable (maintenance,
        deployment, upstream provider outages). We don't guarantee
        uninterrupted access and aren't liable for losses resulting from
        downtime.
      </p>

      <h3>7. Termination</h3>
      <p>
        We may suspend or terminate accounts that violate these terms. You
        may stop using the platform and request account deletion at any
        time (see the Privacy Policy for how).
      </p>

      <h3>8. Changes to these terms</h3>
      <p>
        We may update these terms as the platform evolves. Continued use
        after an update constitutes acceptance of the revised terms.
      </p>

      <h3>9. Contact</h3>
      <p>Questions about these terms: <a href="mailto:legal@digidaraaiagents.com">legal@digidaraaiagents.com</a></p>
    </article>
  );
}

function PrivacyContent() {
  return (
    <article className="legal-doc">
      <h2>DigiDARA Privacy Policy</h2>
      <p className="legal-meta">Effective date: {EFFECTIVE_DATE}</p>

      <h3>1. What we collect</h3>
      <ul>
        <li><strong>Account data:</strong> name, email, mobile number, and password (stored hashed, never in plain text).</li>
        <li><strong>Usage data:</strong> chat messages and actions sent to each agent, code submissions and evaluation results (CodeForge), practice session transcripts and scores (Communication Coach, Aptitude Trainer), uploaded submission files (Capstone — `.docx`/`.zip`), and resumes/documents you upload (Resume Builder).</li>
        <li><strong>LLM usage metadata:</strong> token counts, model name, and request type per call, used for billing and rate-limiting — not the content of every prompt.</li>
        <li><strong>Technical data:</strong> IP address and browser user-agent, standard web server logs.</li>
      </ul>

      <h3>2. How we use it</h3>
      <ul>
        <li>To operate each agent's core functionality (eligibility checks, code execution, scoring, certificate/exam generation, resume export).</li>
        <li>To bridge your DigiDARA identity into each agent's own session so your progress persists across visits.</li>
        <li>To process payments and token top-ups via Razorpay.</li>
        <li>To improve reliability (error monitoring, health checks) and enforce rate limits / prevent abuse.</li>
      </ul>

      <h3>3. Third-party processors</h3>
      <p>
        Chat/scoring/generation content is sent to the LLM provider configured
        for the relevant agent (OpenAI, Groq, or Anthropic, depending on
        configuration) solely to produce that response — we don't sell this
        data. Payments are processed by Razorpay, which receives only the
        data needed to complete a transaction. Code submissions to CodeForge
        are executed in a sandboxed Judge0 environment.
      </p>

      <h3>4. Data storage</h3>
      <p>
        All account and platform data is stored in MySQL databases operated
        by DigiDARA. Uploaded submission files (Capstone) and resumes
        (Resume Builder) are retained only as long as needed to provide the
        related feature, or until you delete them.
      </p>

      <h3>5. Your rights</h3>
      <ul>
        <li>Request a copy of the personal data we hold about you.</li>
        <li>Request correction of inaccurate account data.</li>
        <li>Request deletion of your account and associated data, subject to records we're legally required to retain.</li>
      </ul>
      <p>To exercise any of these, email <a href="mailto:privacy@digidaraaiagents.com">privacy@digidaraaiagents.com</a>.</p>

      <h3>6. Cookies and local storage</h3>
      <p>
        The platform uses browser local storage to keep you signed in and
        cache chat history on your device. We don't use third-party
        advertising trackers.
      </p>

      <h3>7. Security</h3>
      <p>
        Passwords are hashed with bcrypt. Session tokens are signed and
        expiring. Inter-agent calls are authenticated with a shared secret.
        No system is perfectly secure — report suspected vulnerabilities to
        <a href="mailto:security@digidaraaiagents.com"> security@digidaraaiagents.com</a>.
      </p>

      <h3>8. Children's privacy</h3>
      <p>
        DigiDARA is intended for learners old enough to independently manage
        an account and is not directed at children under 13.
      </p>

      <h3>9. Changes to this policy</h3>
      <p>
        We may update this policy as the platform evolves. Material changes
        will be reflected by updating the effective date above.
      </p>

      <h3>10. Contact</h3>
      <p>Questions about this policy: <a href="mailto:privacy@digidaraaiagents.com">privacy@digidaraaiagents.com</a></p>
    </article>
  );
}
