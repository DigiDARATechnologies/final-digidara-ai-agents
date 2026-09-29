import { useRef, useState, useCallback } from "react";
import { logClientEvent, reportClientError } from "./utils/clientLogger";
import { joinSpeechSegments, updateSpeechResultSlots } from "./utils/speechTranscript";

const DONE_PHRASE_PATTERNS = [
  /\b(?:i\s+am|i\s*['’]?\s*m)\s+done(?:\s+answering)?[\s,.;:!?]*$/i,
  /\b(?:i\s+am|i\s*['’]?\s*m)\s+finished(?:\s+answering)?[\s,.;:!?]*$/i,
  /\b(?:that\s+is|that['’]?s)\s+my\s+answer[\s,.;:!?]*$/i,
  /\b(?:done|finished)[\s,.;:!?]*$/i,
];

export function stripTrailingDonePhrase(text) {
  const input = text || "";
  for (const pattern of DONE_PHRASE_PATTERNS) {
    const match = input.match(pattern);
    if (!match) continue;

    return {
      matched: true,
      matchedPhrase: match[0].trim(),
      cleanedText: input
        .slice(0, match.index)
        .replace(/[\s,.;:!?]+$/, "")
        .trim(),
    };
  }
  return { matched: false, matchedPhrase: null, cleanedText: input };
}

// Wraps the browser's built-in Web Speech API.
// speak()   -> AI reads the question out loud (Text-to-Speech)
// listen()  -> converts the student's spoken answer to text (Speech-to-Text)
export default function useSpeech() {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isCandidateSpeaking, setIsCandidateSpeaking] = useState(false);
  const recognitionRef = useRef(null);
  const manuallyStoppingRef = useRef(false);
  const finishListeningRef = useRef(null);
  const finishSpeakingRef = useRef(null);
  const isSpeechRecognitionSupported = Boolean(
    typeof window !== "undefined"
    && (window.SpeechRecognition || window.webkitSpeechRecognition)
  );

  const speak = useCallback((text) => {
    return new Promise((resolve) => {
      let settled = false;
      const utterance = new SpeechSynthesisUtterance(text);
      const complete = () => {
        if (settled) return;
        settled = true;
        finishSpeakingRef.current = null;
        setIsSpeaking(false);
        resolve();
      };

      utterance.rate = 1;
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = complete;
      utterance.onerror = complete;
      finishSpeakingRef.current = complete;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    });
  }, []);

  const listen = useCallback(({ onTranscript, onListeningStart } = {}) => {
    return new Promise((resolve, reject) => {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        reject(new Error("Speech recognition is not supported in this browser. Try Chrome."));
        return;
      }

      const recognition = new SpeechRecognition();
      recognition.lang = "en-US";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognitionRef.current = recognition;
      manuallyStoppingRef.current = false;

      let finalTranscript = "";
      let interimTranscript = "";
      let completedSessionsTranscript = "";
      let currentSessionTranscript = "";
      const resultSlots = new Map();
      let settled = false;

      const detachHandlers = () => {
        recognition.onresult = null;
        recognition.onspeechend = null;
        recognition.onerror = null;
        recognition.onend = null;
      };

      const cleanup = () => {
        detachHandlers();
        finishListeningRef.current = null;
        setIsListening(false);
        setIsCandidateSpeaking(false);
      };

      const complete = () => {
        if (settled) return;
        settled = true;
        manuallyStoppingRef.current = true;
        cleanup();
        try {
          recognition.stop();
        } catch (e) {
          // Recognition may already be stopped by the browser.
          logClientEvent(
            "debug",
            "speech_recognition_stop_ignored",
            "Browser reported recognition was already stopped",
            { error: e }
          );
        }
        resolve((finalTranscript || interimTranscript).trim());
      };

      finishListeningRef.current = complete;

      recognition.onstart = () => {
        setIsListening(true);
        onListeningStart?.();
      };
      recognition.onresult = (event) => {
        if (settled) return;

        let newlyFinalized = "";
        const assembled = updateSpeechResultSlots(resultSlots, event);
        currentSessionTranscript = assembled.displayText;
        finalTranscript = joinSpeechSegments([completedSessionsTranscript, assembled.finalText]);
        interimTranscript = assembled.interimText;
        newlyFinalized = assembled.finalText;
        const displayedTranscript = joinSpeechSegments([completedSessionsTranscript, currentSessionTranscript]);

        onTranscript?.(displayedTranscript);
        setIsCandidateSpeaking(true);

        // Check the combined final + interim text. Some Web Speech
        // implementations never finalize the last short utterance before
        // ending, which previously made "I'm done" appear to do nothing.
        const combinedTranscript = displayedTranscript;
        const { matched, matchedPhrase, cleanedText } =
          stripTrailingDonePhrase(combinedTranscript);
        if (matched) {
          logClientEvent("debug", "speech_completion_phrase_detected", "Completion phrase detected", {
            matchedPhrase,
            resultWasFinal: Boolean(newlyFinalized),
          });
          finalTranscript = cleanedText;
          interimTranscript = "";
          completedSessionsTranscript = cleanedText;
          currentSessionTranscript = "";
          resultSlots.clear();
          onTranscript?.(finalTranscript);
          complete();
        }
      };
      recognition.onspeechend = () => {
        // A pause never completes the answer.
      };
      recognition.onerror = (event) => {
        if (settled) return;
        if (event.error === "no-speech") return;

        settled = true;
        cleanup();
        const permissionErrors = ["not-allowed", "service-not-allowed", "permission-denied"];
        if (permissionErrors.includes(event.error)) {
          reject(new Error("Microphone permission was denied. Please allow microphone access and resume when ready."));
          return;
        }
        reject(new Error(event.error));
      };
      recognition.onend = () => {
        setIsListening(false);
        if (settled || manuallyStoppingRef.current) return;

        completedSessionsTranscript = joinSpeechSegments([
          completedSessionsTranscript,
          currentSessionTranscript || finalTranscript || interimTranscript,
        ]);
        finalTranscript = completedSessionsTranscript;
        interimTranscript = "";
        currentSessionTranscript = "";
        resultSlots.clear();

        // Native recognition commonly ends after silence. Always restart it;
        // only finishListening() or a voice command may settle this session.
        window.setTimeout(() => {
          if (settled || manuallyStoppingRef.current) return;
          try {
            recognition.start();
          } catch (e) {
            settled = true;
            cleanup();
            reportClientError("speech_recognition_restart_failed", e);
            reject(new Error("Speech recognition stopped unexpectedly. Please resume when ready."));
          }
        }, 150);
      };

      logClientEvent("debug", "speech_recognition_start_requested", "Speech recognition start requested", {
        monotonic_ms: Math.round(performance.now()),
      });
      recognition.start();
    });
  }, []);

  const stopListening = useCallback(() => {
    manuallyStoppingRef.current = true;
    finishListeningRef.current = null;
    recognitionRef.current?.stop();
  }, []);

  const finishListening = useCallback(() => {
    finishListeningRef.current?.();
  }, []);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis.cancel();
    finishSpeakingRef.current?.();
    setIsSpeaking(false);
  }, []);

  return {
    speak,
    listen,
    stopListening,
    finishListening,
    stopSpeaking,
    isListening,
    isSpeaking,
    isCandidateSpeaking,
    isSpeechRecognitionSupported,
  };
}
