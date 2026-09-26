import type { ChatOption, User } from "../types";
import {
  ensureCertificateProfile,
  submitCertificateExam,
  getCertificateLeaderboard,
  getMyCertificates,
  requestCertificateEmailVerification,
  verifyCertificateEmail,
  interpretCertificateRequest,
  downloadCertificatePdf,
  startCertificateChat,
  sendCertificateChatMessage,
  getCertificateChatSession,
  getChatSessionQuestions,
  recoverCertificateForChatSession,
  updateCertificateRecipient,
  type CertificateProfileResponse,
} from "./certificateAgentApi";

export type CertificateStep =
  | "awaiting_action"
  | "awaiting_topic"
  | "awaiting_question"
  | "exam_instructions"
  | "awaiting_chat_session"
  | "awaiting_certificate_name"
  | "confirming_certificate_name"
  | "awaiting_certificate_email"
  | "confirming_certificate_email"
  | "awaiting_certificate_email_code"
  | "completed";

export interface QuestionItem {
  id: number;
  question_text: string;
  options: string[];
  difficulty?: string;
}

export interface CertificateFlowState {
  step: CertificateStep;
  token?: string;
  topic?: string;
  examId?: number;
  questions?: QuestionItem[];
  currentQuestionIndex?: number;
  answers?: Array<{ question_id: number; answer: string }>;
  score?: number;
  passed?: boolean;
  certificates?: Array<Record<string, unknown>>;
  /** Certificate issued by the completed chat exam, when one was earned. */
  certificateId?: number;
  certificateNumber?: string;
  selectedCertificateId?: number;
  pendingRecipientName?: string;
  pendingCertificateEmail?: string;
  sessionId?: string;
  mode?: "exam" | "chat";
  totalQuestions?: number;
  /** Absolute deadline keeps the per-question timer intact after a refresh. */
  questionDeadlineAt?: number;
}

export interface CertificateFlowMessage {
  text: string;
  options?: ChatOption[];
}

export interface CertificateFlowResponse {
  state: CertificateFlowState;
  messages: CertificateFlowMessage[];
}

const DEFAULT_TOPICS = [
  "Python Programming",
  "Data Science & Analytics",
  "Machine Learning & AI",
  "Cloud Computing & DevOps",
  "Web Development",
];

const topicOptions: ChatOption[] = DEFAULT_TOPICS.map((value) => ({
  label: value,
  value,
}));

export const createInitialCertificateState = (): CertificateFlowState => ({
  step: "awaiting_action",
});

export const initialCertificateMessage = (user: User): CertificateFlowMessage => ({
  text: `Hi ${user.name.split(" ")[0]}! Welcome to the AI Certification Agent.\n\nChoose an action to begin:`,
  options: [
    { label: "Take Certification Exam", value: "start_exam" },
    { label: "My Certificates", value: "my_certificates" },
    { label: "Leaderboard", value: "leaderboard" },
  ],
});

export async function openCertificateChat(user: User) {
  const state = createInitialCertificateState();
  try {
    const profile: CertificateProfileResponse = await ensureCertificateProfile(
      user.id,
      user.name,
      user.email
    );
    const token = profile.token || profile.sessionToken;
    localStorage.setItem(
      `digidara_cert_token_${user.email.toLowerCase()}`,
      token
    );
    return {
      state: { ...state, token },
      messages: [initialCertificateMessage(user)],
    };
  } catch (error) {
    return {
      state,
      messages: [
        {
          text: `Could not connect to Certification Agent: ${(error as Error).message}`,
          options: [{ label: "Retry Connection", value: "retry" }],
        },
      ],
    };
  }
}

