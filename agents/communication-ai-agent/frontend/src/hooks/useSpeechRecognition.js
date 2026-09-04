import { useCallback, useEffect, useRef, useState } from "react";

const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

export default function useSpeechRecognition({ locale = "en-US", onStop }) {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [confidence, setConfidence] = useState(null);
  const [durationSeconds, setDurationSeconds] = useState(null);
  const [error, setError] = useState("");
  const recognitionRef = useRef(null);
  const startTimeRef = useRef(null);

  const stop = useCallback(() => {
    if (!recognitionRef.current) return;
    try {
      recognitionRef.current.stop();
    } catch {
      // Browser recognition may already be stopped.
    }
  }, []);

  const hardReset = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore browser-specific abort errors.
      }
      recognitionRef.current = null;
    }
    setListening(false);
    setInterimTranscript("");
  }, []);

  const start = useCallback(
    ({ clear = false } = {}) => {
      setError("");
      if (clear) {
        setTranscript("");
        setInterimTranscript("");
        setConfidence(null);
        setDurationSeconds(null);
      }
      if (!SpeechRecognitionAPI) {
        setError("Speech Recognition is not supported. Type what you spoke, then submit for basic matching.");
        onStop?.();
        return false;
      }
      hardReset();
      const recognition = new SpeechRecognitionAPI();
      recognition.lang = locale;
      recognition.interimResults = true;
      recognition.continuous = true;
      startTimeRef.current = Date.now();

      recognition.onresult = (event) => {
        let finalText = "";
        let interimText = "";
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const resultItem = event.results[index];
          const text = resultItem[0]?.transcript || "";
          if (resultItem.isFinal) {
            finalText += text;
            setConfidence(resultItem[0]?.confidence ?? null);
          } else {
            interimText += text;
          }
        }
        if (finalText) setTranscript((current) => `${current} ${finalText}`.trim());
        setInterimTranscript(interimText.trim());
      };

      recognition.onerror = (event) => {
        const messages = {
          "no-speech": "No speech was detected. Try again or type what you spoke.",
          "audio-capture": "No microphone was found.",
          "not-allowed": "Microphone permission was denied.",
          network: "Speech recognition network error. Try again.",
          aborted: "Listening stopped.",
        };
        setError(messages[event.error] || "Speech recognition stopped unexpectedly.");
      };

      recognition.onend = () => {
        const duration = startTimeRef.current ? (Date.now() - startTimeRef.current) / 1000 : null;
        setDurationSeconds(duration);
        setInterimTranscript("");
        setListening(false);
        recognitionRef.current = null;
        onStop?.();
      };

      recognitionRef.current = recognition;
      setListening(true);
      recognition.start();
      return true;
    },
    [hardReset, locale, onStop]
  );

  const clear = useCallback(() => {
    setTranscript("");
    setInterimTranscript("");
    setConfidence(null);
    setDurationSeconds(null);
    setError("");
  }, []);

  useEffect(() => hardReset, [hardReset]);

  return {
    supported: Boolean(SpeechRecognitionAPI),
    listening,
    transcript,
    interimTranscript,
    confidence,
    durationSeconds,
    error,
    setTranscript,
    setError,
    start,
    stop,
    clear,
    hardReset,
  };
}
