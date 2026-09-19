import { useRef, useState, useCallback } from "react";
import { logClientEvent, reportClientError } from "./utils/clientLogger";

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

  const listen = useCallback(({ onTranscript } = {}) => {
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

      recognition.onstart = () => setIsListening(true);
      recognition.onresult = (event) => {
        if (settled) return;

        interimTranscript = "";
        let newlyFinalized = "";

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += `${transcript} `;
            newlyFinalized += transcript;
          } else {
            interimTranscript += transcript;
          }
        }

        onTranscript?.((finalTranscript + interimTranscript).trim());
        setIsCandidateSpeaking(true);

        // Check the combined final + interim text. Some Web Speech
        // implementations never finalize the last short utterance before
        // ending, which previously made "I'm done" appear to do nothing.
        const combinedTranscript = (finalTranscript + interimTranscript).trim();
        const { matched, matchedPhrase, cleanedText } =
          stripTrailingDonePhrase(combinedTranscript);
        if (matched) {
          logClientEvent("debug", "speech_completion_phrase_detected", "Completion phrase detected", {
            matchedPhrase,
            resultWasFinal: Boolean(newlyFinalized),
          });
          finalTranscript = cleanedText;
          interimTranscript = "";
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
