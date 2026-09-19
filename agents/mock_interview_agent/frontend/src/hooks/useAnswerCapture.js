import { useEffect, useRef, useState } from "react";
import { logClientEvent, reportClientError, reportClientWarning } from "../utils/clientLogger";

function debugInterview(stage, details = {}) {
  logClientEvent("debug", `voice_interview_${stage.replace(/\s+/g, "_")}`, stage, details);
}

export default function useAnswerCapture({ interviewId, currentQuestionRef, captureGenerationRef, timeExpiredRef, isExitBlocked, setPhase, setError, onAnswerReady, listen, stopListening, isListening, isSpeechRecognitionSupported }) {
  const [transcript, setTranscript] = useState("");
  const [audioUrl, setAudioUrl] = useState(null);
  const [manualAnswerMode, setManualAnswerMode] = useState(false);
  const [manualAnswer, setManualAnswer] = useState("");
  const [manualAnswerReason, setManualAnswerReason] = useState("");
  const transcriptRef = useRef("");
  const manualAnswerRef = useRef("");
  const manualAnswerModeRef = useRef(false);
  const mediaRecorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioBlobRef = useRef(null);
  const audioBlobPromiseRef = useRef(null);
  const recordingGenerationRef = useRef(0);
  const captureInProgressRef = useRef(false);
  const onAnswerReadyRef = useRef(onAnswerReady);

  useEffect(() => { onAnswerReadyRef.current = onAnswerReady; }, [onAnswerReady]);

  function reset() {
    captureGenerationRef.current += 1;
    setTranscript("");
    transcriptRef.current = "";
    setManualAnswer("");
    manualAnswerRef.current = "";
    setManualAnswerMode(false);
    manualAnswerModeRef.current = false;
    setManualAnswerReason("");
    recordingGenerationRef.current += 1;
    audioBlobRef.current = null;
    audioBlobPromiseRef.current = null;
    setAudioUrl(null);
  }

  function updateTranscript(text) {
    transcriptRef.current = text;
    setTranscript(text);
  }

  function enableManualAnswer(reason) {
    stopListening();
    captureInProgressRef.current = false;
    manualAnswerModeRef.current = true;
    setManualAnswerMode(true);
    setManualAnswerReason(reason);
    setError(null);
    setPhase("manual");
  }

  function handleManualAnswerChange(event) {
    const value = event.target.value;
    manualAnswerRef.current = value;
    transcriptRef.current = value;
    setManualAnswer(value);
    setTranscript(value);
    setError(null);
  }

  function submitManualAnswer() {
    const typedAnswer = manualAnswerRef.current.trim();
    if (!typedAnswer) {
      setError("Type an answer before submitting, or wait for the timer to expire.");
      return;
    }
    onAnswerReadyRef.current(typedAnswer, { timedOut: false });
  }

  function handleManualAnswerTimeout() {
    // Let the timer's own state update commit before starting submission.
    window.setTimeout(() => {
      const typedAnswer = manualAnswerRef.current.trim();
      onAnswerReadyRef.current(typedAnswer, { timedOut: !typedAnswer });
    }, 0);
  }

  async function finishAudioRecording() {
    const recorder = mediaRecorderRef.current;
    const pendingBlob = audioBlobPromiseRef.current;
    if (recorder?.state === "recording") recorder.stop();
    if (!pendingBlob) return audioBlobRef.current;
    return Promise.race([
      pendingBlob,
      new Promise((resolve) => { setTimeout(() => resolve(audioBlobRef.current), 2000); }),
    ]);
  }

  async function startAnswerCapture() {
    if (isListening || captureInProgressRef.current || isExitBlocked()) return;
    const generation = captureGenerationRef.current;
    captureInProgressRef.current = true;
    debugInterview("answer capture started", { questionOrder: currentQuestionRef.current.order });
    setError(null);
    setPhase("answering");
    if (!isSpeechRecognitionSupported) {
      enableManualAnswer("Speech recognition is not supported in this browser. Type your answer below instead.");
      return;
    }
    let resolveAudioBlob = null;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const recordingGeneration = recordingGenerationRef.current + 1;
      const recordingChunks = [];
      recordingGenerationRef.current = recordingGeneration;
      mediaStreamRef.current = stream;
      audioBlobRef.current = null;
      audioBlobPromiseRef.current = new Promise((resolve) => { resolveAudioBlob = resolve; });
      recorder.ondataavailable = (e) => { if (e.data.size > 0) recordingChunks.push(e.data); };
      recorder.onstop = () => {
        const blob = new Blob(recordingChunks, { type: "audio/webm" });
        if (recordingGenerationRef.current === recordingGeneration) {
          audioBlobRef.current = blob.size > 0 ? blob : null;
          if (blob.size > 0) setAudioUrl(URL.createObjectURL(blob));
        }
        resolveAudioBlob?.(blob.size > 0 ? blob : null);
        stream.getTracks().forEach((track) => track.stop());
        if (mediaStreamRef.current === stream) mediaStreamRef.current = null;
        if (mediaRecorderRef.current === recorder) mediaRecorderRef.current = null;
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
    } catch (e) {
      resolveAudioBlob?.(null);
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
      mediaRecorderRef.current = null;
      reportClientWarning("local_audio_recording_unavailable", e, { interview_id: interviewId, question_order: currentQuestionRef.current.order });
    }
    try {
      const text = await listen({ onTranscript: (nextTranscript) => {
        if (captureGenerationRef.current !== generation) return;
        transcriptRef.current = nextTranscript;
        setTranscript(nextTranscript);
      }});
      if (isExitBlocked() || captureGenerationRef.current !== generation) return;
      transcriptRef.current = text;
      setTranscript(text);
      debugInterview("speech capture completed", { questionOrder: currentQuestionRef.current.order, answerLength: text.length });
      mediaRecorderRef.current?.stop();
      debugInterview("recording stop requested");
      captureInProgressRef.current = false;
      const timedOut = timeExpiredRef.current && !text.trim();
      const hasRecordedAudio = Boolean(audioBlobPromiseRef.current || audioBlobRef.current?.size);
      if (text.trim() || timeExpiredRef.current || hasRecordedAudio) {
        onAnswerReadyRef.current(text, { timedOut });
      } else {
        setError("Could not hear an answer. Resume when you are ready to try again.");
        setPhase("ready");
      }
    } catch (e) {
      if (isExitBlocked()) return;
      mediaRecorderRef.current?.stop();
      captureInProgressRef.current = false;
      reportClientError("speech_answer_capture_failed", e, { interview_id: interviewId, question_order: currentQuestionRef.current.order });
      enableManualAnswer(`${e.message || "Speech recognition is unavailable."} Type your answer below instead.`);
    }
  }

  function stopCaptureResources() {
    captureInProgressRef.current = false;
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  }

  return { transcript, transcriptRef, audioUrl, manualAnswerMode, manualAnswer, manualAnswerReason, manualAnswerModeRef, manualAnswerRef, mediaRecorderRef, mediaStreamRef, audioBlobRef, audioBlobPromiseRef, recordingGenerationRef, captureInProgressRef, reset, updateTranscript, startAnswerCapture, finishAudioRecording, enableManualAnswer, submitManualAnswer, handleManualAnswerTimeout, handleManualAnswerChange, stopCaptureResources };
}
