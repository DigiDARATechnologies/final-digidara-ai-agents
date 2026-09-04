import { useCallback, useEffect, useRef, useState } from "react";
import type { Agent, Chat, ChatMessage, ChatOption, User, View } from "./types";
import { DEFAULT_AGENT, CANNED_REPLIES, findAgent, findAgentByBackendName } from "./data/agents";
import { useChats, nowStr } from "./hooks/useChats";
import {
  handleCapstoneText,
  createInitialCapstoneState,
  initialCapstoneMessage,
  mergeCapstoneFiles,
  submitCapstoneFiles,
  regenerateTopicsForDifficulty,
  type CapstoneFlowState,
} from "./lib/capstoneFlow";
import {
  handleCodeForgeText,
  openCodeForgeChat,
  runCodeForgeCode,
  submitCodeForgeCode,
  type CodeForgeFlowState,
} from "./lib/codeforgeFlow";
import { handleAptitudeText, createInitialAptitudeState, openAptitudeChat, type AptitudeFlowState } from "./lib/aptitudeFlow";
import {
  handleCommunicationText,
  openCommunicationChat,
  MENU_OPTIONS as COMMUNICATION_MENU_OPTIONS,
  type CommunicationFlowState,
} from "./lib/communicationFlow";
import LoginOverlay from "./components/LoginOverlay";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import StoreView from "./components/StoreView";
import NewChatLanding from "./components/NewChatLanding";
import ChatView from "./components/ChatView";
import SettingsModal from "./components/SettingsModal";
import CodeForgePlayground from "./components/CodeForgePlayground";
import ProfilePage from "./components/ProfilePage";
import Toast from "./components/Toast";
import AgentDashboard from "./components/AgentDashboard";
import CodeForgeDashboard from "./components/CodeForgeDashboard";
import AptitudeDashboard from "./components/AptitudeDashboard";
import AptitudePracticePanel from "./components/AptitudePracticePanel";
import CommunicationDashboard from "./components/CommunicationDashboard";
import ResumeBuilderDashboard from "./components/ResumeBuilderDashboard";
import AgentDetailsModal from "./components/AgentDetailsModal";
import { checkCapstoneHealth } from "./lib/capstoneApi";
import { checkCodeForgeHealth } from "./lib/codeforgeApi";
import { checkAptitudeHealth } from "./lib/aptitudeApi";
import { checkCommunicationHealth, getDailyChallengeToday } from "./lib/communicationApi";
import { checkResumeBuilderHealth } from "./lib/resumeBuilderApi";
import { createInitialResumeBuilderState, handleResumeBuilderText, importResumeBuilderFile, openResumeBuilderChat, type ResumeBuilderFlowState } from "./lib/resumeBuilderFlow";
import { checkCertificateAgentHealth } from "./lib/certificateAgentApi";
import { createInitialCertificateState, handleCertificateText, openCertificateChat, type CertificateFlowState } from "./lib/certificateAgentFlow";
import { fetchMe, googleAuth, login as loginApi, signup as signupApi, type AuthUser } from "./lib/authApi";
import { routeMessage, type RouteTurn } from "./lib/orchestratorApi";

type OpenMenu = "user" | "notif" | null;

const TOKEN_KEY = "digidara_token";
const GOOGLE_OAUTH_CALLBACK_PATH = "/auth/google/callback";
const GOOGLE_OAUTH_STATE_KEY = "digidara_google_oauth_state";
const isGoogleOAuthCallback = () => window.location.pathname === GOOGLE_OAUTH_CALLBACK_PATH;

function loadUser(): User | null {
  const saved = JSON.parse(localStorage.getItem("digidara_user") || "null") as User | null;
  return saved?.id ? saved : null;
}

function loadToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function toUser(authUser: AuthUser): User {
  const name = authUser.name || "User";
  return { id: authUser.id, name, email: authUser.email, mobile: authUser.mobile ?? "", initial: (name[0] || "U").toUpperCase() };
}

function capstoneKey(email: string) {
  return `digidara_capstone_${email.trim().toLowerCase()}`;
}

function loadCapstoneStates(email?: string): Record<string, CapstoneFlowState> {
  if (!email) return {};
  return JSON.parse(localStorage.getItem(capstoneKey(email)) || "{}");
}

function codeforgeKey(email: string) {
  return `digidara_codeforge_${email.trim().toLowerCase()}`;
}

function loadCodeForgeStates(email?: string): Record<string, CodeForgeFlowState> {
  if (!email) return {};
  return JSON.parse(localStorage.getItem(codeforgeKey(email)) || "{}");
}

function aptitudeKey(email: string) { return `digidara_aptitude_${email.trim().toLowerCase()}`; }
function loadAptitudeStates(email?: string): Record<string, AptitudeFlowState> { if (!email) return {}; return JSON.parse(localStorage.getItem(aptitudeKey(email)) || "{}"); }

function communicationKey(email: string) {
  return `digidara_communication_${email.trim().toLowerCase()}`;
}

function loadCommunicationStates(email?: string): Record<string, CommunicationFlowState> {
  if (!email) return {};
  return JSON.parse(localStorage.getItem(communicationKey(email)) || "{}");
}

function resumeBuilderKey(email: string) { return `digidara_resume_builder_${email.trim().toLowerCase()}`; }
function loadResumeBuilderStates(email?: string): Record<string, ResumeBuilderFlowState> { return email ? JSON.parse(localStorage.getItem(resumeBuilderKey(email)) || "{}") : {}; }

function certificateKey(email: string) { return `digidara_certificate_${email.trim().toLowerCase()}`; }
function loadCertificateStates(email?: string): Record<string, CertificateFlowState> { return email ? JSON.parse(localStorage.getItem(certificateKey(email)) || "{}") : {}; }

