/**
 * The device voice used only when the DigiDARA voice cannot be reached: an
 * Indian voice (Indian English, or Tamil for Tamil text), preferring a
 * woman's voice so it stays as close as possible to Nila on every device.
 */
export function pickIndianVoice(lang: "ta" | "en" = "en"): SpeechSynthesisVoice | null {
  const voices = (typeof window !== "undefined" ? window.speechSynthesis?.getVoices() : undefined) ?? [];
  const tag = (v: SpeechSynthesisVoice) => (v.lang || "").toLowerCase().replace("_", "-");
  if (lang === "ta") return voices.find((v) => tag(v).startsWith("ta")) ?? null;
  const indian = voices.filter((v) => tag(v) === "en-in");
  const preferred = [/Neerja/i, /Heera/i, /Google.*India/i, /Veena/i, /female/i];
  for (const pattern of preferred) {
    const voice = indian.find((v) => pattern.test(v.name));
    if (voice) return voice;
  }
  return indian[0] ?? null;
}
