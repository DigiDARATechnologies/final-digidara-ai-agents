import { useEffect, useRef, useState } from "react";
import client from "../api/client";
import DifficultySelector from "../components/DifficultySelector.jsx";
import SessionResultDashboard from "../components/SessionResultDashboard.jsx";
import PronunciationModeTabs from "../components/pronunciation/PronunciationModeTabs.jsx";
import PronunciationResult from "../components/pronunciation/PronunciationResult.jsx";
import PronunciationWorkflow from "../components/pronunciation/PronunciationWorkflow.jsx";
import ErrorBoundary from "../components/ErrorBoundary.jsx";
import DailyChallengeReminder from "../components/DailyChallengeReminder.jsx";
import LeaveSessionDialog from "../components/LeaveSessionDialog.jsx";
import ModuleBackButton from "../components/ModuleBackButton.jsx";
import { formatScoreNumber } from "../utils/scoreFormat.js";


const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

export default function Pronunciation() {
  // Setup state
  const [mode, setMode] = useState(() => {
    const requestedMode = new URLSearchParams(window.location.search).get("mode");
    return requestedMode === "daily" ? "daily" : "sentence";
  });
  const [difficulty, setDifficulty] = useState("easy");
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [dailyChallengeStatus, setDailyChallengeStatus] = useState(null);
  const [dailyChallengeReminderDismissed, setDailyChallengeReminderDismissed] = useState(false);

  // Flow state
  const [phase, setPhase] = useState("setup");
  // phases: 'setup', 'loading_item', 'ready', 'listening', 'transcript_ready', 'submitting', 'showing_result', 'session_complete', 'error'
  
  const [focusAreas, setFocusAreas] = useState([]);
  
  const [sessionId, setSessionId] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [sessionSummary, setSessionSummary] = useState(null);

  const [item, setItem] = useState(null);
  const [nextItem, setNextItem] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [maxAttempts, setMaxAttempts] = useState(3);
  const [attemptNumber, setAttemptNumber] = useState(1);
  const [transcript, setTranscript] = useState("");
  const [result, setResult] = useState(null);
  const [sessionResults, setSessionResults] = useState([]);
  const [transitionMessage, setTransitionMessage] = useState("");
  const [minimalPairStep, setMinimalPairStep] = useState(0);
  const [minimalPairResponses, setMinimalPairResponses] = useState([]);
  const [showLeaveDialog, setShowLeaveDialog] = useState(false);

  // Hardware / System
  const [sysError, setSysError] = useState("");
  const recognitionRef = useRef(null);
  const recognitionStartTimeRef = useRef(null);
  const finalTranscriptRef = useRef("");
  const confidenceTotalRef = useRef(0);
  const confidenceCountRef = useRef(0);
  const manuallyStoppedRef = useRef(false);
  const routeLeaveResolverRef = useRef(null);

  useEffect(() => {
    // Priority 2: Fetch insights
    client.get("/pronunciation/insights").then((res) => {
      if (res.data?.insights) {
        setFocusAreas(res.data.insights);
      }
    }).catch(() => {});
    loadDailyChallengeStatus();
    
    return () => {
      try {
        if (recognitionRef.current) recognitionRef.current.stop();
      } catch (err) {}
    };
  }, []);

  const loadDailyChallengeStatus = async () => {
    try {
      const res = await client.get("/pronunciation/daily-challenge-status");
      setDailyChallengeStatus(res.data);
    } catch {
      setDailyChallengeStatus(null);
    }
  };

  const resetPracticeState = () => {
    setAttemptId(null);
    setTranscript("");
    setResult(null);
    setTransitionMessage("");
    setMinimalPairStep(0);
    setMinimalPairResponses([]);
    finalTranscriptRef.current = "";
    confidenceTotalRef.current = 0;
    confidenceCountRef.current = 0;
    manuallyStoppedRef.current = false;
  };

  const toScoreValue = (value) => {
    const numeric = Number(value);
    if (Number.isNaN(numeric)) return null;
    return Math.max(0, Math.min(numeric > 10 ? numeric / 10 : numeric, 10));
  };

  const getScoreValue = (source, keys) => {
    const scores = source?.scores || {};
    for (const key of keys) {
      const value = scores[key] ?? source?.[key];
      const score = toScoreValue(value);
      if (score != null) return score;
    }
    return null;
  };

  const buildPronunciationSessionSummary = (results) => {
    const items = (results || []).map((entry, index) => {
      const payload = entry?.last_turn_result || entry?.data || entry || {};
      const overall = getScoreValue(payload, ["overall", "overall_score"]) ?? toScoreValue(payload?.match_percentage);
      const accuracy = getScoreValue(payload, ["accuracy", "word_accuracy"]);
      const clarity = getScoreValue(payload, ["clarity"]);
      const fluency = getScoreValue(payload, ["fluency"]);
      const completeness = getScoreValue(payload, ["completeness"]);
      const label = entry?.item?.text || entry?.item?.content?.word_a || entry?.item?.content?.word_b || entry?.item?.label || `Item ${index + 1}`;
      return {
        id: entry?.item_id || `${index + 1}`,
        label,
        overall,
        accuracy,
        clarity,
        fluency,
        completeness,
        status: overall == null ? "Needs review" : overall >= 8 ? "Strong" : overall >= 5.5 ? "Needs polish" : "Needs practice",
      };
    });

    const validScores = items.map((item) => item.overall).filter((score) => score != null);
    const averageOverall = validScores.length ? validScores.reduce((sum, score) => sum + score, 0) / validScores.length : null;
    const averageAccuracy = items.map((item) => item.accuracy).filter((score) => score != null);
    const averageClarity = items.map((item) => item.clarity).filter((score) => score != null);
    const averageFluency = items.map((item) => item.fluency).filter((score) => score != null);
    const averageCompleteness = items.map((item) => item.completeness).filter((score) => score != null);

    const average = (values) => (values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null);
    const strengths = items.filter((item) => item.overall != null && item.overall >= 7.5).slice(0, 3);
    const needsWork = items.filter((item) => item.overall != null && item.overall < 6).slice(0, 3);

    return {
      topic_title: `${mode === "daily" ? "Daily challenge" : "Sentence"} practice`,
      mode,
      difficulty,
      overall_score: averageOverall,
      average_accuracy: average(averageAccuracy),
      average_clarity: average(averageClarity),
      average_fluency: average(averageFluency),
      average_completeness: average(averageCompleteness),
      summary_feedback: `${items.length} items completed. ${averageOverall == null ? "Scores are still being reviewed." : `Average pronunciation score ${averageOverall.toFixed(1)}/10.`} ${strengths.length ? `Strongest items: ${strengths.map((item) => item.label).join(", ")}.` : "Keep practicing to build consistency."}`,
      strengths: strengths.map((item) => `${item.label} (${item.overall != null ? item.overall.toFixed(1) : "n/a"}/10)`),
      areas_to_improve: needsWork.map((item) => `${item.label} (${item.overall != null ? item.overall.toFixed(1) : "n/a"}/10)`),
      items,
      turns: items.map((item) => ({
        id: item.id,
        title: item.label,
        feedback: item.status,
        overall_score: item.overall,
      })),
      created_at: new Date().toISOString(),
    };
  };

  const SummaryMetric = ({ label, value, compact = false }) => {
    const normalizedValue = value == null ? null : Math.max(0, Math.min(Number(value), 10));
    const toneClass = normalizedValue == null ? "text-slate-500" : normalizedValue >= 8 ? "text-emerald-700" : normalizedValue >= 5.5 ? "text-amber-700" : "text-red-700";
    const containerClass = compact ? "rounded-2xl border border-slate-200 bg-white p-3" : "rounded-2xl border border-slate-200 bg-slate-50 p-4";

    return (
      <div className={containerClass}>
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
        <p className={`mt-2 ${compact ? "text-xl" : "text-2xl"} font-bold ${toneClass}`}>{formatScoreNumber(normalizedValue, "-")}</p>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-brand-500"
            style={{ width: `${Math.max(0, Math.min(((normalizedValue ?? 0) / 10) * 100, 100))}%` }}
          />
        </div>
      </div>
    );
  };

  const startSession = async (requestedMode = mode) => {
    const effectiveMode = ["word", "sentence", "daily", "minimal_pairs"].includes(requestedMode) ? requestedMode : mode;
    setSysError("");
    setPhase("loading_item");
    resetPracticeState();
    setSessionId(null);
    setSessionSummary(null);
    setSessionResults([]);
    if (effectiveMode === "daily") {
      setMode("daily");
    }

    try {
      const res = await client.post("/pronunciation/session/start", {
        practice_mode: effectiveMode,
        difficulty,
      });
      setSessionId(res.data.session_id);
      setQuestionNumber(res.data.question_number);
      setTotalQuestions(res.data.total_questions || 0);
      setItem(res.data.item);
      setPhase("ready");
      if (effectiveMode === "daily") {
        loadDailyChallengeStatus();
      }
    } catch (err) {
      setPhase("error");
      setSysError(err.response?.data?.message || "Failed to start pronunciation session.");
    }
  };

  const minimalPairWords = () => {
    const pair = item?.content?.pair || item?.metadata?.pair || [];
    const wordA = item?.content?.word_a || item?.metadata?.word_a || pair[0];
    const wordB = item?.content?.word_b || item?.metadata?.word_b || pair[1];
    return [wordA, wordB].filter(Boolean);
  };

  const currentReferenceText = () => {
    if (mode === "minimal_pairs") {
      return minimalPairWords()[minimalPairStep] || item?.text;
    }
    return item?.text;
  };

  const handleListen = (overrideText = null) => {
    const referenceText = typeof overrideText === "string" ? overrideText : currentReferenceText();
    if (!referenceText || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(referenceText);
    utterance.lang = "en-US";
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  };

  const startListening = () => {
    if (!SpeechRecognitionAPI) {
      setSysError("Your browser does not support Speech Recognition. Please use Chrome, Edge or Safari.");
      return;
    }
    setSysError("");
    finalTranscriptRef.current = "";
    confidenceTotalRef.current = 0;
    confidenceCountRef.current = 0;
    manuallyStoppedRef.current = false;
    setTranscript("");
    setPhase("listening");

    const recognition = new SpeechRecognitionAPI();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognitionRef.current = recognition;

    recognition.onstart = () => {
      recognitionStartTimeRef.current = Date.now();
    };

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscriptRef.current += event.results[i][0].transcript;
          if (event.results[i][0].confidence > 0) {
            confidenceTotalRef.current += event.results[i][0].confidence;
            confidenceCountRef.current += 1;
          }
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      setTranscript((finalTranscriptRef.current + interim).trim());
    };

    recognition.onerror = (event) => {
      if (event.error !== "no-speech") {
        setSysError(`Microphone error: ${event.error}`);
        setPhase("ready");
      }
    };

    recognition.onend = () => {
      if (!manuallyStoppedRef.current && phase === "listening") {
        setPhase("transcript_ready");
      }
    };

    try {
      recognition.start();
    } catch (err) {
      setSysError("Could not start microphone.");
      setPhase("ready");
    }
  };

  const stopListening = () => {
    manuallyStoppedRef.current = true;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {}
    }
    setPhase("transcript_ready");
  };

  const cancelTranscript = () => {
    resetPracticeState();
    setPhase("ready");
  };

  const submitPronunciation = async () => {
    console.log("[pronunciation] submit clicked", { transcript, item, attemptId });
    if (phase === "submitting") return;
    if (!transcript.trim()) {
      setSysError("Please review or speak your transcript before submitting.");
      return;
    }

    if (mode === "minimal_pairs" && minimalPairStep === 0) {
      const avgConfidence = confidenceCountRef.current > 0 ? confidenceTotalRef.current / confidenceCountRef.current : 0;
      const duration = recognitionStartTimeRef.current ? (Date.now() - recognitionStartTimeRef.current) / 1000 : 0;
      const word = minimalPairWords()[0];
      setMinimalPairResponses([{ word, recognised_text: transcript, recognition_confidence: avgConfidence, duration_seconds: duration }]);
      setMinimalPairStep(1);
      setTranscript("");
      finalTranscriptRef.current = "";
      confidenceTotalRef.current = 0;
      confidenceCountRef.current = 0;
      recognitionStartTimeRef.current = null;
      setPhase("ready");
      setSysError(`Now say "${minimalPairWords()[1]}".`);
      return;
    }

    setPhase("submitting");
    console.log("[pronunciation] phase set to submitting");
    setSysError("");
    try {
      let currentAttemptId = attemptId;
      console.log("[pronunciation] attemptId resolved", currentAttemptId);
      if (!currentAttemptId) {
        const initRes = await client.post("/pronunciation/start", { item_id: item.item_id });
        currentAttemptId = initRes.data.data.attempt_id;
        setAttemptId(currentAttemptId);
        setAttemptNumber(initRes.data.data.attempt_number);
        setMaxAttempts(initRes.data.data.max_attempts);
      }

      const avgConfidence = confidenceCountRef.current > 0 ? confidenceTotalRef.current / confidenceCountRef.current : 0;
      let duration = 0;
      if (recognitionStartTimeRef.current) {
        duration = (Date.now() - recognitionStartTimeRef.current) / 1000;
      }
      const payload = {
        session_id: sessionId,
        item_id: item.item_id,
        attempt_id: currentAttemptId,
        recognised_text: mode === "minimal_pairs" ? "" : transcript,
        recognition_confidence: avgConfidence,
        duration_seconds: duration,
        reference_locale: "en-US",
      };
      if (mode === "minimal_pairs") {
        payload.minimal_pair_responses = [
          ...minimalPairResponses,
          {
            word: minimalPairWords()[1],
            recognised_text: transcript,
            recognition_confidence: avgConfidence,
            duration_seconds: duration,
          },
        ];
      }

      const res = await client.post("/pronunciation/submit", payload);

      console.log("[pronunciation] submit response", res.status, res.data);
      const currentResult = res.data.last_turn_result || res.data.data || res.data;
      const nextSessionResults = [...sessionResults, currentResult];
      setResult(currentResult);
      setSessionResults(nextSessionResults);

      if (res.data.adjusted_difficulty) {
        setTransitionMessage(`🎯 Nice! Next one's difficulty is adjusted to ${res.data.adjusted_difficulty}.`);
      } else {
        setTransitionMessage("✓ Item recorded. Moving to the next prompt.");
      }

      if (res.data.done) {
        if (mode === "daily") {
          loadDailyChallengeStatus();
        }
        const aggregatedSummary = buildPronunciationSessionSummary(nextSessionResults);
        setSessionSummary(aggregatedSummary);
        setPhase("session_complete");
        console.log("[pronunciation] phase set to session_complete");
      } else if (res.data.next_item) {
        setNextItem(res.data.next_item);
        setPhase("transitioning");
        console.log("[pronunciation] phase set to transitioning");
      } else {
        setPhase("ready");
      }
    } catch (err) {
      console.error("[pronunciation] submit failed", err.response?.status, err.response?.data || err);
      setPhase("transcript_ready");
      let msg = "Could not submit pronunciation. Please try again.";
      if (err.response?.status === 401) {
        msg = "Your session expired — please sign in again.";
      } else if (err.response?.data?.message) {
        msg = err.response.data.message;
      }
      setSysError(msg);
      requestAnimationFrame(() => {
        document.getElementById("pronunciation-error-banner")?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }
  };

  useEffect(() => {
    if (phase !== "transitioning" || !nextItem) return undefined;

    const timer = window.setTimeout(() => {
      setResult(null);
      setTranscript("");
      setTransitionMessage("");
      finalTranscriptRef.current = "";
      confidenceTotalRef.current = 0;
      confidenceCountRef.current = 0;
      recognitionStartTimeRef.current = null;
      setAttemptId(null);
      setAttemptNumber(1);
      setMinimalPairStep(0);
      setMinimalPairResponses([]);
      setItem(nextItem);
      setQuestionNumber((prev) => prev + 1);
      setNextItem(null);
      setPhase("ready");
    }, 900);

    return () => window.clearTimeout(timer);
  }, [phase, nextItem]);

  const handleNext = () => {
    if (sessionSummary) {
      setPhase("session_complete");
    } else if (nextItem) {
      resetPracticeState();
      setItem(nextItem);
      setQuestionNumber((prev) => prev + 1);
      setNextItem(null);
      setPhase("ready");
    } else {
      setMode("sentence");
      setDifficulty("easy");
      setTotalQuestions(0);
      setPhase("setup");
    }
  };

  const handleTryAgain = () => {
    resetPracticeState();
    setPhase("ready");
  };

  const endPractice = async () => {
    manuallyStoppedRef.current = true;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {}
    }
    if (!sessionId) {
      setPhase("setup");
      return;
    }
    setPhase("submitting");
    setSysError("");
    try {
      const res = await client.post("/pronunciation/session/end", { session_id: sessionId });
      setSessionSummary(res.data);
      setPhase("session_complete");
    } catch (err) {
      setSysError(err.response?.data?.message || "Could not end pronunciation practice. Please try again.");
      setPhase("ready");
    }
  };

  const leaveToPronunciationHome = () => {
    manuallyStoppedRef.current = true;
    try {
      recognitionRef.current?.stop();
    } catch (err) {}
    recognitionRef.current = null;
    window.speechSynthesis?.cancel();
    resetPracticeState();
    setSessionId(null);
    setQuestionNumber(1);
    setSessionSummary(null);
    setSessionResults([]);
    setItem(null);
    setNextItem(null);
    setSysError("");
    setPhase("setup");
  };

  const handleBackToPronunciationHome = () => {
    if (phase === "session_complete" || !sessionId) {
      leaveToPronunciationHome();
      return;
    }
    if (["ready", "listening", "transcript_ready", "submitting", "showing_result", "transitioning"].includes(phase)) {
      setShowLeaveDialog(true);
      return;
    }
    leaveToPronunciationHome();
  };

  useEffect(() => {
    if (!sessionId || phase === "setup" || phase === "session_complete" || phase === "error") {
      return undefined;
    }
    const handleBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [sessionId, phase]);

  useEffect(() => {
    if (!sessionId || phase === "setup" || phase === "session_complete" || phase === "error") {
      return undefined;
    }
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
  }, [sessionId, phase]);

  if (phase === "session_complete") {
    return (
      <div className="mx-auto max-w-5xl space-y-6 px-4 pb-20 sm:px-6 lg:px-0">
        <ModuleBackButton label="Back to Pronunciation" onBack={handleBackToPronunciationHome} />
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-brand-600">Pronunciation session complete</p>
              <h1 className="mt-2 text-2xl font-bold text-slate-900">Session summary</h1>
              <p className="mt-2 text-sm leading-6 text-slate-600">{sessionSummary?.summary_feedback || "Your pronunciation session is complete."}</p>
            </div>
            <button
              onClick={() => { setMode("sentence"); setDifficulty("easy"); setTotalQuestions(0); setPhase("setup"); }}
              className="rounded-full bg-brand-600 px-4 py-2 text-sm font-bold text-white"
            >
              Start another session
            </button>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-600">Overall score</p>
                  <p className="mt-1 text-4xl font-bold text-slate-900">{sessionSummary?.overall_score != null ? sessionSummary.overall_score.toFixed(1) : "-"}/10</p>
                </div>
                <div className="rounded-full border border-brand-200 bg-white px-3 py-1 text-sm font-semibold text-brand-700">
                  {sessionSummary?.items?.length || 0} items
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <SummaryMetric label="Accuracy" value={sessionSummary?.average_accuracy} />
                <SummaryMetric label="Clarity" value={sessionSummary?.average_clarity} />
                <SummaryMetric label="Fluency" value={sessionSummary?.average_fluency} />
                <SummaryMetric label="Completeness" value={sessionSummary?.average_completeness} />
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5">
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-600">What stood out</h2>
              <div className="mt-3 space-y-2">
                {sessionSummary?.strengths?.length ? sessionSummary.strengths.map((item) => (
                  <div key={item} className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800">{item}</div>
                )) : <p className="text-sm text-slate-600">No strong items were recorded for this session.</p>}
              </div>
              <h2 className="mt-5 text-sm font-bold uppercase tracking-wide text-slate-600">Needs attention</h2>
              <div className="mt-3 space-y-2">
                {sessionSummary?.areas_to_improve?.length ? sessionSummary.areas_to_improve.map((item) => (
                  <div key={item} className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800">{item}</div>
                )) : <p className="text-sm text-slate-600">No weak items were recorded for this session.</p>}
              </div>
            </div>
          </div>

          <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-600">Item breakdown</h2>
              <span className="text-sm font-semibold text-slate-500">{sessionSummary?.items?.length || 0} attempts</span>
            </div>
            <div className="mt-4 space-y-3">
              {sessionSummary?.items?.map((item, index) => (
                <div key={item.id || `${index + 1}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="text-sm font-bold text-slate-900">{item.label}</p>
                      <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{item.status}</p>
                    </div>
                    <div className="text-sm font-bold text-slate-800">{item.overall != null ? `${item.overall.toFixed(1)}/10` : "n/a"}</div>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-4">
                    <SummaryMetric label="Accuracy" value={item.accuracy} compact />
                    <SummaryMetric label="Clarity" value={item.clarity} compact />
                    <SummaryMetric label="Fluency" value={item.fluency} compact />
                    <SummaryMetric label="Completeness" value={item.completeness} compact />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    );
  }

  if (phase === "setup" || phase === "loading_item" || phase === "error") {
    if (!SpeechRecognitionAPI) {
      return (
        <div className="mx-auto max-w-4xl space-y-6 px-4 pb-20 sm:px-6 lg:px-0">
          <header className="mx-auto flex w-full max-w-2xl flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Friendly Voice Pronunciation</h1>
            </div>
          </header>
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm font-semibold text-red-700">
            <h2 className="mb-2 text-lg">Browser Not Supported</h2>
            <p>Your browser doesn't support voice recognition — try Chrome or Edge for the best experience.</p>
            <p className="mt-2 font-normal">Typing what you said defeats the purpose of pronunciation practice, so we require a supported browser for this feature.</p>
          </div>
        </div>
      );
    }

    return (
      <div className="mx-auto max-w-4xl space-y-6 px-4 pb-20 sm:px-6 lg:px-0">
        <header className="mx-auto flex w-full max-w-2xl flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Friendly Voice Pronunciation</h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-500">
              Listen to a clear reference voice, repeat it, review your transcript, then submit manually for a speech-match score.
            </p>
          </div>
        </header>

        {sysError && (
          <div id="pronunciation-error-banner" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
            {sysError}
          </div>
        )}

        {!dailyChallengeReminderDismissed && (
          <DailyChallengeReminder
            status={dailyChallengeStatus}
            moduleLabel="Pronunciation"
            onDismiss={() => setDailyChallengeReminderDismissed(true)}
            onStart={() => {
              setDailyChallengeReminderDismissed(true);
              startSession("daily");
            }}
            loading={phase === "loading_item"}
          />
        )}

        <div className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
          <h2 className="mb-4 text-lg font-bold text-slate-900">Configure Practice Session</h2>
          
          <div className="space-y-6">
            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">Difficulty</label>
              <DifficultySelector value={difficulty} onChange={setDifficulty} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">Practice Mode</label>
              <PronunciationModeTabs value={mode} onChange={setMode} />
            </div>
            <button
              onClick={() => startSession()}
              disabled={phase === "loading_item"}
              className="w-full rounded-xl bg-brand-600 px-4 py-3 font-bold text-white transition hover:bg-brand-700 disabled:opacity-50"
            >
              {phase === "loading_item" ? "Starting..." : "Start Practice"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 pb-20 sm:px-6 lg:px-0">
      <ModuleBackButton label="Back to Pronunciation" onBack={handleBackToPronunciationHome} disabled={phase === "submitting"} />

      <header className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white px-4 py-4 shadow-sm md:flex-row md:items-center md:justify-between md:px-5">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
            {mode === "daily" ? "Daily Pronunciation Challenge" : "Pronunciation"} mode - {difficulty} - Item {questionNumber}
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-normal text-slate-900">Pronunciation practice</h1>
        </div>
        <div className="flex flex-col items-start gap-2 sm:items-end">
          <span className="rounded-full border border-brand-100 bg-brand-50 px-4 py-2 text-xs font-bold text-brand-700">
            Attempt {attemptNumber} of {maxAttempts}
          </span>
          <button
            type="button"
            onClick={endPractice}
            disabled={phase === "submitting"}
            className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-bold text-red-600 transition hover:bg-red-100 disabled:opacity-50"
          >
            End Practice
          </button>
        </div>
      </header>

      {sysError && (
        <div id="pronunciation-error-banner" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
          {sysError}
        </div>
      )}

      {phase === "transitioning" ? (
        <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-600 text-lg font-bold text-white">✓</div>
            <div>
              <p className="text-sm font-bold text-emerald-800">Item recorded</p>
              <p className="text-sm text-emerald-700">{transitionMessage || "Preparing the next prompt…"}</p>
            </div>
          </div>
        </div>
      ) : (
        <PronunciationWorkflow
          phase={phase}
          item={item}
          mode={mode}
          minimalPairStep={minimalPairStep}
          minimalPairResponses={minimalPairResponses}
          transcript={transcript}
          error={sysError}
          onListen={handleListen}
          onSpeak={startListening}
          onReview={stopListening}
          onSubmit={submitPronunciation}
          onStartListening={startListening}
          onStopListening={stopListening}
          onTranscriptChange={setTranscript}
          onCancel={cancelTranscript}
        />
      )}
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
          leaveToPronunciationHome();
          if (routeLeaveResolverRef.current) {
            routeLeaveResolverRef.current(true);
            routeLeaveResolverRef.current = null;
          }
        }}
      />
    </div>
  );
}
