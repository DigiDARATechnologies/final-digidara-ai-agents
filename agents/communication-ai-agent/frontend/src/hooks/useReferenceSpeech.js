import { useCallback, useEffect, useMemo, useState } from "react";

export default function useReferenceSpeech({ text, locale = "en-US", muted = false, onEnd, onError }) {
  const [voices, setVoices] = useState([]);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(0.95);

  useEffect(() => {
    const loadVoices = () => {
      const available = window.speechSynthesis?.getVoices?.() || [];
      setVoices(available.filter((voice) => voice.lang?.startsWith("en")));
    };
    loadVoices();
    window.speechSynthesis?.addEventListener?.("voiceschanged", loadVoices);
    return () => window.speechSynthesis?.removeEventListener?.("voiceschanged", loadVoices);
  }, []);

  const selectedVoice = useMemo(() => {
    const patterns = [
      /Jenny.*Natural/i,
      /Aria.*Natural/i,
      /Microsoft Jenny/i,
      /Microsoft Aria/i,
      /Google US English/i,
      /Google UK English Female/i,
      /Samantha/i,
      /Victoria/i,
      /Karen/i,
      /Zira/i,
      /Natural.*English/i,
      /en-US.*female/i,
    ];
    for (const p of patterns) {
      const match = voices.find((v) => p.test(v.name) && v.lang?.startsWith("en"));
      if (match) return match;
    }
    return (
      voices.find((v) => v.lang === locale && /female|woman/i.test(v.name)) ||
      voices.find((v) => v.lang === locale) ||
      voices.find((v) => v.lang?.startsWith("en")) ||
      null
    );
  }, [locale, voices]);

  const stop = useCallback(() => {
    window.speechSynthesis?.cancel?.();
    setPlaying(false);
  }, []);

  const speak = useCallback(
    (nextRate = 0.95, overrideText = "") => {
      const speechText = overrideText || text;
      if (!speechText || muted || !window.speechSynthesis) return false;
      window.speechSynthesis.cancel();
      setRate(nextRate);
      setPlaying(true);
      const utterance = new SpeechSynthesisUtterance(speechText);
      utterance.lang = locale;
      utterance.rate = nextRate;
      if (selectedVoice) utterance.voice = selectedVoice;
      utterance.onend = () => {
        setPlaying(false);
        onEnd?.();
      };
      utterance.onerror = () => {
        setPlaying(false);
        onError?.("Reference audio could not play in this browser.");
      };
      window.speechSynthesis.speak(utterance);
      return true;
    },
    [locale, muted, onEnd, onError, selectedVoice, text]
  );

  useEffect(() => stop, [stop]);

  return {
    voices,
    playing,
    rate,
    speak,
    stop,
    selectedVoiceName: selectedVoice?.name || "Browser default English voice",
    supported: Boolean(window.speechSynthesis),
  };
}
