import { useState } from "react";

interface Props {
  open: boolean;
  initialTab: "terms" | "privacy";
  onClose: () => void;
}

const EFFECTIVE_DATE = "September 11, 2026";

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
      <p>
        This policy explains how DigiDARA Technologies ("DigiDARA", "we")
        collects, uses, stores, and protects your personal data as a Data
        Fiduciary under India's Digital Personal Data Protection Act, 2023
        ("DPDP Act"), and the rights you have as a Data Principal.
      </p>

      <h3>1. What we collect</h3>
      <ul>
        <li><strong>Account data:</strong> name, email, mobile number, and password (stored hashed, never in plain text).</li>
        <li><strong>Usage data:</strong> chat messages and actions sent to each agent, code submissions and evaluation results (CodeForge), practice session transcripts and scores (Communication Coach, Aptitude Trainer), uploaded submission files (Capstone — `.docx`/`.zip`), and resumes/documents you upload (Resume Builder).</li>
        <li><strong>LLM usage metadata:</strong> token counts, model name, and request type per call, used for billing and rate-limiting — not the content of every prompt.</li>
        <li><strong>Technical data:</strong> IP address and browser user-agent, standard web server logs.</li>
        <li><strong>Consent record:</strong> the date/time you accepted this policy and the Terms of Service, and which version you accepted.</li>
      </ul>

      <h3>2. How we use it</h3>
      <ul>
        <li>To operate each agent's core functionality (eligibility checks, code execution, scoring, certificate/exam generation, resume export).</li>
        <li>To bridge your DigiDARA identity into each agent's own session so your progress persists across visits.</li>
        <li>To process payments and token top-ups via Razorpay.</li>
        <li>To improve reliability (error monitoring, health checks) and enforce rate limits / prevent abuse.</li>
      </ul>
      <p>We only use personal data for the purposes described here. We don't sell personal data or use it for third-party advertising.</p>

      <h3>3. Consent</h3>
      <p>
        Everything above is processed on the basis of the specific,
        informed, and unconditional consent you give by ticking the consent
        checkbox when you create an account (including via "Continue with
        Google") — not on any implied or bundled basis. You can withdraw
        that consent at any time from Settings → Privacy &amp; data → Delete
        my account. Because every feature on this platform depends on
        having an authenticated account, withdrawing consent and deleting
        your account are the same action; withdrawal does not affect the
        lawfulness of processing that already happened before you withdrew.
      </p>

      <h3>4. Third-party processors</h3>
      <p>
        Chat/scoring/generation content is sent to the LLM provider configured
        for the relevant agent (OpenAI, Groq, or Anthropic, depending on
        configuration) solely to produce that response — we don't sell this
        data. Payments are processed by Razorpay, which receives only the
        data needed to complete a transaction. Code submissions to CodeForge
        are executed in a sandboxed Judge0 environment. These processors may
        be located outside India; the DPDP Act permits such transfers except
        to countries the Central Government restricts by notification.
      </p>

      <h3>5. Data storage &amp; retention</h3>
      <p>
        All account and platform data is stored in MySQL databases operated
        by DigiDARA, hosted in the region configured for this deployment.
        Uploaded submission files (Capstone) and resumes (Resume Builder)
        are retained only as long as needed to provide the related feature,
        or until you delete them. Payment records are retained for the
        period required under applicable tax and accounting law even after
        an account is deleted, since they don't contain your name, email,
        or mobile number on their own. All other personal data is erased
        when you delete your account, as described in section 6.
      </p>

      <h3>6. Your rights</h3>
      <p>As a Data Principal under the DPDP Act, you have the right to:</p>
      <ul>
        <li><strong>Access</strong> a summary of the personal data we hold about you and how it's processed — download it any time from Settings → Privacy &amp; data → Download my data.</li>
        <li><strong>Correction and completion</strong> of inaccurate or incomplete account data.</li>
        <li><strong>Erasure</strong> of your account and associated personal data, subject to records we're legally required to retain — self-serve from Settings → Privacy &amp; data → Delete my account, or by emailing us.</li>
        <li><strong>Withdraw consent</strong> at any time (see section 3).</li>
        <li><strong>Grievance redressal</strong>, as described in section 9.</li>
        <li><strong>Nominate</strong> another individual to exercise these rights on your behalf in the event of your death or incapacity, by emailing our Grievance Officer.</li>
      </ul>
      <p>To exercise any right that isn't self-serve in Settings, email <a href="mailto:privacy@digidaraaiagents.com">privacy@digidaraaiagents.com</a>. We'll acknowledge your request within 7 days and resolve it as soon as reasonably possible.</p>

      <h3>7. Cookies and local storage</h3>
      <p>
        The platform uses browser local storage to keep you signed in and
        keep a temporary chat-history cache on your device. Your account-linked
        conversation history is stored in DigiDARA's MySQL database so it is
        available when you sign in on another browser or device. We don't use
        third-party advertising trackers or cookies for behavioural profiling.
      </p>

      <h3>8. Security safeguards</h3>
      <p>
        Passwords are hashed with bcrypt. Session tokens are signed and
        expiring. Inter-agent calls are authenticated with a shared secret.
        No system is perfectly secure — report suspected vulnerabilities to
        <a href="mailto:security@digidaraaiagents.com"> security@digidaraaiagents.com</a>.
      </p>

      <h3>9. Grievance Officer</h3>
      <p>
        In accordance with the DPDP Act, DigiDARA has appointed a Grievance
        Officer to handle complaints about the processing of your personal
        data. Reach out at{" "}
        <a href="mailto:grievance@digidaraaiagents.com">grievance@digidaraaiagents.com</a>{" "}
        with your account email and the nature of your complaint. We
        acknowledge grievances within 7 days and aim to resolve them within
        30 days. If you're unsatisfied with our response, you may escalate
        to the Data Protection Board of India.
      </p>

      <h3>10. Personal data breach notification</h3>
      <p>
        If a personal data breach occurs, we will notify the Data
        Protection Board of India and affected users as required under the
        DPDP Act, describing the nature of the breach, the data involved,
        and the steps we're taking in response.
      </p>

      <h3>11. Children's privacy</h3>
      <p>
        Under the DPDP Act, anyone under 18 is a "child" and processing
        their personal data requires verifiable consent from a parent or
        lawful guardian. DigiDARA does not knowingly collect personal data
        from, or create accounts for, anyone under 18 without such consent,
        and does not carry out behavioural monitoring, tracking, or
        targeted advertising directed at children. If you believe a child
        has created an account without appropriate parental consent, email{" "}
        <a href="mailto:privacy@digidaraaiagents.com">privacy@digidaraaiagents.com</a>{" "}
        and we will remove the account.
      </p>

      <h3>12. Changes to this policy</h3>
      <p>
        We may update this policy as the platform evolves. Material changes
        will be reflected by updating the effective date above; where a
        change materially affects how your data is used, we'll ask for
        fresh consent for accounts created after that change.
      </p>

      <h3>13. Contact</h3>
      <p>Questions about this policy: <a href="mailto:privacy@digidaraaiagents.com">privacy@digidaraaiagents.com</a></p>
    </article>
  );
}
