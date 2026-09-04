import { useEffect, useMemo, useRef, useState } from "react";
import client from "../api/client";
import DifficultySelector from "../components/DifficultySelector.jsx";
import DraftStatus from "../components/writing/DraftStatus.jsx";
import ModeTabs from "../components/ModeTabs.jsx";
import SessionResultDashboard from "../components/SessionResultDashboard.jsx";
import GenerateTopicsButton from "../components/GenerateTopicsButton.jsx";
import DailyChallengeReminder from "../components/DailyChallengeReminder.jsx";
import LeaveSessionDialog from "../components/LeaveSessionDialog.jsx";
import ModuleBackButton from "../components/ModuleBackButton.jsx";
import WritingFeedback from "../components/writing/WritingFeedback.jsx";
import WritingGoalCard from "../components/writing/WritingGoalCard.jsx";
import WritingHintCard from "../components/writing/WritingHintCard.jsx";
import WritingStatistics from "../components/writing/WritingStatistics.jsx";
import { getWritingGoal, getWritingStats, getReadabilityGrade, analyzeSentenceIssues } from "../components/writing/writingMetrics.js";
import { BarChart2, Cake, Home, Keyboard, Lightbulb, MessageCircle, RefreshCw, Send, ShieldCheck, Smile, Sparkles, Trees, Utensils, X } from "lucide-react";

const DIFFICULTIES = new Set(["easy", "medium", "hard"]);

