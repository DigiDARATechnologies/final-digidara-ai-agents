import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import client from "../api/client";
import DifficultySelector from "../components/DifficultySelector.jsx";
import IconButton from "../components/IconButton.jsx";
import ModeTabs from "../components/ModeTabs.jsx";
import ScoreRing from "../components/ScoreRing.jsx";
import SessionResultDashboard from "../components/SessionResultDashboard.jsx";
import DailyConversationStart from "../components/DailyConversationStart.jsx";
import DailyProgress from "../components/DailyProgress.jsx";
import DailyQuickFeedback from "../components/DailyQuickFeedback.jsx";
import DailySessionSummary from "../components/DailySessionSummary.jsx";
import DailyMilestone from "../components/DailyMilestone.jsx";
import GenerateTopicsButton from "../components/GenerateTopicsButton.jsx";
import DailyChallengeReminder from "../components/DailyChallengeReminder.jsx";
import LeaveSessionDialog from "../components/LeaveSessionDialog.jsx";
import ModuleBackButton from "../components/ModuleBackButton.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import tutorAvatar from "../assets/avatar/tutor.png";
import { formatScore10 } from "../utils/scoreFormat.js";
import { Briefcase, GraduationCap, HeartHandshake, MessageCircle, PawPrint, Plane, RefreshCw, ShoppingBag, Sparkles, Utensils } from "lucide-react";

const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

const NO_SPEECH_FALLBACK_SECONDS = 60;
const NO_TRANSCRIPT_FALLBACK_SECONDS = 20;
const NOISE_WARNING_LEVEL = 0.015;
const SPEECH_RECOGNITION_LANG = "en-IN";
const DONE_TRIGGER_PATTERN = /(?:[\s,.;:!?-]+|^)(?:(?:and|then|and[\s,.;:!?-]+(?:then|them|all))[\s,.;:!?-]+)?(?:i[\s,.;:!?-]*(?:am|['\u2019]?m)[\s,.;:!?-]+(?:(?:then|them|all)[\s,.;:!?-]+)?(?:done|finish(?:ed)?)|that[\s,.;:!?-]*(?:is|['\u2019]?s)[\s,.;:!?-]+all|all[\s,.;:!?-]+done)[\s,.;:!?-]*$/i;
const ANSWER_SECONDS_BY_DIFFICULTY = {
  easy: 60,
  medium: 90,
  hard: 120,
};

