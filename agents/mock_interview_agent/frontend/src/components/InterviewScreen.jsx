import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import useSpeech from "../useSpeech";
import useInterviewFocusTracking from "../useInterviewFocusTracking";
import useInterviewTimer from "../hooks/useInterviewTimer";
import useExitGuard from "../hooks/useExitGuard";
import useAnswerCapture from "../hooks/useAnswerCapture";
import useInterviewSubmission from "../hooks/useInterviewSubmission";
import InterviewHeader from "./interview/InterviewHeader";
import AIQuestionPanel from "./interview/AIQuestionPanel";
import InterviewStatusFooter from "./interview/InterviewStatusFooter";
import ExitInterviewModal from "./interview/ExitInterviewModal";
import CandidateAnswerPanel from "./interview/CandidateAnswerPanel";

const TIME_LIMIT_BY_DIFFICULTY = {
  beginner: 60,
  intermediate: 90,
  advanced: 120,
};

/**
 * Continuous voice interview screen with TTS prompts, STT capture, and timed answer submission.
 * @param {{ interviewId: number, firstQuestion: string, difficulty: string, totalQuestions: number, onFinished: (result: object) => void, onExited: () => void }} props
 */
export default function InterviewScreen({
  interviewId,
  firstQuestion,
  difficulty,
  totalQuestions,
  initialQuestionOrder = 1,
  initialRealQuestionIndex = 1,
  initialIsFrequentlyAsked = false,
  onFinished,
  onExited,
}) {
  const TIME_LIMIT_SEC = TIME_LIMIT_BY_DIFFICULTY[difficulty] ?? 90;
  const [questionOrder, setQuestionOrder] = useState(initialQuestionOrder);
  const [realQuestionIndex, setRealQuestionIndex] = useState(initialRealQuestionIndex);
  const [question, setQuestion] = useState(null);
  const [isFrequentlyAsked, setIsFrequentlyAsked] = useState(initialIsFrequentlyAsked);
  const [phase, setPhase] = useState("loading"); // loading | asking | ready | answering | manual | submitting | finishing
  const [error, setError] = useState(null);
  const { speak, listen, stopListening, finishListening, stopSpeaking, isListening, isSpeaking, isCandidateSpeaking, isSpeechRecognitionSupported } = useSpeech();
  const currentQuestionRef = useRef({ order: initialQuestionOrder, text: null });
  const realQuestionIndexRef = useRef(initialRealQuestionIndex);
  const captureGenerationRef = useRef(0);
  // Timer, capture, submission, and exit form a deliberate callback cycle.
  // These forwarders make that cycle explicit without changing hook order or
  // allowing a hook config to rely on a later declaration via hoisting.
  const askQuestionRef = useRef(null);
  const handleSubmitRef = useRef(null);
  const handleManualAnswerTimeoutRef = useRef(null);
  const timerExpiryHandlerRef = useRef(null);
  const isExitBlockedRef = useRef(null);
  const isExitStartedRef = useRef(null);
  const stopInterviewResourcesRef = useRef(null);

  const { timeLeft, timeExpiredRef, startTimeRef, startTimer, clearTimer } = useInterviewTimer({
    timeLimitSec: TIME_LIMIT_SEC,
    captureGenerationRef,
    onTimeExpired: () => timerExpiryHandlerRef.current?.(),
  });

  const answerCapture = useAnswerCapture({
    interviewId,
    currentQuestionRef,
    captureGenerationRef,
    timeExpiredRef,
    isExitBlocked: () => isExitBlockedRef.current?.() ?? false,
    setPhase,
    setError,
    onAnswerReady: (...args) => handleSubmitRef.current?.(...args),
    listen,
    stopListening,
    isListening,
    isSpeechRecognitionSupported,
  });
  const {
    transcript, transcriptRef, audioUrl, manualAnswerMode,
    manualAnswer, manualAnswerReason, manualAnswerModeRef,
    captureInProgressRef, reset: resetAnswerCapture, updateTranscript,
    startAnswerCapture, finishAudioRecording,
    submitManualAnswer, handleManualAnswerTimeout, handleManualAnswerChange, stopCaptureResources,
  } = answerCapture;

  const submission = useInterviewSubmission({
    interviewId,
    timeLimitSec: TIME_LIMIT_SEC,
    totalQuestions,
    currentQuestionRef,
    realQuestionIndexRef,
    startTimeRef,
    isExitStarted: () => isExitStartedRef.current?.() ?? false,
    phase,
    setPhase,
    setError,
    clearTimer,
    stopListening,
    captureInProgressRef,
    finishAudioRecording,
    updateTranscript,
    askQuestion: (...args) => askQuestionRef.current?.(...args),
    onFinished,
  });
  const {
    cancelActiveRequest,
    lastVerdict,
    setLastVerdict,
    isTranscribing,
    hasRetryableSubmission,
    resetSubmission,
    handleSubmit: submitAnswerForInterview,
    retryLastSubmission: retrySubmission,
  } = submission;

  const {
    showExitModal,
    isExiting,
    exitStartedRef,
    continueButtonRef,
    exitButtonRef,
    openExitModal,
    handleContinueInterview,
    handleConfirmExit,
  } = useExitGuard({
    interviewId,
    timeLimitSec: TIME_LIMIT_SEC,
    currentQuestionRef,
    transcriptRef,
    startTimeRef,
    cancelActiveRequest,
    stopInterviewResources: () => stopInterviewResourcesRef.current?.(),
    setPhase,
    setError,
    onExited,
    isListening,
    isSpeaking,
    phase,
    manualAnswerModeRef,
    onContinue: ({ wasAsking, wasManual, wasListening }) => {
      if (wasAsking && question) {
        askQuestionRef.current?.(question, questionOrder, realQuestionIndex, isFrequentlyAsked);
      } else if (wasManual) {
        setPhase("manual");
        startTimer({ reset: false });
      } else if (phase === "answering" || wasListening) {
        startTimer({ reset: false });
        startAnswerCapture();
      }
    },
  });

  const { warning: focusWarning, summary: focusSummary } = useInterviewFocusTracking(
    interviewId,
    phase !== "finishing" && !isExiting
  );

  useEffect(() => {
    if (firstQuestion) {
      askQuestionRef.current?.(
        firstQuestion,
        initialQuestionOrder,
        initialRealQuestionIndex,
        initialIsFrequentlyAsked
      );
    }

    return () => {
      stopInterviewResourcesRef.current?.();
      cancelActiveRequest();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- interview startup must only restart when the supplied first question changes.
  }, [firstQuestion, initialIsFrequentlyAsked]);

  const askQuestion = useCallback(async (text, order, realIndex = realQuestionIndexRef.current, frequentlyAsked = false) => {
    if (exitStartedRef.current) return;

    currentQuestionRef.current = { order, text };
    realQuestionIndexRef.current = realIndex;
    setLastVerdict(null);
    setQuestion(text);
    setIsFrequentlyAsked(Boolean(frequentlyAsked));
    setQuestionOrder(order);
    setRealQuestionIndex(realIndex);
    resetSubmission();
    timeExpiredRef.current = false;
    resetAnswerCapture();
    setError(null);
    setPhase("asking");
    await speak(text);

    if (exitStartedRef.current || showExitModal) return;

    startTimer();
    startAnswerCapture();
  }, [exitStartedRef, resetAnswerCapture, resetSubmission, setLastVerdict, showExitModal, speak, startAnswerCapture, startTimer, timeExpiredRef]);

  function stopInterviewResources() {
    clearTimer();
    stopListening();
    stopSpeaking();
    stopCaptureResources();
  }

  function handleSubmit(answerText = transcript, { timedOut = false } = {}) {
    return submitAnswerForInterview(answerText, { timedOut });
  }

  function retryLastSubmission() {
    return retrySubmission();
  }

  useLayoutEffect(() => {
    askQuestionRef.current = askQuestion;
  }, [askQuestion]);

  useEffect(() => {
    handleSubmitRef.current = handleSubmit;
    handleManualAnswerTimeoutRef.current = handleManualAnswerTimeout;
    timerExpiryHandlerRef.current = () => {
      if (manualAnswerModeRef.current) {
        handleManualAnswerTimeoutRef.current?.();
      } else {
        finishListening();
      }
    };
    isExitBlockedRef.current = () => exitStartedRef.current || showExitModal;
    isExitStartedRef.current = () => exitStartedRef.current;
    stopInterviewResourcesRef.current = stopInterviewResources;
  });

  const progressPct = Math.round((timeLeft / TIME_LIMIT_SEC) * 100);
  const voiceState = (() => {
    if (isExiting) return "exiting";
    if (phase === "asking" || isSpeaking) return "asking";
    if (phase === "submitting" || phase === "finishing") return "processing";
    if (phase === "manual") return "manual";
    if (isCandidateSpeaking) return "speaking";
    if (isListening || phase === "answering") return "listening";
    return "ready";
  })();
  const voiceStateLabel = {
    asking: "AI is asking the next question",
    listening: "Listening",
    speaking: "Candidate speaking",
    manual: "Type your answer",
    processing: isTranscribing ? "Transcribing your answer…" : "Processing answer",
    exiting: "Exiting interview...",
    ready: "Ready to listen",
  }[voiceState];
  const statusSteps = [
    { key: "asking", label: "AI is asking" },
    { key: "listening", label: "Listening to your answer" },
    { key: "manual", label: "Typing your answer" },
    { key: "processing", label: "Processing answer" },
    { key: "ready", label: "Preparing next question" },
  ];

  return (
    <div className="page interview-page">
      <div className="interview-workspace">
        <InterviewHeader realQuestionIndex={realQuestionIndex} totalQuestions={totalQuestions} timeLeft={timeLeft} progressPct={progressPct} isExiting={isExiting} onExit={openExitModal} />

        {focusWarning && (
          <div className="focus-loss-warning" role="alert">
            <strong>Interview focus notice</strong>
            <span>{focusWarning}</span>
            <small>
              Recorded events: {focusSummary.focus_loss_count || 0}
            </small>
          </div>
        )}

        <div className="interview-panels">
          <AIQuestionPanel question={question} isFrequentlyAsked={isFrequentlyAsked} voiceState={voiceState} voiceStateLabel={voiceStateLabel} />

          <CandidateAnswerPanel
            isListening={isListening}
            isCandidateSpeaking={isCandidateSpeaking}
            voiceState={voiceState}
            voiceStateLabel={voiceStateLabel}
            phase={phase}
            isTranscribing={isTranscribing}
            manualAnswerMode={manualAnswerMode}
            timeLeft={timeLeft}
            manualAnswerReason={manualAnswerReason}
            manualAnswer={manualAnswer}
            handleManualAnswerChange={handleManualAnswerChange}
            submitManualAnswer={submitManualAnswer}
            transcript={transcript}
            audioUrl={audioUrl}
            lastVerdict={lastVerdict}
          />
        </div>

        <aside className="interview-tips" aria-label="Interview tips">
          <strong>Quick answer tips</strong>
          <ul>
            <li>Take a moment to think</li>
            <li>Structure your answer clearly</li>
            <li>Speak naturally and stay relevant</li>
          </ul>
        </aside>

        <InterviewStatusFooter
          voiceState={voiceState}
          voiceStateLabel={voiceStateLabel}
          manualAnswerMode={manualAnswerMode}
          statusSteps={statusSteps}
        />

        {error && (
          <div className="submission-error" role="alert">
            <p className="error-text">{error}</p>
            {phase === "ready" && hasRetryableSubmission && (
              <button className="secondary-btn compact-btn" onClick={retryLastSubmission}>
                Try submitting again
              </button>
            )}
          </div>
        )}

        {phase === "finishing" && (
          <button className="primary-btn" disabled>
            Generating your results...
          </button>
        )}
      </div>

      {showExitModal && <ExitInterviewModal continueButtonRef={continueButtonRef} exitButtonRef={exitButtonRef} onContinue={handleContinueInterview} onConfirm={handleConfirmExit} isExiting={isExiting} />}
    </div>
  );
}