export default function Writing() {
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
  const [dailyChallenge, setDailyChallenge] = useState(null);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [dailyError, setDailyError] = useState("");
  const [dailyChallengeStatus, setDailyChallengeStatus] = useState(null);
  const [dailyChallengeReminderDismissed, setDailyChallengeReminderDismissed] = useState(false);
  const [starting, setStarting] = useState(false);
  const [startingNotice, setStartingNotice] = useState("");
  const [setupError, setSetupError] = useState("");

  const [session, setSession] = useState(null);
  const [turnNumber, setTurnNumber] = useState(1);
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState("");
  const [phase, setPhase] = useState("setup"); // setup → answering → reviewing → complete
  const [lastScores, setLastScores] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [pendingNext, setPendingNext] = useState(null);
  const [submittedAnswer, setSubmittedAnswer] = useState("");
  const [turnId, setTurnId] = useState(null);
  const [draftStatus, setDraftStatus] = useState("");
  const [draftUpdatedAt, setDraftUpdatedAt] = useState(null);
  const [hint, setHint] = useState(null);
  const [inspirationExpanded, setInspirationExpanded] = useState(false);
  const [answerFocused, setAnswerFocused] = useState(false);
  const [hintCount, setHintCount] = useState(0);
  const [hintLoading, setHintLoading] = useState(false);
  const [hintError, setHintError] = useState("");
  const [revisionDraft, setRevisionDraft] = useState("");
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [retryableSubmitError, setRetryableSubmitError] = useState(false);
  const [showLeaveDialog, setShowLeaveDialog] = useState(false);
  const topicRequestRef = useRef({ id: 0, controller: null });
  const topicAutoTimerRef = useRef(null);
  const lastGenerateAtRef = useRef(0);
  const lastAutoGenerateRef = useRef({ key: "", at: 0 });
  const difficultyRef = useRef(difficulty);
  const draftSaveTimerRef = useRef(null);
  const latestAnswerRef = useRef("");
  const chatEndRef = useRef(null);
  const answerInputRef = useRef(null);
  const routeLeaveResolverRef = useRef(null);
  
  const [tone, setTone] = useState(null);
  const [liveIssues, setLiveIssues] = useState([]);
  const [liveGrade, setLiveGrade] = useState(null);
  const [liveChecking, setLiveChecking] = useState(false);
  const [activeLiveIssue, setActiveLiveIssue] = useState(null);
  const [weakAreas, setWeakAreas] = useState([]);
  const [isDuplicate, setIsDuplicate] = useState(false);
  const [usedAiSuggestion, setUsedAiSuggestion] = useState(false);
  const aiCheckTimerRef = useRef(null);
  const lastLiveCheckTextRef = useRef("");
  const liveCheckRequestRef = useRef(0);

  const allTopicOptions = useMemo(
    () => (customTopic ? [customTopic, ...topicOptions] : topicOptions),
    [customTopic, topicOptions]
  );

  const writingGoal = useMemo(
    () => getWritingGoal({
      mode: session?.mode || mode,
      difficulty: session?.difficulty || difficulty,
      topicTitle: session?.topic_title || allTopicOptions.find((topic) => topic.topic_id === selectedTopicId || topic.id === selectedTopicId)?.title,
      prompt,
      turnNumber,
    }),
    [difficulty, mode, prompt, selectedTopicId, session?.difficulty, session?.mode, session?.topic_title, allTopicOptions, turnNumber]
  );
  const selectedTopic = useMemo(
    () => allTopicOptions.find((topic) => topic.topic_id === selectedTopicId || topic.id === selectedTopicId) || allTopicOptions[0] || null,
    [selectedTopicId, allTopicOptions]
  );
  const writingStats = useMemo(() => getWritingStats(answer, writingGoal), [answer, writingGoal]);
  const readabilityGrade = useMemo(() => getReadabilityGrade(answer), [answer]);
  const sentenceIssues = useMemo(() => (phase === "answering" ? analyzeSentenceIssues(answer) : []), [answer, phase]);
  const draftKey = session?.session_id && turnId ? `writing:draft:${session.session_id}:${turnId}` : "";
  const compactInspiration = inspirationExpanded && (answerFocused || answer.trim().length > 0);

  const loadDailyChallengeStatus = async () => {
    try {
      const res = await client.get("/writing/daily-challenge-status");
      setDailyChallengeStatus(res.data);
    } catch {
      setDailyChallengeStatus(null);
    }
  };

  useEffect(() => {
    loadDailyChallengeStatus();
  }, []);

  useEffect(() => {
    if (phase !== "setup") return undefined;
    difficultyRef.current = difficulty;
    if (mode === "daily") {
      topicRequestRef.current.controller?.abort();
      setTopicOptions([]);
      setSelectedTopicId("");
      setTopicError("");
      setTopicLoading(false);
      loadDailyWritingChallenge();
      return undefined;
    }
    setDailyChallenge(null);
    setDailyError("");
    const autoKey = `writing:${mode}:${difficulty}`;
    const now = Date.now();
    if (lastAutoGenerateRef.current.key === autoKey && now - lastAutoGenerateRef.current.at < 1500) {
      return undefined;
    }
    lastAutoGenerateRef.current = { key: autoKey, at: now };
    topicAutoTimerRef.current = window.setTimeout(() => {
      generateTopics();
    }, 250);
    return () => {
      if (topicAutoTimerRef.current) clearTimeout(topicAutoTimerRef.current);
    };
  }, [phase, difficulty, mode]);

  useEffect(() => {
    client.get("/writing/insights").then((res) => {
      setWeakAreas(res.data?.weak_areas || []);
    }).catch(() => {
      setWeakAreas([]);
    });
  }, []);

  useEffect(() => {
    return () => {
      if (topicAutoTimerRef.current) clearTimeout(topicAutoTimerRef.current);
      topicRequestRef.current.controller?.abort();
    };
  }, []);

  useEffect(() => {
    latestAnswerRef.current = answer;
  }, [answer]);

  useEffect(() => {
    if (phase === "setup" || phase === "complete") return;
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [phase, prompt, submittedAnswer, feedback, hint, liveIssues, revisionDraft]);

  useEffect(() => {
    if (!draftKey || phase !== "answering") return undefined;
    window.localStorage.setItem(draftKey, answer);
    if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current);
    draftSaveTimerRef.current = setTimeout(() => {
      saveDraft(answer, { silent: true });
    }, 1200);
    return () => {
      if (draftSaveTimerRef.current) clearTimeout(draftSaveTimerRef.current);
    };
  }, [answer, draftKey, phase]);

  useEffect(() => {
    const handleBeforeUnload = () => {
      if (draftKey && phase === "answering") {
        window.localStorage.setItem(draftKey, latestAnswerRef.current);
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [draftKey, phase]);

  useEffect(() => {
    if (!session || phase === "setup" || phase === "complete") return undefined;
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
  }, [session, phase]);

  useEffect(() => {
    if (phase !== "answering" || answer.trim().length < 8) {
      setTone(null);
      setLiveIssues([]);
      setLiveGrade(null);
      setLiveChecking(false);
      setActiveLiveIssue(null);
      setIsDuplicate(false);
      return undefined;
    }
    if (aiCheckTimerRef.current) clearTimeout(aiCheckTimerRef.current);
    aiCheckTimerRef.current = setTimeout(async () => {
      const text = answer;
      if (text === lastLiveCheckTextRef.current) return;
      const requestId = liveCheckRequestRef.current + 1;
      liveCheckRequestRef.current = requestId;
      setLiveChecking(true);
      try {
        const res = await client.post("/writing/live-check", {
          text,
          difficulty: session?.difficulty || difficultyRef.current,
          mode: session?.mode || mode,
          prompt,
        });
        if (liveCheckRequestRef.current !== requestId) return;
        lastLiveCheckTextRef.current = text;
        setLiveIssues(res.data.issues || []);
        setLiveGrade(res.data.grade ?? null);
        setActiveLiveIssue(null);
        if (res.data.tone) {
          setTone(res.data.tone);
        }
        setIsDuplicate(Boolean(res.data.is_duplicate));
      } catch (err) {
        // Live correction should never block typing or final submission.
        if (liveCheckRequestRef.current !== requestId) return;
        setLiveIssues([]);
        setLiveGrade(null);
        setActiveLiveIssue(null);
      } finally {
        if (liveCheckRequestRef.current === requestId) {
          setLiveChecking(false);
        }
      }
    }, 2800);
    return () => {
      if (aiCheckTimerRef.current) clearTimeout(aiCheckTimerRef.current);
    };
  }, [answer, difficulty, mode, phase, prompt, session?.difficulty, session?.mode]);

  const handleDifficultyChange = (nextDifficulty) => {
    const normalizedDifficulty = normalizeDifficulty(nextDifficulty);
    difficultyRef.current = normalizedDifficulty;
    setDifficulty(normalizedDifficulty);
    setTopicOptions([]);
    setSelectedTopicId(customTopic?.id || "");
    setTopicError("");
    setDailyChallenge(null);
    setDailyError("");
    setSetupError("");
    setError("");
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
    if (title.length < 3 || title.length > 120) {
      errors.title = "Title must be 3 to 120 characters.";
    }
    if (description.length < 10 || description.length > 500) {
      errors.description = "Instruction must be 10 to 500 characters.";
    }
    return { title, description, errors };
  };

  const saveCustomTopic = () => {
    const { title, description, errors } = validateCustomTopic();
    if (Object.keys(errors).length > 0) {
      setCustomTopicErrors(errors);
      return;
    }
    const topic = {
      id: "custom-writing-topic",
      topic_id: "custom-writing-topic",
      title,
      description,
      difficulty,
      minimum_word_count: 60,
      maximum_word_count: 90,
      isCustom: true,
    };
    setCustomTopic(topic);
    setSelectedTopicId(topic.id);
    setShowCustomTopicForm(false);
    setCustomTopicErrors({});
    setTopicError("");
    setSetupError("");
  };

  const removeCustomTopic = () => {
    setCustomTopic(null);
    setShowCustomTopicForm(false);
    setCustomTopicErrors({});
    setSelectedTopicId(topicOptions[0]?.topic_id || topicOptions[0]?.id || "");
  };

  const generateTopics = async (manual = false, { retrying = false } = {}) => {
    if (mode !== "topic") return;
    topicRequestRef.current.controller?.abort();
    const controller = new AbortController();
    const requestId = topicRequestRef.current.id + 1;
    topicRequestRef.current = { id: requestId, controller };
    const selectedDifficulty = difficultyRef.current;

    const now = Date.now();
    if (manual && now - lastGenerateAtRef.current < 5000) {
      setTopicError("Please wait a few seconds before generating more topics.");
      return;
    }
    lastGenerateAtRef.current = now;

    setTopicOptions([]);
    setSelectedTopicId("");
    setTopicError("");
    setTopicLoading(true);
    let retryScheduled = false;
    try {
      const res = await client.post("/practice/generate-topics", {
        practice_type: "writing",
        mode: mode === "topic" ? "topic_wise" : "daily_conversation",
        difficulty: selectedDifficulty,
      }, {
        signal: controller.signal,
      });
      if (topicRequestRef.current.id !== requestId) return;
      const payload = res.data.data || res.data.topics || res.data;
      const topics = dedupeTopicOptions(Array.isArray(payload) ? payload : []);
      setTopicOptions(topics);
      setSelectedTopicId(topics[0]?.topic_id || topics[0]?.id || "");
    } catch (err) {
      if (err.code === "ERR_CANCELED" || err.name === "CanceledError") return;
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
      setSelectedTopicId("");
      setTopicError(getApiErrorMessage(err, "Could not generate a writing topic. Check the backend and try again."));
    } finally {
      if (topicRequestRef.current.id === requestId && !retryScheduled) {
        setTopicLoading(false);
      }
    }
  };

  const loadDailyWritingChallenge = async () => {
    setDailyLoading(true);
    setDailyError("");
    setSetupError("");
    try {
      const res = await client.get("/writing/daily", {
        params: { difficulty: difficultyRef.current },
      });
      setDailyChallenge(res.data);
    } catch (err) {
      setDailyChallenge(null);
      setDailyError(getApiErrorMessage(err, "Today's writing challenge could not be loaded right now."));
    } finally {
      setDailyLoading(false);
    }
  };

  const startSession = async () => {
    setSetupError("");
    setStartingNotice("");
    if (!selectedTopic) {
      setSetupError("Please choose a writing prompt before starting.");
      return;
    }
    setStarting(true);
    const noticeTimer = window.setTimeout(() => {
      setStartingNotice("Connecting to AI tutor… this may take a moment. We’ll use a safe starter prompt if AI is busy.");
    }, 2500);
    try {
      const selectedDifficulty = difficultyRef.current;
      const startPayload = selectedTopic.isCustom
        ? {
            mode,
            difficulty: selectedDifficulty,
            generated_topic_id: null,
            topic_title: selectedTopic.title,
            topic_description: selectedTopic.description,
            topic_source: "custom",
          }
        : {
            mode,
            difficulty: selectedDifficulty,
            generated_topic_id: selectedTopic.topic_id,
            topic_title: selectedTopic.title,
            topic_description: selectedTopic.description,
          };
      const res = await client.post("/writing/start", startPayload);
      setSession(res.data);
      setTurnId(res.data.turn_id || null);
      setTurnNumber(res.data.turn_number);
      setPrompt(res.data.prompt);
      setAnswer("");
      setDraftStatus("");
      setDraftUpdatedAt(null);
      setTone(null);
      setLiveIssues([]);
      setLiveGrade(null);
      setActiveLiveIssue(null);
      setIsDuplicate(false);
      setUsedAiSuggestion(false);
      setHint(null);
      setInspirationExpanded(false);
      setAnswerFocused(false);
      setHintCount(0);
      setHintError("");
      setFeedback(null);
      setPendingNext(null);
      setSetupError("");
      setPhase("answering");
    } catch (err) {
      setSetupError(getApiErrorMessage(err, "AI tutor is busy right now. Please try again in a minute."));
    } finally {
      window.clearTimeout(noticeTimer);
      setStarting(false);
      setStartingNotice("");
    }
  };

  const submitAnswer = async () => {
    if (phase !== "answering" || pendingNext) {
      setError("This prompt has already been evaluated. Continue to the next prompt when ready.");
      return;
    }
    setRetryableSubmitError(false);
    if (!answer.trim()) return;
    const belowGoal = writingStats.words > 0 && writingStats.words < writingGoal.minWords;
    if (belowGoal) {
      setError(`Your answer is below the suggested ${writingGoal.minWords}-word target. You can still submit when ready.`);
    }
    setPhase("evaluating");
    if (!belowGoal) setError("");
    try {
      const res = await client.post("/writing/respond", {
        session_id: session.session_id,
        answer,
        used_ai_suggestion: usedAiSuggestion,
      });
      setLastScores(res.data.last_turn_scores);
      setFeedback(res.data.feedback || res.data.last_turn_scores);
      setSubmittedAnswer(answer);
      if (draftKey) window.localStorage.removeItem(draftKey);
      setDraftStatus("Submitted");

      if (res.data.done) {
        if (session?.mode === "daily") {
          loadDailyChallengeStatus();
        }
        setSummary(res.data);
        setPendingNext({ done: true });
        setPhase("feedback");
      } else {
        setPendingNext({
          done: false,
          turnId: res.data.turn_id,
          turnNumber: res.data.turn_number,
          prompt: res.data.prompt,
        });
        setPhase("feedback");
      }
    } catch (err) {
      const errorCode = err.response?.data?.error_code;
      setRetryableSubmitError(
        err.response?.status >= 500 ||
        ["EVALUATION_FAILED", "DATABASE_ERROR"].includes(errorCode)
      );
      setError(getApiErrorMessage(err, "Something went wrong evaluating your answer."));
      setPhase("answering");
    }
  };

  const saveDraft = async (text = answer, options = {}) => {
    if (!draftKey || !session?.session_id || !turnId) return;
    window.localStorage.setItem(draftKey, text);
    if (!options.silent) setDraftStatus("Saving...");
    try {
      const res = await client.put("/writing/draft", {
        session_id: session.session_id,
        turn_id: turnId,
        draft_text: text,
      });
      setDraftUpdatedAt(res.data.draft_updated_at);
      setDraftStatus(options.silent ? "Draft autosaved" : "Draft saved");
    } catch {
      setDraftStatus("Saved on this browser");
    }
  };

  const clearDraft = async () => {
    if (!window.confirm("Clear this draft for the current prompt?")) return;
    setAnswer("");
    if (draftKey) window.localStorage.removeItem(draftKey);
    setDraftStatus("Draft cleared");
    try {
      await client.delete("/writing/draft", { data: { session_id: session.session_id, turn_id: turnId } });
      setDraftUpdatedAt(null);
    } catch {
      // Local draft clear already succeeded.
    }
  };

  const getHint = async () => {
    if (!session?.session_id || !turnId) {
      console.log("[writing] hint blocked", { sessionId: session?.session_id, turnId, hintCount });
      setHintError("Start writing before requesting a hint.");
      return;
    }
    if (hint && !inspirationExpanded) {
      setInspirationExpanded(true);
      setHintError("");
      return;
    }
    if (hintCount >= 2) {
      console.log("[writing] hint blocked", { sessionId: session.session_id, turnId, hintCount });
      setHintError("You've used both hints for this prompt.");
      return;
    }
    setHintLoading(true);
    setHintError("");
    try {
      const res = await client.post("/writing/hint", {
        session_id: session.session_id,
        turn_id: turnId,
        answer,
        hint_count: hintCount,
      });
      console.log("[writing] hint response", res.data);
      setHint(res.data.hint);
      setInspirationExpanded(true);
      setHintCount(res.data.hint_count);
    } catch (err) {
      const data = err.response?.data;
      console.error("[writing] hint failed", err.response?.status, data);
      setHintError(getApiErrorMessage(err, "Could not get a hint right now."));
    } finally {
      setHintLoading(false);
    }
  };

  const continueToNextPrompt = () => {
    if (pendingNext?.done) {
      setPhase("complete");
      return;
    }
    setTurnId(pendingNext.turnId);
    setTurnNumber(pendingNext.turnNumber);
    setPrompt(pendingNext.prompt);
    setAnswer("");
    setSubmittedAnswer("");
    setLastScores(null);
    setFeedback(null);
    setPendingNext(null);
    setTone(null);
    setLiveIssues([]);
    setLiveGrade(null);
    setLiveChecking(false);
    setActiveLiveIssue(null);
    setIsDuplicate(false);
    lastLiveCheckTextRef.current = "";
    setHint(null);
    setInspirationExpanded(false);
    setAnswerFocused(false);
    setHintCount(0);
    setHintError("");
    setRevisionDraft("");
    setDraftStatus("");
    setDraftUpdatedAt(null);
    setError("");
    setPhase("answering");
  };

  const markSuggestionUsed = async () => {
    if (!session?.session_id || !turnId) return;
    setUsedAiSuggestion(true);
    try {
      await client.post("/writing/mark-suggestion-used", { session_id: session.session_id, turn_id: turnId });
    } catch (err) {
      try { await client.post(`/writing/turn/${turnId}/flag_ai`); } catch (fallbackErr) {}
    }
  };

  const acceptLiveSuggestion = async (issue) => {
    if (!issue || phase !== "answering") return;
    const currentText = latestAnswerRef.current;
    const start = Number(issue.start);
    const end = Number(issue.end);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > currentText.length) {
      return;
    }
    if (currentText.slice(start, end) !== issue.text) {
      setActiveLiveIssue(null);
      setLiveIssues([]);
      return;
    }
    const nextText = `${currentText.slice(0, start)}${issue.suggestion}${currentText.slice(end)}`;
    const nextCursor = start + issue.suggestion.length;
    if (inspirationExpanded && nextText.trim()) {
      setInspirationExpanded(false);
      requestAnimationFrame(() => {
        answerInputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }
    setAnswer(nextText);
    setLiveIssues((issues) => issues.filter((item) => item !== issue));
    setActiveLiveIssue(null);
    await markSuggestionUsed();
    requestAnimationFrame(() => {
      answerInputRef.current?.focus();
      answerInputRef.current?.setSelectionRange(nextCursor, nextCursor);
    });
  };

  const handleAnswerChange = (nextValue) => {
    if (inspirationExpanded && nextValue !== answer && nextValue.trim()) {
      setInspirationExpanded(false);
      requestAnimationFrame(() => {
        answerInputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }
    setAnswer(nextValue);
    if (error) setError("");
  };

  const prepareRetry = async (useSuggestions = false, explicitStarter = null) => {
    const starter = explicitStarter ?? (useSuggestions ? feedback?.better_natural_answer || feedback?.corrected_answer || "" : submittedAnswer);
    setRevisionDraft(starter);
    if ((useSuggestions || explicitStarter != null) && turnId) {
      await markSuggestionUsed();
    }
    setDraftStatus("Original attempt is saved in history. This revision is for practice before you continue.");
  };

  const submitCurrentAnswer = submitAnswer;

  const resetToSetup = () => {
    setSession(null);
    setSummary(null);
    setAnswer("");
    setPrompt("");
    setLastScores(null);
    setFeedback(null);
    setPendingNext(null);
    setSubmittedAnswer("");
    setTurnId(null);
    setTone(null);
    setLiveIssues([]);
    setLiveGrade(null);
    setLiveChecking(false);
    setActiveLiveIssue(null);
    setIsDuplicate(false);
    setUsedAiSuggestion(false);
    lastLiveCheckTextRef.current = "";
    setHint(null);
    setInspirationExpanded(false);
    setAnswerFocused(false);
    setHintCount(0);
    setHintError("");
    setRevisionDraft("");
    setDraftStatus("");
    setDraftUpdatedAt(null);
    setError("");
    setRetryableSubmitError(false);
    setSetupError("");
      setTopicOptions([]);
      setSelectedTopicId("");
      setTopicError("");
      setDailyChallenge(null);
      setDailyError("");
      setPhase("setup");
  };

  const endWriting = async () => {
    if (!session?.session_id) {
      resetToSetup();
      return;
    }
    setPhase("evaluating");
    setError("");
    try {
      const res = await client.post("/writing/end", { session_id: session.session_id });
      setSummary(res.data);
      setSession((current) => current ? { ...current, status: "completed" } : current);
      setPendingNext(null);
      setPhase("complete");
      if (session.mode === "daily") {
        loadDailyChallengeStatus();
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not end the writing session. Please try again."));
      setPhase("answering");
    }
  };

  // ── Setup phase ──────────────────────────────────────────────────────────────
  const hasUnsavedWritingWork = Boolean(answer.trim() || revisionDraft.trim() || draftStatus);

  const leaveToWritingHome = () => {
    topicRequestRef.current.controller?.abort();
    if (draftSaveTimerRef.current) {
      window.clearTimeout(draftSaveTimerRef.current);
      draftSaveTimerRef.current = null;
    }
    if (aiCheckTimerRef.current) {
      window.clearTimeout(aiCheckTimerRef.current);
      aiCheckTimerRef.current = null;
    }
    setStarting(false);
    setStartingNotice("");
    resetToSetup();
  };

  const handleBackToWritingHome = () => {
    if (phase === "complete" || !session) {
      leaveToWritingHome();
      return;
    }
    if (phase === "answering" || phase === "evaluating" || phase === "feedback" || hasUnsavedWritingWork) {
      setShowLeaveDialog(true);
      return;
    }
    leaveToWritingHome();
  };

  if (phase === "setup") {
    const handleStartWriting = async (requestedMode = mode) => {
      const effectiveMode = requestedMode === "daily" || requestedMode === "topic" ? requestedMode : mode;
      setSetupError("");
      setStartingNotice("");
      setStarting(true);
      difficultyRef.current = difficulty;
      if (effectiveMode === "daily") {
        setMode("daily");
      }
      const noticeTimer = window.setTimeout(() => {
        setStartingNotice("Connecting to AI tutor… this may take a moment. We’ll use a safe starter prompt if AI is busy.");
      }, 2500);
      try {
        if (effectiveMode === "topic" && !selectedTopic) {
          setSetupError("Please choose a writing prompt before starting.");
          return;
        }
        // Start the backend session with the generated topic
        const payload = effectiveMode === "daily" ? {
          mode: "daily",
          difficulty,
        } : selectedTopic.isCustom ? {
          mode: effectiveMode,
          difficulty,
          generated_topic_id: null,
          topic_title: selectedTopic.title,
          topic_description: selectedTopic.description,
          topic_source: "custom",
        } : {
          mode: effectiveMode,
          difficulty,
          generated_topic_id: selectedTopic.topic_id,
          topic_title: selectedTopic.title,
          topic_description: selectedTopic.description,
        };
        const sessionRes = await client.post("/writing/start", payload);
        setSession(sessionRes.data);
        setTurnId(sessionRes.data.turn_id || null);
        setTurnNumber(sessionRes.data.turn_number);
        setPrompt(sessionRes.data.prompt);
        setAnswer("");
        setDraftStatus("");
        setDraftUpdatedAt(null);
        setHint(null);
        setInspirationExpanded(false);
        setAnswerFocused(false);
        setHintCount(0);
        setHintError("");
        setFeedback(null);
        setPendingNext(null);
        setPhase("answering");
        if (effectiveMode === "daily") {
          loadDailyChallengeStatus();
        }
      } catch (err) {
        setSetupError(getApiErrorMessage(err, "Could not start the session. Please try again."));
      } finally {
        window.clearTimeout(noticeTimer);
        setStarting(false);
        setStartingNotice("");
      }
    };

    return (
      <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <h1 className="text-2xl font-bold text-slate-900">Writing Practice</h1>
        <p className="mt-1 text-sm text-slate-500">
          Same conversation-style practice as speaking, but here you type your answers instead of talking.
        </p>

        {weakAreas.length > 0 && (
          <div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
            <p className="font-semibold">Your focus areas</p>
            <p className="mt-1 text-xs">You often struggle with: {weakAreas.map((area) => area.tag).join(", ")}</p>
          </div>
        )}

        {!dailyChallengeReminderDismissed && (
          <DailyChallengeReminder
            status={dailyChallengeStatus}
            moduleLabel="Writing"
            onDismiss={() => setDailyChallengeReminderDismissed(true)}
            onStart={() => {
              setDailyChallengeReminderDismissed(true);
              handleStartWriting("daily");
            }}
            loading={starting}
          />
        )}

        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">
          <h2 className="text-base font-semibold text-slate-800 mb-4">Configure your session</h2>

          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <p className="text-sm font-semibold text-slate-700">Difficulty level</p>
            <DifficultySelector value={difficulty} onChange={handleDifficultyChange} />
          </div>

          <div className="mt-5">
            <ModeTabs
              value={mode}
              onChange={setMode}
              dailyLabel="Daily Writing Challenge"
              tabs={[
                { key: "topic", label: "Topic-wise" },
                { key: "daily", label: "Daily Writing Challenge" },
              ]}
            />
          </div>

          {mode === "daily" ? (
            <DailyWritingChallengeCard
              data={dailyChallenge}
              difficulty={difficulty}
              loading={dailyLoading}
              error={dailyError}
              onRetry={loadDailyWritingChallenge}
            />
          ) : (
            <WritingTopicOptionGrid
              topics={allTopicOptions}
              selectedTopicId={selectedTopicId}
              loading={topicLoading}
              error={topicError}
              onSelect={setSelectedTopicId}
              onRetry={() => generateTopics(true)}
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
          )}

          {setupError && <p className="mt-4 text-sm font-medium text-red-500">{setupError}</p>}
          {startingNotice && (
            <p className="mt-4 flex items-center gap-2 rounded-xl border border-brand-100 bg-brand-50 p-3 text-sm font-semibold text-brand-700">
              <RefreshCw className="h-4 w-4 animate-spin" />
              {startingNotice}
            </p>
          )}

          <button
            type="button"
            onClick={() => handleStartWriting()}
            disabled={starting || (mode === "topic" ? topicLoading || !selectedTopic : dailyLoading || dailyChallenge?.completed)}
            className="mt-6 w-full rounded-xl bg-brand-600 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-60"
          >
            {starting ? "Starting…" : mode === "daily" ? getDailyWritingActionLabel(dailyChallenge) : "Start Writing"}
          </button>
        </div>
      </div>
    );
  }

  if (phase === "complete" && summary) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 px-4 pb-20 sm:px-6 lg:px-0">
        <ModuleBackButton label="Back to Writing" onBack={handleBackToWritingHome} />
        <SessionResultDashboard session={session} summary={summary} type="writing" onStartAnother={resetToSetup} />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <WritingChatHeader
        session={session}
        turnNumber={turnNumber}
        writingGoal={writingGoal}
      />

      <main className="mx-auto flex min-h-0 w-full max-w-4xl flex-1 flex-col px-4 py-5 sm:px-6">
        <div className="mb-3">
          <ModuleBackButton label="Back to Writing" onBack={handleBackToWritingHome} disabled={phase === "evaluating"} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto rounded-3xl border border-slate-200 bg-white/95 px-3 py-4 shadow-sm sm:px-4 md:px-6 md:py-5">
          <div className="space-y-4">
            <ChatBubble side="tutor" label="AI Tutor">
              <p>{prompt}</p>
            </ChatBubble>

            {submittedAnswer && (
              <ChatBubble side="student" label="You">
                <p>{submittedAnswer}</p>
              </ChatBubble>
            )}

            {phase === "evaluating" && (
              <ChatBubble side="tutor" label="AI Tutor">
                <div className="flex items-center gap-3">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
                  <span>Analysing your writing...</span>
                </div>
              </ChatBubble>
            )}

            {phase === "feedback" && feedback && (
              <ChatBubble side="tutor" label="AI Feedback">
                <div className="space-y-4">
                  <div>
                    <p className="font-semibold text-slate-900">{feedback.appreciation || feedback.status || "Reviewed"}</p>
                    <p className="mt-1 text-slate-700">{feedback.short_feedback || feedback.feedback}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                    <ScoreCell label="Grammar" value={feedback.scores?.grammar ?? feedback.grammar} />
                    <ScoreCell label="Vocabulary" value={feedback.scores?.vocabulary ?? feedback.vocabulary} />
                    <ScoreCell label="Clarity" value={feedback.scores?.clarity ?? feedback.clarity} />
                    <ScoreCell label="Readability" value={`Grade ${readabilityGrade}`} />
                    <ScoreCell label="Overall" value={feedback.scores?.overall ?? feedback.overall} />
                  </div>

                  <div className="grid gap-2 md:grid-cols-2">
                    <VersionCard
                      title="Corrected version"
                      text={feedback.corrected_answer}
                      actionLabel="Apply this correction"
                      onAction={() => prepareRetry(false, feedback.corrected_answer)}
                    />
                    <VersionCard title="More natural version" text={feedback.better_natural_answer} />
                  </div>

                  {feedback.mistakes?.length > 0 && (
                    <div>
                      <p className="mb-1 text-xs font-semibold text-slate-600">Corrections</p>
                      <div className="space-y-2">
                        {feedback.mistakes.map((m, i) => (
                          <div key={i} className="rounded-xl border border-red-400 bg-red-50 px-3 py-2.5 text-sm text-slate-700">
                            <span className="font-semibold text-red-700">{m.incorrect}</span> {"->"} <span className="font-semibold text-red-700">{m.correct}</span>
                            <WritingMistakeExplanation mistake={m} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex flex-col gap-2 md:flex-row">
                    <button type="button" onClick={() => prepareRetry(false)} className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                      Edit and Retry
                    </button>
                    <button type="button" onClick={() => prepareRetry(true)} className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-700 hover:bg-brand-100">
                      Rewrite Using Suggestions
                    </button>
                    <button type="button" onClick={continueToNextPrompt} className="flex-1 rounded-xl bg-brand-600 px-4 py-3 text-sm font-bold text-white hover:bg-brand-700">
                      {pendingNext?.done ? "View Session Result" : "Continue to Next Prompt"}
                    </button>
                  </div>

                  {usedAiSuggestion && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-bold text-indigo-700">
                      AI-assisted
                    </span>
                  )}
                </div>
              </ChatBubble>
            )}

            {hint && inspirationExpanded && (
              <ChatBubble side="tutor" label="Inspiration">
                <InspirationPanel hint={hint} compact={compactInspiration} />
              </ChatBubble>
            )}

            {revisionDraft && (
              <ChatBubble side="student" label="Revision Practice">
                <textarea
                  value={revisionDraft}
                  onChange={(event) => setRevisionDraft(event.target.value)}
                  rows={4}
                  className="w-full resize-y rounded-xl border border-brand-200 bg-white p-3 text-sm leading-6 text-slate-800 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
                />
                <p className="mt-2 text-xs text-blue-100">
                  This revision is not submitted as a second score. Your original attempt remains in the session history.
                </p>
              </ChatBubble>
            )}

            <div ref={chatEndRef} />
          </div>
        </div>

        <div className="mt-4">
          {phase === "answering" && (
            <button
              type="button"
              onClick={getHint}
              disabled={hintLoading || (!hint && hintCount >= 2) || (hintCount >= 2 && inspirationExpanded)}
              className="mb-3 inline-flex items-center gap-2 rounded-full bg-blue-50 px-4 py-2 text-sm font-bold text-brand-700 shadow-sm transition hover:bg-blue-100 disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" />
              Inspire me!
            </button>
          )}

          <div className="rounded-3xl border border-slate-200 bg-white p-3 shadow-sm">
            <LiveWritingTextarea
              refEl={answerInputRef}
              value={answer}
      onChange={(nextValue) => {
        handleAnswerChange(nextValue);
        setActiveLiveIssue(null);
        setRetryableSubmitError(false);
      }}
              issues={liveIssues}
              activeIssue={activeLiveIssue}
              onIssueClick={setActiveLiveIssue}
              onAccept={acceptLiveSuggestion}
              onFocus={() => setAnswerFocused(true)}
              onBlur={() => setAnswerFocused(false)}
              disabled={phase !== "answering"}
            />

            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap gap-2">
                <Badge tone="success" icon={<BarChart2 className="h-3.5 w-3.5" />}>
                  {liveGrade ? `Grade ${liveGrade}/10 (live)` : `Grade ${readabilityGrade ?? "-"}`}
                </Badge>
                <Badge tone={liveIssues.length > 0 ? "warning" : "neutral"} icon={<RefreshCw className={`h-3.5 w-3.5 ${liveChecking ? "animate-spin" : ""}`} />}>
                  {liveChecking ? "Checking..." : `${liveIssues.length} live ${liveIssues.length === 1 ? "issue" : "issues"}`}
                </Badge>
                {tone && (
                  <Badge tone="accent" icon={<Smile className="h-3.5 w-3.5" />}>
                    Tone: {tone}
                  </Badge>
                )}
                {answer.length > 20 && (
                  <Badge tone={isDuplicate ? "warning" : "success"} icon={<ShieldCheck className="h-3.5 w-3.5" />}>
                    {isDuplicate ? "Similar" : "Original"}
                  </Badge>
                )}
              </div>
              <div className="flex flex-wrap gap-3 text-xs text-slate-400">
                <span>{writingStats.words} words</span>
                <span>{writingStats.sentences} sentences</span>
                <span>{writingStats.paragraphs} paragraphs</span>
              </div>
            </div>

            {error && (
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <p className="text-sm font-medium text-red-500">{error}</p>
                {retryableSubmitError && (
                  <button
                    type="button"
                    onClick={submitCurrentAnswer}
                    disabled={phase !== "answering" || !answer.trim()}
                    className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-bold text-red-600 transition hover:bg-red-100 disabled:opacity-50"
                  >
                    Try again
                  </button>
                )}
              </div>
            )}
            {hintError && <p className="mt-3 text-xs font-medium text-red-500">{hintError}</p>}
            {writingStats.words > 0 && writingStats.words < writingGoal.minWords && phase === "answering" && (
              <p className="mt-3 text-sm font-medium text-amber-600">
                Suggested minimum is {writingGoal.minWords} words. You can still submit when ready.
              </p>
            )}

            <div className="mt-4 flex flex-wrap items-end justify-center gap-4 md:gap-6">
              <BottomIconButton
                icon={<Keyboard className="h-5 w-5" />}
                label="Type"
                onClick={() => answerInputRef.current?.focus()}
                disabled={phase !== "answering"}
              />
              <BottomIconButton
                icon={<Send className="h-6 w-6" />}
                label={phase === "feedback" ? (pendingNext?.done ? "Results" : "Next") : "Submit"}
                primary
                onClick={phase === "feedback" ? continueToNextPrompt : submitCurrentAnswer}
                disabled={phase === "evaluating" || (phase === "answering" && !answer.trim())}
              />
              <BottomIconButton
                icon={<Lightbulb className="h-5 w-5" />}
                label="Inspire"
                onClick={getHint}
                disabled={phase !== "answering" || hintLoading || (!hint && hintCount >= 2) || (hintCount >= 2 && inspirationExpanded)}
              />
              <BottomIconButton
                icon={<X className="h-5 w-5" />}
                label="End Writing"
                onClick={endWriting}
                danger
                disabled={phase === "evaluating"}
              />
            </div>
          </div>

          <div className="mt-4 border-t border-slate-200 pt-4">
            <DraftStatus status={draftStatus} updatedAt={draftUpdatedAt} onSave={() => saveDraft(answer)} onClear={clearDraft} disabled={phase !== "answering"} />
          </div>
        </div>
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
            leaveToWritingHome();
            if (routeLeaveResolverRef.current) {
              routeLeaveResolverRef.current(true);
              routeLeaveResolverRef.current = null;
            }
          }}
        />
      </main>
    </div>
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="mb-0.5 text-xs text-slate-400">
            {session.mode === "topic" ? "Topic-wise Writing" : "Daily Writing Challenge"} · Prompt {turnNumber}
          </p>
          <p className="text-sm font-semibold text-slate-900">{prompt}</p>
        </div>
        {writingGoal && (
          <span className="rounded-lg bg-slate-50 px-2.5 py-1 text-xs text-slate-600 sm:ml-4 sm:whitespace-nowrap">
            Target {writingGoal.minWords}-{writingGoal.maxWords} words
          </span>
        )}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <Badge tone="success" icon={<BarChart2 className="h-3.5 w-3.5" />}>
          Readability: grade {readabilityGrade ?? "–"}
        </Badge>
        {tone && (
          <Badge tone="accent" icon={<Smile className="h-3.5 w-3.5" />}>
            Tone: {tone}
          </Badge>
        )}
        {answer.length > 20 && (
          <Badge tone={isDuplicate ? "warning" : "success"} icon={<ShieldCheck className="h-3.5 w-3.5" />}>
            {isDuplicate ? "Similar to a previous submission" : "Looks original"}
          </Badge>
        )}
      </div>

      <div className="mt-2 relative">
        <textarea
          ref={answerInputRef}
          value={answer}
          onChange={(event) => handleAnswerChange(event.target.value)}
          onFocus={() => setAnswerFocused(true)}
          onBlur={() => setAnswerFocused(false)}
          rows={10}
          placeholder="Type your answer here..."
          className="w-full resize-y rounded-xl border border-slate-200 p-4 text-sm leading-6 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
          disabled={phase !== "answering"}
        />
      </div>

      {liveIssues.length > 0 && (
        <div className="mt-2 space-y-1">
          {liveIssues.map((issue, i) => (
            <p key={`${issue.phrase}-${i}`} className="text-xs text-amber-700">
              <span className="font-semibold">{issue.phrase}</span> {"->"} {issue.suggestion}
            </p>
          ))}
        </div>
      )}

      {phase === "answering" && answer.trim() && (
        <div className="mt-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm leading-relaxed text-slate-700">
          {sentenceIssues.map((s, i) => (
            <span
              key={i}
              className={
                s.veryHard || s.hard
                  ? "rounded bg-amber-100 px-0.5"
                  : s.passive
                  ? "rounded bg-blue-100 px-0.5"
                  : ""
              }
            >
              {s.text}{" "}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 mb-4 flex flex-wrap gap-3 text-xs text-slate-400">
        <span>{writingStats.words} words</span>
        <span>{writingStats.sentences} sentences</span>
        <span>{writingStats.paragraphs} paragraphs</span>
        <span className="flex items-center gap-1 text-blue-600">
          <span className="h-2.5 w-2.5 rounded-sm bg-blue-200" /> passive voice
        </span>
        <span className="flex items-center gap-1 text-amber-600">
          <span className="h-2.5 w-2.5 rounded-sm bg-amber-200" /> hard to read
        </span>
      </div>

      {hint && inspirationExpanded && (
        <div className="mb-4 rounded-xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-bold text-xs uppercase mb-2">AI Hint</p>
          <InspirationPanel hint={hint} compact={compactInspiration} />
        </div>
      )}

      {error && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <p className="text-sm font-medium text-red-500">{error}</p>
          {retryableSubmitError && (
            <button
              type="button"
              onClick={submitCurrentAnswer}
              disabled={phase !== "answering" || !answer.trim()}
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-bold text-red-600 transition hover:bg-red-100 disabled:opacity-50"
            >
              Try again
            </button>
          )}
        </div>
      )}
      {writingStats.words > 0 && writingStats.words < writingGoal.minWords && phase === "answering" && (
        <p className="mb-4 text-sm font-medium text-amber-600">
          Suggested minimum is {writingGoal.minWords} words. You can still submit when ready.
        </p>
      )}

      {phase === "answering" && (
        <div className="mb-4 flex flex-col gap-2 md:flex-row">
          <button onClick={getHint} disabled={hintLoading} className="min-h-10 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <Lightbulb className="mr-1.5 inline h-4 w-4" /> Get a hint
          </button>
              <button onClick={submitCurrentAnswer} disabled={!answer.trim()} className="min-h-10 flex-1 rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white hover:opacity-90 disabled:opacity-50">
            <Send className="mr-1.5 inline h-4 w-4" /> Submit for scoring
          </button>
        </div>
      )}
      {hintError && <p className="mb-4 text-xs font-medium text-red-500">{hintError}</p>}

      {phase === "evaluating" && (
        <div className="mt-6 flex flex-col items-center py-10">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-200 border-t-brand-600" />
          <p className="mt-3 text-sm font-semibold text-slate-600">Analysing your writing...</p>
        </div>
      )}

      {phase === "feedback" && feedback && (
        <div className="border-t border-slate-200 pt-4">
          <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-slate-600">After scoring</p>
            {usedAiSuggestion && (
              <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-bold text-indigo-700">
                 AI-assisted
              </span>
            )}
          </div>
          
          <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-5">
            <ScoreCell label="Grammar" value={feedback.scores?.grammar ?? feedback.grammar} />
            <ScoreCell label="Vocabulary" value={feedback.scores?.vocabulary ?? feedback.vocabulary} />
            <ScoreCell label="Clarity" value={feedback.scores?.clarity ?? feedback.clarity} />
            <ScoreCell label="Readability" value={`Grade ${readabilityGrade}`} />
            <ScoreCell label="Overall" value={feedback.scores?.overall ?? feedback.overall} />
          </div>
          
          <div className="grid gap-2.5 md:grid-cols-2">
            <VersionCard
              title="Corrected version"
              text={feedback.corrected_answer}
              actionLabel="Apply this correction"
              onAction={() => prepareRetry(false, feedback.corrected_answer)}
            />
            <VersionCard title="More natural version" text={feedback.better_natural_answer} />
          </div>
          
          {feedback.mistakes?.length > 0 && (
            <div className="mt-3">
               <p className="mb-1 text-xs font-semibold text-slate-600">Corrections</p>
               <div className="space-y-2">
                 {feedback.mistakes.map((m, i) => (
                    <div key={i} className="rounded-xl border border-red-400 bg-red-50 px-3 py-2.5 text-sm text-slate-700">
                      <span className="font-semibold text-red-700">{m.incorrect}</span> &rarr; <span className="font-semibold text-red-700">{m.correct}</span>
                      <WritingMistakeExplanation mistake={m} />
                    </div>
                 ))}
               </div>
            </div>
          )}

          <div className="mt-6 flex flex-col gap-2 md:flex-row">
            <button type="button" onClick={() => prepareRetry(false)} className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              Edit and Retry
            </button>
            <button type="button" onClick={() => prepareRetry(true)} className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-700 hover:bg-brand-100">
              Rewrite Using Suggestions
            </button>
            <button type="button" onClick={continueToNextPrompt} className="flex-1 rounded-xl bg-brand-600 px-4 py-3 text-sm font-bold text-white hover:bg-brand-700">
              {pendingNext?.done ? "View Session Result" : "Continue to Next Prompt"}
            </button>
          </div>

          {revisionDraft && (
            <div className="mt-4 rounded-xl border border-brand-100 bg-brand-50 p-4">
              <p className="text-xs font-bold uppercase text-brand-600">Revision Practice</p>
              <textarea
                value={revisionDraft}
                onChange={(event) => setRevisionDraft(event.target.value)}
                rows={4}
                className="mt-3 w-full resize-y rounded-xl border border-brand-200 bg-white p-3 text-sm leading-6 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
              />
              <p className="mt-2 text-xs text-slate-500">
                This revision is not submitted as a second score. Your original attempt remains in the session history.
              </p>
            </div>
          )}
        </div>
      )}

      <div className="mt-8 border-t border-slate-200 pt-4">
        <DraftStatus status={draftStatus} updatedAt={draftUpdatedAt} onSave={() => saveDraft(answer)} onClear={clearDraft} disabled={phase !== "answering"} />
      </div>
    </div>
  );
}

function WritingTopicOptionGrid({
  topics,
  selectedTopicId,
  loading,
  error,
  onSelect,
  onRetry,
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
  if (loading) {
    return (
      <section className="mt-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex items-center gap-3 text-sm font-semibold text-slate-500">
          <RefreshCw className="h-4 w-4 animate-spin text-brand-600" />
          Generating writing prompts...
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <div key={item} className="h-44 animate-pulse rounded-3xl border border-slate-100 bg-slate-50" />
          ))}
        </div>
      </section>
    );
  }

  if (error && topics.length === 0) {
    return (
      <section className="mt-5 rounded-3xl border border-amber-200 bg-amber-50 p-5">
        <p className="text-sm font-bold text-amber-800">Could not load writing prompts.</p>
        <p className="mt-1 text-sm text-amber-700">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-2xl border border-amber-200 bg-white px-4 py-2 text-sm font-bold text-amber-700 hover:bg-amber-100"
        >
          <RefreshCw className="h-4 w-4" />
          Try again
        </button>
      </section>
    );
  }

  return (
    <section className="mt-5">
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-bold text-slate-900">Choose a writing prompt</p>
          <p className="mt-1 text-xs text-slate-500">Pick one AI-generated prompt, then start your writing session.</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={onOpenCustomTopic}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-2xl border border-brand-100 bg-brand-50 px-4 py-2 text-sm font-bold text-brand-700 transition hover:bg-brand-100"
          >
            <Sparkles className="h-4 w-4" />
            Customize Topic
          </button>
          <GenerateTopicsButton loading={loading} onClick={onRetry} />
        </div>
      </div>

      {showCustomTopicForm && (
        <div className="mb-4 rounded-3xl border border-brand-100 bg-brand-50/70 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-slate-900">Write your own topic</p>
              <p className="mt-1 text-xs text-slate-500">Add a title and instruction. Then choose this custom card and click Start Writing.</p>
            </div>
            <button
              type="button"
              onClick={onCloseCustomTopic}
              className="rounded-full px-2 py-1 text-sm font-bold text-slate-500 transition hover:bg-white"
              aria-label="Close custom topic form"
            >
              ×
            </button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <label className="text-sm font-semibold text-slate-700">
              Topic title
              <input
                value={customTopicForm.title}
                onChange={(event) => onCustomTopicFormChange("title", event.target.value)}
                placeholder="Example: My future career"
                className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-300 focus:ring-2 focus:ring-brand-100"
              />
              {customTopicErrors.title && <span className="mt-1 block text-xs font-medium text-red-500">{customTopicErrors.title}</span>}
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Writing instruction
              <input
                value={customTopicForm.description}
                onChange={(event) => onCustomTopicFormChange("description", event.target.value)}
                placeholder="Example: Write about the job you want and why it interests you."
                className="mt-1 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-300 focus:ring-2 focus:ring-brand-100"
              />
              {customTopicErrors.description && <span className="mt-1 block text-xs font-medium text-red-500">{customTopicErrors.description}</span>}
            </label>
          </div>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={onSaveCustomTopic}
              className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-700"
            >
              Use This Topic
            </button>
            <button
              type="button"
              onClick={onCloseCustomTopic}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {topics.map((topic) => {
          const id = topic.topic_id || topic.id;
          const Icon = getWritingTopicIcon(topic);
          const selected = id === selectedTopicId;
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
                    {selected ? "Selected" : topic.isCustom ? "Custom" : topic.difficulty}
                  </span>
                </div>
                <h2 className="mt-4 line-clamp-2 text-base font-bold text-slate-900">{topic.title}</h2>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">{topic.description}</p>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="learning-badge capitalize">{topic.isCustom ? "Custom topic" : topic.difficulty}</span>
                {topic.minimum_word_count && topic.maximum_word_count && (
                  <span className="learning-badge">{topic.minimum_word_count}-{topic.maximum_word_count} words</span>
                )}
                {topic.isCustom && (
                  <>
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(event) => {
                        event.stopPropagation();
                        onEditCustomTopic();
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          event.stopPropagation();
                          onEditCustomTopic();
                        }
                      }}
                      className="learning-badge cursor-pointer bg-white text-brand-700"
                    >
                      Edit
                    </span>
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(event) => {
                        event.stopPropagation();
                        onRemoveCustomTopic();
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          event.stopPropagation();
                          onRemoveCustomTopic();
                        }
                      }}
                      className="learning-badge cursor-pointer bg-red-50 text-red-600"
                    >
                      Remove
                    </span>
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {error && <p className="mt-3 rounded-2xl border border-amber-100 bg-amber-50 p-3 text-sm font-medium text-amber-700">{error}</p>}
    </section>
  );
}

function DailyWritingChallengeCard({ data, difficulty, loading, error, onRetry }) {
  if (loading) {
    return (
      <section className="mt-5 rounded-3xl border border-brand-100 bg-brand-50 p-5">
        <div className="flex items-center gap-3 text-sm font-semibold text-brand-700">
          <RefreshCw className="h-4 w-4 animate-spin" />
          Loading today's assigned writing challenge...
        </div>
      </section>
    );
  }

  if (error && !data) {
    return (
      <section className="mt-5 rounded-3xl border border-amber-200 bg-amber-50 p-5">
        <p className="text-sm font-bold text-amber-800">Could not load Daily Writing Challenge.</p>
        <p className="mt-1 text-sm text-amber-700">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-2xl border border-amber-200 bg-white px-4 py-2 text-sm font-bold text-amber-700 hover:bg-amber-100"
        >
          <RefreshCw className="h-4 w-4" />
          Try again
        </button>
      </section>
    );
  }

  const challenge = data?.challenge || {};
  const challengeStatus = data?.challenge_status || (data?.completed ? "completed" : "not_started");
  const firstTurn = Array.isArray(challenge.turns) ? challenge.turns[0] : null;
  const promptText = challenge.prompt || firstTurn?.ai_prompt || "Today's writing question is ready.";
  const goal = getWritingGoal({
    mode: "daily",
    difficulty: challenge.difficulty || difficulty,
    topicTitle: challenge.topic_title || "Daily Writing Challenge",
    prompt: promptText,
    turnNumber: 1,
  });
  const completed = challengeStatus === "completed" || Boolean(data?.completed || challenge.status === "completed");

  return (
    <section className="mt-5 rounded-3xl border border-brand-100 bg-gradient-to-br from-brand-50 to-white p-5 shadow-soft">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-600">{data?.challenge_date || "Today"}</p>
          <h3 className="mt-1 text-xl font-extrabold text-slate-900">Daily Writing Challenge</h3>
          <p className="mt-1 text-sm text-slate-600">One assigned question for today. Refreshing or reopening keeps this same challenge.</p>
        </div>
        <span className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-bold ${completed ? "bg-emerald-100 text-emerald-700" : "bg-white text-brand-700"}`}>
          {completed ? "Completed today" : challengeStatus === "in_progress" ? "In progress" : "Not started"}
        </span>
      </div>

      <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-400">Assigned topic</p>
        <p className="mt-1 text-base font-bold text-slate-900">{challenge.topic_title || "Daily Writing Challenge"}</p>
        <p className="mt-3 text-xs font-bold uppercase tracking-wide text-slate-400">Question</p>
        <p className="mt-1 text-sm leading-6 text-slate-700">{promptText}</p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <DailyInfo label="Difficulty" value={challenge.difficulty || difficulty} />
        <DailyInfo label="Word target" value={goal.expectedWordCount} />
        <DailyInfo label="XP reward" value={`${data?.xp_reward ?? 30} XP`} />
        <DailyInfo label="Status" value={completed ? "Completed" : challengeStatus === "in_progress" ? "In progress" : "Ready"} />
      </div>
    </section>
  );
}

function getDailyWritingActionLabel(dailyChallenge) {
  if (dailyChallenge?.completed || dailyChallenge?.challenge_status === "completed") return "Completed Today";
  if (dailyChallenge?.challenge_status === "in_progress") return "Continue Challenge";
  return "Start Challenge";
}

function DailyInfo({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white px-3 py-3">
      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-bold capitalize text-slate-800">{value}</p>
    </div>
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

function getWritingTopicIcon(topic) {
  const text = `${topic?.title || ""} ${topic?.description || ""}`.toLowerCase();
  if (/\b(park|garden|tree|nature|outdoor)\b/.test(text)) return Trees;
  if (/\b(bedroom|home|house|family|room)\b/.test(text)) return Home;
  if (/\b(birthday|party|celebration|cake)\b/.test(text)) return Cake;
  if (/\b(food|restaurant|cook|meal|breakfast|lunch|dinner)\b/.test(text)) return Utensils;
  if (/\b(message|letter|email|chat|conversation)\b/.test(text)) return MessageCircle;
  return Sparkles;
}

function LiveWritingTextarea({
  refEl,
  value,
  onChange,
  issues,
  activeIssue,
  onIssueClick,
  onAccept,
  onFocus,
  onBlur,
  disabled,
}) {
  const overlayRef = useRef(null);
  const sortedIssues = useMemo(() => normalizeLiveIssuesForText(issues, value), [issues, value]);

  const syncScroll = () => {
    if (!overlayRef.current || !refEl.current) return;
    overlayRef.current.scrollTop = refEl.current.scrollTop;
    overlayRef.current.scrollLeft = refEl.current.scrollLeft;
  };

  return (
    <div className="relative">
      <div
        ref={overlayRef}
        className="pointer-events-none absolute inset-0 z-20 box-border overflow-hidden rounded-2xl border border-transparent bg-transparent p-4 text-sm font-normal leading-6 tracking-normal text-slate-900 whitespace-pre-wrap break-words"
      >
        <LiveTextOverlay text={value} issues={sortedIssues} onIssueClick={onIssueClick} />
      </div>
      <textarea
        ref={refEl}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          window.requestAnimationFrame(syncScroll);
        }}
        onScroll={syncScroll}
        onFocus={onFocus}
        onBlur={onBlur}
        rows={4}
        placeholder="Type your answer here..."
        className="relative z-10 box-border w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm font-normal leading-6 tracking-normal text-transparent caret-slate-900 outline-none transition placeholder:text-transparent focus:border-brand-400 focus:bg-white focus:ring-2 focus:ring-brand-100"
        disabled={disabled}
      />
      {activeIssue && (
        <div className="absolute left-4 top-full z-30 mt-2 w-[min(28rem,calc(100vw-3rem))] rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-xl">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className={`text-xs font-bold uppercase ${activeIssue.type === "clarity" ? "text-blue-600" : "text-amber-600"}`}>
                {activeIssue.type === "clarity" ? "Clarity" : "Grammar"}
              </p>
              <p className="mt-1 text-slate-700">{activeIssue.explanation}</p>
              <p className="mt-2 text-slate-500">
                <span className="font-semibold text-slate-800">{activeIssue.text}</span>
                {" -> "}
                <span className="font-semibold text-emerald-700">{activeIssue.suggestion}</span>
              </p>
            </div>
            <button
              type="button"
              onClick={() => onIssueClick(null)}
              className="rounded-full p-1 text-slate-400 hover:bg-slate-50 hover:text-slate-700"
              aria-label="Close suggestion"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <button
            type="button"
            onClick={() => onAccept(activeIssue)}
            className="mt-3 rounded-xl bg-brand-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-brand-700"
          >
            Accept
          </button>
        </div>
      )}
    </div>
  );
}

function LiveTextOverlay({ text, issues, onIssueClick }) {
  if (!text) {
    return <span className="text-slate-400">Type your answer here...</span>;
  }
  const parts = [];
  let cursor = 0;
  issues.forEach((issue, index) => {
    if (issue.start > cursor) {
      parts.push(<span key={`text-${index}-${cursor}`}>{text.slice(cursor, issue.start)}</span>);
    }
    parts.push(
      <span
        key={`issue-${issue.start}-${issue.end}-${index}`}
        role="button"
        tabIndex={0}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onIssueClick(issue);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            event.stopPropagation();
            onIssueClick(issue);
          }
        }}
        className={`pointer-events-auto cursor-pointer rounded decoration-2 underline-offset-4 ${
          issue.type === "clarity"
            ? "bg-blue-50/70 decoration-blue-500 underline"
            : "bg-amber-50/80 decoration-amber-500 underline"
        }`}
      >
        {text.slice(issue.start, issue.end)}
      </span>
    );
    cursor = issue.end;
  });
  if (cursor < text.length) {
    parts.push(<span key={`text-end-${cursor}`}>{text.slice(cursor)}</span>);
  }
  return parts;
}

function normalizeLiveIssuesForText(issues, text) {
  const normalized = [];
  const taken = [];
  (issues || []).forEach((issue) => {
    const start = Number(issue.start);
    const end = Number(issue.end);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > text.length) return;
    if (issue.text && text.slice(start, end) !== issue.text) return;
    if (taken.some(([usedStart, usedEnd]) => start < usedEnd && end > usedStart)) return;
    taken.push([start, end]);
    normalized.push({ ...issue, start, end, text: text.slice(start, end) });
  });
  return normalized.sort((a, b) => a.start - b.start);
}

function WritingChatHeader({ session, turnNumber, writingGoal }) {
  const modeLabel = session?.mode === "topic" ? "Topic-wise Writing" : "Daily Writing Challenge";
  const progressLabel = `Prompt ${turnNumber}`;
  return (
    <header className="border-b border-slate-200 bg-white/95 px-4 py-3 shadow-sm">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 md:flex-nowrap md:gap-4">
        <div className="order-3 w-full min-w-0 flex-none text-center md:order-none md:w-auto md:flex-1">
          <p className="truncate text-sm font-bold text-slate-900">Writing Practice</p>
          <p className="mt-0.5 text-xs font-medium text-slate-500">
            {modeLabel} · {progressLabel}
          </p>
        </div>
        {writingGoal ? (
          <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-600">
            {writingGoal.minWords}-{writingGoal.maxWords} words
          </span>
        ) : (
          <span className="h-10 w-10" aria-hidden="true" />
        )}
      </div>
    </header>
  );
}

function ChatBubble({ side = "tutor", label, children }) {
  const isStudent = side === "student";
  return (
    <div className={`flex ${isStudent ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[90%] break-words sm:max-w-[82%] lg:max-w-[68%] ${isStudent ? "text-right" : "text-left"}`}>
        {label && (
          <p className={`mb-1 text-xs font-bold uppercase ${isStudent ? "text-brand-500" : "text-slate-400"}`}>
            {label}
          </p>
        )}
        <div
          className={`relative rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
            isStudent
              ? "rounded-tr-sm bg-brand-600 text-white"
              : "rounded-tl-sm bg-slate-100 text-slate-800"
          }`}
        >
          {children}
          <span
            className={`absolute top-3 h-3 w-3 rotate-45 ${
              isStudent ? "-right-1 bg-brand-600" : "-left-1 bg-slate-100"
            }`}
            aria-hidden="true"
          />
        </div>
      </div>
    </div>
  );
}

function InspirationPanel({ hint, compact }) {
  const [showMore, setShowMore] = useState(false);
  const shouldCap = compact;
  const capClass = shouldCap ? (showMore ? "max-h-64" : "max-h-32") : "max-h-none";

  return (
    <div>
      <div className={`overflow-y-auto pr-1 transition-[max-height,opacity] duration-200 ${capClass}`}>
        <HintContent hint={hint} />
      </div>
      {shouldCap && (
        <button
          type="button"
          onClick={() => setShowMore((value) => !value)}
          className="mt-2 text-xs font-bold text-brand-700 hover:text-brand-800"
        >
          {showMore ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

function HintContent({ hint }) {
  if (typeof hint === "string") {
    return <p>{hint}</p>;
  }
  return (
    <div className="space-y-3">
      {hint.outline?.length > 0 && (
        <div>
          <p className="text-xs font-bold uppercase text-slate-500">Outline</p>
          <ul className="mt-1 list-disc pl-4 text-slate-700">
            {hint.outline.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}
      {hint.useful_words?.length > 0 && (
        <div>
          <p className="text-xs font-bold uppercase text-slate-500">Useful Words</p>
          <p className="mt-1 text-slate-700">{hint.useful_words.join(", ")}</p>
        </div>
      )}
      {hint.teacher_tip && <p className="rounded-xl bg-white p-3 text-slate-700">{hint.teacher_tip}</p>}
    </div>
  );
}

function BottomIconButton({ icon, label, onClick, primary = false, danger = false, disabled = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex min-w-[64px] flex-col items-center gap-1 text-xs font-bold transition disabled:opacity-40 ${
        danger ? "text-red-600" : "text-slate-500"
      }`}
    >
      <span
        className={`flex items-center justify-center rounded-full shadow-sm transition ${
          primary
            ? "h-14 w-14 bg-brand-600 text-white hover:bg-brand-700"
            : danger
              ? "h-11 w-11 border border-red-200 bg-red-50 text-red-600 hover:bg-red-100"
              : "h-11 w-11 border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
        }`}
      >
        {icon}
      </span>
      <span>{label}</span>
    </button>
  );
}

function FeedbackBlock({ title, children }) {
  const theme = getWritingFeedbackTheme(title);
  const classes = {
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
      label: "text-slate-500",
      body: "text-slate-700",
    },
  }[theme];

  return (
    <div className={`rounded-xl p-3 ${classes.card}`}>
      <p className={`text-xs font-bold uppercase ${classes.label}`}>{title}</p>
      <p className={`mt-1 whitespace-pre-wrap text-sm ${classes.body}`}>{children || "Not available."}</p>
    </div>
  );
}

function normalizeDifficulty(difficulty) {
  return DIFFICULTIES.has(difficulty) ? difficulty : "easy";
}

function getApiErrorMessage(err, fallback) {
  const data = err?.response?.data;
  return data?.message || data?.msg || data?.error || data?.description || fallback;
}

function Badge({ tone, icon, children }) {
  const tones = {
    success: "bg-emerald-50 text-emerald-700",
    accent: "bg-brand-50 text-brand-700",
    warning: "bg-amber-50 text-amber-700",
    neutral: "bg-slate-50 text-slate-600",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium ${tones[tone]}`}>
      {icon}{children}
    </span>
  );
}

function ScoreCell({ label, value }) {
  return (
    <div className="rounded-xl bg-slate-50 px-1.5 py-2.5 text-center">
      <p className="mb-0.5 text-[11px] text-slate-400">{label}</p>
      <p className="text-lg font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function getWritingMistakePoints(mistake) {
  if (!Array.isArray(mistake?.mistake_points)) return [];
  return mistake.mistake_points.filter((item) => typeof item === "string" && item.trim());
}

function WritingMistakeExplanation({ mistake }) {
  const points = getWritingMistakePoints(mistake);
  if (points.length > 0) {
    return (
      <ul className="mt-1.5 list-disc space-y-1 pl-5 text-xs text-slate-700">
        {points.map((point, index) => (
          <li key={`${mistake?.incorrect || "mistake"}-${index}`}>{point}</li>
        ))}
      </ul>
    );
  }
  const fallbackText = mistake?.mistake_explanation || mistake?.explanation;
  return fallbackText ? <p className="mt-0.5 text-xs text-slate-700">{fallbackText}</p> : null;
}

function VersionCard({ title, text, actionLabel, onAction }) {
  const theme = getWritingFeedbackTheme(title);
  const classes = {
    corrected: {
      card: "border border-emerald-500 bg-emerald-50",
      label: "text-emerald-700",
      body: "text-slate-800",
      button: "border-emerald-200 text-emerald-700 hover:bg-emerald-100",
    },
    neutral: {
      card: "bg-slate-50",
      label: "text-slate-600",
      body: "text-slate-700",
      button: "border-slate-200 text-slate-600 hover:bg-slate-50",
    },
  }[theme === "corrected" ? "corrected" : "neutral"];

  return (
    <div className={`rounded-xl px-3 py-2.5 ${classes.card}`}>
      <p className={`mb-1 text-xs font-semibold ${classes.label}`}>{title}</p>
      <p className={`text-sm leading-relaxed ${classes.body}`}>{text}</p>
      {actionLabel && text && (
        <button
          type="button"
          onClick={onAction}
          className={`mt-2 rounded-lg border px-3 py-1.5 text-xs font-semibold ${classes.button}`}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

function getWritingFeedbackTheme(title) {
  const normalized = (title || "").toLowerCase();
  if (normalized.includes("corrected")) return "corrected";
  if (normalized.includes("mistake") || normalized.includes("explanation")) return "mistake";
  return "neutral";
}