export default function Speaking() {
  const { user } = useAuth() || {};
  const [mode, setMode] = useState(() => {
    const requestedMode = new URLSearchParams(window.location.search).get("mode");
    return requestedMode === "daily" ? "daily" : "topic";
  });
  const [difficulty, setDifficulty] = useState("easy");
  const [topicOptions, setTopicOptions] = useState([]);
  const [selectedTopicId, setSelectedTopicId] = useState("");
  const [customTopic, setCustomTopic] = useState(null);
  const [showCustomTopicForm, setShowCustomTopicForm] = useState(false);
  const [customTopicForm, setCustomTopicForm] = useState({ title: "", description: "" });
  const [customTopicErrors, setCustomTopicErrors] = useState({});
  const [topicLoading, setTopicLoading] = useState(false);
  const [topicError, setTopicError] = useState("");
  const [setupError, setSetupError] = useState("");
  const [setupNotice, setSetupNotice] = useState("");
  const [dailyVocabulary, setDailyVocabulary] = useState([]);
  const [dailyVocabularyUsed, setDailyVocabularyUsed] = useState([]);
  const [dailyChallengeStatus, setDailyChallengeStatus] = useState(null);
  const [dailyChallengeReminderDismissed, setDailyChallengeReminderDismissed] = useState(false);

  const [state, setState] = useState("setup");
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [turnNumber, setTurnNumber] = useState(1);
  const [transcript, setTranscript] = useState("");
  const [currentFeedback, setCurrentFeedback] = useState(null);
  const [summary, setSummary] = useState(null);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [micError, setMicError] = useState("");
  const [flowError, setFlowError] = useState("");
  const [answerSecondsLeft, setAnswerSecondsLeft] = useState(getAnswerLimitSeconds(difficulty));
  const [answerLimitSeconds, setAnswerLimitSeconds] = useState(getAnswerLimitSeconds(difficulty));
  const [answerTimerNotice, setAnswerTimerNotice] = useState("");
  const [retryingCorrectionId, setRetryingCorrectionId] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showLeaveDialog, setShowLeaveDialog] = useState(false);

  const recognitionRef = useRef(null);
  const answerTimerRef = useRef(null);
  const noSpeechFallbackTimerRef = useRef(null);
  const noTranscriptFallbackTimerRef = useRef(null);
  const transitionTimerRef = useRef(null);
  const submitRetryTimerRef = useRef(null);
  const routeLeaveResolverRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const audioMonitorFrameRef = useRef(null);
  const audioMonitorPeakRef = useRef(0);
  const answerRecorderRef = useRef(null);
  const answerRecorderStreamRef = useRef(null);
  const answerAudioChunksRef = useRef([]);
  const answerAudioMimeTypeRef = useRef("");
  const noisyInputSinceRef = useRef(null);
  const finalTranscriptRef = useRef("");
  const transcriptSnapshotRef = useRef("");
  const keepListeningRef = useRef(false);
  const networkErrorCountRef = useRef(0);
  const noSpeechErrorCountRef = useRef(0);
  const recognitionDiagnosticsRef = useRef({});
  const stopReasonRef = useRef("");
  const submittingRef = useRef(false);
  const submissionLockRef = useRef(false);
  const submissionRetryPendingRef = useRef(false);
  const isLeavingRef = useRef(false);
  const chatEndRef = useRef(null);
  const topicRequestRef = useRef({ id: 0, controller: null });
  const topicAutoTimerRef = useRef(null);
  const lastGenerateAtRef = useRef(0);
  const lastAutoGenerateRef = useRef({ key: "", at: 0 });
  const listeningCycleRef = useRef(0);
  const stateRef = useRef(state);
  const sessionRef = useRef(session);
  const difficultyRef = useRef(difficulty);
  const turnNumberRef = useRef(turnNumber);
  const answerSecondsLeftRef = useRef(answerSecondsLeft);
  const answerLimitSecondsRef = useRef(answerLimitSeconds);
  const allTopicOptions = useMemo(
    () => (customTopic ? [customTopic, ...topicOptions] : topicOptions),
    [customTopic, topicOptions]
  );
  const selectedTopic = useMemo(
    () => allTopicOptions.find((topic) => topic.topic_id === selectedTopicId || topic.id === selectedTopicId) || null,
    [selectedTopicId, allTopicOptions]
  );
  const openingGreeting = useMemo(() => getTimeBasedGreeting(user?.name), [user?.name]);

  const recordSpeechDiagnostic = (eventName, details = {}) => {
    const current = recognitionDiagnosticsRef.current || {};
    const events = { ...(current.events || {}), [eventName]: Date.now() };
    recognitionDiagnosticsRef.current = {
      ...current,
      events,
      lastEvent: eventName,
      lastDetails: details,
      resultCount: current.resultCount || 0,
    };
    console.info(`[speaking.recognition] ${eventName}`, {
      cycle: current.cycle,
      permission: current.permissionState || "unknown",
      resultCount: recognitionDiagnosticsRef.current.resultCount,
      ...details,
    });
  };

  const loadDailyChallengeStatus = async () => {
    try {
      const res = await client.get("/speaking/daily-challenge-status");
      setDailyChallengeStatus(res.data);
    } catch {
      setDailyChallengeStatus(null);
    }
  };

  useEffect(() => {
    loadDailyChallengeStatus();
  }, []);

  useEffect(() => {
    difficultyRef.current = difficulty;
    if (mode !== "topic") {
      setShowCustomTopicForm(false);
      setCustomTopicErrors({});
      setTopicOptions([]);
      setSelectedTopicId("");
      let cancelled = false;
      client.get("/speaking/daily").then((res) => {
        if (!cancelled) {
          setDailyVocabulary(res.data.daily_vocabulary || []);
          setDailyVocabularyUsed(res.data.daily_vocab_used || []);
        }
      }).catch(() => {
        // The start screen keeps a small curated vocabulary fallback.
      });
      return () => { cancelled = true; };
    }
    const autoKey = `speaking:${mode}:${difficulty}`;
    const now = Date.now();
    if (lastAutoGenerateRef.current.key === autoKey && now - lastAutoGenerateRef.current.at < 1500) {
      return;
    }
    lastAutoGenerateRef.current = { key: autoKey, at: now };
    topicAutoTimerRef.current = window.setTimeout(() => {
      generateTopics();
    }, 250);
    return () => {
      if (topicAutoTimerRef.current) clearTimeout(topicAutoTimerRef.current);
    };
  }, [difficulty, mode]);

  useEffect(() => {
    return () => {
      if (topicAutoTimerRef.current) clearTimeout(topicAutoTimerRef.current);
      topicRequestRef.current.controller?.abort();
      cleanupVoiceAndTimers();
    };
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, state, transcript, currentFeedback]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const handleDifficultyChange = (nextDifficulty) => {
    const normalizedDifficulty = normalizeDifficulty(nextDifficulty);
    difficultyRef.current = normalizedDifficulty;
    const limitSeconds = getAnswerLimitSeconds(normalizedDifficulty);
    answerSecondsLeftRef.current = limitSeconds;
    answerLimitSecondsRef.current = limitSeconds;
    setDifficulty(normalizedDifficulty);
    setAnswerSecondsLeft(limitSeconds);
    setAnswerLimitSeconds(limitSeconds);
    setTopicOptions([]);
    setSelectedTopicId((current) => (customTopic && current === customTopic.id ? current : ""));
    setTopicError("");
    setSetupError("");
    setSetupNotice("");
  };

  const openCustomTopicForm = () => {
    setSetupError("");
    setCustomTopicErrors({});
    setCustomTopicForm({
      title: customTopic?.title || "",
      description: customTopic?.description || "",
    });
    setShowCustomTopicForm(true);
  };

  const closeCustomTopicForm = () => {
    setShowCustomTopicForm(false);
    setCustomTopicErrors({});
  };

  const validateCustomTopic = (form = customTopicForm) => {
    const title = String(form.title || "").trim();
    const description = String(form.description || "").trim();
    const errors = {};
    if (title.length < 3 || title.length > 80) {
      errors.title = "Title must be 3 to 80 characters.";
    }
    if (description.length < 10 || description.length > 500) {
      errors.description = "Description must be 10 to 500 characters.";
    }
    return { title, description, errors };
  };

  const saveCustomTopic = () => {
    const { title, description, errors } = validateCustomTopic();
    setCustomTopicErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const id = customTopic?.id || `custom-${window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
    const nextTopic = {
      id,
      topic_id: null,
      title,
      description,
      difficulty,
      expected_duration_seconds: getAnswerLimitSeconds(difficulty),
      source: "custom",
      isCustom: true,
    };
    setCustomTopic(nextTopic);
    setSelectedTopicId(id);
    setShowCustomTopicForm(false);
    setCustomTopicErrors({});
    setSetupError("");
  };

  const removeCustomTopic = () => {
    setCustomTopic(null);
    setShowCustomTopicForm(false);
    setCustomTopicErrors({});
    setSelectedTopicId((current) => (current === customTopic?.id ? "" : current));
  };

  useEffect(() => {
    turnNumberRef.current = turnNumber;
  }, [turnNumber]);

  useEffect(() => {
    answerSecondsLeftRef.current = answerSecondsLeft;
  }, [answerSecondsLeft]);

  useEffect(() => {
    answerLimitSecondsRef.current = answerLimitSeconds;
  }, [answerLimitSeconds]);

  useEffect(() => {
    if (!session || state === "setup" || state === "completed") return undefined;
    const handleBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [session, state]);

  useEffect(() => {
    if (!session || state === "setup" || state === "completed") return undefined;
    const requestLeave = () => {
      setShowLeaveDialog(true);
      return new Promise((resolve) => {
        routeLeaveResolverRef.current = resolve;
      });
    };
    window.__communiCoachRequestLeave = requestLeave;
    return () => {
      if (window.__communiCoachRequestLeave === requestLeave) {
        delete window.__communiCoachRequestLeave;
      }
      if (routeLeaveResolverRef.current) {
        routeLeaveResolverRef.current(false);
        routeLeaveResolverRef.current = null;
      }
    };
  }, [session, state]);

  useEffect(() => {
    if (!showCustomTopicForm) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        closeCustomTopicForm();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showCustomTopicForm]);

  const generateTopics = async (manual = false, { retrying = false } = {}) => {
    topicRequestRef.current.controller?.abort();
    const controller = new AbortController();
    const requestId = topicRequestRef.current.id + 1;
    topicRequestRef.current = { id: requestId, controller };
    const selectedDifficulty = difficultyRef.current;

    const now = Date.now();
    if (manual && now - lastGenerateAtRef.current < 5000) {
      setTopicError("Please wait a few seconds before generating another topic.");
      return;
    }
    lastGenerateAtRef.current = now;

    setTopicLoading(true);
    setTopicError("");
    setTopicOptions([]);
    setSelectedTopicId((current) => (customTopic && current === customTopic.id ? current : ""));
    let retryScheduled = false;
    try {
      const res = await client.post("/practice/generate-topics", {
        practice_type: "speaking",
        mode: mode === "topic" ? "topic_wise" : "daily_conversation",
        difficulty: selectedDifficulty,
      }, {
        signal: controller.signal,
      });
      if (topicRequestRef.current.id !== requestId) return;
      const payload = res.data.data || res.data.topics || res.data;
      const topics = dedupeTopicOptions(Array.isArray(payload) ? payload : []);
      setTopicOptions(topics);
      setSelectedTopicId((current) => (customTopic && current === customTopic.id ? current : (topics[0]?.topic_id || topics[0]?.id || "")));
      if (topics.some((topic) => topic.source === "fallback")) {
        setTopicError("");
      }
    } catch (err) {
      if (err.code === "ERR_CANCELED" || err.name === "CanceledError") {
        if (!manual && !retrying && topicRequestRef.current.id === requestId) {
          retryScheduled = true;
          window.setTimeout(() => {
            if (topicRequestRef.current.id === requestId) {
              generateTopics(false, { retrying: true });
            }
          }, 1500);
        }
        return;
      }
      if (topicRequestRef.current.id !== requestId) return;
      const shouldRetryAutomatic =
        !manual &&
        !retrying &&
        (err.response?.status === 429 || err.response?.status === 202) &&
        ["RATE_LIMITED", "GENERATION_IN_PROGRESS"].includes(err.response?.data?.error_code);
      if (shouldRetryAutomatic) {
        retryScheduled = true;
        window.setTimeout(() => {
          if (topicRequestRef.current.id === requestId) {
            generateTopics(false, { retrying: true });
          }
        }, 1500);
        return;
      }
      setTopicOptions([]);
      setSelectedTopicId((current) => (customTopic && current === customTopic.id ? current : ""));
      setTopicError(getApiMessage(err, "Could not generate a speaking topic. Check the backend and try again."));
    } finally {
      if (topicRequestRef.current.id === requestId && !retryScheduled) {
        setTopicLoading(false);
      }
    }
  };

  const restoreActiveSession = async () => {
    try {
      const res = await client.get("/speaking/active");
      const active = res.data.session;
      if (!active) return;
      setSession(active);
      setMode(active.mode);
      if (active.mode === "topic") handleDifficultyChange(active.difficulty || "easy");
      setDailyVocabulary(active.daily_vocabulary || []);
      setDailyVocabularyUsed(active.daily_vocab_used || []);
      setTurnNumber(active.turn_number || 1);
      setCurrentQuestion(active.question || "");
      setMessages(messagesFromTurns(active.turns || [], active.mode === "daily", openingGreeting));
      setState(active.question ? "waiting_for_user" : "setup");
      setFlowError("An active speaking session was restored. Resume voice when you are ready.");
    } catch {
      // Active restore is helpful, not required for first load.
    }
  };

  const startSession = async (requestedMode = mode) => {
    const effectiveMode = requestedMode === "daily" || requestedMode === "topic" ? requestedMode : mode;
    isLeavingRef.current = false;
    submissionLockRef.current = false;
    submittingRef.current = false;
    setIsSubmitting(false);
    setSetupError("");
    setSetupNotice("");
    setFlowError("");
    if (effectiveMode === "daily") {
      cleanupVoiceAndTimers();
      setSetupNotice("Loading today's conversation...");
      setState("starting");
      try {
        setMode("daily");
        const res = await client.post("/speaking/start", { mode: "daily" });
        const started = res.data;
        const hasAnsweredTurns = (started.turns || []).some((turn) => turn.user_answer);
        const shouldSpeakOpeningGreeting = (started.turn_number || 1) === 1 && !(started.answered_turns || 0) && !hasAnsweredTurns;
        setFlowError("");
        sessionRef.current = started;
        turnNumberRef.current = started.turn_number || 1;
        setSession(started);
        setTurnNumber(started.turn_number || 1);
        setDailyVocabulary(started.daily_vocabulary || []);
        setDailyVocabularyUsed(started.daily_vocab_used || []);
        setCurrentQuestion(started.question || "");
        setMessages(shouldSpeakOpeningGreeting
          ? [{ type: "greeting", turnNumber: "intro", text: openingGreeting }]
          : messagesFromTurns(started.turns || [], true, openingGreeting)
        );
        if (started.status === "completed") {
          setSummary(started.summary || null);
          setState("completed");
        } else {
          if (shouldSpeakOpeningGreeting) {
            askQuestionWithOpeningGreeting(started.question, openingGreeting, {
              type: "question",
              turnNumber: started.turn_number || 1,
              text: started.question,
            });
          } else {
            askQuestion(started.question);
          }
        }
      } catch (err) {
        setState("setup");
        setSetupNotice("");
        setSetupError(getApiMessage(err, "Today's conversation could not be loaded. Please try again."));
      }
      return;
    }

    if (!selectedTopic) {
      setSetupError("Please choose a topic before starting.");
      return;
    }

    cleanupVoiceAndTimers();
    setSetupNotice("Connecting to AI tutor… this may take a moment. We’ll use a safe starter question if AI is busy.");
    setState("starting");
    try {
      const selectedDifficulty = difficultyRef.current;
      const startPayload = selectedTopic.isCustom
        ? {
            mode: effectiveMode,
            difficulty: selectedDifficulty,
            generated_topic_id: null,
            topic_id: null,
            topic_title: selectedTopic.title,
            topic_description: selectedTopic.description,
            topic_source: "custom",
          }
        : {
            mode: effectiveMode,
            difficulty: selectedDifficulty,
            generated_topic_id: selectedTopic.topic_id,
            topic_id: selectedTopic.topic_id,
            topic_title: selectedTopic.title,
            topic_description: selectedTopic.description,
            daily_category: effectiveMode === "daily" ? selectedTopic.title : null,
          };
      const res = await client.post("/speaking/start", startPayload);
      const started = res.data;
      setFlowError("");
      sessionRef.current = started;
      turnNumberRef.current = started.turn_number;
      setSession(started);
      setTurnNumber(started.turn_number);
      setCurrentQuestion(started.question);
      setMessages([
        { type: "greeting", turnNumber: "intro", text: openingGreeting },
      ]);
      askQuestionWithOpeningGreeting(started.question, openingGreeting, {
        type: "question",
        turnNumber: started.turn_number,
        text: started.question,
      });
    } catch (err) {
      setState("setup");
      setSetupNotice("");
      setSetupError(getApiMessage(err, "AI tutor is busy right now. Please try again in a minute."));
    }
  };

  const askQuestion = (questionText) => {
    const limitSeconds = getAnswerLimitSeconds(sessionRef.current?.difficulty || difficultyRef.current);
    networkErrorCountRef.current = 0;
    answerSecondsLeftRef.current = limitSeconds;
    answerLimitSecondsRef.current = limitSeconds;
    setCurrentFeedback(null);
    setTranscript("");
    setMicError("");
    setAnswerTimerNotice("");
    setAnswerSecondsLeft(limitSeconds);
    setAnswerLimitSeconds(limitSeconds);
    finalTranscriptRef.current = "";
    setState("ai_speaking");
    speak(questionText, () => {
      if (isLeavingRef.current) return;
      startListening();
    });
  };

  const askQuestionWithOpeningGreeting = (questionText, greetingText, questionMessage) => {
    const limitSeconds = getAnswerLimitSeconds(sessionRef.current?.difficulty || difficultyRef.current);
    networkErrorCountRef.current = 0;
    answerSecondsLeftRef.current = limitSeconds;
    answerLimitSecondsRef.current = limitSeconds;
    setCurrentFeedback(null);
    setTranscript("");
    setMicError("");
    setAnswerTimerNotice("");
    setAnswerSecondsLeft(limitSeconds);
    setAnswerLimitSeconds(limitSeconds);
    finalTranscriptRef.current = "";
    setState("ai_speaking");
    speak(greetingText, () => {
      if (isLeavingRef.current) return;
      setMessages((items) => (
        items.some((item) => item.type === "question" && item.turnNumber === questionMessage.turnNumber)
          ? items
          : [...items, questionMessage]
      ));
      speak(questionText, () => {
        if (isLeavingRef.current) return;
        startListening();
      });
    });
  };

  const speak = (text, onDone) => {
    if (!voiceEnabled || !window.speechSynthesis) {
      setAiSpeaking(false);
      onDone?.();
      return;
    }
    window.speechSynthesis.cancel();
    setAiSpeaking(false);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.98;
    utterance.onstart = () => setAiSpeaking(true);
    utterance.onend = () => {
      setAiSpeaking(false);
      onDone?.();
    };
    utterance.onerror = () => {
      setAiSpeaking(false);
      onDone?.();
    };
    window.speechSynthesis.speak(utterance);
  };

  const startListening = ({ resetAnswer = true, restartTimer = resetAnswer } = {}) => {
    if (isLeavingRef.current) return;
    if (state === "completed" || recognitionRef.current) return;
    setMicError("");
    stopReasonRef.current = "";
    if (restartTimer) {
      listeningCycleRef.current += 1;
    }
    const listeningCycle = listeningCycleRef.current;
    recognitionDiagnosticsRef.current = {
      cycle: listeningCycle,
      startedAt: Date.now(),
      permissionState: "unknown",
      events: {},
      resultCount: 0,
    };
    audioMonitorPeakRef.current = 0;
    noSpeechErrorCountRef.current = 0;
    navigator.permissions?.query?.({ name: "microphone" }).then((status) => {
      if (listeningCycleRef.current !== listeningCycle) return;
      recognitionDiagnosticsRef.current = {
        ...recognitionDiagnosticsRef.current,
        permissionState: status.state,
      };
      console.info("[speaking.recognition] microphone permission", { cycle: listeningCycle, state: status.state });
    }).catch(() => {
      console.info("[speaking.recognition] microphone permission", { cycle: listeningCycle, state: "unavailable" });
    });
    if (resetAnswer) {
      const limitSeconds = getAnswerLimitSeconds(sessionRef.current?.difficulty || difficultyRef.current);
      answerSecondsLeftRef.current = limitSeconds;
      answerLimitSecondsRef.current = limitSeconds;
      setTranscript("");
      setAnswerTimerNotice("");
      setAnswerSecondsLeft(limitSeconds);
      setAnswerLimitSeconds(limitSeconds);
      finalTranscriptRef.current = "";
      transcriptSnapshotRef.current = "";
    }

    if (!SpeechRecognitionAPI) {
      setMicError("Speech recognition is not supported in this browser. Type your answer below.");
      setState("transcript_ready");
      return;
    }

    const recognition = new SpeechRecognitionAPI();
    recognition.lang = SPEECH_RECOGNITION_LANG;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    scheduleNoSpeechFallback(listeningCycle);
    scheduleNoTranscriptFallback(listeningCycle);
    startAnswerRecording(listeningCycle);
    startAudioMonitoring();

    recognition.onstart = () => {
      recordSpeechDiagnostic("start");
      if (stateRef.current === "listening" && listeningCycleRef.current === listeningCycle) {
        setMicError("");
      }
    };

    recognition.onaudiostart = () => {
      recordSpeechDiagnostic("audio_start");
    };

    recognition.onaudioend = () => {
      recordSpeechDiagnostic("audio_end");
    };

    recognition.onsoundstart = () => {
      recordSpeechDiagnostic("sound_start");
    };

    recognition.onsoundend = () => {
      recordSpeechDiagnostic("sound_end");
    };

    recognition.onspeechstart = () => {
      recordSpeechDiagnostic("speech_start");
      if (stateRef.current === "listening" && listeningCycleRef.current === listeningCycle) {
        setMicError("");
      }
    };

    recognition.onspeechend = () => {
      recordSpeechDiagnostic("speech_end");
    };

    recognition.onnomatch = () => {
      recordSpeechDiagnostic("no_match");
      if (stateRef.current === "listening" && listeningCycleRef.current === listeningCycle) {
        setMicError("I could not recognize clear words yet. Please speak a little slower or retry recording.");
      }
    };

    recognition.onresult = (event) => {
      if (stateRef.current !== "listening" || listeningCycleRef.current !== listeningCycle || submittingRef.current) return;
      noSpeechErrorCountRef.current = 0;
      let interim = "";
      const resultDetails = [];
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const alternative = event.results[i][0];
        const text = alternative?.transcript || "";
        resultDetails.push({
          index: i,
          final: event.results[i].isFinal,
          confidence: alternative?.confidence,
          transcript: text,
        });
        if (event.results[i].isFinal) {
          finalTranscriptRef.current = `${finalTranscriptRef.current} ${text}`.trim();
        } else {
          interim += text;
        }
      }
      recognitionDiagnosticsRef.current = {
        ...recognitionDiagnosticsRef.current,
        resultCount: (recognitionDiagnosticsRef.current.resultCount || 0) + resultDetails.length,
        lastResultAt: Date.now(),
      };
      recordSpeechDiagnostic("result", { resultIndex: event.resultIndex, results: resultDetails });
      const combined = `${finalTranscriptRef.current} ${interim}`.trim();
      const triggerResult = getDoneTriggerResult(combined);
      const visibleTranscript = triggerResult.matched ? triggerResult.cleanedAnswer : combined;
      finalTranscriptRef.current = triggerResult.matched ? triggerResult.cleanedAnswer : finalTranscriptRef.current;
      transcriptSnapshotRef.current = visibleTranscript;
      setTranscript(visibleTranscript);
      if (visibleTranscript) clearNoTranscriptFallbackTimer();
      scheduleNoSpeechFallback(listeningCycle);
      if (triggerResult.matched) {
        if (triggerResult.cleanedAnswer) {
          finishAnswerNow({ answerOverride: triggerResult.cleanedAnswer, listeningCycle });
        } else {
          setMicError("Say your answer before saying \"I am done.\"");
        }
      }
    };

    recognition.onerror = async (event) => {
      recordSpeechDiagnostic("error", { error: event.error, message: event.message });
      if (event.error === "network") {
        networkErrorCountRef.current += 1;
      } else {
        networkErrorCountRef.current = 0;
      }
      if (event.error === "no-speech") {
        noSpeechErrorCountRef.current += 1;
        recordSpeechDiagnostic("no_speech_retry", {
          count: noSpeechErrorCountRef.current,
          audioMonitorPeak: Number((audioMonitorPeakRef.current || 0).toFixed(4)),
        });
        if (noSpeechErrorCountRef.current >= 2) {
          const handled = await recoverWithBackupTranscription(listeningCycle, "repeated_no_speech");
          if (handled) return;
        }
      }
      if (event.error === "not-allowed") {
        keepListeningRef.current = false;
        clearNoSpeechFallbackTimer();
        clearNoTranscriptFallbackTimer();
        setMicError("Microphone permission was denied.");
        setState("transcript_ready");
        return;
      }
      setMicError(event.error === "no-speech" ? "Still listening. You can pause, then continue speaking." : `Microphone reconnecting after: ${event.error}`);
    };

    recognition.onend = () => {
      recordSpeechDiagnostic("end");
      recognitionRef.current = null;
      if (keepListeningRef.current) {
        if (networkErrorCountRef.current >= 3) {
          const recoveredText = (transcriptSnapshotRef.current || finalTranscriptRef.current).trim();
          const triggerResult = getDoneTriggerResult(recoveredText);
          if (triggerResult.matched && triggerResult.cleanedAnswer) {
            keepListeningRef.current = false;
            clearNoSpeechFallbackTimer();
            clearNoTranscriptFallbackTimer();
            stopAudioMonitoring();
            finishAnswerNow({ answerOverride: triggerResult.cleanedAnswer, listeningCycle });
            return;
          }
          keepListeningRef.current = false;
          clearNoSpeechFallbackTimer();
          clearNoTranscriptFallbackTimer();
          stopAudioMonitoring();
          setMicError("Voice recognition is having trouble connecting. You can keep typing your answer below.");
          setState("transcript_ready");
          return;
        }
        window.setTimeout(() => {
          if (keepListeningRef.current && !recognitionRef.current) {
            startListening({ resetAnswer: false, restartTimer: false });
          }
        }, 250);
        return;
      }
      stopAudioMonitoring();
      const finalText = transcriptSnapshotRef.current.trim() || finalTranscriptRef.current.trim();
      const triggerResult = getDoneTriggerResult(finalText);
      if (triggerResult.matched && triggerResult.cleanedAnswer) {
        finishAnswerNow({ answerOverride: triggerResult.cleanedAnswer, listeningCycle });
        return;
      }
      setTranscript(finalText);
      if (stopReasonRef.current === "auto_submit") return;
      setState("transcript_ready");
    };

    recognitionRef.current = recognition;
    keepListeningRef.current = true;
    stateRef.current = "listening";
    setState("listening");
    try {
      recordSpeechDiagnostic("start_call");
      recognition.start();
      recordSpeechDiagnostic("start_call_ok");
      if (restartTimer) {
        startAnswerTimer();
      }
    } catch (err) {
      recordSpeechDiagnostic("start_call_failed", { message: err?.message });
      recognitionRef.current = null;
      keepListeningRef.current = false;
      stopAudioMonitoring();
      clearAnswerTimer();
      clearNoSpeechFallbackTimer();
      clearNoTranscriptFallbackTimer();
      setMicError("Could not start the microphone. Type your answer below.");
      setState("transcript_ready");
    }
  };

  const stopListening = ({ timeUp = false, reason = "review" } = {}) => {
    keepListeningRef.current = false;
    stopReasonRef.current = reason;
    clearAnswerTimer();
    clearNoSpeechFallbackTimer();
    clearNoTranscriptFallbackTimer();
    if (timeUp) {
      answerSecondsLeftRef.current = 0;
      setAnswerSecondsLeft(0);
      setAnswerTimerNotice("Time is up. Finishing your answer now.");
      finishAnswerNow();
      return;
    }
    try {
      recognitionRef.current?.stop();
    } catch {
      recognitionRef.current = null;
    }
  };

  const retryRecording = () => {
    stopListening({ reason: "retry" });
    const limitSeconds = getAnswerLimitSeconds(sessionRef.current?.difficulty || difficultyRef.current);
    answerSecondsLeftRef.current = limitSeconds;
    answerLimitSecondsRef.current = limitSeconds;
    setTranscript("");
    setMicError("");
    setAnswerTimerNotice("");
    setAnswerSecondsLeft(limitSeconds);
    setAnswerLimitSeconds(limitSeconds);
    finalTranscriptRef.current = "";
    transcriptSnapshotRef.current = "";
    window.setTimeout(() => startListening(), 250);
  };

  const cancelTranscript = () => {
    clearNoSpeechFallbackTimer();
    clearNoTranscriptFallbackTimer();
    setTranscript("");
    setAnswerTimerNotice("");
    setState("waiting_for_user");
  };

  const finishAnswerNow = ({ answerOverride = "", listeningCycle = listeningCycleRef.current } = {}) => {
    const answer = (answerOverride || transcriptSnapshotRef.current || finalTranscriptRef.current || transcript).trim();
    if (!answer) {
      setMicError("No answer captured yet. Keep speaking, or type your answer if the microphone is unavailable.");
      return;
    }
    if (listeningCycleRef.current !== listeningCycle || submittingRef.current || submissionLockRef.current) return;
    listeningCycleRef.current += 1;
    keepListeningRef.current = false;
    stopReasonRef.current = "auto_submit";
    clearAnswerTimer();
    clearNoSpeechFallbackTimer();
    clearNoTranscriptFallbackTimer();
    stopAnswerRecording({ keepBlob: false });
    try {
      recognitionRef.current?.stop();
    } catch {
      recognitionRef.current = null;
    }
    submitTranscript({ answerOverride: answer, turnNumberOverride: turnNumberRef.current });
  };

  const submitTranscript = async ({ answerOverride = "", turnNumberOverride = turnNumberRef.current } = {}) => {
    const answer = (answerOverride || transcript).trim();
    const activeSession = sessionRef.current;
    const sessionEnded = stateRef.current === "completed" || activeSession?.status === "completed";
    if (submissionLockRef.current || isSubmitting || sessionEnded || !activeSession?.session_id) return;
    if (!answer) {
      setFlowError("No answer was captured. Please retry this question.");
      setState("transcript_ready");
      return;
    }
    if (!activeSession?.session_id) {
      setFlowError("Could not submit because the speaking session is not ready. Please start the conversation again.");
      setState("transcript_ready");
      return;
    }
    submissionLockRef.current = true;
    submittingRef.current = true;
    setIsSubmitting(true);
    stateRef.current = "submitting";
    setState("submitting");
    setFlowError("");
    clearAnswerTimer();
    clearNoSpeechFallbackTimer();
    clearNoTranscriptFallbackTimer();
    stopAnswerRecording({ keepBlob: false });
    keepListeningRef.current = false;
    stopReasonRef.current = "auto_submit";
    try { recognitionRef.current?.stop(); } catch { recognitionRef.current = null; }
    const submissionId = `${activeSession.session_id}:${turnNumberOverride}`;

    try {
      const timeUsedSeconds = Math.max(0, answerLimitSecondsRef.current - answerSecondsLeftRef.current);
      const res = await client.post("/speaking/respond", {
        session_id: activeSession.session_id,
        answer,
        answer_time_seconds: timeUsedSeconds,
        answer_time_limit_seconds: answerLimitSecondsRef.current,
        submission_id: submissionId,
      }, { timeout: 45000 });
      const data = res.data;
      const feedback = data.feedback || {};
      if (data.daily_vocab_used) setDailyVocabularyUsed(data.daily_vocab_used);
      if (activeSession.mode !== "topic") {
        setSession((current) => current ? { ...current, answered_turns: (current.answered_turns || 0) + 1 } : current);
      }
      const feedbackSpeech = getFeedbackSpeechParts(feedback, answer);
      const feedbackMessage = {
        ...feedback,
        turn_id: data.feedback_turn_id,
        submittedAnswer: answer,
        explanation: feedbackSpeech.displayExplanation || feedbackSpeech.explanation,
        corrected_answer: feedback.corrected_answer || null,
        correctionReading: false,
      };
      setCurrentFeedback(feedbackMessage);
      setMessages((items) => [
        ...items,
        { type: "answer", turnNumber: turnNumberOverride, text: answer, timeUsedSeconds },
        { type: "feedback", turnNumber: turnNumberOverride, feedback: feedbackMessage },
      ]);
      setState("showing_feedback");

      const completeSession = () => {
        const completedSummary = data.summary;
        transitionTimerRef.current = window.setTimeout(() => {
          setSummary(completedSummary);
          setState("completed");
        }, 700);
      };

      const nextQuestion = data.next_question;
      const nextTurn = data.turn_number;
      const continueAfterFeedback = () => {
        if (data.done) {
          if (sessionRef.current?.mode === "daily") {
            loadDailyChallengeStatus();
          }
          completeSession();
          return;
        }
        turnNumberRef.current = nextTurn;
        setTurnNumber(nextTurn);
        setCurrentQuestion(nextQuestion);
        setMessages((items) => [...items, { type: "question", turnNumber: nextTurn, text: nextQuestion }]);
        askQuestion(nextQuestion);
      };

      const setCorrectionReading = (isReading) => {
        const updateFeedback = (item) => (
          item.type === "feedback" && item.turnNumber === turnNumberOverride
            ? { ...item, feedback: { ...item.feedback, correctionReading: isReading } }
            : item
        );
        setMessages((items) => items.map(updateFeedback));
        setCurrentFeedback((current) => current ? { ...current, correctionReading: isReading } : current);
      };

      const speakCorrectionThenContinue = () => {
        if (!feedbackSpeech.correctedAnswer) {
          continueAfterFeedback();
          return;
        }
        setCorrectionReading(true);
        setState("ai_feedback_speaking");
        transitionTimerRef.current = window.setTimeout(() => {
          speak(feedbackSpeech.correctedAnswer, () => {
            setCorrectionReading(false);
            continueAfterFeedback();
          });
        }, 150);
      };

      if (voiceEnabled) {
        setState("ai_feedback_speaking");
        transitionTimerRef.current = window.setTimeout(() => {
          speak(feedbackSpeech.explanation, feedbackSpeech.correctedAnswer ? speakCorrectionThenContinue : continueAfterFeedback);
        }, 150);
      } else {
        continueAfterFeedback();
      }
    } catch (err) {
      if (err.response?.status === 401) {
        cleanupVoiceAndTimers();
        localStorage.removeItem("cc_token");
        stateRef.current = "transcript_ready";
        setState("transcript_ready");
        setFlowError("Your login session expired. Please log in again before submitting.");
        return;
      }
      const submitErrorCode = err.response?.data?.error_code || err.response?.data?.code;
      if (submitErrorCode === "SESSION_ALREADY_COMPLETED" || submitErrorCode === "SESSION_COMPLETED") {
        cleanupVoiceAndTimers();
        setSession((current) => current ? { ...current, status: "completed" } : current);
        setFlowError("This session has already ended. Start a new conversation to continue.");
        setState("completed");
        return;
      }
      stateRef.current = "transcript_ready";
      setState("transcript_ready");
      setFlowError(getSubmitErrorMessage(err));
    } finally {
      submittingRef.current = false;
      submissionLockRef.current = false;
      setIsSubmitting(false);
    }
  };

  const retryCorrection = async (feedback) => {
    const turnId = feedback?.turn_id;
    const activeSession = sessionRef.current;
    if (!turnId || !activeSession?.session_id || retryingCorrectionId) return;
    setRetryingCorrectionId(turnId);
    try {
      const res = await client.post(`/speaking/turns/${turnId}/retry-correction`, {
        session_id: activeSession.session_id,
      }, { timeout: 20000 });
      const updatedFeedback = {
        ...(res.data.feedback || {}),
        turn_id: turnId,
        submittedAnswer: feedback.submittedAnswer || feedback.original_answer,
        correctionReading: false,
      };
      const speechParts = getFeedbackSpeechParts(updatedFeedback, updatedFeedback.submittedAnswer);
      updatedFeedback.explanation = speechParts.explanation;
      setCurrentFeedback((current) => current?.turn_id === turnId ? updatedFeedback : current);
      setMessages((items) => items.map((item) => (
        item.type === "feedback" && item.feedback?.turn_id === turnId
          ? { ...item, feedback: updatedFeedback }
          : item
      )));
    } catch (err) {
      const message = err.response?.data?.message || "Correction is still unavailable. You can retry later.";
      setMessages((items) => items.map((item) => (
        item.type === "feedback" && item.feedback?.turn_id === turnId
          ? { ...item, feedback: { ...item.feedback, retryError: message } }
          : item
      )));
    } finally {
      setRetryingCorrectionId(null);
    }
  };

  const endConversation = async () => {
    if (!session) return;
    cleanupVoiceAndTimers();
    setState("submitting");
    try {
      const res = await client.post("/speaking/end", { session_id: session.session_id });
      const completedSummary = res.data?.summary || res.data;
      setSummary(completedSummary);
      setFlowError("");
      setMicError("");
      setAnswerTimerNotice("");
      setSession((current) => current ? { ...current, status: "completed" } : current);
      setState("completed");
    } catch (err) {
      setFlowError(err.response?.data?.message || "Could not end the session. Please try again.");
      setState("waiting_for_user");
    }
  };

  const leaveToSpeakingHome = () => {
    isLeavingRef.current = true;
    keepListeningRef.current = false;
    cleanupVoiceAndTimers();
    submissionLockRef.current = false;
    submittingRef.current = false;
    submissionRetryPendingRef.current = false;
    setIsSubmitting(false);
    sessionRef.current = null;
    turnNumberRef.current = 1;
    setSession(null);
    setMessages([]);
    setCurrentQuestion("");
    setTurnNumber(1);
    setTranscript("");
    setCurrentFeedback(null);
    setSummary(null);
    setMicError("");
    setFlowError("");
    setAnswerTimerNotice("");
    setState("setup");
    if (mode === "topic") {
      generateTopics(true);
    }
    window.setTimeout(() => {
      isLeavingRef.current = false;
    }, 0);
  };

  const handleBackToSpeakingHome = () => {
    if (!session || state === "completed" || session.status === "completed") {
      leaveToSpeakingHome();
      return;
    }
    setShowLeaveDialog(true);
  };

  const resetToSetup = () => {
    setFlowError("");
    isLeavingRef.current = false;
    cleanupVoiceAndTimers();
    submissionLockRef.current = false;
    submittingRef.current = false;
    setIsSubmitting(false);
    sessionRef.current = null;
    turnNumberRef.current = 1;
    setSession(null);
    setMessages([]);
    setCurrentQuestion("");
    setTurnNumber(1);
    setTranscript("");
    setCurrentFeedback(null);
    setSummary(null);
    setMicError("");
    setAnswerTimerNotice("");
    const limitSeconds = getAnswerLimitSeconds(difficultyRef.current);
    answerSecondsLeftRef.current = limitSeconds;
    answerLimitSecondsRef.current = limitSeconds;
    setAnswerSecondsLeft(limitSeconds);
    setAnswerLimitSeconds(limitSeconds);
    setState("setup");
    if (mode === "topic") {
      generateTopics(true);
    }
  };

  const continueToDailyConversation = () => {
    setFlowError("");
    cleanupVoiceAndTimers();
    submissionLockRef.current = false;
    submittingRef.current = false;
    setIsSubmitting(false);
    sessionRef.current = null;
    turnNumberRef.current = 1;
    setSession(null);
    setMessages([]);
    setCurrentQuestion("");
    setTurnNumber(1);
    setTranscript("");
    setCurrentFeedback(null);
    setSummary(null);
    setMicError("");
    setAnswerTimerNotice("");
    const limitSeconds = getAnswerLimitSeconds(difficultyRef.current);
    answerSecondsLeftRef.current = limitSeconds;
    answerLimitSecondsRef.current = limitSeconds;
    setAnswerSecondsLeft(limitSeconds);
    setAnswerLimitSeconds(limitSeconds);
    setTopicOptions([]);
    setSelectedTopicId("");
    setTopicError("");
    setSetupError("");
    setSetupNotice("Topic-wise conversation completed. Continue with a Daily Speaking Challenge next.");
    setMode("daily");
    setState("setup");
  };

  const startDisabled =
    state === "starting" ||
    (mode === "topic" && (!selectedTopic || Object.keys(customTopicErrors).length > 0));

  const startDailyChallengeFromReminder = () => {
    setDailyChallengeReminderDismissed(true);
    setMode("daily");
    startSession("daily");
  };

  if (!session || state === "setup" || state === "starting") {
    return (
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <h1 className="text-4xl font-extrabold tracking-tight text-slate-900">Speaking Practice</h1>
        <p className="mt-2 text-base leading-7 text-slate-500">
          Practice a guided AI voice conversation with automatic listening, transcript confirmation, and teacher feedback.
        </p>

        {!dailyChallengeReminderDismissed && (
          <DailyChallengeReminder
            status={dailyChallengeStatus}
            moduleLabel="Speaking"
            onDismiss={() => setDailyChallengeReminderDismissed(true)}
            onStart={startDailyChallengeFromReminder}
            loading={state === "starting"}
          />
        )}

        <div className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-soft sm:p-6 lg:p-7">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p className="text-sm font-bold text-slate-700">Difficulty level</p>
            <DifficultySelector value={difficulty} onChange={handleDifficultyChange} />
          </div>

          <div className="mt-6">
            <ModeTabs
              value={mode}
              onChange={(value) => {
                setSetupNotice("");
                setMode(value);
              }}
            />
          </div>

          {mode === "daily" ? (
            <DailyConversationStart vocabulary={dailyVocabulary} loading={state === "starting"} onStart={startSession} />
          ) : (
            <>
              <TopicOptionGrid
                topics={allTopicOptions}
                selectedTopicId={selectedTopicId}
                loading={topicLoading}
                error={topicError}
                onSelect={setSelectedTopicId}
                onRetry={() => generateTopics(true)}
                difficulty={difficulty}
                customTopic={customTopic}
                showCustomTopicForm={showCustomTopicForm}
                customTopicForm={customTopicForm}
                customTopicErrors={customTopicErrors}
                onOpenCustomTopic={openCustomTopicForm}
                onCloseCustomTopic={closeCustomTopicForm}
                onCustomTopicFormChange={(field, value) => {
                  setCustomTopicForm((current) => ({ ...current, [field]: value }));
                  setCustomTopicErrors((current) => {
                    const next = { ...current };
                    delete next[field];
                    return next;
                  });
                }}
                onSaveCustomTopic={saveCustomTopic}
                onEditCustomTopic={openCustomTopicForm}
                onRemoveCustomTopic={removeCustomTopic}
              />
            </>
          )}

          {setupError && <p className="mt-4 text-sm font-medium text-red-500">{setupError}</p>}
          {setupNotice && (
            <p className="mt-4 flex items-center gap-2 rounded-xl border border-brand-100 bg-brand-50 p-3 text-sm font-semibold text-brand-700">
              <RefreshCw className="h-4 w-4 animate-spin" />
              {setupNotice}
            </p>
          )}

          {mode === "topic" && (
            <button
              onClick={startSession}
              disabled={startDisabled}
              className="mt-6 w-full rounded-xl bg-gradient-to-r from-brand-500 to-violet-500 py-3.5 text-sm font-extrabold text-white shadow-lg shadow-brand-500/20 transition hover:from-brand-600 hover:to-violet-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {state === "starting" ? "Starting..." : "Start Conversation"}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (state === "completed" && summary) {
    if (session.mode !== "topic") {
      return (
        <div className="mx-auto max-w-5xl space-y-4 px-4 pb-20 sm:px-6 lg:px-0">
          <ModuleBackButton label="Back to Speaking" onBack={handleBackToSpeakingHome} />
          <DailySessionSummary summary={summary} onStartAnother={resetToSetup} />
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-5xl space-y-4 px-4 pb-20 sm:px-6 lg:px-0">
        <ModuleBackButton label="Back to Speaking" onBack={handleBackToSpeakingHome} />
        <SessionResultDashboard
          session={session}
          summary={summary}
          type="speaking"
          onStartAnother={session.mode === "topic" ? continueToDailyConversation : resetToSetup}
          startAnotherLabel={session.mode === "topic" ? "Continue to Daily Speaking Challenge" : "Start Another Session"}
        />
      </div>
    );
  }

  /* Derive a human-readable avatar status from the current session state */
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      {/* ── Top bar ── */}
      <div className="mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col px-4 pb-28 pt-3 sm:px-6 sm:pt-4">
        <div className="mb-3">
          <ModuleBackButton label="Back to Speaking" onBack={handleBackToSpeakingHome} disabled={state === "submitting"} />
        </div>

      {flowError && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
            <p>{flowError}</p>
            {state === "completed" && (
              <button
                type="button"
                onClick={resetToSetup}
                className="mt-3 rounded-lg bg-brand-600 px-3 py-2 text-xs font-bold text-white transition hover:bg-brand-700"
              >
                Start a new conversation
              </button>
            )}
        </div>
      )}

              <SpeakingHero
          session={session}
          turnNumber={turnNumber}
          state={state}
          aiSpeaking={aiSpeaking}
          answerSecondsLeft={answerSecondsLeft}
              />

              {session.mode !== "topic" && (
                <>
                  <DailyProgress answered={session.answered_turns || 0} total={20} vocabularyUsed={dailyVocabularyUsed} />
                  <DailyMilestone answered={session.answered_turns || 0} />
                </>
              )}

        <div className="min-h-0 flex-1 overflow-y-auto rounded-3xl border border-slate-200 bg-white/90 px-3 py-4 shadow-sm sm:px-4 md:px-6 md:py-5">
          <div className="space-y-4">
            {messages.map((message, index) => (
              <ChatTutorMessage
                key={`${message.type}-${message.turnNumber}-${index}`}
                message={message}
                daily={session.mode !== "topic"}
                onRetryCorrection={retryCorrection}
                retryingCorrectionId={retryingCorrectionId}
              />
            ))}

            {state === "listening" && (
              <LiveListeningBubble
                transcript={transcript}
                micError={micError}
                answerTimerNotice={answerTimerNotice}
                answerSecondsLeft={answerSecondsLeft}
                answerLimitSeconds={answerLimitSeconds}
                noSpeechFallbackSeconds={NO_SPEECH_FALLBACK_SECONDS}
                onEnd={endConversation}
              />
            )}

            {state === "transcript_ready" && (
              <ChatTranscriptReview
                transcript={transcript}
                micError={micError}
                flowError={flowError}
                answerTimerNotice={answerTimerNotice}
                isSubmitting={isSubmitting}
                sessionEnded={state === "completed"}
                sessionId={session?.session_id}
                onTranscriptChange={setTranscript}
                onSubmit={submitTranscript}
                onRetry={retryRecording}
                onCancel={cancelTranscript}
                onEnd={endConversation}
              />
            )}

            {(state === "ai_speaking" || state === "submitting" || state === "showing_feedback" || state === "ai_feedback_speaking") && (
              <ChatStatusBubble state={state} aiSpeaking={aiSpeaking} />
            )}

            <div ref={chatEndRef} />
          </div>
        </div>

        <ChatTutorBottomBar
          state={state}
          voiceEnabled={voiceEnabled}
          transcript={transcript}
          onToggleVoice={() => setVoiceEnabled((value) => !value)}
          onResumeVoice={() => askQuestion(currentQuestion)}
        />
        <LeaveSessionDialog
          open={showLeaveDialog}
          onStay={() => {
            setShowLeaveDialog(false);
            if (routeLeaveResolverRef.current) {
              routeLeaveResolverRef.current(false);
              routeLeaveResolverRef.current = null;
            }
          }}
          onLeave={() => {
            setShowLeaveDialog(false);
            leaveToSpeakingHome();
            if (routeLeaveResolverRef.current) {
              routeLeaveResolverRef.current(true);
              routeLeaveResolverRef.current = null;
            }
          }}
        />
      </div>
    </div>
  );

  function clearAnswerTimer() {
    if (answerTimerRef.current) {
      window.clearInterval(answerTimerRef.current);
      answerTimerRef.current = null;
    }
  }

  function clearNoSpeechFallbackTimer() {
    if (noSpeechFallbackTimerRef.current) {
      window.clearTimeout(noSpeechFallbackTimerRef.current);
      noSpeechFallbackTimerRef.current = null;
    }
  }

  function clearNoTranscriptFallbackTimer() {
    if (noTranscriptFallbackTimerRef.current) {
      window.clearTimeout(noTranscriptFallbackTimerRef.current);
      noTranscriptFallbackTimerRef.current = null;
    }
  }

  function scheduleNoSpeechFallback(listeningCycle) {
    clearNoSpeechFallbackTimer();
    noSpeechFallbackTimerRef.current = window.setTimeout(() => {
      const answer = (finalTranscriptRef.current || transcriptSnapshotRef.current).trim();
      if (
        stateRef.current !== "listening" ||
        listeningCycleRef.current !== listeningCycle ||
        submittingRef.current ||
        !answer
      ) {
        return;
      }
      finishAnswerNow({ answerOverride: answer, listeningCycle });
    }, NO_SPEECH_FALLBACK_SECONDS * 1000);
  }

  function getRecordingMimeType() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/wav",
    ];
    return candidates.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || "";
  }

  async function startAnswerRecording(listeningCycle) {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      recordSpeechDiagnostic("recorder_unavailable");
      return;
    }
    if (answerRecorderRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (listeningCycleRef.current !== listeningCycle || stateRef.current !== "listening") {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      const mimeType = getRecordingMimeType();
      answerAudioMimeTypeRef.current = mimeType || "audio/webm";
      answerAudioChunksRef.current = [];
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      answerRecorderRef.current = recorder;
      answerRecorderStreamRef.current = stream;
      recorder.ondataavailable = (event) => {
        if (event.data?.size) {
          answerAudioChunksRef.current.push(event.data);
        }
      };
      recorder.onerror = (event) => {
        recordSpeechDiagnostic("recorder_error", { error: event.error?.message || event.error?.name });
      };
      recorder.onstart = () => recordSpeechDiagnostic("recorder_start", { mimeType: answerAudioMimeTypeRef.current });
      recorder.onstop = () => recordSpeechDiagnostic("recorder_stop", { chunks: answerAudioChunksRef.current.length });
      recorder.start(1000);
    } catch (err) {
      recordSpeechDiagnostic("recorder_failed", { message: err?.message, name: err?.name });
    }
  }

  function stopAnswerRecording({ keepBlob = false } = {}) {
    return new Promise((resolve) => {
      const recorder = answerRecorderRef.current;
      const stream = answerRecorderStreamRef.current;
      const chunksAtStop = answerAudioChunksRef.current;
      const mimeType = answerAudioMimeTypeRef.current || "audio/webm";

      const cleanup = () => {
        stream?.getTracks?.().forEach((track) => track.stop());
        answerRecorderRef.current = null;
        answerRecorderStreamRef.current = null;
        if (!keepBlob) {
          answerAudioChunksRef.current = [];
        }
      };

      if (!recorder) {
        cleanup();
        resolve(null);
        return;
      }

      recorder.onstop = () => {
        recordSpeechDiagnostic("recorder_stop", { chunks: chunksAtStop.length });
        const blob = keepBlob && chunksAtStop.length
          ? new Blob(chunksAtStop, { type: mimeType })
          : null;
        cleanup();
        resolve(blob);
      };

      try {
        if (recorder.state !== "inactive") {
          recorder.stop();
        } else {
          recorder.onstop();
        }
      } catch {
        cleanup();
        resolve(null);
      }
    });
  }

  async function transcribeRecordedAnswer(listeningCycle) {
    const audioBlob = await stopAnswerRecording({ keepBlob: true });
    if (
      listeningCycleRef.current !== listeningCycle ||
      submittingRef.current ||
      !audioBlob ||
      audioBlob.size < 1024
    ) {
      return "";
    }

    recordSpeechDiagnostic("backup_transcription_start", { bytes: audioBlob.size, type: audioBlob.type });
    const formData = new FormData();
    const extension = audioBlob.type.includes("mp4") ? "mp4" : audioBlob.type.includes("wav") ? "wav" : "webm";
    formData.append("audio", audioBlob, `speaking-answer.${extension}`);
    const response = await client.post("/speaking/transcribe", formData, {
      timeout: 60000,
    });
    const text = String(response.data?.transcript || "").trim();
    recordSpeechDiagnostic("backup_transcription_done", { hasText: Boolean(text), text });
    return text;
  }

  async function recoverWithBackupTranscription(listeningCycle, reason = "no_transcript") {
    if (
      stateRef.current !== "listening" ||
      listeningCycleRef.current !== listeningCycle ||
      submittingRef.current
    ) {
      return false;
    }

    keepListeningRef.current = false;
    stopReasonRef.current = reason;
    clearAnswerTimer();
    clearNoSpeechFallbackTimer();
    clearNoTranscriptFallbackTimer();
    stopAudioMonitoring();
    try {
      recognitionRef.current?.stop();
    } catch {
      recognitionRef.current = null;
    }

    try {
      setMicError("Chrome/Edge did not return words. Trying Whisper backup transcription...");
      const backupTranscript = await transcribeRecordedAnswer(listeningCycle);
      if (!backupTranscript) return false;

      const triggerResult = getDoneTriggerResult(backupTranscript);
      const visibleTranscript = triggerResult.matched ? triggerResult.cleanedAnswer : backupTranscript;
      finalTranscriptRef.current = visibleTranscript;
      transcriptSnapshotRef.current = visibleTranscript;
      setTranscript(visibleTranscript);
      if (triggerResult.matched && triggerResult.cleanedAnswer) {
        finishAnswerNow({ answerOverride: triggerResult.cleanedAnswer, listeningCycle });
        return true;
      }
      setMicError("Whisper backup transcription captured your answer. Review it, then submit.");
      stateRef.current = "transcript_ready";
      setState("transcript_ready");
      return true;
    } catch (err) {
      recordSpeechDiagnostic("backup_transcription_failed", {
        status: err?.response?.status,
        message: err?.response?.data?.message || err?.message,
      });
      return false;
    }
  }

  function scheduleNoTranscriptFallback(listeningCycle) {
    clearNoTranscriptFallbackTimer();
    noTranscriptFallbackTimerRef.current = window.setTimeout(async () => {
      const answer = (finalTranscriptRef.current || transcriptSnapshotRef.current).trim();
      if (
        stateRef.current !== "listening" ||
        listeningCycleRef.current !== listeningCycle ||
        submittingRef.current ||
        answer
      ) {
        return;
      }

      if (await recoverWithBackupTranscription(listeningCycle, "no_transcript_timeout")) return;
      const diagnostics = recognitionDiagnosticsRef.current || {};
      const events = diagnostics.events || {};
      const heardAudio = Boolean(events.audio_start || events.sound_start || events.audio_monitor_sound);
      const heardSpeech = Boolean(events.speech_start);
      const resultCount = diagnostics.resultCount || 0;
      console.warn("[speaking.recognition] no transcript fallback", {
        cycle: diagnostics.cycle,
        permission: diagnostics.permissionState || "unknown",
        heardAudio,
        heardSpeech,
        resultCount,
        audioMonitorPeak: Number((audioMonitorPeakRef.current || 0).toFixed(4)),
        events,
        lastDetails: diagnostics.lastDetails,
      });
      const message = !heardAudio
        ? "Speech recognition did not receive microphone audio. Check the browser microphone input, then retry recording."
        : !heardSpeech
          ? "The microphone is active, but speech was not detected clearly. Move closer, choose the correct input device, or retry recording."
          : resultCount === 0
            ? "Speech was detected, but no transcript was returned by the browser speech service. Retry recording or type your answer here."
            : "Speech recognition returned results, but no usable words were captured. Type your answer here, or retry recording.";
      setMicError(message);
      stateRef.current = "transcript_ready";
      setState("transcript_ready");
    }, NO_TRANSCRIPT_FALLBACK_SECONDS * 1000);
  }

  function startAnswerTimer() {
    clearAnswerTimer();
    answerTimerRef.current = window.setInterval(() => {
      const nextSeconds = Math.max(0, answerSecondsLeftRef.current - 1);
      answerSecondsLeftRef.current = nextSeconds;
      setAnswerSecondsLeft(nextSeconds);
      if (nextSeconds !== 0) return;

      clearAnswerTimer();
      if ((transcriptSnapshotRef.current || finalTranscriptRef.current).trim()) {
        stopListening({ timeUp: true });
      } else {
        setAnswerTimerNotice("Time is up, but no answer was captured. You can type your answer below.");
        stopListening({ reason: "review" });
      }
    }, 1000);
  }

  async function startAudioMonitoring() {
    if (mediaStreamRef.current || !navigator.mediaDevices?.getUserMedia) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
      mediaStreamRef.current = stream;
      recordSpeechDiagnostic("audio_monitor_start");

      const AudioContextAPI = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextAPI) {
        recordSpeechDiagnostic("audio_monitor_unavailable", { reason: "AudioContext unsupported" });
        return;
      }

      const audioContext = new AudioContextAPI();
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      audioContext.createMediaStreamSource(stream).connect(analyser);

      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      const samples = new Uint8Array(analyser.fftSize);

      const monitor = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteTimeDomainData(samples);
        let sum = 0;
        for (let i = 0; i < samples.length; i += 1) {
          const centered = (samples[i] - 128) / 128;
          sum += centered * centered;
        }

        const rms = Math.sqrt(sum / samples.length);
        audioMonitorPeakRef.current = Math.max(audioMonitorPeakRef.current || 0, rms);
        recognitionDiagnosticsRef.current = {
          ...(recognitionDiagnosticsRef.current || {}),
          audioMonitorPeak: audioMonitorPeakRef.current,
        };
        const hasTranscript = Boolean((transcriptSnapshotRef.current || finalTranscriptRef.current).trim());
        if (rms > NOISE_WARNING_LEVEL && !hasTranscript) {
          const currentEvents = recognitionDiagnosticsRef.current?.events || {};
          if (!currentEvents.audio_monitor_sound) {
            recordSpeechDiagnostic("audio_monitor_sound", { rms: Number(rms.toFixed(4)) });
          }
          noisyInputSinceRef.current = noisyInputSinceRef.current || Date.now();
          if (Date.now() - noisyInputSinceRef.current > 1500) {
            setMicError("The microphone is hearing sound, but no clear speech yet. Reduce background noise or move closer.");
          }
        } else {
          noisyInputSinceRef.current = null;
        }

        audioMonitorFrameRef.current = window.requestAnimationFrame(monitor);
      };

      monitor();
    } catch (err) {
      recordSpeechDiagnostic("audio_monitor_failed", { message: err?.message, name: err?.name });
      // SpeechRecognition will surface permission/device errors; monitoring is best-effort.
      stopAudioMonitoring();
    }
  }

  function stopAudioMonitoring() {
    try {
      if (audioMonitorFrameRef.current) {
        window.cancelAnimationFrame(audioMonitorFrameRef.current);
        audioMonitorFrameRef.current = null;
      }
      analyserRef.current = null;
      noisyInputSinceRef.current = null;

      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;

      const audioContext = audioContextRef.current;
      audioContextRef.current = null;
      if (audioContext && audioContext.state !== "closed") {
        audioContext.close().catch(() => {});
      }
    } catch {
      audioMonitorFrameRef.current = null;
      analyserRef.current = null;
      noisyInputSinceRef.current = null;
      mediaStreamRef.current = null;
      audioContextRef.current = null;
    }
  }

  function cleanupVoiceAndTimers() {
    keepListeningRef.current = false;
    clearAnswerTimer();
    clearNoSpeechFallbackTimer();
    clearNoTranscriptFallbackTimer();
    stopAnswerRecording({ keepBlob: false });
    stopAudioMonitoring();
    if (transitionTimerRef.current) {
      window.clearTimeout(transitionTimerRef.current);
      transitionTimerRef.current = null;
    }
    if (submitRetryTimerRef.current) {
      window.clearTimeout(submitRetryTimerRef.current);
      submitRetryTimerRef.current = null;
    }
    submissionRetryPendingRef.current = false;
    window.speechSynthesis?.cancel();
    setAiSpeaking(false);
    try {
      recognitionRef.current?.stop();
    } catch {
      recognitionRef.current = null;
    }
  }

}

function TopicOptionGrid({
  topics,
  selectedTopicId,
  loading,
  error,
  onSelect,
  onRetry,
  difficulty,
  customTopic,
  showCustomTopicForm,
  customTopicForm,
  customTopicErrors,
  onOpenCustomTopic,
  onCloseCustomTopic,
  onCustomTopicFormChange,
  onSaveCustomTopic,
  onEditCustomTopic,
  onRemoveCustomTopic,
}) {
  return (
    <section className="mt-5">
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-bold text-slate-900">Choose a conversation topic</p>
          <p className="mt-1 text-xs text-slate-500">Pick one AI-generated card, then start your guided conversation.</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            onClick={onOpenCustomTopic}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-2xl border border-brand-100 bg-brand-50 px-4 py-2 text-sm font-bold text-brand-700 transition hover:bg-brand-100 focus:outline-none focus:ring-2 focus:ring-brand-200"
          >
            <Sparkles className="h-4 w-4" />
            Customize Topic
          </button>
          <GenerateTopicsButton loading={loading} onClick={onRetry} />
        </div>
      </div>

      {showCustomTopicForm && (
        <section className="mb-4 rounded-3xl border border-brand-100 bg-brand-50/70 p-4 shadow-soft sm:p-5" aria-labelledby="custom-topic-heading">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 id="custom-topic-heading" className="text-base font-extrabold text-slate-900">Create Your Own Topic</h2>
              <p className="mt-1 text-sm text-slate-500">Add a title and description. Your text is used only as plain topic content.</p>
            </div>
            <button
              type="button"
              onClick={onCloseCustomTopic}
              className="self-start rounded-xl px-3 py-2 text-sm font-bold text-slate-500 transition hover:bg-white hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              Cancel
            </button>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4">
            <div>
              <label htmlFor="custom-topic-title" className="text-sm font-bold text-slate-700">Topic title *</label>
              <input
                id="custom-topic-title"
                value={customTopicForm.title}
                onChange={(event) => onCustomTopicFormChange("title", event.target.value)}
                maxLength={80}
                aria-invalid={Boolean(customTopicErrors.title)}
                aria-describedby="custom-topic-title-count custom-topic-title-error"
                className="mt-2 min-h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-900 outline-none transition focus:border-brand-400 focus:ring-4 focus:ring-brand-100"
                placeholder="Group Discussion in College"
              />
              <div className="mt-1 flex items-center justify-between gap-3 text-xs">
                <span id="custom-topic-title-error" className="font-semibold text-red-500">{customTopicErrors.title || ""}</span>
                <span id="custom-topic-title-count" className="font-semibold text-slate-400">Title: {customTopicForm.title.length}/80</span>
              </div>
            </div>

            <div>
              <label htmlFor="custom-topic-description" className="text-sm font-bold text-slate-700">Topic description *</label>
              <textarea
                id="custom-topic-description"
                value={customTopicForm.description}
                onChange={(event) => onCustomTopicFormChange("description", event.target.value)}
                maxLength={500}
                rows={4}
                aria-invalid={Boolean(customTopicErrors.description)}
                aria-describedby="custom-topic-description-count custom-topic-description-error"
                className="mt-2 w-full resize-y rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold leading-6 text-slate-900 outline-none transition focus:border-brand-400 focus:ring-4 focus:ring-brand-100"
                placeholder="Ask me about introducing myself, sharing opinions, listening to others and discussing important college topics."
              />
              <div className="mt-1 flex items-center justify-between gap-3 text-xs">
                <span id="custom-topic-description-error" className="font-semibold text-red-500">{customTopicErrors.description || ""}</span>
                <span id="custom-topic-description-count" className="font-semibold text-slate-400">Description: {customTopicForm.description.length}/500</span>
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={onCloseCustomTopic}
              className="min-h-11 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onSaveCustomTopic}
              className="min-h-11 rounded-2xl bg-brand-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              Use This Topic
            </button>
          </div>
        </section>
      )}

      {error && topics.length === 0 && !loading && (
        <div className="mb-4 rounded-3xl border border-amber-200 bg-amber-50 p-5">
          <p className="text-sm font-bold text-amber-800">Could not load speaking topics.</p>
          <p className="mt-1 text-sm text-amber-700">{error}</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-2xl border border-amber-200 bg-white px-4 py-2 text-sm font-bold text-amber-700 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-200"
          >
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {topics.filter((topic) => !loading || topic.isCustom).map((topic) => {
          const id = topic.topic_id || topic.id;
          const Icon = getTopicIcon(topic);
          const selected = id === selectedTopicId;
          if (topic.isCustom) {
            return (
              <article
                key={id}
                className={`learning-card text-left ${selected ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100" : ""}`}
              >
                <button type="button" onClick={() => onSelect(id)} className="block w-full text-left focus:outline-none">
                  <div className="flex items-start justify-between gap-3">
                    <span className="learning-card-icon"><Icon className="h-5 w-5" /></span>
                    <span className={selected ? "learning-badge bg-brand-600 text-white" : "learning-badge"}>
                      {selected ? "Selected" : "Custom Topic"}
                    </span>
                  </div>
                  <p className="mt-4 text-xs font-extrabold uppercase tracking-[0.16em] text-brand-600">Custom Topic</p>
                  <h2 className="mt-2 line-clamp-2 text-base font-bold text-slate-900">{topic.title}</h2>
                  <p className="mt-2 line-clamp-4 text-sm leading-6 text-slate-500">{topic.description}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="learning-badge capitalize">{difficulty || topic.difficulty}</span>
                    <span className="learning-badge">{formatTopicDuration(getAnswerLimitSeconds(difficulty || topic.difficulty))}</span>
                  </div>
                </button>
                <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                  <button
                    type="button"
                    onClick={onEditCustomTopic}
                    className="rounded-xl border border-brand-100 bg-white px-3 py-2 text-xs font-bold text-brand-700 transition hover:bg-brand-50 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={onRemoveCustomTopic}
                    className="rounded-xl border border-red-100 bg-white px-3 py-2 text-xs font-bold text-red-600 transition hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-100"
                  >
                    Remove
                  </button>
                </div>
              </article>
            );
          }
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              className={`learning-card text-left ${selected ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100" : ""}`}
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <span className="learning-card-icon"><Icon className="h-5 w-5" /></span>
                  <span className={selected ? "learning-badge bg-brand-600 text-white" : "learning-badge capitalize"}>
                    {selected ? "Selected" : topic.difficulty}
                  </span>
                </div>
                <h2 className="mt-4 line-clamp-2 text-base font-bold text-slate-900">{topic.title}</h2>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">{topic.description}</p>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="learning-badge capitalize">{topic.difficulty}</span>
                {topic.expected_duration_seconds && (
                  <span className="learning-badge">{formatTopicDuration(topic.expected_duration_seconds)}</span>
                )}
              </div>
            </button>
          );
        })}
        {loading && [1, 2, 3].map((item) => (
          <div key={`loading-${item}`} className="h-44 animate-pulse rounded-3xl border border-slate-100 bg-slate-50" />
        ))}
      </div>

      {error && topics.length > 0 && <p className="mt-3 rounded-2xl border border-amber-100 bg-amber-50 p-3 text-sm font-medium text-amber-700">{error}</p>}
    </section>
  );
}