export default function App() {
  const [user, setUser] = useState<User | null>(() => loadUser());
  const [googleAuthPending, setGoogleAuthPending] = useState(() => isGoogleOAuthCallback());
  const [view, setView] = useState<View>("chat");
  const [activeTab, setActiveTab] = useState("Top Picks");
  const [searchTerm, setSearchTerm] = useState("");
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [newChatPending, setNewChatPending] = useState(true);
  const [chats, setChats] = useState<Chat[]>([]);
  const [capstoneStates, setCapstoneStates] = useState<Record<string, CapstoneFlowState>>(() => loadCapstoneStates(loadUser()?.email));
  const [codeforgeStates, setCodeforgeStates] = useState<Record<string, CodeForgeFlowState>>(() => loadCodeForgeStates(loadUser()?.email));
  const [aptitudeStates, setAptitudeStates] = useState<Record<string, AptitudeFlowState>>(() => loadAptitudeStates(loadUser()?.email));
  const [communicationStates, setCommunicationStates] = useState<Record<string, CommunicationFlowState>>(() => loadCommunicationStates(loadUser()?.email));
  const [resumeBuilderStates, setResumeBuilderStates] = useState<Record<string, ResumeBuilderFlowState>>(() => loadResumeBuilderStates(loadUser()?.email));
  const [certificateStates, setCertificateStates] = useState<Record<string, CertificateFlowState>>(() => loadCertificateStates(loadUser()?.email));
  const [dashboardOpen, setDashboardOpen] = useState(false);
  const [capstoneOnline, setCapstoneOnline] = useState(false);
  const [codeforgeOnline, setCodeforgeOnline] = useState(false);
  const [aptitudeOnline, setAptitudeOnline] = useState(false);
  const [communicationOnline, setCommunicationOnline] = useState(false);
  const [resumeBuilderOnline, setResumeBuilderOnline] = useState(false);
  const [certificateOnline, setCertificateOnline] = useState(false);
  const [certificateSecondsLeft, setCertificateSecondsLeft] = useState<number | null>(null);
  const [dailyChallengeStatus, setDailyChallengeStatus] = useState<"pending" | "completed">("pending");
  const [codeBusy, setCodeBusy] = useState(false);
  const skipCapstoneSave = useRef(true);
  const skipCodeforgeSave = useRef(true);
  const skipCommunicationSave = useRef(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [playgroundOpen, setPlaygroundOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [openMenu, setOpenMenu] = useState<OpenMenu>(null);
  const [glowOn, setGlowOn] = useState(true);
  const [typing, setTyping] = useState(false);
  const [toastMsg, setToastMsg] = useState("");
  const [toastShow, setToastShow] = useState(false);
  const toastTimer = useRef<number | undefined>(undefined);
  const replyTimer = useRef<number | undefined>(undefined);
  const aptitudeTimeoutSubmissions = useRef(new Set<string>());
  // A timeout belongs to a particular question, not an entire session. A
  // single session contains 30 questions, each with its own three minutes.
  const certificateTimeoutQuestionRef = useRef<string | null>(null);
  const certificateTabFailureSessionRef = useRef<string | null>(null);

  const { loadChats, saveChats } = useChats(user?.email);

  // Must run before the `!user` early return below — React requires every
  // render to call the same hooks in the same order, and this one used to
  // live after that return, so it ran only while logged in. Flipping
  // logged-out <-> logged-in changed the hook count mid-flight and crashed
  // the whole tree ("Rendered fewer hooks than expected").
  const dailyChallengeChat = chats.find((c) => c.id === currentChatId) || null;
  const dailyChallengeCommState = dailyChallengeChat ? communicationStates[dailyChallengeChat.id] : undefined;
  useEffect(() => {
    if (!dailyChallengeCommState?.authToken) return;
    let active = true;
    getDailyChallengeToday(dailyChallengeCommState.authToken)
      .then((status) => active && setDailyChallengeStatus(status.all_completed ? "completed" : "pending"))
      .catch(() => active && setDailyChallengeStatus("pending"));
    return () => { active = false; };
  }, [dailyChallengeCommState?.authToken, dailyChallengeCommState?.step, dailyChallengeCommState?.sessionId]);

  const showToast = useCallback((msg: string) => {
    setToastMsg(msg);
    setToastShow(true);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToastShow(false), 2600);
  }, []);

  // Validate the cached session against the backend once on boot, rather
  // than trusting a stale/tampered localStorage user indefinitely. Skipped
  // on the Google OAuth callback URL — that load is handled by the effect
  // below instead, and there's usually no prior session to validate yet.
  useEffect(() => {
    if (isGoogleOAuthCallback()) return;
    const token = loadToken();
    if (!token) {
      if (user) setUser(null);
      return;
    }
    let active = true;
    fetchMe(token)
      .then((authUser) => {
        if (!active) return;
        const freshUser = toUser(authUser);
        localStorage.setItem("digidara_user", JSON.stringify(freshUser));
        setUser(freshUser);
      })
      .catch(() => {
        if (!active) return;
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem("digidara_user");
        setUser(null);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Completes the Google OAuth redirect: exchange the one-time `code` for a
  // real session, verify `state` to guard against CSRF, then clean the URL
  // back to "/" regardless of outcome so a refresh doesn't replay the code
  // (Google authorization codes are single-use).
  useEffect(() => {
    if (!isGoogleOAuthCallback()) return;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const oauthError = params.get("error");
    const expectedState = sessionStorage.getItem(GOOGLE_OAUTH_STATE_KEY);
    sessionStorage.removeItem(GOOGLE_OAUTH_STATE_KEY);
    window.history.replaceState({}, "", "/");

    if (oauthError) {
      setGoogleAuthPending(false);
      showToast("Google sign-in was cancelled.");
      return;
    }
    if (!code || !state || !expectedState || state !== expectedState) {
      setGoogleAuthPending(false);
      showToast("Google sign-in failed — please try again.");
      return;
    }
    googleAuth(code)
      .then((result) => {
        const newUser = toUser(result.user);
        localStorage.setItem(TOKEN_KEY, result.access_token);
        localStorage.setItem("digidara_user", JSON.stringify(newUser));
        setUser(newUser);
        setView("chat");
        setNewChatPending(true);
        setCurrentChatId(null);
        showToast(`Welcome, ${newUser.name.split(" ")[0]}!`);
      })
      .catch((error) => {
        showToast(`Google sign-in failed: ${(error as Error).message}`);
      })
      .finally(() => setGoogleAuthPending(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // load this user's chats once they're known
  useEffect(() => {
    if (user) {
      setChats(loadChats());
      setCapstoneStates(loadCapstoneStates(user.email));
      setCodeforgeStates(loadCodeForgeStates(user.email));
      setAptitudeStates(loadAptitudeStates(user.email));
      setCommunicationStates(loadCommunicationStates(user.email));
      setCertificateStates(loadCertificateStates(user.email));
    } else {
      setChats([]);
      setCapstoneStates({});
      setCodeforgeStates({});
      setAptitudeStates({});
      setCommunicationStates({});
      setCertificateStates({});
    }
    skipCapstoneSave.current = true;
    skipCodeforgeSave.current = true;
    skipCommunicationSave.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email]);

  useEffect(() => {
    if (!user) return;
    if (skipCapstoneSave.current) {
      skipCapstoneSave.current = false;
      return;
    }
    const serializable = Object.fromEntries(
      Object.entries(capstoneStates).map(([id, state]) => {
        const { docxFile: _docxFile, zipFile: _zipFile, ...saved } = state;
        return [id, saved];
      }),
    );
    localStorage.setItem(capstoneKey(user.email), JSON.stringify(serializable));
  }, [capstoneStates, user]);

  useEffect(() => {
    if (!user) return;
    if (skipCodeforgeSave.current) {
      skipCodeforgeSave.current = false;
      return;
    }
    localStorage.setItem(codeforgeKey(user.email), JSON.stringify(codeforgeStates));
  }, [codeforgeStates, user]);

  useEffect(() => { if (!user) return; localStorage.setItem(aptitudeKey(user.email), JSON.stringify(aptitudeStates)); }, [aptitudeStates, user]);

  useEffect(() => {
    if (!user) return;
    if (skipCommunicationSave.current) {
      skipCommunicationSave.current = false;
      return;
    }
    localStorage.setItem(communicationKey(user.email), JSON.stringify(communicationStates));
  }, [communicationStates, user]);

  useEffect(() => {
    if (user) localStorage.setItem(resumeBuilderKey(user.email), JSON.stringify(resumeBuilderStates));
  }, [resumeBuilderStates, user]);

  useEffect(() => {
    if (user) localStorage.setItem(certificateKey(user.email), JSON.stringify(certificateStates));
  }, [certificateStates, user]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const updateHealth = () => checkCapstoneHealth().then((online) => { if (active) setCapstoneOnline(online); });
    updateHealth();
    const timer = window.setInterval(updateHealth, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const updateHealth = () => checkResumeBuilderHealth().then((online) => { if (active) setResumeBuilderOnline(online); });
    updateHealth();
    const timer = window.setInterval(updateHealth, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const updateHealth = () => checkCertificateAgentHealth().then((online) => { if (active) setCertificateOnline(online); });
    updateHealth();
    const timer = window.setInterval(updateHealth, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const updateHealth = () => checkAptitudeHealth().then((online) => { if (active) setAptitudeOnline(online); });
    updateHealth(); const timer = window.setInterval(updateHealth, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const updateHealth = () => checkCodeForgeHealth().then((online) => { if (active) setCodeforgeOnline(online); });
    updateHealth();
    const timer = window.setInterval(updateHealth, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [user]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const updateHealth = () => checkCommunicationHealth().then((online) => { if (active) setCommunicationOnline(online); });
    updateHealth();
    const timer = window.setInterval(updateHealth, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [user]);

  useEffect(() => {
    document.body.classList.toggle("glow-off", !glowOn);
  }, [glowOn]);

  useEffect(() => {
    function onDocClick() {
      setOpenMenu(null);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setSettingsOpen(false);
        setSelectedAgent(null);
        setOpenMenu(null);
      }
    }
    document.addEventListener("click", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("click", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  useEffect(() => () => window.clearTimeout(replyTimer.current), []);

  useEffect(() => {
    const commState = currentChatId ? communicationStates[currentChatId] : undefined;
    if (!user || !commState?.authToken) return;
    let active = true;
    getDailyChallengeToday(commState.authToken)
      .then((status) => active && setDailyChallengeStatus(status.all_completed ? "completed" : "pending"))
      .catch(() => active && setDailyChallengeStatus("pending"));
    return () => { active = false; };
  }, [user, currentChatId, communicationStates]);

  // The standalone certificate UI gives each chat-exam question three
  // minutes. Store an absolute deadline in its persisted flow state so a
  // browser refresh cannot reset the timer.
  useEffect(() => {
    const certState = currentChatId ? certificateStates[currentChatId] : undefined;
    if (!currentChatId || certState?.step !== "awaiting_chat_session" || !certState.sessionId) {
      setCertificateSecondsLeft(null);
      return;
    }

    const sessionId = certState.sessionId;
    const questionKey = `${sessionId}:${certState.currentQuestionIndex ?? 0}`;
    const deadline = certState.questionDeadlineAt ?? Date.now() + 3 * 60 * 1000;
    const tick = () => {
      const secondsLeft = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setCertificateSecondsLeft(secondsLeft);
      if (secondsLeft === 0 && certificateTimeoutQuestionRef.current !== questionKey) {
        certificateTimeoutQuestionRef.current = questionKey;
        sendMessage("Timeout");
      }
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [currentChatId, certificateStates]);

  // Three visibility changes close the attempt. The counter is kept in
  // sessionStorage, so refreshing cannot clear it; the backend receives a
  // terminal failure event and becomes the source of truth for the outcome.
  useEffect(() => {
    const certState = currentChatId ? certificateStates[currentChatId] : undefined;
    if (certState?.step !== "awaiting_chat_session" || !certState.sessionId) return;

    const sessionId = certState.sessionId;
    const storageKey = `digidara_cert_tab_switches_${sessionId}`;
    const onVisibilityChange = () => {
      if (!document.hidden) return;
      const count = Number(sessionStorage.getItem(storageKey) || "0") + 1;
      sessionStorage.setItem(storageKey, String(count));
      if (count >= 3 && certificateTabFailureSessionRef.current !== sessionId) {
        certificateTabFailureSessionRef.current = sessionId;
        sendMessage("force_fail_due_to_tab_switches", undefined, true);
      } else if (count < 3) {
        showToast(`Tab-switch warning ${count}/3. A third switch fails this exam.`);
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [currentChatId, certificateStates]);

  function persistChats(next: Chat[]) {
    setChats(next);
    saveChats(next);
  }

  async function handleAuthenticate(
    mode: "login" | "signup",
    details: { name: string; email: string; mobile: string; password: string },
  ): Promise<string | null> {
    const email = details.email.trim().toLowerCase();
    try {
      const result = mode === "signup"
        ? await (async () => {
            const mobile = details.mobile.replace(/[\s()-]/g, "");
            if (!/^\+?\d{8,15}$/.test(mobile)) throw new Error("Enter a valid mobile number with country code.");
            return signupApi(details.name.trim(), email, mobile, details.password);
          })()
        : await loginApi(email, details.password);

      const newUser = toUser(result.user);
      localStorage.setItem(TOKEN_KEY, result.access_token);
      localStorage.setItem("digidara_user", JSON.stringify(newUser));
      setUser(newUser);
      setView("chat");
      setNewChatPending(true);
      setCurrentChatId(null);
      showToast(`${mode === "signup" ? "Account created" : "Welcome back"}, ${newUser.name.split(" ")[0]}!`);
      return null;
    } catch (error) {
      return (error as Error).message;
    }
  }

  function handleLogout() {
    localStorage.removeItem("digidara_user");
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setCurrentChatId(null);
    setNewChatPending(true);
    setCapstoneStates({});
    setCodeforgeStates({});
    setAptitudeStates({});
    setCommunicationStates({});
    setResumeBuilderStates({});
    setCertificateStates({});
    setDashboardOpen(false);
    setView("chat");
  }

  function switchView(next: View) {
    setView(next);
    if (next === "store") {
      setCurrentChatId(null);
      setNewChatPending(false);
      setDashboardOpen(false);
    }
    setMobileOpen(false);
  }

  function appendAgentMessages(chatId: string, messages: { text: string; options?: ChatOption[] }[]) {
    if (!messages.length) return;
    setChats((prev) => {
      const next = prev.map((c) =>
        c.id === chatId
          ? {
              ...c,
              messages: [...c.messages, ...messages.map((message) => ({ role: "agent" as const, text: message.text, options: message.options, time: nowStr() }))],
              updatedAt: Date.now(),
            }
          : c
      );
      saveChats(next);
      return next;
    });
  }

  function scheduleReply(chatId: string) {
    window.clearTimeout(replyTimer.current);
    replyTimer.current = window.setTimeout(() => {
      const reply = CANNED_REPLIES[Math.floor(Math.random() * CANNED_REPLIES.length)];
      setChats((prev) => {
        const next = prev.map((c) =>
          c.id === chatId
            ? { ...c, messages: [...c.messages, { role: "agent" as const, text: reply, time: nowStr() }], updatedAt: Date.now() }
            : c
        );
        saveChats(next);
        return next;
      });
      setTyping(false);
    }, 950 + Math.random() * 500);
  }

  /** Switches an existing (general-chat) thread over to a specialized
   * agent's own dedicated multi-turn flow, without losing what was already
   * said — mirrors openAgentChat's per-kind setup but appends onto the
   * current chat instead of replacing it. */
  async function handoffToAgent(chatId: string, agent: Agent) {
    if (!user) return;
    appendAgentMessages(chatId, [{ text: `Connecting you to the ${agent.name}…` }]);
    setChats((prev) => {
      const next = prev.map((c) => (c.id === chatId ? { ...c, agentId: agent.id } : c));
      saveChats(next);
      return next;
    });
    setDashboardOpen(false);

    if (agent.kind === "capstone") {
      const initialState = createInitialCapstoneState(user);
      const welcome = initialCapstoneMessage(user);
      setCapstoneStates((prev) => ({ ...prev, [chatId]: initialState }));
      appendAgentMessages(chatId, [{ text: welcome.text, options: welcome.options }]);
    } else if (agent.kind === "codeforge") {
      const { state: initialState, messages } = await openCodeForgeChat(user);
      setCodeforgeStates((prev) => ({ ...prev, [chatId]: initialState }));
      appendAgentMessages(chatId, messages);
    } else if (agent.kind === "aptitude") {
      const { state: initialState, messages } = await openAptitudeChat(user);
      setAptitudeStates((prev) => ({ ...prev, [chatId]: initialState }));
      appendAgentMessages(chatId, messages);
    } else if (agent.kind === "communication") {
      const { state: initialState, messages } = await openCommunicationChat(user);
      setCommunicationStates((prev) => ({ ...prev, [chatId]: initialState }));
      appendAgentMessages(chatId, messages);
    } else if (agent.kind === "resume-builder") {
      const { state, messages } = await openResumeBuilderChat(user);
      setResumeBuilderStates((prev) => ({ ...prev, [chatId]: state }));
      appendAgentMessages(chatId, messages);
    } else if (agent.kind === "certificate") {
      const { state, messages } = await openCertificateChat(user);
      setCertificateStates((prev) => ({ ...prev, [chatId]: state }));
      appendAgentMessages(chatId, messages);
    }
    setTyping(false);
  }

  /** Last 12 turns of a chat, oldest first, as {role, content} for the
   * router — enough for a vague opener to accumulate real signal across a
   * few follow-ups without letting the request grow unbounded. */
  function toRouteHistory(messages: ChatMessage[]): RouteTurn[] {
    return messages.slice(-12).map((m) => ({ role: m.role === "user" ? "user" : "assistant", content: m.text }));
  }

  /** General-chat turn: asks the orchestrator's LLM router whether this
   * message matches a registered agent. A match hands the chat off to that
   * agent's real flow; no match shows the router's own reply. Falls back to
   * a canned reply if the orchestrator/LLM is unreachable, so general chat
   * still feels alive offline. `history` is this chat's prior turns (not
   * including `text`) — without it, every message is routed in isolation
   * and a vague opener followed by several turns of added detail never
   * accumulates enough signal to route; see orchestrator/graph.py. */
  async function routeGeneralMessage(chatId: string, text: string, history: RouteTurn[] = []) {
    try {
      const result = await routeMessage(text, history);
      const matched = result.agent_name ? findAgentByBackendName(result.agent_name) : undefined;
      if (matched) {
        await handoffToAgent(chatId, matched);
        return;
      }
      appendAgentMessages(chatId, [{ text: result.reply || "I'm not sure how to help with that yet — could you rephrase it?" }]);
      setTyping(false);
    } catch {
      scheduleReply(chatId);
    }
  }

  function openAgentChat(agentId: string) {
    const agent = findAgent(agentId);
    if (!agent || !user) return;
    const chat: Chat = {
      id: "c_" + Date.now(),
      agentId: agent.id,
      title: agent.name,
      messages: [{ role: "agent", text: agent.greeting, time: nowStr() }],
      updatedAt: Date.now(),
    };
    persistChats([...chats, chat]);
    setCurrentChatId(chat.id);
    setNewChatPending(false);
    setTyping(false);
    if (agent.kind === "capstone") {
      const initialState = createInitialCapstoneState(user);
      const welcome = initialCapstoneMessage(user);
      chat.messages = [{ role: "agent", text: welcome.text, options: welcome.options, time: nowStr() }];
      persistChats([...chats, chat]);
      setCapstoneStates((prev) => ({ ...prev, [chat.id]: initialState }));
      setDashboardOpen(false);
    } else if (agent.kind === "codeforge") {
      setDashboardOpen(false);
      setTyping(true);
      openCodeForgeChat(user).then(({ state: initialState, messages }) => {
        setCodeforgeStates((prev) => ({ ...prev, [chat.id]: initialState }));
        setChats((prev) => {
          const next = prev.map((c) =>
            c.id === chat.id
              ? { ...c, messages: messages.map((m) => ({ role: "agent" as const, text: m.text, options: m.options, time: nowStr() })), updatedAt: Date.now() }
              : c
          );
          saveChats(next);
          return next;
        });
        setTyping(false);
      });
    } else if (agent.kind === "aptitude") {
      setDashboardOpen(false);
      setTyping(true);
      openAptitudeChat(user).then(({ state: initialState, messages }) => {
        setAptitudeStates((prev) => ({ ...prev, [chat.id]: initialState }));
        setChats((prev) => {
          const next = prev.map((c) =>
            c.id === chat.id
              ? { ...c, messages: messages.map((m) => ({ role: "agent" as const, text: m.text, options: m.options, time: nowStr() })), updatedAt: Date.now() }
              : c
          );
          saveChats(next);
          return next;
        });
        setTyping(false);
      });
    } else if (agent.kind === "communication") {
      setDashboardOpen(false);
      setTyping(true);
      openCommunicationChat(user).then(({ state: initialState, messages }) => {
        setCommunicationStates((prev) => ({ ...prev, [chat.id]: initialState }));
        setChats((prev) => {
          const next = prev.map((c) =>
            c.id === chat.id
              ? { ...c, messages: messages.map((m) => ({ role: "agent" as const, text: m.text, options: m.options, time: nowStr() })), updatedAt: Date.now() }
              : c
          );
          saveChats(next);
          return next;
        });
        setTyping(false);
      });
    } else if (agent.kind === "resume-builder") {
      setDashboardOpen(false);
      setTyping(true);
      openResumeBuilderChat(user).then(({ state, messages }) => {
        setResumeBuilderStates((prev) => ({ ...prev, [chat.id]: state }));
        setChats((prev) => {
          const next = prev.map((c) => c.id === chat.id
            ? { ...c, messages: messages.map((m) => ({ role: "agent" as const, text: m.text, options: m.options, time: nowStr() })), updatedAt: Date.now() }
            : c);
          saveChats(next);
          return next;
        });
        setTyping(false);
      });
    } else if (agent.kind === "certificate") {
      setDashboardOpen(false);
      setTyping(true);
      openCertificateChat(user).then(({ state, messages }) => {
        setCertificateStates((prev) => ({ ...prev, [chat.id]: state }));
        setChats((prev) => {
          const next = prev.map((c) => c.id === chat.id
            ? { ...c, messages: messages.map((m) => ({ role: "agent" as const, text: m.text, options: m.options, time: nowStr() })), updatedAt: Date.now() }
            : c);
          saveChats(next);
          return next;
        });
        setTyping(false);
      });
    }
    switchView("chat");
  }

  function openAgentDetails(agentId: string) {
    const agent = findAgent(agentId);
    if (agent) setSelectedAgent(agent);
  }

  function startChatFromDetails(agentId: string) {
    setSelectedAgent(null);
    openAgentChat(agentId);
  }

  function startNewChatLanding() {
    setCurrentChatId(null);
    setNewChatPending(true);
    setTyping(false);
    setDashboardOpen(false);
    switchView("chat");
  }

  function startNewChatWithMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    const chat: Chat = {
      id: "c_" + Date.now(),
      agentId: DEFAULT_AGENT.id,
      title: trimmed.length > 42 ? trimmed.slice(0, 42) + "…" : trimmed,
      messages: [{ role: "user", text: trimmed, time: nowStr() }],
      updatedAt: Date.now(),
    };
    persistChats([...chats, chat]);
    setCurrentChatId(chat.id);
    setNewChatPending(false);
    setTyping(true);
    routeGeneralMessage(chat.id, trimmed);
  }

  function openChatById(chatId: string) {
    const chat = chats.find((c) => c.id === chatId);
    if (!chat) return;
    setCurrentChatId(chat.id);
    setNewChatPending(false);
    setTyping(false);
    setDashboardOpen(false);
    switchView("chat");
  }

  /** The flow state a given agent kind is currently sitting at for this
   * chat — used both to process a fresh message and, for `sendMessage`'s
   * `editIndex` path, as the fallback when an older message has no snapshot
   * of its own (shouldn't normally happen, but keeps editing from silently
   * no-oping). */
  function currentFlowStateFor(kind: Agent["kind"], chatId: string): unknown {
    if (kind === "capstone") return capstoneStates[chatId];
    if (kind === "codeforge") return codeforgeStates[chatId];
    if (kind === "aptitude") return aptitudeStates[chatId];
    if (kind === "communication") return communicationStates[chatId];
    if (kind === "certificate") return certificateStates[chatId];
    return undefined;
  }

  /** Sends `text` as a new user message, or — when `editIndex` is given —
   * replaces the user message at that index and discards everything after
   * it, then resumes processing from the flow state snapshot captured just
   * before that original message. That's what makes editing, say, a
   * Capstone topic-request message regenerate topics from the new wording:
   * it's just re-running the normal flow handler with different text from
   * the same starting point, not a special "edit" code path per agent. */
  function sendMessage(text: string, editIndex?: number, internal = false, displayText?: string) {
    if (!text.trim() || !currentChatId || !user) return;
    const chatId = currentChatId;
    const chat = chats.find((c) => c.id === chatId);
    const agent = chat ? findAgent(chat.agentId) : undefined;

    const isEdit = editIndex != null && !!chat;
    const editedMessage = isEdit ? chat!.messages[editIndex!] : undefined;
    const baseMessages = isEdit ? chat!.messages.slice(0, editIndex!) : chat?.messages ?? [];
    const resumeSnapshot = isEdit ? editedMessage?.stateSnapshot : currentFlowStateFor(agent?.kind, chatId);
    // Match the standalone CertifyAI chat: as soon as a difficulty is chosen,
    // acknowledge the background generation job and lock the composer.  Only
    // do this when the preceding prompt was the difficulty picker; otherwise
    // a casual use of the word "beginner" must remain a normal chat message.
    const previousOptions = !isEdit ? chat?.messages.at(-1)?.options?.map((option) => option.value.toLowerCase()) ?? [] : [];
    const isDifficultyChoice = ["beginner", "intermediate", "advanced", "mixed"].includes(text.trim().toLowerCase())
      && ["beginner", "intermediate", "advanced", "mixed"].every((level) => previousOptions.includes(level));
    const certificateGenerationNotice = agent?.kind === "certificate"
      && !internal
      && (resumeSnapshot as CertificateFlowState | undefined)?.step === "awaiting_topic"
      && isDifficultyChoice
      ? `⚡ Generating your 30-question **${text.trim().charAt(0).toUpperCase()}${text.trim().slice(1).toLowerCase()}** certification exam${(resumeSnapshot as CertificateFlowState).topic ? ` for **'${(resumeSnapshot as CertificateFlowState).topic}'**` : ""}...\nThis usually takes 15–20 seconds. Please wait!`
      : undefined;

    const withUserMsg = chats.map((c) => {
      if (c.id !== chatId) return c;
      const messages = internal
        ? baseMessages
        : [
            ...baseMessages,
            { role: "user" as const, text: displayText ?? text, time: nowStr(), stateSnapshot: resumeSnapshot },
            ...(certificateGenerationNotice
              ? [{ role: "agent" as const, text: certificateGenerationNotice, time: nowStr() }]
              : []),
          ];
      const isFirstUserMsg = messages.filter((m) => m.role === "user").length === 1;
      return {
        ...c,
        messages,
        updatedAt: Date.now(),
        title: isFirstUserMsg ? ((displayText ?? text).length > 42 ? (displayText ?? text).slice(0, 42) + "…" : (displayText ?? text)) : c.title,
      };
    });
    persistChats(withUserMsg);
    setTyping(true);

    if (agent?.kind === "capstone") {
      const flowState = (resumeSnapshot as CapstoneFlowState | undefined) ?? createInitialCapstoneState(user);
      handleCapstoneText(flowState, text).then(({ state: nextState, messages }) => {
        setCapstoneStates((prev) => ({ ...prev, [chatId]: nextState }));
        appendAgentMessages(chatId, messages);
        setTyping(false);
      });
      return;
    }

    if (agent?.kind === "codeforge") {
      const flowState = resumeSnapshot as CodeForgeFlowState | undefined;
      if (!flowState) {
        setTyping(false);
        return;
      }
      handleCodeForgeText(flowState, text).then(({ state: nextState, messages }) => {
        setCodeforgeStates((prev) => ({ ...prev, [chatId]: nextState }));
        appendAgentMessages(chatId, messages);
        setTyping(false);
      });
      return;
    }

    if (agent?.kind === "aptitude") {
      const flowState = aptitudeStates[chatId] ?? createInitialAptitudeState();
      handleAptitudeText(flowState, text, user)
        .then(({ state: nextState, messages }) => {
          setAptitudeStates((prev) => ({ ...prev, [chatId]: nextState as AptitudeFlowState }));
          appendAgentMessages(chatId, messages);
        })
        .catch((error) => {
          appendAgentMessages(chatId, [{ text: `Aptitude request failed: ${(error as Error).message}` }]);
        })
        .finally(() => setTyping(false));
      return;
    }

    if (agent?.kind === "communication") {
      const flowState = resumeSnapshot as CommunicationFlowState | undefined;
      if (!flowState) {
        setTyping(false);
        return;
      }
      handleCommunicationText(flowState, text).then(({ state: nextState, messages }) => {
        setCommunicationStates((prev) => ({ ...prev, [chatId]: nextState }));
        appendAgentMessages(chatId, messages);
        setTyping(false);
      });
      return;
    }

    if (agent?.kind === "resume-builder") {
      const flowState = resumeBuilderStates[chatId] ?? createInitialResumeBuilderState();
      handleResumeBuilderText(flowState, user, text).then(({ state, messages }) => {
        setResumeBuilderStates((prev) => ({ ...prev, [chatId]: state }));
        appendAgentMessages(chatId, messages);
        setTyping(false);
      });
      return;
    }

    if (agent?.kind === "certificate") {
      const flowState = certificateStates[chatId] ?? createInitialCertificateState();
      handleCertificateText(flowState, text, user)
        .then(({ state, messages }) => {
          setCertificateStates((prev) => ({ ...prev, [chatId]: state }));
          appendAgentMessages(chatId, messages);
        })
        .catch(() => {
          appendAgentMessages(chatId, [{
            text: "I couldn’t complete that certificate request right now. Your certificate records are safe. Please try again in a moment.",
          }]);
        })
        .finally(() => setTyping(false));
      return;
    }

    routeGeneralMessage(chatId, text, toRouteHistory(baseMessages));
  }

  function editMessage(index: number, newText: string) {
    sendMessage(newText, index);
  }

  function expireAptitudeQuestion() {
    if (!currentChat || !user) return;
    const chatId = currentChat.id;
    const flowState = aptitudeStates[chatId];
    if (!flowState || flowState.step !== "awaiting_question" || !flowState.question) return;
    const timeoutKey = `${flowState.testId || ""}:${flowState.question.sequence}`;
    // This guard lives above the question panel, so moving/remounting that
    // panel after a chat update can never submit the same timeout twice.
    if (aptitudeTimeoutSubmissions.current.has(timeoutKey)) return;
    aptitudeTimeoutSubmissions.current.add(timeoutKey);
    setTyping(true);
    handleAptitudeText(flowState, "__aptitude_timeout__", user)
      .then(({ state: nextState, messages }) => {
        setAptitudeStates((prev) => ({ ...prev, [chatId]: nextState as AptitudeFlowState }));
        appendAgentMessages(chatId, messages);
      })
      .catch((error) => {
        appendAgentMessages(chatId, [{ text: `The timer expired, but the answer could not be submitted: ${(error as Error).message}` }]);
      })
      .finally(() => setTyping(false));
  }

  function handleRunCode(code: string) {
    if (!currentChatId) return;
    const chatId = currentChatId;
    const flowState = codeforgeStates[chatId];
    if (!flowState) return;
    setCodeBusy(true);
    runCodeForgeCode(flowState, code).then(({ state: nextState, messages }) => {
      setCodeforgeStates((prev) => ({ ...prev, [chatId]: nextState }));
      appendAgentMessages(chatId, messages);
      setCodeBusy(false);
    });
  }

  function handleSubmitCode(code: string) {
    if (!currentChatId) return;
    const chatId = currentChatId;
    const flowState = codeforgeStates[chatId];
    if (!flowState) return;
    setCodeBusy(true);
    submitCodeForgeCode(flowState, code).then(({ state: nextState, messages }) => {
      setCodeforgeStates((prev) => ({ ...prev, [chatId]: nextState }));
      appendAgentMessages(chatId, messages);
      setCodeBusy(false);
    });
  }

  function handleAttachFiles(files: FileList) {
    if (!currentChatId || !user) return;
    const chatId = currentChatId;
    const chat = chats.find((c) => c.id === chatId);
    const agent = chat ? findAgent(chat.agentId) : undefined;

    if (agent?.kind === "capstone") {
      const flowState = capstoneStates[chatId] ?? createInitialCapstoneState(user);
      const { state: mergedState, messages } = mergeCapstoneFiles(flowState, Array.from(files));
      setCapstoneStates((prev) => ({ ...prev, [chatId]: mergedState }));
      appendAgentMessages(chatId, messages);

      if (mergedState.docxFile && mergedState.zipFile) {
        setTyping(true);
        submitCapstoneFiles(mergedState).then(({ state: finalState, messages: finalMessages }) => {
          setCapstoneStates((prev) => ({ ...prev, [chatId]: finalState }));
          appendAgentMessages(chatId, finalMessages);
          setTyping(false);
        });
      }
      return;
    }

    if (agent?.kind === "resume-builder") {
      const file = Array.from(files)[0];
      if (!file) return;
      setTyping(true);
      importResumeBuilderFile(resumeBuilderStates[chatId] ?? createInitialResumeBuilderState(), user, file).then(({ state, messages }) => {
        setResumeBuilderStates((prev) => ({ ...prev, [chatId]: state }));
        appendAgentMessages(chatId, messages);
        setTyping(false);
      });
      return;
    }

    showToast("File attachments are only available in the Capstone Project Agent chat.");
  }

  function handleNavAction(action: "my-agents" | "workflows" | "saved" | "settings" | "playground") {
    if (action === "settings") {
      setSettingsOpen(true);
      return;
    }
    if (action === "playground") {
      setPlaygroundOpen(true);
      return;
    }
    if (action === "my-agents") {
      switchView("store");
      return;
    }
    showToast("This section is coming soon.");
  }

  function handleUserMenuAction(action: "profile" | "settings" | "logout") {
    if (action === "logout") handleLogout();
    if (action === "settings") setSettingsOpen(true);
    if (action === "profile") setProfileOpen(true);
    setOpenMenu(null);
  }

  function handleClearHistory() {
    persistChats([]);
    setCapstoneStates({});
    setCodeforgeStates({});
    setAptitudeStates({});
    setCommunicationStates({});
    startNewChatLanding();
    setSettingsOpen(false);
    showToast("Chat history cleared.");
  }

  if (!user) {
    if (googleAuthPending) {
      return (
        <div className="login-overlay">
          <div className="login-card">
            <div className="login-logo">
              <span className="logo-mark">⚡</span>
              <span className="logo-text">Digi<b>DARA</b></span>
            </div>
            <p className="login-sub">Signing you in with Google…</p>
          </div>
        </div>
      );
    }
    return <LoginOverlay onAuthenticate={handleAuthenticate} />;
  }

  const currentChat = chats.find((c) => c.id === currentChatId) || null;
  const currentAgent = currentChat ? findAgent(currentChat.agentId) || DEFAULT_AGENT : DEFAULT_AGENT;
  const isHome = view === "chat" && newChatPending;
  const topbarTitle = view === "store" ? "My agents" : !isHome && currentChat ? currentAgent.name : "DigiDARA Agents";
  const isCapstoneChat = currentAgent.kind === "capstone";
  const isCodeForgeChat = currentAgent.kind === "codeforge";
  const isAptitudeChat = currentAgent.kind === "aptitude";
  const isCommunicationChat = currentAgent.kind === "communication";
  const isResumeBuilderChat = currentAgent.kind === "resume-builder";
  const isCertificateChat = currentAgent.kind === "certificate";
  const capstoneState = currentChat ? capstoneStates[currentChat.id] : undefined;
  const codeforgeState = currentChat ? codeforgeStates[currentChat.id] : undefined;
  const aptitudeState = currentChat ? aptitudeStates[currentChat.id] : undefined;
  const communicationState = currentChat ? communicationStates[currentChat.id] : undefined;
  const resumeBuilderState = currentChat ? resumeBuilderStates[currentChat.id] : undefined;
  const certificateState = currentChat ? certificateStates[currentChat.id] : undefined;

  const pendingFiles = capstoneState ? [capstoneState.docxFile, capstoneState.zipFile].filter((f): f is File => !!f) : [];
  const systemOnline = isCapstoneChat ? capstoneOnline : isCodeForgeChat ? codeforgeOnline : isAptitudeChat ? aptitudeOnline : isCommunicationChat ? communicationOnline : isResumeBuilderChat ? resumeBuilderOnline : isCertificateChat ? certificateOnline : true;

  const CAPSTONE_STEP_LABELS: Record<string, string> = {
    awaiting_topic_request: "Choosing a topic",
    awaiting_topic_choice: "Choose a project",
    awaiting_timer_confirm: "Ready to start",
    awaiting_submission: "Project in progress",
    not_eligible: "Verification required",
    graded: "Graded",
  };
  const CODEFORGE_STEP_LABELS: Record<string, string> = {
    awaiting_course: "Choose a course",
    awaiting_technology: "Choose a technology",
    awaiting_topic: "Choose a topic",
    awaiting_problem: "Choose a problem",
    awaiting_code: "Solving a problem",
  };
  const COMMUNICATION_STEP_LABELS: Record<string, string> = {
    main_menu: "Choose what to practice",
    awaiting_writing_topic: "Choose a writing topic",
    awaiting_speaking_topic: "Choose a speaking topic",
    awaiting_pronunciation_mode: "Choose a pronunciation mode",
    writing_turn: "Writing practice",
    speaking_turn: "Speaking practice",
    pronunciation_turn: "Pronunciation practice",
  };

  let connectorStatus: string | undefined;
  let connectorPendingTask: string | null | undefined;
  let connectorDifficultyPicker: { value: "easy" | "medium" | "hard"; onChange: (value: "easy" | "medium" | "hard") => void } | undefined;
  let connectorQuickActions: ChatOption[] | undefined;
  let typingLabel: string | undefined;

  if (isCapstoneChat && capstoneState) {
    connectorStatus = CAPSTONE_STEP_LABELS[capstoneState.step] ?? capstoneState.step;
    connectorPendingTask = capstoneState.step === "awaiting_submission" && capstoneState.deadlineAt
      ? `Deadline ${new Date(capstoneState.deadlineAt).toLocaleString()}`
      : capstoneState.step === "awaiting_topic_choice"
        ? "Pick project A or B to continue"
        : null;
    if ((capstoneState.step === "awaiting_topic_request" || capstoneState.step === "awaiting_topic_choice") && currentChat) {
      const chatId = currentChat.id;
      connectorDifficultyPicker = {
        value: capstoneState.difficulty,
        onChange: (value) => {
          const flowState = capstoneStates[chatId];
          if (!flowState || value === flowState.difficulty) return;
          if (flowState.step !== "awaiting_topic_choice") {
            setCapstoneStates((prev) => ({ ...prev, [chatId]: { ...prev[chatId], difficulty: value } }));
            return;
          }
          setTyping(true);
          regenerateTopicsForDifficulty(flowState, value).then(({ state: nextState, messages }) => {
            setCapstoneStates((prev) => ({ ...prev, [chatId]: nextState }));
            appendAgentMessages(chatId, messages);
            setTyping(false);
          });
        },
      };
    }
  } else if (isCodeForgeChat && codeforgeState) {
    connectorStatus = CODEFORGE_STEP_LABELS[codeforgeState.step] ?? codeforgeState.step;
    connectorPendingTask = codeforgeState.step === "awaiting_code" && codeforgeState.problemName
      ? `Solve: ${codeforgeState.problemName}`
      : null;
  } else if (isAptitudeChat && aptitudeState) {
    connectorStatus = aptitudeState.step === "completed" ? "Test completed" : aptitudeState.step === "awaiting_next_question" ? "Next question pending" : aptitudeState.question ? `Question ${aptitudeState.question.sequence}` : "Ready to practice";
    connectorPendingTask = aptitudeState.question ? `${aptitudeState.question.category} · ${aptitudeState.question.difficulty}` : null;
  } else if (isCommunicationChat && communicationState) {
    connectorStatus = COMMUNICATION_STEP_LABELS[communicationState.step] ?? communicationState.step;
    connectorPendingTask = communicationState.activeModule && communicationState.currentItemText
      ? `Practicing: ${communicationState.currentItemText}`
      : null;
    if (communicationState.step === "main_menu") connectorQuickActions = COMMUNICATION_MENU_OPTIONS;
  } else if (isCertificateChat && certificateState) {
    connectorStatus = (certificateState.step === "awaiting_question" && certificateState.questions
      ? `${certificateState.topic} Exam (${(certificateState.currentQuestionIndex ?? 0) + 1}/${certificateState.questions.length})`
      : certificateState.step === "awaiting_chat_session"
        ? `${certificateState.topic || "Certification"} Exam (${(certificateState.currentQuestionIndex ?? 0) + 1}/${certificateState.totalQuestions ?? 30})`
      : certificateState.step === "awaiting_topic"
        ? "Choose an exam topic"
        : certificateState.step === "completed"
          ? "Exam completed"
          : certificateState.step === "exam_instructions"
            ? "Exam instructions"
            : "Certification Agent");
    connectorPendingTask = typing
      ? "Generating certification questions..."
      : null;
    if (typing && certificateState.step === "awaiting_topic") {
      typingLabel = "CertifyAI is generating your 30-question certification exam…";
    }
  }

  function handleChatBack() {
    if (currentChat && currentChat.agentId !== DEFAULT_AGENT.id) {
      switchView("store");
    } else {
      startNewChatLanding();
    }
  }

  return (
    <>
      <div className="app" id="app">
        <Sidebar
          user={user}
          collapsed={sidebarCollapsed}
          mobileOpen={mobileOpen}
          homeActive={isHome}
          chats={chats}
          currentChatId={currentChatId}
          userMenuOpen={openMenu === "user"}
          onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
          onNewChat={startNewChatLanding}
          onGoHome={startNewChatLanding}
          onOpenChat={openChatById}
          onNavAction={handleNavAction}
          onToggleUserMenu={(e) => {
            e.stopPropagation();
            setOpenMenu((m) => (m === "user" ? null : "user"));
          }}
          onUserMenuAction={handleUserMenuAction}
        />

        <main className="main">
          <Topbar
            title={topbarTitle}
            user={user}
            notifOpen={openMenu === "notif"}
            dashboardAvailable={(isCapstoneChat || isCodeForgeChat || isAptitudeChat || isCommunicationChat || isResumeBuilderChat) && !!currentChat}
            dashboardOpen={dashboardOpen}
            onToggleDashboard={() => setDashboardOpen((open) => !open)}
            systemOnline={systemOnline}
            onToggleMobileMenu={() => setMobileOpen((v) => !v)}
            onToggleNotif={(e) => {
              e.stopPropagation();
              setOpenMenu((m) => (m === "notif" ? null : "notif"));
            }}
          />

          {view === "store" && (
            <StoreView
              activeTab={activeTab}
              searchTerm={searchTerm}
              onTabChange={setActiveTab}
              onSearchChange={setSearchTerm}
              onOpenAgent={openAgentDetails}
            />
          )}

          {view === "chat" && newChatPending && <NewChatLanding onSend={startNewChatWithMessage} />}

          {view === "chat" && !newChatPending && currentChat && (
            <div className="chat-workspace">
              <ChatView
                chat={currentChat}
                agent={currentAgent}
                user={user}
                typing={typing}
                typingLabel={typingLabel}
                composerDisabled={isCertificateChat && typing}
                onBack={handleChatBack}
                onSend={sendMessage}
                onChooseOption={(value, label) => sendMessage(value, undefined, false, label)}
                onEditMessage={editMessage}
                attachEnabled={isCapstoneChat || isResumeBuilderChat}
                attachAccept={isResumeBuilderChat ? ".pdf,.doc,.docx,.txt" : ".docx,.zip"}
                pendingFiles={pendingFiles}
                onAttachFiles={handleAttachFiles}
                onAttachDisabled={() => showToast("File attachments are only available in the Capstone Project Agent chat.")}
                codeMode={isCodeForgeChat && codeforgeState?.step === "awaiting_code"}
                codeSeed={codeforgeState?.starterCode}
                codeBusy={codeBusy}
                onRunCode={handleRunCode}
                onSubmitCode={handleSubmitCode}
                connectorStatus={connectorStatus}
                connectorPendingTask={connectorPendingTask}
                connectorDifficultyPicker={connectorDifficultyPicker}
                contextPanel={isAptitudeChat && aptitudeState ? <AptitudePracticePanel state={aptitudeState} onChoose={sendMessage} onExpire={expireAptitudeQuestion} /> : undefined}
                connectorQuickActions={connectorQuickActions}
                onConnectorQuickAction={sendMessage}
                dailyChallengeStatus={isCommunicationChat ? dailyChallengeStatus : undefined}
                onDailyChallenge={() => sendMessage("daily_challenge")}
                immersiveSpeaking={isCommunicationChat && communicationState?.step === "speaking_turn"}
                certificateExamInstructions={isCertificateChat && certificateState?.step === "exam_instructions"
                  ? {
                      topic: certificateState.topic || "Certification",
                      totalQuestions: certificateState.totalQuestions ?? 30,
                      onStart: () => sendMessage("start_certificate_exam", undefined, true),
                    }
                  : undefined}
                certificateExamTimer={isCertificateChat && certificateState?.step === "awaiting_chat_session" && certificateSecondsLeft !== null
                  ? {
                      secondsLeft: certificateSecondsLeft,
                      currentQuestion: (certificateState.currentQuestionIndex ?? 0) + 1,
                      totalQuestions: certificateState.totalQuestions ?? 30,
                    }
                  : undefined}
              />
              {isCapstoneChat && dashboardOpen && capstoneState && (
                <AgentDashboard user={user} state={capstoneState} onClose={() => setDashboardOpen(false)} />
              )}
              {isCodeForgeChat && dashboardOpen && codeforgeState && (
                <CodeForgeDashboard user={user} state={codeforgeState} onClose={() => setDashboardOpen(false)} />
              )}
              {isAptitudeChat && dashboardOpen && aptitudeState && (
                <AptitudeDashboard user={user} state={aptitudeState} onClose={() => setDashboardOpen(false)} />
              )}
              {isCommunicationChat && dashboardOpen && communicationState && (
                <CommunicationDashboard user={user} state={communicationState} onClose={() => setDashboardOpen(false)} />
              )}
              {isResumeBuilderChat && dashboardOpen && resumeBuilderState && (
                <ResumeBuilderDashboard user={user} state={resumeBuilderState} onClose={() => setDashboardOpen(false)} />
              )}
            </div>
          )}
        </main>
      </div>

      <SettingsModal
        open={settingsOpen}
        user={user}
        chats={chats}
        onOpenChat={(chatId) => {
          setSettingsOpen(false);
          openChatById(chatId);
        }}
        glowOn={glowOn}
        onClose={() => setSettingsOpen(false)}
        onGlowToggle={setGlowOn}
        onClearHistory={handleClearHistory}
        onToast={showToast}
      />

      <ProfilePage open={profileOpen} user={user} onClose={() => setProfileOpen(false)} />

      <CodeForgePlayground open={playgroundOpen} onClose={() => setPlaygroundOpen(false)} onToast={showToast} />

      <AgentDetailsModal
        agent={selectedAgent}
        onClose={() => setSelectedAgent(null)}
        onStartChat={startChatFromDetails}
      />

      <Toast message={toastMsg} show={toastShow} />
    </>
  );
}
