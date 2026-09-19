import { useEffect, useRef, useState } from "react";
import { exitInterview } from "../api";
import { reportClientError } from "../utils/clientLogger";

export default function useExitGuard({
  interviewId, timeLimitSec, currentQuestionRef, transcriptRef, startTimeRef,
  cancelActiveRequest, stopInterviewResources, setPhase, setError, onExited,
  isListening, isSpeaking, phase, manualAnswerModeRef, onContinue,
}) {
  const [showExitModal, setShowExitModal] = useState(false);
  const [isExiting, setIsExiting] = useState(false);
  const exitStartedRef = useRef(false);
  const wasListeningBeforeModalRef = useRef(false);
  const wasAskingBeforeModalRef = useRef(false);
  const wasManualBeforeModalRef = useRef(false);
  const continueButtonRef = useRef(null);
  const exitButtonRef = useRef(null);
  const previousFocusRef = useRef(null);
  const onContinueRef = useRef(onContinue);

  useEffect(() => {
    onContinueRef.current = onContinue;
  }, [onContinue]);

  function openExitModal() {
    if (isExiting) return;
    wasListeningBeforeModalRef.current = isListening || phase === "answering";
    wasAskingBeforeModalRef.current = isSpeaking || phase === "asking";
    wasManualBeforeModalRef.current = manualAnswerModeRef.current;
    stopInterviewResources();
    setShowExitModal(true);
  }

  function handleContinueInterview() {
    setShowExitModal(false);
    if (exitStartedRef.current) return;
    onContinueRef.current?.({
      wasListening: wasListeningBeforeModalRef.current,
      wasAsking: wasAskingBeforeModalRef.current,
      wasManual: wasManualBeforeModalRef.current,
    });
  }

  async function handleConfirmExit() {
    if (isExiting || exitStartedRef.current) return;
    exitStartedRef.current = true;
    setIsExiting(true);
    setPhase("finishing");
    cancelActiveRequest();
    stopInterviewResources();
    const timeTaken = startTimeRef.current
      ? Math.min(timeLimitSec, Math.round((Date.now() - startTimeRef.current) / 1000))
      : 0;
    try {
      await exitInterview({
        interview_id: interviewId,
        question_order: currentQuestionRef.current.order,
        answer: transcriptRef.current,
        time_taken_sec: timeTaken,
      });
    } catch (e) {
      reportClientError("interview_exit_failed", e, {
        interview_id: interviewId,
        question_order: currentQuestionRef.current.order,
      });
      setError(e.message || "Could not save exit status, but the interview has been stopped.");
    } finally {
      onExited();
    }
  }

  useEffect(() => {
    const handleBeforeUnload = (event) => {
      if (exitStartedRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const handlePopState = () => {
      if (!exitStartedRef.current) {
        openExitModal();
        window.history.pushState(null, "", window.location.href);
      }
    };
    window.history.pushState(null, "", window.location.href);
    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("popstate", handlePopState);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!showExitModal) return;
    previousFocusRef.current = document.activeElement;
    continueButtonRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        handleContinueInterview();
        return;
      }
      if (event.key !== "Tab") return;
      const focusableElements = [continueButtonRef.current, exitButtonRef.current].filter(Boolean);
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocusRef.current?.focus?.();
    };
  }, [showExitModal]);

  return { showExitModal, isExiting, exitStartedRef, continueButtonRef, exitButtonRef, openExitModal, handleContinueInterview, handleConfirmExit };
}
