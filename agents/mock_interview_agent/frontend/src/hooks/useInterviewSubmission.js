import { useEffect, useRef, useState } from "react";
import { endInterview, submitAnswer, transcribeAudio } from "../api";
import { stripTrailingDonePhrase } from "../useSpeech";
import { logClientEvent, reportClientError, reportClientWarning } from "../utils/clientLogger";

const VERDICT_DISPLAY_MS = 1400;
const TRANSCRIPTION_TIMEOUT_MS = 10000;
const ANSWER_SUBMISSION_TIMEOUT_MS = 30000;
const FINAL_RESULT_TIMEOUT_MS = 45000;

function debugInterview(stage, details = {}) {
  logClientEvent("debug", `voice_interview_${stage.replace(/\s+/g, "_")}`, stage, details);
}

export default function useInterviewSubmission({ interviewId, timeLimitSec, totalQuestions, currentQuestionRef, realQuestionIndexRef, startTimeRef, isExitStarted, phase, setPhase, setError, clearTimer, stopListening, captureInProgressRef, finishAudioRecording, updateTranscript, askQuestion, onFinished }) {
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [lastVerdict, setLastVerdict] = useState(null);
  const [hasRetryableSubmission, setHasRetryableSubmission] = useState(false);
  const submittingRef = useRef(false);
  const lastSubmissionRef = useRef(null);
  const activeRequestRef = useRef(null);
  const phaseRef = useRef(phase);
  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  async function handleSubmit(answerText, { timedOut = false } = {}) {
    if (submittingRef.current || phaseRef.current === "submitting" || phaseRef.current === "finishing" || isExitStarted()) return;
    const submittedQuestion = currentQuestionRef.current;
    lastSubmissionRef.current = { answerText, timedOut };
    setHasRetryableSubmission(true);
    submittingRef.current = true;
    clearTimer();
    stopListening();
    captureInProgressRef.current = false;
    setPhase("submitting");
    setError(null);
    debugInterview("submission started", { questionOrder: submittedQuestion.order, answerLength: (answerText || "").length, timedOut });
    const timeTaken = Math.min(timeLimitSec, Math.round((Date.now() - startTimeRef.current) / 1000));
    const controller = new AbortController();
    activeRequestRef.current = controller;
    let requestTimedOut = false;
    let requestTimeout = null;
    try {
      const audioBlob = await finishAudioRecording();
      let finalAnswer = answerText || "";
      const shouldTranscribe = audioBlob?.size > 0 && (!timedOut || Boolean(finalAnswer.trim()));
      if (shouldTranscribe) {
        const transcriptionController = new AbortController();
        const abortTranscription = () => transcriptionController.abort();
        const transcriptionTimeout = setTimeout(abortTranscription, TRANSCRIPTION_TIMEOUT_MS);
        controller.signal.addEventListener("abort", abortTranscription, { once: true });
        setIsTranscribing(true);
        debugInterview("audio transcription requested");
        try {
          const accurateText = await transcribeAudio(audioBlob, { signal: transcriptionController.signal, interviewId, questionOrder: submittedQuestion.order });
          if (accurateText?.trim()) {
            finalAnswer = stripTrailingDonePhrase(accurateText.trim()).cleanedText;
            updateTranscript(finalAnswer);
          }
          debugInterview("audio transcription completed", { answerLength: finalAnswer.length });
        } catch (e) {
          if (controller.signal.aborted) throw e;
          reportClientWarning("audio_transcription_fallback_used", e, { interview_id: interviewId, question_order: submittedQuestion.order });
          debugInterview("audio transcription unavailable; using live transcript", { error: e.message });
        } finally {
          clearTimeout(transcriptionTimeout);
          controller.signal.removeEventListener("abort", abortTranscription);
          setIsTranscribing(false);
        }
      }
      if (!finalAnswer.trim() && !timedOut) {
        setError(audioBlob?.size > 0 ? "Your recording was captured, but no answer could be transcribed. Resume when you are ready to try again." : "Could not hear an answer. Resume when you are ready to try again.");
        lastSubmissionRef.current = null;
        setHasRetryableSubmission(false);
        setPhase("ready");
        return;
      }
      if (isExitStarted()) return;
      requestTimeout = window.setTimeout(() => { requestTimedOut = true; controller.abort(); }, ANSWER_SUBMISSION_TIMEOUT_MS);
      debugInterview("answer API request sent", { questionOrder: submittedQuestion.order });
      const res = await submitAnswer({ interview_id: interviewId, question_order: submittedQuestion.order, answer: finalAnswer, time_taken_sec: timeTaken, timed_out: timedOut && !finalAnswer.trim() }, { signal: controller.signal });
      window.clearTimeout(requestTimeout);
      requestTimeout = null;
      if (isExitStarted()) return;
      debugInterview("answer API response received", { questionOrder: submittedQuestion.order, done: Boolean(res.done), nextQuestionOrder: res.question_order });
      const answeredVerdict = res.answered_question_verdict;
      const verdict = answeredVerdict?.verdict || res.verdict;
      const verdictReason = answeredVerdict?.reason || res.verdict_reason;
      if (verdict) {
        setLastVerdict({ verdict, reason: verdictReason });
        await new Promise((resolve) => setTimeout(resolve, VERDICT_DISPLAY_MS));
        if (isExitStarted()) return;
      }
      if (res.done) {
        setPhase("finishing");
        requestTimeout = window.setTimeout(() => { requestTimedOut = true; controller.abort(); }, FINAL_RESULT_TIMEOUT_MS);
        debugInterview("final evaluation requested");
        const finalResult = await endInterview(interviewId, { signal: controller.signal });
        window.clearTimeout(requestTimeout);
        requestTimeout = null;
        debugInterview("final evaluation received");
        if (!isExitStarted()) onFinished(finalResult);
        return;
      }
      const nextRealQuestionIndex = realQuestionIndexRef.current + 1;
      if (nextRealQuestionIndex > totalQuestions) {
        setPhase("finishing");
        requestTimeout = window.setTimeout(() => { requestTimedOut = true; controller.abort(); }, FINAL_RESULT_TIMEOUT_MS);
        const finalResult = await endInterview(interviewId, { signal: controller.signal });
        window.clearTimeout(requestTimeout);
        requestTimeout = null;
        if (!isExitStarted()) onFinished(finalResult);
        return;
      }
      debugInterview("next question triggered", { questionOrder: res.question_order, realQuestionIndex: nextRealQuestionIndex });
      askQuestion(
        res.question,
        res.question_order,
        nextRealQuestionIndex,
        Boolean(res.is_frequently_asked)
      );
    } catch (e) {
      if (isExitStarted()) return;
      if (requestTimedOut) {
        setError("The interview service took too long to respond. Your answer is still here—please try submitting it again.");
      } else if (e.name === "AbortError") {
        return;
      } else {
        setError(e.message || "Something went wrong. Please try submitting your answer again.");
      }
      debugInterview("submission failed", { timedOut: requestTimedOut, error: e.message });
      reportClientError("answer_submission_failed", e, { interview_id: interviewId, question_order: submittedQuestion.order, timed_out: requestTimedOut });
      setPhase("ready");
    } finally {
      if (requestTimeout) window.clearTimeout(requestTimeout);
      setIsTranscribing(false);
      submittingRef.current = false;
      if (activeRequestRef.current === controller) activeRequestRef.current = null;
    }
  }

  function retryLastSubmission() {
    const pending = lastSubmissionRef.current;
    if (!pending || submittingRef.current) return;
    handleSubmit(pending.answerText, { timedOut: pending.timedOut });
  }

  function cancelActiveRequest() {
    activeRequestRef.current?.abort();
  }

  function resetSubmission() {
    lastSubmissionRef.current = null;
    setHasRetryableSubmission(false);
  }

  return { cancelActiveRequest, submittingRef, lastVerdict, setLastVerdict, isTranscribing, hasRetryableSubmission, resetSubmission, handleSubmit, retryLastSubmission };
}
