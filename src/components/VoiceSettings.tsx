import { useState } from "react";
import { previewVoice, stopSpeaking } from "../lib/voiceEngine";
import {
  VOICE_LANGUAGES,
  VOICE_PERSONAS,
  loadVoicePrefs,
  saveVoicePrefs,
  type VoicePrefs,
} from "../lib/voicePrefs";

/** Settings > General > Voice: how the agents sound. Kept on this device. */
export default function VoiceSettings() {
  const [prefs, setPrefs] = useState<VoicePrefs>(() => loadVoicePrefs());
  const [previewing, setPreviewing] = useState(false);

  function update(change: Partial<VoicePrefs>) {
    const next = { ...prefs, ...change };
    setPrefs(next);
    saveVoicePrefs(next);
  }

  async function preview() {
    if (previewing) {
      stopSpeaking();
      setPreviewing(false);
      return;
    }
    setPreviewing(true);
    await previewVoice({ onEnd: () => setPreviewing(false) });
  }

  return (
    <div className="settings-section voice-settings">
      <div className="setting-row">
        <div><b>Speak replies</b><p>Agents can read their questions and answers aloud.</p></div>
        <label className="switch">
          <input type="checkbox" checked={prefs.enabled} onChange={(e) => update({ enabled: e.target.checked })} />
          <span className="slider" />
        </label>
      </div>
      <div className="setting-row">
        <div><b>Natural voice</b><p>A warm, human-like voice. Off uses your device's built-in voice.</p></div>
        <label className="switch">
          <input type="checkbox" checked={prefs.mode === "natural"} disabled={!prefs.enabled}
            onChange={(e) => update({ mode: e.target.checked ? "natural" : "device" })} />
          <span className="slider" />
        </label>
      </div>
      <div className="setting-row voice-personas-row">
        <div><b>Voice</b><p>Choose who speaks to you.</p></div>
        <div className="voice-personas" role="radiogroup" aria-label="Voice">
          {VOICE_PERSONAS.map((persona) => (
            <button key={persona.id} type="button" role="radio" aria-checked={prefs.persona === persona.id}
              disabled={!prefs.enabled || prefs.mode !== "natural"}
              className={prefs.persona === persona.id ? "active" : ""} onClick={() => update({ persona: persona.id })}>
              <b>{persona.label}</b><span>{persona.description}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="setting-row">
        <div><b>Language</b><p>Tamil, English, or follow each reply. Voice input uses it too.</p></div>
        <select className="voice-select" value={prefs.language} disabled={!prefs.enabled}
          onChange={(e) => update({ language: e.target.value as VoicePrefs["language"] })}>
          {VOICE_LANGUAGES.map((language) => <option key={language.id} value={language.id}>{language.label}</option>)}
        </select>
      </div>
      <div className="setting-row">
        <div><b>Speed</b><p>{prefs.speed.toFixed(2)}×</p></div>
        <input className="voice-speed" type="range" min={0.8} max={1.3} step={0.05} value={prefs.speed} disabled={!prefs.enabled}
          aria-label="Speech speed" onChange={(e) => update({ speed: Number(e.target.value) })} />
      </div>
      <div className="setting-row">
        <div><b>Try it</b><p>Hear the voice with your settings.</p></div>
        <button type="button" className="btn btn-outline" onClick={() => void preview()}>
          {previewing ? "Stop" : "Preview"}
        </button>
      </div>
    </div>
  );
}