function dedupeTopicOptions(topics) {
  const seen = new Set();
  return topics.filter((topic) => {
    const key = String(topic?.title || topic?.topic_id || topic?.id || "").trim().toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function getTopicIcon(topic) {
  const text = `${topic?.title || ""} ${topic?.description || ""}`.toLowerCase();
  if (/\b(pet|dog|cat|animal)\b/.test(text)) return PawPrint;
  if (/\b(travel|trip|flight|airport|journey|vacation)\b/.test(text)) return Plane;
  if (/\b(work|company|job|office|career|meeting|project)\b/.test(text)) return Briefcase;
  if (/\b(school|college|class|study|exam|teacher|student)\b/.test(text)) return GraduationCap;
  if (/\b(food|restaurant|cook|meal|breakfast|lunch|dinner)\b/.test(text)) return Utensils;
  if (/\b(shop|buy|store|market|purchase)\b/.test(text)) return ShoppingBag;
  if (/\b(friend|family|help|support|feedback|conflict)\b/.test(text)) return HeartHandshake;
  return MessageCircle;
}

function formatTopicDuration(seconds) {
  if (!seconds) return "Expected time";
  if (seconds <= 60) return "30-60 sec";
  if (seconds <= 120) return "1-2 min";
  return "2-3 min";
}

function getApiMessage(err, fallback) {
  if (!err.response) return "Backend unavailable. Check that Flask is running on http://localhost:5001.";
  if (err.response.status === 401) return "Please log in to start speaking practice.";
  if (err.response.status === 422) return "Your session expired. Refresh the page and try again.";
  return err.response?.data?.message || fallback;
}

function getSubmitErrorMessage(err) {
  if (err.response?.status === 401) return "Your login session expired. Please log in again before submitting.";
  if (err.code === "ECONNABORTED") return "The answer evaluation took too long. Please retry submitting your answer.";
  return err.response?.data?.message || "Could not submit your answer. Please retry.";
}

function isGroqUnavailableSubmitError(err) {
  return err.response?.status === 502 && err.response?.data?.error_code === "GROQ_UNAVAILABLE";
}

function messagesFromTurns(turns, daily = false, greetingText = "") {
  const restored = greetingText
    ? [{ type: "greeting", turnNumber: "intro", text: greetingText }]
    : [];
  const visibleTurns = daily
    ? turns.slice(0, Math.max(1, turns.findIndex((turn) => !turn.user_answer) + 1 || turns.length))
    : turns;
  visibleTurns.forEach((turn) => {
    restored.push({ type: "question", turnNumber: turn.turn_number, text: turn.ai_question });
    if (turn.user_answer) {
      restored.push({
        type: "answer",
        turnNumber: turn.turn_number,
        text: turn.user_answer,
        timeUsedSeconds: turn.answer_time_seconds,
      });
      if (turn.feedback) {
        restored.push({
          type: "feedback",
          turnNumber: turn.turn_number,
          feedback: { ...turn.feedback, turn_id: turn.turn_id, submittedAnswer: turn.user_answer },
        });
      }
    }
  });
  return restored;
}

function getTimeBasedGreeting(name) {
  const hour = new Date().getHours();
  const period =
    hour >= 5 && hour < 12
      ? "morning"
      : hour >= 12 && hour < 17
        ? "afternoon"
        : hour >= 17 && hour < 21
          ? "evening"
          : "night";
  const cleanName = String(name || "").trim();
  const isGuestName = /^guest(?:\s+student)?$/i.test(cleanName);
  if (!cleanName || isGuestName) {
    return `Good ${period}! Ready to practice?`;
  }
  return `Good ${period}, ${cleanName}!`;
}

function formatTimer(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safeSeconds / 60);
  const remaining = safeSeconds % 60;
  return `${minutes}:${String(remaining).padStart(2, "0")}`;
}

function formatDurationLabel(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(safeSeconds / 60);
  const remaining = safeSeconds % 60;
  if (!minutes) return `${remaining}s`;
  if (!remaining) return `${minutes}m`;
  return `${minutes}m ${remaining}s`;
}

function getAnswerLimitSeconds(difficulty) {
  return ANSWER_SECONDS_BY_DIFFICULTY[difficulty] || ANSWER_SECONDS_BY_DIFFICULTY.medium;
}

function getFeedbackSpeechParts(feedback, submittedAnswer) {
  const correctionUnavailable = feedback?.correction_available === false;
  const alreadyCorrect = feedback?.correction_available === true && feedback?.has_errors === false;
  const reaction = String(feedback?.reaction || "").trim();
  const explanation =
    correctionUnavailable
      ? "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved."
      : alreadyCorrect
        ? "No grammatical correction was needed. Your sentence is already correct."
        : (
    feedback.mistake_explanation ||
    feedback.short_explanation ||
    feedback.explanation ||
    feedback.short_feedback ||
    "Review the corrected answer."
        );

  const correctedAnswer =
      feedback?.correction_available !== false && feedback?.corrected_answer
      ? feedback.corrected_answer
      : "";

  const spokenExplanation = reaction ? `${reaction} ${explanation}` : explanation;

  return { explanation: spokenExplanation, displayExplanation: explanation, correctedAnswer };
}

function normalizeDifficulty(difficulty) {
  return ANSWER_SECONDS_BY_DIFFICULTY[difficulty] ? difficulty : "medium";
}

function getDoneTriggerResult(text) {
  const match = DONE_TRIGGER_PATTERN.exec(text);
  if (!match) return { matched: false, cleanedAnswer: text.trim() };
  return {
    matched: true,
    cleanedAnswer: text.slice(0, match.index).trim(),
  };
}

function SpeakingHero({ state, aiSpeaking, answerSecondsLeft }) {
  const heroState = getHeroAvatarState(state, aiSpeaking);
  const isUrgent = answerSecondsLeft <= 30;

  return (
    <section className="sticky top-0 z-30 mb-3 overflow-hidden rounded-3xl border border-slate-200 bg-white/95 shadow-lg shadow-slate-200/60 backdrop-blur">
      <div className="relative flex h-32 w-full items-center justify-center overflow-hidden rounded-3xl bg-gradient-to-br from-brand-100 via-indigo-50 to-violet-100 sm:h-36">
        <div className={`speaking-hero-avatar speaking-hero-${heroState} relative h-24 w-24 shrink-0 rounded-full bg-white p-1 shadow-md ring-4 ring-brand-100 sm:h-28 sm:w-28`}>
          <img
            src={tutorAvatar}
            alt="AI tutor"
            className="h-full w-full rounded-full object-cover object-[center_28%]"
            draggable="false"
          />
        </div>

        <div className={`absolute right-3 top-3 z-10 rounded-full px-3 py-2 text-xs font-bold shadow-sm backdrop-blur md:px-4 md:text-sm ${isUrgent ? "bg-red-500/80 text-white" : "bg-white/20 text-slate-700"}`}>
          {formatTimer(answerSecondsLeft)} remaining
        </div>
      </div>
    </section>
  );
}

function getHeroAvatarState(state, aiSpeaking) {
  if (aiSpeaking || state === "ai_speaking" || state === "ai_feedback_speaking") return "speaking";
  if (state === "listening") return "listening";
  if (state === "submitting" || state === "showing_feedback") return "evaluating";
  return "idle";
}

function ChatTutorHeader({ session, turnNumber, state, answerSecondsLeft, onEnd }) {
  const label = session.mode === "topic" ? "Topic-wise Conversation" : "Daily Speaking Challenge";
  const subject = session.mode === "topic" ? session.topic_title : session.daily_category;

  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-4 py-3 shadow-sm backdrop-blur">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={onEnd}
          disabled={state === "submitting"}
          aria-label="End conversation"
          className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-bold text-red-600 transition hover:bg-red-100 disabled:opacity-50"
        >
          End Conversation
        </button>
        <div className="min-w-[12rem] flex-1 text-center sm:min-w-0">
          <h1 className="truncate text-base font-bold text-slate-900">{label}</h1>
          <p className="truncate text-xs font-medium capitalize text-slate-500">
            {subject} - {session.difficulty} - Question {turnNumber}
          </p>
        </div>
        <div className={`rounded-full px-3 py-2 text-sm font-bold shadow-sm sm:px-4 ${answerSecondsLeft <= 30 ? "bg-red-50 text-red-600" : "bg-brand-50 text-brand-700"}`}>
          {formatTimer(answerSecondsLeft)}
        </div>
      </div>
    </header>
  );
}

function ChatTutorMessage({ message, daily = false, onRetryCorrection, retryingCorrectionId }) {
  if (message.type === "question" || message.type === "greeting") {
    return (
      <div className="flex justify-start">
        <div className="relative max-w-[85%] break-words rounded-2xl rounded-tl-md border border-slate-200 bg-white px-5 py-4 text-base font-medium text-slate-800 shadow-sm sm:max-w-[82%] sm:px-6 lg:max-w-[68%] md:text-lg">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-brand-600">{daily ? "AI Partner" : "AI Coach"}</p>
          <p className="relative whitespace-pre-wrap leading-relaxed">{message.text}</p>
        </div>
      </div>
    );
  }

  if (message.type === "answer") {
    return (
      <div className="flex justify-end">
        <div className="relative max-w-[88%] break-words rounded-2xl rounded-br-md bg-brand-600 px-4 py-3 text-sm text-white shadow-sm sm:max-w-[82%] lg:max-w-[68%]">
          <span className="absolute -right-1 bottom-3 h-3 w-3 rotate-45 bg-brand-600" />
          <p className="mb-1 text-right text-xs font-bold uppercase tracking-wide text-brand-100">
            You{message.timeUsedSeconds ? ` - ${formatDurationLabel(message.timeUsedSeconds)}` : ""}
          </p>
          <p className="relative whitespace-pre-wrap leading-relaxed">{message.text}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="relative max-w-[90%] break-words rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3 shadow-sm sm:max-w-[86%] lg:max-w-[72%]">
        <span className="absolute -left-1 bottom-3 h-3 w-3 rotate-45 bg-slate-100" />
        <p className={`mb-2 text-xs font-bold uppercase tracking-wide ${daily ? "text-slate-500" : "text-emerald-600"}`}>{daily ? "AI Partner" : "AI Feedback"}</p>
        {daily ? <DailyQuickFeedback feedback={message.feedback} onRetry={onRetryCorrection} retrying={retryingCorrectionId === message.feedback?.turn_id} /> : (
          <SpeakingFeedbackCard
            feedback={message.feedback}
            onRetryCorrection={onRetryCorrection}
            retryingCorrection={retryingCorrectionId === message.feedback?.turn_id}
          />
        )}
      </div>
    </div>
  );
}

function LiveListeningBubble({ transcript, micError, answerTimerNotice, answerSecondsLeft, answerLimitSeconds, noSpeechFallbackSeconds, onEnd }) {
  const timerPercent = Math.max(0, Math.min(100, (answerSecondsLeft / Math.max(1, answerLimitSeconds)) * 100));
  const isWarning = answerSecondsLeft <= 30;

  return (
    <div className="flex justify-end">
      <div className={`relative max-w-[90%] break-words rounded-2xl rounded-br-md px-4 py-3 text-sm shadow-sm sm:max-w-[86%] lg:max-w-[72%] ${isWarning ? "bg-red-500 text-white" : "bg-brand-600 text-white"}`}>
        <span className={`absolute -right-1 bottom-3 h-3 w-3 rotate-45 ${isWarning ? "bg-red-500" : "bg-brand-600"}`} />
        <div className="relative">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs font-bold uppercase tracking-wide opacity-80">Listening</p>
            <p className="text-xs font-bold">{formatTimer(answerSecondsLeft)} remaining</p>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/25">
            <div className="h-full rounded-full bg-white transition-all duration-300" style={{ width: `${timerPercent}%` }} />
          </div>
          <p className="mt-3 whitespace-pre-wrap leading-relaxed">{transcript || "Speak your answer now. Say 'I am done' to finish."}</p>
          <p className="mt-2 text-xs opacity-80">Safety fallback after {noSpeechFallbackSeconds}s of silence.</p>
          {answerTimerNotice && <p className="mt-2 rounded-lg bg-white/15 px-3 py-2 text-xs font-bold">{answerTimerNotice}</p>}
          {micError && <p className="mt-2 rounded-lg bg-white/15 px-3 py-2 text-xs font-bold">{micError}</p>}
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={onEnd}
              className="min-h-10 rounded-xl border border-white/60 bg-white/15 px-4 py-2 text-sm font-bold text-white transition hover:bg-white/25 focus:outline-none focus:ring-2 focus:ring-white/50"
            >
              End Conversation
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatTranscriptReview({ transcript, micError, flowError, answerTimerNotice, isSubmitting, sessionEnded, sessionId, onTranscriptChange, onSubmit, onRetry, onCancel, onEnd }) {
  return (
    <div className="flex justify-end">
      <div className="relative max-w-[94%] break-words rounded-2xl rounded-br-md bg-brand-50 px-3 py-3 shadow-sm ring-1 ring-brand-100 sm:max-w-[90%] sm:px-4 lg:max-w-[76%]">
        <span className="absolute -right-1 bottom-3 h-3 w-3 rotate-45 bg-brand-50 ring-1 ring-brand-100" />
        <div className="relative">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs font-bold uppercase tracking-wide text-brand-700">Review transcript</p>
            <p className="text-xs font-semibold text-slate-400">Fallback review</p>
          </div>
            <textarea
              value={transcript}
              onChange={(event) => onTranscriptChange(event.target.value)}
              disabled={isSubmitting || sessionEnded}
            rows={4}
            placeholder="Type or edit your answer here."
            className="mt-3 w-full resize-none rounded-xl border border-brand-100 bg-white p-3 text-sm text-slate-800 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
          />
          {answerTimerNotice && <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-bold text-amber-800">{answerTimerNotice}</p>}
          {micError && <p className="mt-2 text-xs font-medium text-red-600">{micError}</p>}
          {flowError && <p className="mt-2 text-xs font-medium text-amber-700">{flowError}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onSubmit}
              disabled={isSubmitting || sessionEnded || !sessionId || !transcript.trim()}
              className="min-h-10 rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-700 disabled:opacity-50"
            >
              {isSubmitting ? "Submitting…" : "Submit Answer"}
            </button>
            <button type="button" onClick={onRetry} disabled={isSubmitting || sessionEnded} className="min-h-10 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
              Retry Recording
            </button>
            <button type="button" onClick={onCancel} disabled={isSubmitting || sessionEnded} className="min-h-10 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 disabled:opacity-50">
              Clear Transcript
            </button>
            <button
              type="button"
              onClick={onEnd}
              disabled={isSubmitting || sessionEnded}
              className="min-h-10 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-bold text-red-600 transition hover:bg-red-100 disabled:opacity-50"
            >
              End Conversation
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatStatusBubble({ state, aiSpeaking }) {
  const text = (() => {
    if (aiSpeaking || state === "ai_speaking") return "AI Coach is asking the question...";
    if (state === "submitting") return "Evaluating your answer...";
    if (state === "showing_feedback" || state === "ai_feedback_speaking") return "Preparing the next question...";
    return "Working...";
  })();

  return (
    <div className="flex justify-start">
      <div className="rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3 text-sm font-semibold text-slate-600 shadow-sm">
        {text}
      </div>
    </div>
  );
}

function ChatTutorBottomBar({ state, voiceEnabled, onToggleVoice, onResumeVoice }) {
  const label = state === "listening" ? "Listening now" : state === "ai_speaking" ? "AI speaking" : state === "submitting" ? "Evaluating" : "Voice ready";

  return (
    <div className="fixed bottom-4 left-1/2 z-30 w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 shadow-xl shadow-slate-300/30 backdrop-blur sm:px-5">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onToggleVoice}
          className={`min-h-10 rounded-full px-4 py-2 text-sm font-bold transition ${voiceEnabled ? "bg-brand-50 text-brand-700" : "bg-slate-100 text-slate-500"}`}
        >
          {voiceEnabled ? "Voice On" : "Voice Off"}
        </button>
        <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-slate-500">
          {state === "listening" && (
            <span className="flex h-5 items-end gap-0.5" aria-hidden="true">
              <span className="h-2 w-1 rounded-full bg-brand-400 animate-pulse" />
              <span className="h-4 w-1 rounded-full bg-brand-500 animate-pulse [animation-delay:120ms]" />
              <span className="h-3 w-1 rounded-full bg-brand-400 animate-pulse [animation-delay:240ms]" />
              <span className="h-5 w-1 rounded-full bg-brand-600 animate-pulse [animation-delay:360ms]" />
            </span>
          )}
          <span className="truncate">{label}</span>
        </div>
        {state === "waiting_for_user" && (
          <button type="button" onClick={onResumeVoice} className="min-h-10 rounded-full bg-brand-600 px-4 py-2 text-sm font-bold text-white">
            Resume Voice
          </button>
        )}
      </div>
    </div>
  );
}

function ConversationHeader({
  session,
  turnNumber,
  state,
  voiceEnabled,
  onToggleVoice,
  onEnd,
}) {
  const label = session.mode === "topic" ? "Topic-wise Conversation" : "Daily Speaking Challenge";
  const subject = session.mode === "topic" ? session.topic_title : session.daily_category;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">{label}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {subject} · {session.difficulty} · Question {turnNumber}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onToggleVoice}
            className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50"
          >
            Voice {voiceEnabled ? "On" : "Off"}
          </button>
          <button
            onClick={onEnd}
            disabled={state === "submitting"}
            className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-bold text-red-600 transition hover:bg-red-100 disabled:opacity-60"
          >
            End Conversation
          </button>
        </div>
      </div>
    </div>
  );
}

function ConversationMessage({ message, onRetryCorrection, retryingCorrectionId }) {
  if (message.type === "question") {
    return (
      <div className="mb-4 max-w-2xl">
        <p className="mb-1 text-xs font-bold uppercase text-brand-600">AI Coach</p>
        <div className="rounded-2xl rounded-tl-sm bg-brand-50 p-4 text-sm font-medium text-slate-800">
          {message.text}
        </div>
      </div>
    );
  }

  if (message.type === "answer") {
    return (
      <div className="mb-4 ml-auto max-w-2xl">
        <p className="mb-1 text-right text-xs font-bold uppercase text-slate-500">
          You{message.timeUsedSeconds ? ` · ${formatDurationLabel(message.timeUsedSeconds)}` : ""}
        </p>
        <div className="rounded-2xl rounded-tr-sm bg-brand-600 p-4 text-sm text-white">{message.text}</div>
      </div>
    );
  }

  return (
    <div className="mb-5 max-w-2xl">
      <p className="mb-1 text-xs font-bold uppercase text-emerald-600">AI Feedback</p>
      <SpeakingFeedbackCard
        feedback={message.feedback}
        onRetryCorrection={onRetryCorrection}
        retryingCorrection={retryingCorrectionId === message.feedback?.turn_id}
      />
    </div>
  );
}

function VoiceConversationControls({
  state,
  transcript,
  micError,
  flowError,
  answerSecondsLeft,
  answerLimitSeconds,
  answerTimerNotice,
  noSpeechFallbackSeconds,
  onResumeVoice,
  onTranscriptChange,
  onSubmit,
  onRetry,
  onCancel,
}) {
  if (state === "ai_speaking") {
    return <StatusPanel title="AI is speaking" body="Listening starts automatically after the question finishes." />;
  }

  if (state === "waiting_for_user") {
    return (
      <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-sm font-semibold text-slate-700">Ready to continue?</p>
        <button onClick={onResumeVoice} className="mt-3 rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white">
          Resume Voice
        </button>
      </div>
    );
  }

  if (state === "listening") {
    const timerPercent = Math.max(0, Math.min(100, (answerSecondsLeft / Math.max(1, answerLimitSeconds)) * 100));
    const isWarning = answerSecondsLeft <= 30;

    return (
      <div className={`mt-5 rounded-2xl border p-4 text-center ${isWarning ? "border-red-100 bg-red-50" : "border-brand-100 bg-brand-50/50"}`}>
        <p className={`text-sm font-bold ${isWarning ? "text-red-600" : "text-brand-700"}`}>Listening...</p>
        <p className={`mt-1 text-lg font-bold ${isWarning ? "text-red-600" : "text-slate-800"}`}>
          {formatTimer(answerSecondsLeft)} remaining
        </p>
        <div className="mx-auto mt-3 h-2 w-full max-w-md overflow-hidden rounded-full bg-white">
          <div
            className={`h-full rounded-full transition-all duration-300 ${isWarning ? "bg-red-500" : "bg-brand-600"}`}
            style={{ width: `${timerPercent}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-slate-500">
          You have {formatDurationLabel(answerLimitSeconds)} for this answer.
        </p>
        <p className="mt-1 text-xs font-medium text-slate-500">
          Say "I am done" to finish, or use the fallback button.
        </p>
        <p className="mt-1 text-xs font-medium text-slate-400">
          Safety fallback: submits after {noSpeechFallbackSeconds} seconds with no speech.
        </p>
        <p className="mt-2 min-h-[1.5rem] text-sm text-slate-600">{transcript || "Speak your answer now."}</p>
        {answerTimerNotice && <p className="mt-3 text-xs font-bold text-amber-700">{answerTimerNotice}</p>}
        {micError && <p className="mt-3 text-xs font-medium text-red-600">{micError}</p>}
      </div>
    );
  }

  if (state === "transcript_ready") {
    return (
      <TranscriptConfirmation
        transcript={transcript}
        micError={micError}
        flowError={flowError}
        answerTimerNotice={answerTimerNotice}
        onTranscriptChange={onTranscriptChange}
        onSubmit={onSubmit}
        onRetry={onRetry}
        onCancel={onCancel}
      />
    );
  }

  if (state === "submitting") {
    return <StatusPanel title="Evaluating your answer" body="The teacher is checking your fluency, grammar and clarity." />;
  }

  if (state === "showing_feedback" || state === "ai_feedback_speaking") {
    return <StatusPanel title="Preparing the next question" body="Feedback is shown first, then the AI will continue." />;
  }

  return null;
}

function TranscriptConfirmation({
  transcript,
  micError,
  flowError,
  answerTimerNotice,
  onTranscriptChange,
  onSubmit,
  onRetry,
  onCancel,
}) {
  return (
    <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-bold text-slate-800">Review transcript</p>
        <p className="text-xs font-semibold text-slate-400">Submit only when ready</p>
      </div>
      <textarea
        value={transcript}
        onChange={(event) => onTranscriptChange(event.target.value)}
        rows={4}
        placeholder="Type or edit your answer here."
        className="mt-3 w-full resize-none rounded-xl border border-slate-200 bg-white p-3 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
      />
      {answerTimerNotice && <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-bold text-amber-800">{answerTimerNotice}</p>}
      {micError && <p className="mt-2 text-xs font-medium text-red-600">{micError}</p>}
      {flowError && <p className="mt-2 text-xs font-medium text-amber-700">{flowError}</p>}
      <p className="mt-2 text-xs font-medium text-slate-500">
        Edit the transcript if needed. Nothing is sent until you click Submit Answer.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={onSubmit}
          disabled={!transcript.trim()}
          className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-700 disabled:opacity-50"
        >
          Submit Answer
        </button>
        <button onClick={onRetry} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600">
          Retry Recording
        </button>
        <button onClick={onCancel} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600">
          Clear Transcript
        </button>
      </div>
    </div>
  );
}

function SpeakingFeedbackCard({ feedback, onRetryCorrection, retryingCorrection = false }) {
  if (!feedback) return null;
  const scores = feedback.scores || {};
  const correctionUnavailable = feedback.correction_available === false;
  const alreadyCorrect = feedback.correction_available === true && feedback.has_errors === false;
  const reaction = String(feedback.reaction || "").trim();
  const explanation =
    correctionUnavailable
      ? "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved."
      : alreadyCorrect
        ? "No grammatical correction was needed. Your sentence is already correct."
        : (
    feedback.mistake_explanation ||
    feedback.explanation ||
    feedback.short_feedback ||
    "Review the corrected answer."
        );
  const mistakePoints = getMistakePoints(feedback, explanation);
  const correctedAnswer =
    feedback.correction_available === true && feedback.corrected_answer
      ? feedback.corrected_answer
      : "";
  const canRetryCorrection = (correctionUnavailable || feedback.source === "local_rules") && feedback.turn_id && onRetryCorrection;
  const scoresVerified = feedback.scores_verified !== false && feedback.source !== "local_rules" && !correctionUnavailable;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
      <p className={`font-semibold ${correctionUnavailable ? "text-amber-700" : "text-emerald-700"}`}>
        {correctionUnavailable ? "Correction unavailable" : feedback.appreciation || "Good attempt."}
      </p>
      {reaction && reaction !== feedback.appreciation && (
        <p className="mt-2 rounded-xl border border-brand-100 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800">
          {reaction}
        </p>
      )}
      {feedback.correctionReading && (
        <p className="mt-2 rounded-lg bg-white px-3 py-2 text-xs font-bold text-brand-700">
          AI is reading your corrected answer...
        </p>
      )}

      {feedback.submittedAnswer && (
        <FeedbackDetail label="Your original answer" text={feedback.submittedAnswer} />
      )}
      {correctionUnavailable && (
        <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm font-semibold text-amber-800">
          Detailed grammar correction is temporarily unavailable. Your original answer has been preserved.
        </p>
      )}
      {alreadyCorrect && (
        <p className="mt-3 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800">
          No grammatical correction was needed. Your sentence is already correct.
        </p>
      )}
      <FeedbackDetail label="Mistake explanation" text={explanation} listItems={mistakePoints} />
      {correctedAnswer && <FeedbackDetail label="Corrected answer" text={correctedAnswer} />}
      {feedback.correction_available === true && feedback.better_natural_answer && (
        <FeedbackDetail label="More natural answer" text={feedback.better_natural_answer} />
      )}
      {feedback.source === "local_rules" && (
        <p className="mt-3 rounded-xl border border-sky-300 bg-sky-50 p-3 text-sm font-semibold text-sky-800">
          Basic correction from local grammar rules. Retry with AI for detailed feedback.
        </p>
      )}
      {feedback.rules_applied?.length > 0 && (
        <div className="mt-3 space-y-1 rounded-xl border border-sky-200 bg-sky-50 p-3 text-xs text-sky-900">
          {feedback.rules_applied.map((rule, index) => <p key={`${rule}-${index}`}>{rule}</p>)}
        </div>
      )}
      {feedback.unclear_phrases?.length > 0 && (
        <FeedbackDetail label="Unclear transcript" text={feedback.unclear_phrases.join(", ")} />
      )}
      {feedback.retryError && (
        <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs font-semibold text-amber-800">{feedback.retryError}</p>
      )}
      {canRetryCorrection && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onRetryCorrection(feedback)}
            disabled={retryingCorrection}
            className="rounded-xl border border-brand-200 bg-white px-3 py-2 text-xs font-bold text-brand-700 transition hover:bg-brand-50 disabled:opacity-50"
          >
            {retryingCorrection ? "Retrying..." : "Retry Correction"}
          </button>
        </div>
      )}

      {feedback.mistakes?.length > 0 && (
        <div className="mt-3 space-y-2">
          {feedback.mistakes.map((mistake, index) => (
            <div key={`${mistake.incorrect}-${index}`} className="rounded-xl border border-red-400 bg-red-50 p-3">
              <p className="font-semibold text-red-700">
                {mistake.incorrect || "Issue"} {"->"} {mistake.correct || "Correction"}
              </p>
              {Array.isArray(mistake.mistake_points) && mistake.mistake_points.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-700">
                  {mistake.mistake_points.map((point, pointIndex) => (
                    <li key={`${mistake.incorrect}-${pointIndex}`}>{point}</li>
                  ))}
                </ul>
              ) : mistake.explanation ? (
                <p className="mt-1 text-xs text-slate-700">{mistake.explanation}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
        <ScorePill label="Confidence" value={scores.confidence} />
        <ScorePill label="Fluency" value={scores.fluency} />
        <ScorePill label="Grammar" value={scores.grammar} />
        {scores.knowledge != null && <ScorePill label="Knowledge" value={scores.knowledge} />}
        <ScorePill label="Overall" value={scores.overall} />
      </div>
      {!scoresVerified && (
        <p className="mt-2 text-xs font-semibold text-amber-700">Scores not evaluated.</p>
      )}
    </div>
  );
}

function getMistakePoints(feedback, fallbackText = "") {
  const fromFeedback = Array.isArray(feedback?.mistake_points)
    ? feedback.mistake_points.filter((item) => typeof item === "string" && item.trim())
    : [];
  if (fromFeedback.length) return fromFeedback;

  const collected = [];
  for (const mistake of feedback?.mistakes || []) {
    const points = Array.isArray(mistake?.mistake_points)
      ? mistake.mistake_points.filter((item) => typeof item === "string" && item.trim())
      : [];
    collected.push(...points);
  }
  if (collected.length) return collected;

  return [];
}

function FeedbackDetail({ label, text, listItems = [] }) {
  if (!text && !listItems.length) return null;
  const theme = getFeedbackDetailTheme(label);
  const classes = {
    original: {
      card: "border border-amber-400 bg-amber-50",
      label: "text-amber-700",
      body: "text-slate-800",
    },
    corrected: {
      card: "border border-emerald-500 bg-emerald-50",
      label: "text-emerald-700",
      body: "text-slate-800",
    },
    mistake: {
      card: "border border-red-500 bg-red-50",
      label: "text-red-700",
      body: "text-slate-800",
    },
    neutral: {
      card: "bg-white",
      label: "text-slate-400",
      body: "text-slate-700",
    },
  }[theme];

  return (
    <div className={`mt-3 rounded-xl p-3 ${classes.card}`}>
      <p className={`text-xs font-bold uppercase ${classes.label}`}>{label}</p>
      {listItems.length > 0 ? (
        <ul className={`mt-2 list-disc space-y-1 pl-5 ${classes.body}`}>
          {listItems.map((item, index) => (
            <li key={`${label}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className={`mt-1 whitespace-pre-wrap ${classes.body}`}>{text}</p>
      )}
    </div>
  );
}

function getFeedbackDetailTheme(label) {
  const normalized = (label || "").toLowerCase();
  if (normalized.includes("original") || normalized.includes("your answer")) return "original";
  if (normalized.includes("corrected")) return "corrected";
  if (normalized.includes("mistake")) return "mistake";
  return "neutral";
}

function SpeakingSessionSummary({ session, summary, onStartAnother }) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <h1 className="text-2xl font-bold text-slate-900">Session Complete</h1>
      <p className="mt-1 text-sm text-slate-500">
        {session.mode === "topic" ? session.topic_title : session.daily_category} · {session.difficulty} ·{" "}
        {summary.answered_turns} answered
      </p>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">
        <div className="flex justify-center">
          <ScoreRing score={summary.overall_score} label="Overall Score" size={110} />
        </div>
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <ScoreRing score={summary.confidence_score} label="Confidence" size={72} stroke={6} />
          <ScoreRing score={summary.fluency_score} label="Fluency" size={72} stroke={6} />
          <ScoreRing score={summary.grammar_score} label="Grammar" size={72} stroke={6} />
          {session.mode === "topic" && <ScoreRing score={summary.knowledge_score} label="Knowledge" size={72} stroke={6} />}
        </div>
        <p className="mt-6 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">{summary.summary_feedback}</p>
        <SummaryList title="Strengths" items={summary.strengths} />
        <SummaryList title="Areas to improve" items={summary.areas_to_improve} />
        <div className="mt-6 flex flex-wrap gap-2">
          <button onClick={onStartAnother} className="min-h-10 rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white">
            Start Another Session
          </button>
          <Link to="/history" className="min-h-10 rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600">
            Go to History
          </Link>
        </div>
      </div>
    </div>
  );
}

function SummaryList({ title, items = [] }) {
  if (!items.length) return null;
  return (
    <div className="mt-5">
      <p className="text-sm font-bold text-slate-800">{title}</p>
      <div className="mt-2 space-y-2">
        {items.map((item, index) => (
          <p key={`${title}-${index}`} className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-600">
            {item}
          </p>
        ))}
      </div>
    </div>
  );
}

function StatusPanel({ title, body }) {
  return (
    <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-center">
      <p className="text-sm font-bold text-slate-700">{title}</p>
      <p className="mt-1 text-sm text-slate-500">{body}</p>
    </div>
  );
}

function ScorePill({ label, value }) {
  return (
    <span className="rounded-full bg-white px-3 py-1 text-slate-600">
      {label}: {formatScore10(value, "Not evaluated")}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Dark-theme components — used only in the active session view
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * DarkConversationHeader — top bar for the dark call UI.
 * Shows the mode/topic label in the center, and voice-toggle + end buttons on the right.
 */
function DarkConversationHeader({ session, turnNumber, state, voiceEnabled, onToggleVoice, onEnd }) {
  const label = session.mode === "topic" ? "Topic-wise Conversation" : "Daily Speaking Challenge";
  const subject = session.mode === "topic" ? session.topic_title : session.daily_category;

  return (
    <div className="flex items-center justify-between px-5 pt-5 pb-2">
      {/* Left: mode label + progress */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-slate-900">{label}</p>
        <p className="truncate text-xs text-slate-500">
          {subject} · {session.difficulty} · Question {turnNumber}
        </p>
      </div>

      {/* Right: voice toggle + end */}
      <div className="ml-3 flex items-center gap-2">
        <button
          onClick={onToggleVoice}
          title={voiceEnabled ? "Voice On — click to mute" : "Voice Off — click to unmute"}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50"
        >
          {voiceEnabled ? (
            /* Speaker / volume icon */
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
            </svg>
          ) : (
            /* Muted speaker icon */
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <line x1="23" y1="9" x2="17" y2="15" />
              <line x1="17" y1="9" x2="23" y2="15" />
            </svg>
          )}
        </button>

        <button
          onClick={onEnd}
          disabled={state === "submitting"}
          className="rounded-full border border-red-200 bg-red-50 px-4 py-1.5 text-xs font-bold text-red-600 transition hover:bg-red-100 disabled:opacity-50"
        >
          End
        </button>
      </div>
    </div>
  );
}

/**
 * SessionStatusPill — centered pill that shows the current session state
 * in a translucent dark pill.  All text is derived from existing state vars.
 */
function SessionStatusPill({ state, aiSpeaking, answerSecondsLeft, answerLimitSeconds, transcript, micError, answerTimerNotice, noSpeechFallbackSeconds }) {
  let text = "";
  let subtext = "";
  let accent = "border-slate-200 bg-white";

  if (aiSpeaking || state === "ai_speaking") {
    text = "AI is speaking…";
    subtext = "Listening starts automatically after the question finishes.";
    accent = "border-sky-200 bg-sky-50";
  } else if (state === "listening") {
    const timerPercent = Math.max(0, Math.min(100, (answerSecondsLeft / Math.max(1, answerLimitSeconds)) * 100));
    const isWarning = answerSecondsLeft <= 30;
    text = isWarning ? `⚠ ${formatTimer(answerSecondsLeft)} remaining` : `Listening · ${formatTimer(answerSecondsLeft)}`;
    subtext = transcript ? transcript : "Speak your answer now. Say 'I am done' to finish.";

    accent = isWarning ? "border-red-200 bg-red-50" : "border-brand-200 bg-brand-50";
    return (
      <div className={`mx-auto w-full max-w-sm rounded-2xl border px-5 py-3 text-center ${accent}`}>
        <p className={`text-sm font-bold ${isWarning ? "text-red-600" : "text-brand-700"}`}>{text}</p>
        {/* Progress bar */}
        <div className="mx-auto mt-2 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-white">
          <div
            className={`h-full rounded-full transition-all duration-300 ${isWarning ? "bg-red-500" : "bg-brand-500"}`}
            style={{ width: `${timerPercent}%` }}
          />
        </div>
        {subtext && <p className="mt-2 text-xs text-slate-600 line-clamp-2">{subtext}</p>}
        {answerTimerNotice && <p className="mt-1 text-xs font-bold text-amber-700">{answerTimerNotice}</p>}
        {micError && <p className="mt-1 text-xs text-red-600">{micError}</p>}
      </div>
    );
  } else if (state === "waiting_for_user") {
    text = "Press to continue";
    subtext = "Resume when you are ready.";
    accent = "border-slate-200 bg-white";
  } else if (state === "submitting") {
    text = "Evaluating your answer…";
    subtext = "The teacher is checking your fluency, grammar and clarity.";
    accent = "border-sky-200 bg-sky-50";
  } else if (state === "showing_feedback" || state === "ai_feedback_speaking") {
    text = "Preparing next question";
    subtext = "Feedback is shown first, then the AI will continue.";
    accent = "border-emerald-200 bg-emerald-50";
  } else if (state === "transcript_ready") {
    text = "Review your transcript";
    subtext = "Edit if needed, then submit when ready.";
    accent = "border-slate-200 bg-white";
  }

  if (!text) return null;

  return (
    <div className={`mx-auto w-fit rounded-full border px-6 py-2.5 text-center ${accent}`}>
      <p className="text-sm font-semibold text-slate-800">{text}</p>
      {subtext && <p className="mt-0.5 text-xs text-slate-500">{subtext}</p>}
    </div>
  );
}

/**
 * DarkTranscriptConfirmation — dark-themed transcript review box.
 * Same functionality as TranscriptConfirmation, reskinned for dark background.
 */
function DarkTranscriptConfirmation({ transcript, micError, flowError, answerTimerNotice, onTranscriptChange, onSubmit, onRetry, onCancel }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-soft">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-bold text-slate-900">Review transcript</p>
        <p className="text-xs font-semibold text-slate-500">Submit only when ready</p>
      </div>
      <textarea
        value={transcript}
        onChange={(event) => onTranscriptChange(event.target.value)}
        rows={4}
        placeholder="Type or edit your answer here."
        className="mt-3 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800 placeholder-slate-400 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
      />
      {answerTimerNotice && <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-bold text-amber-700">{answerTimerNotice}</p>}
      {micError && <p className="mt-2 text-xs font-medium text-red-600">{micError}</p>}
      {flowError && <p className="mt-2 text-xs font-medium text-amber-700">{flowError}</p>}
      <p className="mt-2 text-xs font-medium text-slate-500">
        Edit the transcript if needed. Nothing is sent until you click Submit Answer.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={onSubmit}
          disabled={!transcript.trim()}
          className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-700 disabled:opacity-50"
        >
          Submit Answer
        </button>
        <button onClick={onRetry} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50">
          Retry Recording
        </button>
        <button onClick={onCancel} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50">
          Clear Transcript
        </button>
      </div>
    </div>
  );
}

/**
 * DarkConversationMessage — dark-themed chat bubble.
 */
function DarkConversationMessage({ message, onRetryCorrection, retryingCorrectionId }) {
  if (message.type === "question") {
    return (
      <div className="mb-3 max-w-sm">
        <p className="mb-1 text-xs font-bold uppercase text-brand-600">AI Coach</p>
        <div className="rounded-2xl rounded-tl-sm bg-slate-100 p-3 text-sm text-slate-800">
          {message.text}
        </div>
      </div>
    );
  }

  if (message.type === "answer") {
    return (
      <div className="mb-3 ml-auto max-w-sm">
        <p className="mb-1 text-right text-xs font-bold uppercase text-slate-500">
          You{message.timeUsedSeconds ? ` · ${formatDurationLabel(message.timeUsedSeconds)}` : ""}
        </p>
        <div className="rounded-2xl rounded-tr-sm bg-brand-600 p-3 text-sm text-white">
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className="mb-4 max-w-sm">
      <p className="mb-1 text-xs font-bold uppercase text-emerald-700">AI Feedback</p>
      <DarkSpeakingFeedbackCard
        feedback={message.feedback}
        onRetryCorrection={onRetryCorrection}
        retryingCorrection={retryingCorrectionId === message.feedback?.turn_id}
      />
    </div>
  );
}

/**
 * DarkSpeakingFeedbackCard — dark-themed feedback card.
 */
function DarkSpeakingFeedbackCard({ feedback, onRetryCorrection, retryingCorrection = false }) {
  if (!feedback) return null;
  const scores = feedback.scores || {};
  const correctionUnavailable = feedback.correction_available === false;
  const alreadyCorrect = feedback.correction_available === true && feedback.has_errors === false;
  const reaction = String(feedback.reaction || "").trim();
  const explanation =
    correctionUnavailable
      ? "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved."
      : alreadyCorrect
        ? "No grammatical correction was needed. Your sentence is already correct."
        : (
    feedback.explanation ||
    feedback.short_feedback ||
    "Review the corrected answer."
        );
  const mistakePoints = getMistakePoints(feedback, explanation);
  const correctedAnswer =
    feedback.correction_available === true && feedback.corrected_answer
      ? feedback.corrected_answer
      : "";
  const canRetryCorrection = (correctionUnavailable || feedback.source === "local_rules") && feedback.turn_id && onRetryCorrection;
  const scoresVerified = feedback.scores_verified !== false && feedback.source !== "local_rules" && !correctionUnavailable;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-soft">
      <p className={`font-semibold ${correctionUnavailable ? "text-amber-700" : "text-emerald-700"}`}>
        {correctionUnavailable ? "Correction unavailable" : feedback.appreciation || "Good attempt."}
      </p>
      {reaction && reaction !== feedback.appreciation && (
        <p className="mt-2 rounded-xl border border-brand-100 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-800">
          {reaction}
        </p>
      )}
      {feedback.correctionReading && (
        <p className="mt-2 rounded-lg bg-brand-50 px-3 py-2 text-xs font-bold text-brand-700">
          AI is reading your corrected answer...
        </p>
      )}

      {feedback.submittedAnswer && (
        <DarkFeedbackDetail label="Your original answer" text={feedback.submittedAnswer} />
      )}
      {correctionUnavailable && (
        <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm font-semibold text-amber-800">
          Detailed grammar correction is temporarily unavailable. Your original answer has been preserved.
        </p>
      )}
      {alreadyCorrect && (
        <p className="mt-3 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800">
          No grammatical correction was needed. Your sentence is already correct.
        </p>
      )}
      <DarkFeedbackDetail label="Mistake explanation" text={explanation} listItems={mistakePoints} />
      {correctedAnswer && <DarkFeedbackDetail label="Corrected answer" text={correctedAnswer} />}
      {feedback.correction_available === true && feedback.better_natural_answer && (
        <DarkFeedbackDetail label="More natural answer" text={feedback.better_natural_answer} />
      )}
      {feedback.source === "local_rules" && (
        <p className="mt-3 rounded-xl border border-sky-300 bg-sky-50 p-3 text-sm font-semibold text-sky-800">
          Basic correction from local grammar rules. Retry with AI for detailed feedback.
        </p>
      )}
      {feedback.rules_applied?.length > 0 && (
        <div className="mt-3 space-y-1 rounded-xl border border-sky-200 bg-sky-50 p-3 text-xs text-sky-900">
          {feedback.rules_applied.map((rule, index) => <p key={`${rule}-${index}`}>{rule}</p>)}
        </div>
      )}
      {feedback.unclear_phrases?.length > 0 && (
        <DarkFeedbackDetail label="Unclear transcript" text={feedback.unclear_phrases.join(", ")} />
      )}
      {feedback.retryError && (
        <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs font-semibold text-amber-800">{feedback.retryError}</p>
      )}
      {canRetryCorrection && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onRetryCorrection(feedback)}
            disabled={retryingCorrection}
            className="rounded-xl border border-brand-200 bg-white px-3 py-2 text-xs font-bold text-brand-700 transition hover:bg-brand-50 disabled:opacity-50"
          >
            {retryingCorrection ? "Retrying..." : "Retry Correction"}
          </button>
        </div>
      )}

      {feedback.mistakes?.length > 0 && (
        <div className="mt-3 space-y-2">
          {feedback.mistakes.map((mistake, index) => (
            <div key={`${mistake.incorrect}-${index}`} className="rounded-xl border border-red-400 bg-red-50 p-3">
              <p className="font-semibold text-red-700">
                {mistake.incorrect || "Issue"} {"->"} {mistake.correct || "Correction"}
              </p>
              {Array.isArray(mistake.mistake_points) && mistake.mistake_points.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-700">
                  {mistake.mistake_points.map((point, pointIndex) => (
                    <li key={`${mistake.incorrect}-${pointIndex}`}>{point}</li>
                  ))}
                </ul>
              ) : mistake.explanation ? (
                <p className="mt-1 text-xs text-slate-700">{mistake.explanation}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
        <DarkScorePill label="Confidence" value={scores.confidence} />
        <DarkScorePill label="Fluency" value={scores.fluency} />
        <DarkScorePill label="Grammar" value={scores.grammar} />
        {scores.knowledge != null && <DarkScorePill label="Knowledge" value={scores.knowledge} />}
        <DarkScorePill label="Overall" value={scores.overall} />
      </div>
      {!scoresVerified && (
        <p className="mt-2 text-xs font-semibold text-amber-700">Scores not evaluated.</p>
      )}
    </div>
  );
}

function DarkFeedbackDetail({ label, text, listItems = [] }) {
  if (!text && !listItems.length) return null;
  const theme = getFeedbackDetailTheme(label);
  const classes = {
    original: {
      card: "border border-amber-400 bg-amber-50",
      label: "text-amber-700",
      body: "text-slate-800",
    },
    corrected: {
      card: "border border-emerald-500 bg-emerald-50",
      label: "text-emerald-700",
      body: "text-slate-800",
    },
    mistake: {
      card: "border border-red-500 bg-red-50",
      label: "text-red-700",
      body: "text-slate-800",
    },
    neutral: {
      card: "bg-slate-50",
      label: "text-slate-500",
      body: "text-slate-700",
    },
  }[theme];

  return (
    <div className={`mt-3 rounded-xl p-3 ${classes.card}`}>
      <p className={`text-xs font-bold uppercase ${classes.label}`}>{label}</p>
      {listItems.length > 0 ? (
        <ul className={`mt-2 list-disc space-y-1 pl-5 ${classes.body}`}>
          {listItems.map((item, index) => (
            <li key={`${label}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className={`mt-1 whitespace-pre-wrap ${classes.body}`}>{text}</p>
      )}
    </div>
  );
}

function DarkScorePill({ label, value }) {
  return (
    <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">
      {label}: {formatScore10(value, "Not evaluated")}
    </span>
  );
}

/**
 * DarkBottomBar — circular icon button row at the bottom of the dark call UI.
 * Only shows buttons that are relevant to the current phase, mirroring
 * the original conditional-rendering logic exactly — just reskinned.
 */
function DarkBottomBar({ state, voiceEnabled, transcript, onToggleVoice, onResumeVoice, onSubmit, onEnd, onRetry, onCancel }) {
  const isSubmitting = state === "submitting";

  /* Inline SVG icon helpers — avoids needing an icon library */
  const VolumeOnIcon = (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  );
  const VolumeOffIcon = (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <line x1="23" y1="9" x2="17" y2="15" />
      <line x1="17" y1="9" x2="23" y2="15" />
    </svg>
  );
  const PlayIcon = (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
  const SendIcon = (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
  const RetryIcon = (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-4" />
    </svg>
  );
  const XIcon = (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
  const ClearIcon = (
    <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );

  return (
    <div className="flex items-center justify-center gap-6 px-4">
      {/* Voice toggle — always visible during active session */}
      <IconButton
        icon={voiceEnabled ? VolumeOnIcon : VolumeOffIcon}
        label={voiceEnabled ? "Voice On" : "Voice Off"}
        onClick={onToggleVoice}
        disabled={isSubmitting}
      />

      {/* Resume — only when waiting_for_user (mirrors original conditional) */}
      {state === "waiting_for_user" && (
        <IconButton
          icon={PlayIcon}
          label="Resume"
          onClick={onResumeVoice}
          tone="primary"
        />
      )}

      {/* Submit Answer — only when transcript_ready (mirrors original) */}
      {state === "transcript_ready" && (
        <IconButton
          icon={SendIcon}
          label="Submit"
          onClick={onSubmit}
          disabled={!transcript.trim()}
          tone="primary"
        />
      )}

      {/* Retry Recording — only when transcript_ready */}
      {state === "transcript_ready" && (
        <IconButton
          icon={RetryIcon}
          label="Retry"
          onClick={onRetry}
        />
      )}

      {/* Clear Transcript — only when transcript_ready */}
      {state === "transcript_ready" && (
        <IconButton
          icon={ClearIcon}
          label="Clear"
          onClick={onCancel}
        />
      )}

      {/* End — always visible */}
      <IconButton
        icon={XIcon}
        label="End"
        onClick={onEnd}
        tone="danger"
        disabled={isSubmitting}
      />
    </div>
  );
}