export async function handleCertificateText(
  state: CertificateFlowState,
  text: string,
  user?: User,
  allowTokenRefresh = true,
): Promise<CertificateFlowResponse> {
  const val = text.trim();
  const lower = val.toLowerCase();

  try {
    // 1. Top-level global command / button overrides
    if (lower === "menu" || lower === "restart" || lower === "retry" || lower === "main menu") {
      if (user && !state.token) {
        const profile = await ensureCertificateProfile(user.id, user.name, user.email);
        state.token = profile.token || profile.sessionToken;
      }
      return {
        state: { ...createInitialCertificateState(), token: state.token },
        messages: [user ? initialCertificateMessage(user) : { text: "Main Menu:", options: topicOptions }],
      };
    }

    // The standalone certificate agent accepts a normal greeting or topic as
    // its first message. Preserve that behaviour instead of forcing users to
    // click a menu action before they can talk to CertifyAI.
    if (state.step === "awaiting_action") {
      if (!state.token && user) {
        const profile = await ensureCertificateProfile(user.id, user.name, user.email);
        state.token = profile.token || profile.sessionToken;
      }
      const sessionRes = await startCertificateChat(state.token!);
      return handleCertificateText(
        { ...state, step: "awaiting_topic", mode: "chat" as const, sessionId: sessionRes.session_id },
        val,
        user,
      );
    }

    if (val === "start_exam" || lower === "take certification exam" || lower === "take exam") {
      if (!state.token && user) {
        const profile = await ensureCertificateProfile(user.id, user.name, user.email);
        state.token = profile.token || profile.sessionToken;
      }
      const sessionRes = await startCertificateChat(state.token!);
      return {
        // The certificate agent's own exam flow is conversational: it
        // confirms the topic, calibrates difficulty, then evaluates every
        // answer in the chat session. Keep this action on that canonical flow.
        state: { ...state, step: "awaiting_topic" as const, mode: "chat" as const, sessionId: sessionRes.session_id },
        messages: [
          {
            text: "Select a topic for your certification exam, or type a custom topic:",
            options: topicOptions,
          },
        ],
      };
    }

    if (val === "start_chat" || lower === "ai tutor chat exam" || lower === "chat exam") {
      if (!state.token && user) {
        const profile = await ensureCertificateProfile(user.id, user.name, user.email);
        state.token = profile.token || profile.sessionToken;
      }
      const sessionRes = await startCertificateChat(state.token!);
      return {
        state: { ...state, step: "awaiting_topic" as const, mode: "chat" as const, sessionId: sessionRes.session_id },
        messages: [
          {
            text: "Select a topic for your AI Chat Exam Session:",
            options: topicOptions,
          },
        ],
      };
    }

    // Question generation is complete, but the learner must explicitly
    // acknowledge the exam rules before the first timer begins.
    if (val === "start_certificate_exam" && state.step === "exam_instructions") {
      return {
        state: {
          ...state,
          step: "awaiting_chat_session",
          questionDeadlineAt: Date.now() + 3 * 60 * 1000,
        },
        messages: [],
      };
    }

    if (val === "my_certificates" || lower === "my certificates" || lower === "certificates") {
      if (!state.token && user) {
        const profile = await ensureCertificateProfile(user.id, user.name, user.email);
        state.token = profile.token || profile.sessionToken;
      }
      // Recover a certificate for an older passed chat attempt before
      // listing certificates. This covers users who passed before the React
      // interface exposed the download action.
      let recoveredCertificate: { certificate_id: number; certificate_number?: string } | undefined;
      if (state.step === "completed" && state.passed && state.sessionId && !state.certificateId) {
        try {
          recoveredCertificate = await recoverCertificateForChatSession(state.token!, state.sessionId);
          state = {
            ...state,
            certificateId: recoveredCertificate.certificate_id,
            certificateNumber: recoveredCertificate.certificate_number,
          };
        } catch {
          // Continue to the normal list response; it remains useful even if
          // this particular legacy attempt cannot be recovered.
        }
      }

      const certs = await getMyCertificates(state.token!);
      if (recoveredCertificate) {
        return {
          state: { ...state, certificates: certs },
          messages: [
            {
              text: `📜 Your previously passed certification is ready${recoveredCertificate.certificate_number ? `. Certificate number: **${recoveredCertificate.certificate_number}**` : "."}`,
              options: [
                { label: "Download PDF Certificate", value: `download_${recoveredCertificate.certificate_id}` },
                { label: "My Certificates", value: "my_certificates" },
                { label: "Start New Exam", value: "start_exam" },
              ],
            },
          ],
        };
      }
      if (!certs || certs.length === 0) {
        return {
          state,
          messages: [
            {
              text: "You haven't earned any certificates yet. Pass an exam to earn your official certificate!",
              options: [
                { label: "Take Certification Exam", value: "start_exam" },
                { label: "Main Menu", value: "menu" },
              ],
            },
          ],
        };
      }

      const certList = certs
        .map(
          (c, i) =>
            `${i + 1}. **${c.topic || "Certification"}** (Score: ${c.score_percentage ?? 0}% · Issued: ${c.issued_at || "N/A"})`
        )
        .join("\n");

      return {
        state: { ...state, certificates: certs, selectedCertificateId: state.selectedCertificateId ?? Number(certs[0]?.id) },
        messages: [
          {
            text: `🎓 **Your Earned Certificates**:\n\n${certList}\n\nChoose a certificate below to download its official PDF.`,
            options: [
              ...certs.map((c) => ({
                label: `Download ${c.topic || "Certification"} Certificate`,
                value: `download_${c.id}`,
              })),
              { label: "Update Certificate Name", value: "change_certificate_name" },
              { label: "Email a Certificate", value: "email_certificate" },
              { label: "Main Menu", value: "menu" },
            ],
          },
        ],
      };
    }

    if (val === "leaderboard" || lower === "leaderboard" || lower === "top scores") {
      const board = await getCertificateLeaderboard();
      if (!board || board.length === 0) {
        return {
          state,
          messages: [
            {
              text: "No leaderboard entries recorded yet. Be the first to earn a top score!",
              options: [{ label: "Take Certification Exam", value: "start_exam" }, { label: "Main Menu", value: "menu" }],
            },
          ],
        };
      }

      const rows = board
        .slice(0, 10)
        .map(
          (b, i) =>
            `${i + 1}. ${b.name || "Learner"} — ${b.topic || "Exam"}: **${b.best_score ?? 0}%**`
        )
        .join("\n");

      return {
        state,
        messages: [
          {
            text: `🏆 **Certification Leaderboard (Top Scores)**:\n\n${rows}`,
            options: [
              { label: "Take Certification Exam", value: "start_exam" },
              { label: "Main Menu", value: "menu" },
            ],
          },
        ],
      };
    }

    if (val.startsWith("download_") || lower.startsWith("download")) {
      const certIdMatch = val.match(/(\d+)/);
      if (certIdMatch && state.token) {
        const certId = parseInt(certIdMatch[1], 10);
        const { blob, filename } = await downloadCertificatePdf(state.token, certId);
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
        return {
          state,
          messages: [{ text: "✅ Your official certificate PDF has been downloaded." }],
        };
      }
    }

    // Certificate management is deliberately a short, explicit dialogue:
    // natural language chooses the task; the sensitive action only occurs
    // after the learner has reviewed and confirmed the exact value.
    const selectedCertificateId = state.selectedCertificateId ?? state.certificateId;
    if (val === "change_certificate_name" && selectedCertificateId) {
      return {
        state: { ...state, step: "awaiting_certificate_name", selectedCertificateId },
        messages: [{
          text: "Of course. What full name would you like printed on this certificate? I’ll show it back to you for confirmation before changing anything.",
        }],
      };
    }

    if (val === "email_certificate" && selectedCertificateId) {
      return {
        state: { ...state, step: "awaiting_certificate_email", selectedCertificateId },
        messages: [{
          text: "I can email the official PDF certificate. Which email address should I send it to? I’ll ask you to confirm before it is sent.",
        }],
      };
    }

    if (val === "cancel_certificate_management" && [
      "awaiting_certificate_name",
      "confirming_certificate_name",
      "awaiting_certificate_email",
      "confirming_certificate_email",
      "awaiting_certificate_email_code",
    ].includes(state.step)) {
      return {
        state: { ...state, step: "completed", pendingRecipientName: undefined, pendingCertificateEmail: undefined },
        messages: [{ text: "No changes were made. Your current certificate is still available whenever you need it." }],
      };
    }

    if (state.step === "awaiting_certificate_name") {
      const recipientName = val.replace(/\s+/g, " ").trim();
      if (recipientName.length < 2 || recipientName.length > 120) {
        return { state, messages: [{ text: "Please enter the full name exactly as it should appear on the certificate." }] };
      }
      return {
        state: { ...state, step: "confirming_certificate_name", pendingRecipientName: recipientName },
        messages: [{
          text: `I’ll regenerate this certificate with **${recipientName}** as the recipient name. Would you like me to make that change?`,
          options: [
            { label: "Yes, update the certificate", value: "confirm_certificate_name" },
            { label: "Use a different name", value: "change_certificate_name" },
            { label: "Cancel", value: "cancel_certificate_management" },
          ],
        }],
      };
    }

    if (state.step === "awaiting_certificate_email") {
      // People commonly reply with a sentence such as "send it to
      // name@example.com". Use the address within that natural reply rather
      // than forcing them to enter only the email address.
      const email = val.match(/[^\s@]+@[^\s@]+\.[^\s@]+/)?.[0] ?? val.trim();
      if (!/^\S+@\S+\.\S+$/.test(email)) {
        return { state, messages: [{ text: "Please enter a valid email address for the certificate delivery." }] };
      }
      return {
        state: { ...state, step: "confirming_certificate_email", pendingCertificateEmail: email },
        messages: [{
          text: `I’m ready to send the official certificate PDF to **${email}**. Would you like me to send it now?`,
          options: [
            { label: "Yes, send the email", value: "confirm_certificate_email" },
            { label: "Use a different email", value: "email_certificate" },
            { label: "Cancel", value: "cancel_certificate_management" },
          ],
        }],
      };
    }

    if (
      (state.step === "confirming_certificate_name" || state.step === "confirming_certificate_email") &&
      state.token &&
      !["confirm_certificate_name", "confirm_certificate_email", "cancel_certificate_management"].includes(val)
    ) {
      const confirmation = await interpretCertificateRequest(
        state.token,
        val,
        state.step === "confirming_certificate_name" ? "name_confirmation" : "email_confirmation",
      );
      if (confirmation.intent === "confirm") {
        return handleCertificateText(
          state,
          state.step === "confirming_certificate_name" ? "confirm_certificate_name" : "confirm_certificate_email",
          user,
        );
      }
      if (confirmation.intent === "revise") {
        return {
          state: {
            ...state,
            step: state.step === "confirming_certificate_name" ? "awaiting_certificate_name" : "awaiting_certificate_email",
          },
          messages: [{
            text: state.step === "confirming_certificate_name"
              ? "No problem—what name should appear on the certificate instead?"
              : "No problem—which email address should I use instead?",
          }],
        };
      }
      if (confirmation.intent === "cancel") {
        return handleCertificateText(state, "cancel_certificate_management", user);
      }
      return { state, messages: [{ text: "Please confirm the change, ask to revise it, or cancel it." }] };
    }

    if (val === "confirm_certificate_name" && state.step === "confirming_certificate_name" && state.token && state.selectedCertificateId && state.pendingRecipientName) {
      const updated = await updateCertificateRecipient(state.token, state.selectedCertificateId, state.pendingRecipientName);
      return {
        state: {
          ...state,
          step: "completed",
          certificateId: updated.certificate_id,
          certificateNumber: updated.certificate_number,
          pendingRecipientName: undefined,
        },
        messages: [{
          text: `✅ Your certificate has been regenerated with **${updated.recipient_name}** as the recipient name. Would you like to download it here or email it?`,
          options: [
            { label: "Download PDF Certificate", value: `download_${updated.certificate_id}` },
            { label: "Email Certificate", value: "email_certificate" },
          ],
        }],
      };
    }

    if (val === "confirm_certificate_email" && state.step === "confirming_certificate_email" && state.token && state.selectedCertificateId && state.pendingCertificateEmail) {
      try {
        const verification = await requestCertificateEmailVerification(
          state.token,
          state.selectedCertificateId,
          state.pendingCertificateEmail,
        );
        return {
          state: {
            ...state,
            step: "awaiting_certificate_email_code",
            pendingCertificateEmail: verification.email,
          },
          messages: [{
            text: `I sent a six-digit verification code to **${verification.email}**. Enter that code here to confirm you control this inbox. The code expires in ${verification.expires_in_minutes} minutes.`,
            options: [
              { label: "Use a Different Email", value: "email_certificate" },
              { label: "Cancel", value: "cancel_certificate_management" },
            ],
          }],
        };
      } catch {
        const certificateId = state.selectedCertificateId;
        return {
          state: { ...state, step: "completed", pendingCertificateEmail: undefined },
          messages: [{
            text: "I couldn’t deliver the certificate email just now. Your certificate is still safe and ready to download. Please try emailing it again a little later.",
            options: [
              { label: "Download PDF Certificate", value: `download_${certificateId}` },
              { label: "Try Emailing Again", value: "email_certificate" },
            ],
          }],
        };
      }
    }

    if (val === "resend_certificate_email_verification" && state.step === "awaiting_certificate_email_code" && state.token && state.selectedCertificateId && state.pendingCertificateEmail) {
      try {
        const verification = await requestCertificateEmailVerification(
          state.token,
          state.selectedCertificateId,
          state.pendingCertificateEmail,
        );
        return {
          state: { ...state, pendingCertificateEmail: verification.email },
          messages: [{
            text: `I sent a new six-digit verification code to **${verification.email}**. Please enter it here.`,
            options: [
              { label: "Use a Different Email", value: "email_certificate" },
              { label: "Cancel", value: "cancel_certificate_management" },
            ],
          }],
        };
      } catch {
        return {
          state,
          messages: [{
            text: "I couldn’t send a new verification code just now. Your certificate is still safe and ready to download.",
            options: [
              { label: "Download PDF Certificate", value: `download_${state.selectedCertificateId}` },
              { label: "Try Again", value: "resend_certificate_email_verification" },
            ],
          }],
        };
      }
    }

    if (state.step === "awaiting_certificate_email_code" && state.token && state.selectedCertificateId && state.pendingCertificateEmail) {
      const code = val.match(/\b\d{6}\b/)?.[0];
      if (!code) {
        return {
          state,
          messages: [{
            text: "Please enter the six-digit verification code from the email.",
            options: [
              { label: "Resend Verification Code", value: "resend_certificate_email_verification" },
              { label: "Use a Different Email", value: "email_certificate" },
            ],
          }],
        };
      }
      try {
        const sent = await verifyCertificateEmail(
          state.token,
          state.selectedCertificateId,
          state.pendingCertificateEmail,
          code,
        );
        return {
          state: { ...state, step: "completed", pendingCertificateEmail: undefined },
          messages: [{
            text: `✅ Your official certificate PDF has been sent to **${sent.email}**. You can also download it here whenever you need it.`,
            options: [{ label: "Download PDF Certificate", value: `download_${sent.certificate_id}` }],
          }],
        };
      } catch {
        return {
          state,
          messages: [{
            text: "That verification code could not be confirmed. Please check the latest code in your email and try again, or request a new one.",
            options: [
              { label: "Resend Verification Code", value: "resend_certificate_email_verification" },
              { label: "Use a Different Email", value: "email_certificate" },
            ],
          }],
        };
      }
    }

    // A completed or integrity-failed attempt is terminal. Do not send an
    // arbitrary follow-up to the old server session; offer only safe next
    // actions, exactly as the standalone agent does after an exam closes.
    if (state.step === "completed") {
      if (state.passed && state.token) {
        const understanding = await interpretCertificateRequest(state.token, val);
        const activeCertificateId = state.selectedCertificateId ?? state.certificateId;

        if (understanding.intent === "rename_certificate" && activeCertificateId) {
          return {
            state: { ...state, step: "awaiting_certificate_name", selectedCertificateId: activeCertificateId },
            messages: [{ text: "Absolutely. What full name would you like printed on the certificate? I’ll confirm it with you before I regenerate the PDF." }],
          };
        }
        if (understanding.intent === "email_certificate" && activeCertificateId) {
          return {
            state: { ...state, step: "awaiting_certificate_email", selectedCertificateId: activeCertificateId },
            messages: [{ text: "Certainly. Which email address should receive the official certificate PDF? I’ll ask for confirmation before sending it." }],
          };
        }
        if (understanding.intent === "list_certificates") {
          return handleCertificateText(state, "my_certificates", user);
        }
        if (understanding.intent === "download_certificate" || understanding.intent === "unknown") {
          // Existing passed sessions created before certificate metadata was
          // persisted are recovered on demand here.
          try {
            const recovered = state.certificateId
              ? { certificate_id: state.certificateId, certificate_number: state.certificateNumber }
              : state.sessionId
                ? await recoverCertificateForChatSession(state.token, state.sessionId)
                : undefined;
            if (recovered) {
              return {
                state: {
                  ...state,
                  certificateId: recovered.certificate_id,
                  certificateNumber: recovered.certificate_number,
                  selectedCertificateId: recovered.certificate_id,
                },
                messages: [{
                  text: understanding.intent === "unknown"
                    ? (understanding.reply || "Your certificate is ready. You can download it here, update the printed name, or ask me to email it.")
                    : `📜 Your certificate is ready${recovered.certificate_number ? `. Certificate number: **${recovered.certificate_number}**` : "."}`,
                  options: [
                    { label: "Download PDF Certificate", value: `download_${recovered.certificate_id}` },
                    { label: "Update Certificate Name", value: "change_certificate_name" },
                    { label: "Email Certificate", value: "email_certificate" },
                  ],
                }],
              };
            }
          } catch (error) {
            return { state, messages: [{ text: `Could not recover the certificate: ${(error as Error).message}` }] };
          }
        }
      }

      /* Legacy fallback when the LLM service is temporarily unavailable. */
      if (state.passed && (lower.includes("certificate") || lower.includes("download"))) {
        try {
          const recovered = state.certificateId
            ? { certificate_id: state.certificateId, certificate_number: state.certificateNumber }
            : state.sessionId && state.token
              ? await recoverCertificateForChatSession(state.token, state.sessionId)
              : undefined;
          if (!recovered) throw new Error("Certificate details are unavailable");
          return {
            state: {
              ...state,
              certificateId: recovered.certificate_id,
              certificateNumber: recovered.certificate_number,
              selectedCertificateId: recovered.certificate_id,
            },
            messages: [
              {
                text: `📜 Your certificate is ready${recovered.certificate_number ? `. Certificate number: **${recovered.certificate_number}**` : "."}`,
                options: [
                  { label: "Download PDF Certificate", value: `download_${recovered.certificate_id}` },
                  { label: "My Certificates", value: "my_certificates" },
                  { label: "Start New Exam", value: "start_exam" },
                ],
              },
            ],
          };
        } catch (error) {
          return {
            state,
            messages: [{ text: `Could not recover the certificate: ${(error as Error).message}` }],
          };
        }
      }
      return {
        state,
        messages: [
          {
            text: state.passed
              ? "This certification attempt is complete. You can download your certificate or start another exam."
              : "This certification attempt is closed. You can start a new exam when you are ready.",
            options: [
              { label: "Take Certification Exam", value: "start_exam" },
              { label: "My Certificates", value: "my_certificates" },
              { label: "Main Menu", value: "menu" },
            ],
          },
        ],
      };
    }

    // Topic selection & Subject Recognition / Difficulty Selection Flow
    if (state.step === "awaiting_topic") {
      if (!state.token && user) {
        const profile = await ensureCertificateProfile(user.id, user.name, user.email);
        state.token = profile.token || profile.sessionToken;
      }

      let currentSessionId = state.sessionId;
      if (!currentSessionId || currentSessionId === "chat_mode") {
        const sessionRes = await startCertificateChat(state.token!);
        currentSessionId = sessionRes.session_id;
      }

      // Send the user input to chat_orchestrator for intent classification / state progression
      const turnRes = await sendCertificateChatMessage(state.token!, currentSessionId, val);

      if (turnRes.error) {
        return {
          state: { ...state, sessionId: currentSessionId },
          messages: [{ text: `Error: ${turnRes.error}`, options: topicOptions }],
        };
      }

      // Check if questions are generating or completed in chat session
      if (
        turnRes.status?.session_status === "generating" ||
        turnRes.status?.session_status === "in_exam" ||
        turnRes.status?.session_status === "in_progress"
      ) {
        let isReady = false;
        let isFailed = false;

        // Poll GET /api/chat/session/{session_id} every 2.5s for up to 90s (36 attempts)
        for (let attempt = 0; attempt < 36; attempt++) {
          try {
            const sessionData: any = await getCertificateChatSession(state.token!, currentSessionId);
            const status = sessionData?.session?.status || sessionData?.status;
            if (status === "in_exam" || status === "ready") {
              isReady = true;
              break;
            } else if (status === "generation_failed") {
              isFailed = true;
              break;
            }
          } catch {
            // Transient network error during polling
          }
          await new Promise((r) => setTimeout(r, 2500));
        }

        if (isFailed) {
          return {
            state: { ...state, sessionId: currentSessionId },
            messages: [{ text: "Exam question generation failed on the server. Please try another topic.", options: topicOptions }],
          };
        }

        if (!isReady) {
          // Check one last time before timing out
          try {
            const finalCheck: any = await getCertificateChatSession(state.token!, currentSessionId);
            const finalStatus = finalCheck?.session?.status || finalCheck?.status;
            if (finalStatus === "in_exam" || finalStatus === "ready") {
              isReady = true;
            }
          } catch {}
        }

        if (!isReady) {
          return {
            state: { ...state, sessionId: currentSessionId },
            messages: [{ text: "Question generation timed out after 90 seconds. Please try again or select another topic.", options: topicOptions }],
          };
        }

        // Chat mode must continue through the certificate agent's own
        // answer-by-answer evaluator. Do not convert the chat session into a
        // separate form exam, otherwise its feedback and certificate-card
        // behaviour are lost.
        if (state.mode === "chat") {
          const sessionData: any = await getCertificateChatSession(state.token!, currentSessionId);
          const messages = Array.isArray(sessionData?.messages) ? sessionData.messages : [];
          const question = [...messages].reverse().find((message: any) =>
            message?.role === "assistant" &&
            ["mcq_question", "freetext_question"].includes(message?.message_type),
          );

          if (!question) {
            return {
              state: { ...state, sessionId: currentSessionId },
              messages: [{ text: "Your exam is ready, but the first question could not be loaded. Please try again.", options: topicOptions }],
            };
          }

          const options = Array.isArray(question.metadata?.options)
            ? question.metadata.options.map((option: string) => ({ label: option, value: option }))
            : undefined;
          return {
            state: {
              ...state,
              step: "exam_instructions",
              sessionId: currentSessionId,
              topic: sessionData?.session?.topic || state.topic || val,
              totalQuestions: sessionData?.session?.total_questions || turnRes.status?.total_questions,
              currentQuestionIndex: sessionData?.session?.current_question_index || 0,
              questionDeadlineAt: undefined,
            },
            messages: [{ text: question.content, options }],
          };
        }

        // The standard exam mode renders the pre-generated questions in the
        // shared DigiDARA chat interface.
        const questionsRes: any = await getChatSessionQuestions(state.token!, currentSessionId);

        const questions: QuestionItem[] = (questionsRes.questions || []).map((q: any) => ({
          id: q.id,
          question_text: q.question_text || q.question,
          options: q.options || [],
          difficulty: q.difficulty,
        }));

        const firstQ = questions[0];
        if (!firstQ) {
          return {
            state: { ...state, sessionId: currentSessionId },
            messages: [{ text: "The exam was prepared without any questions. Please try another topic.", options: topicOptions }],
          };
        }
        const topicName = questionsRes.topic || state.topic || val;
        return {
          state: {
            ...state,
            step: "awaiting_question" as const,
            sessionId: currentSessionId,
            topic: topicName,
            examId: questionsRes.exam_id,
            questions,
            currentQuestionIndex: 0,
            answers: [],
          },
          messages: [
            {
              text: `📝 **${topicName} Exam** (Question 1/${questions.length})\n\n${firstQ.question_text}`,
              options: firstQ.options.map((opt) => ({
                label: opt,
                value: opt,
              })),
            },
          ],
        };
      }

      // Otherwise, backend returned conversational assistant message(s) (subject refusal, confirmation, or difficulty prompt)
      const assistantMsgs = turnRes.messages.filter((m) => m.role === "assistant");
      const lastMsg = assistantMsgs[assistantMsgs.length - 1];

      const replyText = lastMsg?.content || "Please enter a technical topic to proceed with your certification.";
      const metaOpts: string[] = lastMsg?.metadata?.options || [];

      const messageOptions: ChatOption[] = metaOpts.length > 0
        ? metaOpts.map((opt) => ({ label: opt, value: opt }))
        : topicOptions;

      const currentTopic = lastMsg?.metadata?.temp_topic || state.topic || val;

      return {
        state: {
          ...state,
          sessionId: currentSessionId,
          topic: currentTopic,
        },
        messages: [
          {
            text: replyText,
            options: messageOptions,
          },
        ],
      };
    }

    if (state.step === "awaiting_chat_session" && state.sessionId && state.token) {
      const turnRes = await sendCertificateChatMessage(state.token, state.sessionId, val);
      if (turnRes.error) {
        return { state, messages: [{ text: `Error: ${turnRes.error}` }] };
      }

      const assistantMessages = turnRes.messages.filter((message) => message.role === "assistant");
      const finalMessage = assistantMessages[assistantMessages.length - 1];
      const metadata = finalMessage?.metadata;
      const options = Array.isArray(metadata?.options)
        ? metadata.options.map((option: string) => ({ label: option, value: option }))
        : undefined;
      const status = turnRes.status;
      const isComplete = status?.session_status === "completed" || status?.session_status === "failed";
      const passed = status?.passed ?? state.passed;
      const rawCertificateId = metadata?.certificate_id;
      const certificateId = Number.isFinite(Number(rawCertificateId)) && Number(rawCertificateId) > 0
        ? Number(rawCertificateId)
        : undefined;
      const certificateNumber = typeof metadata?.certificate_number === "string"
        ? metadata.certificate_number
        : undefined;
      const resultOptions: ChatOption[] | undefined = isComplete
        ? certificateId
          ? [
              { label: "Download PDF Certificate", value: `download_${certificateId}` },
              { label: "Update Certificate Name", value: "change_certificate_name" },
              { label: "Email Certificate", value: "email_certificate" },
              { label: "My Certificates", value: "my_certificates" },
              { label: "Start New Exam", value: "start_exam" },
            ]
          : [
              { label: "Start New Exam", value: "start_exam" },
              { label: "Main Menu", value: "menu" },
            ]
        : options;
      return {
        state: {
          ...state,
          step: isComplete ? "completed" : "awaiting_chat_session",
          currentQuestionIndex: status?.current_question_index ?? state.currentQuestionIndex,
          totalQuestions: status?.total_questions ?? state.totalQuestions,
          score: status?.score_percentage ?? state.score,
          passed,
          certificateId: certificateId ?? state.certificateId,
          certificateNumber: certificateNumber ?? state.certificateNumber,
          selectedCertificateId: certificateId ?? state.selectedCertificateId ?? state.certificateId,
          questionDeadlineAt: isComplete ? undefined : Date.now() + 3 * 60 * 1000,
        },
        messages: assistantMessages.length
          ? assistantMessages.map((message, index) => ({
              text: index === assistantMessages.length - 1 && certificateId
                ? `${message.content}\n\n📜 Your official certificate is ready${certificateNumber ? `. Certificate number: **${certificateNumber}**` : ""}. Would you like to download it here, email it to an address you choose, or update the printed recipient name?`
                : message.content,
              options: index === assistantMessages.length - 1 ? resultOptions : undefined,
            }))
          : [{ text: "Your response was recorded. Please continue with the exam." }],
      };
    }

    // Answering questions
    if (state.step === "awaiting_question" && state.questions && state.currentQuestionIndex !== undefined) {
      const currentQ = state.questions[state.currentQuestionIndex];
      const selectedOption = val;

      const updatedAnswers = [
        ...(state.answers || []),
        { question_id: currentQ.id, answer: selectedOption },
      ];

      const nextIndex = state.currentQuestionIndex + 1;

      if (nextIndex < state.questions.length) {
        const nextQ = state.questions[nextIndex];
        return {
          state: {
            ...state,
            currentQuestionIndex: nextIndex,
            answers: updatedAnswers,
          },
          messages: [
            {
              text: `📝 **${state.topic} Exam** (Question ${nextIndex + 1}/${state.questions.length})\n\n${nextQ.question_text}`,
              options: nextQ.options.map((opt) => ({
                label: opt,
                value: opt,
              })),
            },
          ],
        };
      } else {
        // Exam complete - submit all answers
        const result: any = await submitCertificateExam(state.token!, state.examId!, updatedAnswers);
        const score = result.score_percentage ?? result.score ?? result.percentage ?? 0;
        const passed = result.passed ?? score >= 70;

        const options: ChatOption[] = [
          { label: "Main Menu", value: "menu" },
          { label: "Try Another Topic", value: "start_exam" },
        ];

        if (passed && result.certificate_id) {
          options.unshift({
            label: "Download PDF Certificate",
            value: `download_${result.certificate_id}`,
          });
        }

        return {
          state: {
            ...state,
            step: "completed" as const,
            answers: updatedAnswers,
            score,
            passed,
          },
          messages: [
            {
              text: `🎉 **Exam Submitted!**\n\n- Topic: **${state.topic}**\n- Final Score: **${score}%**\n- Outcome: **${passed ? "PASSED ✅" : "FAILED ❌"}**\n\n${
                passed
                  ? "Congratulations! You have passed the certification exam and your official certificate has been issued."
                  : "Keep practicing! You need 70% or higher to earn a certificate."
              }`,
              options,
            },
          ],
        };
      }
    }

    return {
      state,
      messages: [
        {
          text: "I didn't quite catch that. Choose an action from the options below:",
          options: [
            { label: "Take Certification Exam", value: "start_exam" },
            { label: "My Certificates", value: "my_certificates" },
            { label: "Main Menu", value: "menu" },
          ],
        },
      ],
    };
  } catch (error) {
    // The certification backend can be restarted while a learner keeps an
    // existing browser chat open. Refresh its short-lived certificate token
    // and retry the same natural-language request once, instead of exposing a
    // 401 or asking the learner to restart their conversation.
    const message = (error as Error).message || "";
    if (allowTokenRefresh && user && /\b401\b|unauthori[sz]ed|invalid or expired token/i.test(message)) {
      try {
        const profile = await ensureCertificateProfile(user.id, user.name, user.email);
        const token = profile.token || profile.sessionToken;
        localStorage.setItem(`digidara_cert_token_${user.email.toLowerCase()}`, token);
        return handleCertificateText({ ...state, token }, text, user, false);
      } catch {
        // Fall through to the safe learner-facing recovery response below.
      }
    }
    return {
      state,
      messages: [{
        text: "I couldn’t complete that certificate request right now. Your exam and certificate records are safe. Please try again, or choose another certificate option below.",
        options: [
          { label: "My Certificates", value: "my_certificates" },
          { label: "Main Menu", value: "menu" },
        ],
      }],
    };
  }
}
