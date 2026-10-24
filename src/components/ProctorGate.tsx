import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  fetchProctorState, sendProctorEvents, sendProctorSnapshot, startProctoring,
  type ProctoredAgent, type ProctorEventKind, type ProctorSettings, type ProctorState,
} from "../lib/proctorApi";
import { forgetFreshSession, isFreshSession, ruleLines } from "../lib/proctoring";
import "./Proctor.css";

/** Practice sittings run every check (the server decides; this is what the consent screen lists). */
const PRACTICE_SETTINGS: ProctorSettings = { tab: true, fullscreen: true, copy_paste: true, webcam: true, face: true, max_warnings: 3 };
const FIRST_SNAPSHOT_MS = 5_000;
const SNAPSHOT_EVERY_MS = 45_000;
/** The same kind of copy/paste finding is sent at most this often. */
const REPEAT_MS = 3_000;
/** Focus changes right after starting (the browser settling into full screen) are not counted. */
const SETTLE_MS = 3_000;

interface Props {
  agentName: ProctoredAgent;
  /** What is proctored: the interview id, or "<submission>:<attempt>" for a viva. */
  refId: string;
  /** An assessment attempt already started (and agreed to) on the link's page. */
  sessionId?: string;
  /** What the test is called on the consent screen. */
  label: string;
  /** Too many warnings: end the interview or viva. */
  onTerminate: () => void;
  children: ReactNode;
}

function fullscreenSupported(): boolean {
  return typeof document !== "undefined" && Boolean(document.fullscreenEnabled && document.documentElement.requestFullscreen);
}

function requestFullscreen(): void {
  if (!fullscreenSupported() || document.fullscreenElement) return;
  document.documentElement.requestFullscreen().catch(() => { /* The overlay asks again. */ });
}

const VIDEO: MediaTrackConstraints = { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: "user" };

/** The camera, asked for together with the microphone the interview uses, so
 * no permission popup appears later (a popup takes focus from the page and
 * would look like leaving the test). Only the camera is kept open here. */
async function openCamera(): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser cannot use a camera. Use Chrome or Edge on a laptop.");
  try {
    try {
      const both = await navigator.mediaDevices.getUserMedia({ video: VIDEO, audio: true });
      both.getAudioTracks().forEach((track) => { track.stop(); both.removeTrack(track); });
      return both;
    } catch (error) {
      if ((error as DOMException)?.name !== "NotAllowedError") throw error;
      // Microphone refused: the camera alone is enough for proctoring (answers can be typed).
      return await navigator.mediaDevices.getUserMedia({ video: VIDEO, audio: false });
    }
  } catch (error) {
    const name = (error as DOMException)?.name;
    if (name === "NotAllowedError" || name === "SecurityError") throw new Error("Camera access was blocked. Allow the camera for this site (the camera icon in the address bar), then try again.");
    if (name === "NotFoundError" || name === "OverconstrainedError") throw new Error("No camera was found. Connect a camera to take this test.");
    if (name === "NotReadableError") throw new Error("Your camera is being used by another app. Close it and try again.");
    throw new Error("The camera could not be started. Please try again.");
  }
}

/**
 * Proctoring for a Hard/Professional mock interview or capstone viva, or an
 * assessment link: a consent screen first (nothing is watched or recorded
 * before the learner agrees), then full screen, the tab and copy/paste are
 * watched, the camera stays on with a photo about once a minute, and each
 * finding is sent to the server, which keeps the score and decides when too
 * many warnings end the test.
 */
export default function ProctorGate({ agentName, refId, sessionId, label, onTerminate, children }: Props) {
  const [phase, setPhase] = useState<"consent" | "starting" | "live">("consent");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState("");
  const [session, setSession] = useState<ProctorState | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(() => typeof document !== "undefined" && Boolean(document.fullscreenElement));
  const [cameraLost, setCameraLost] = useState(false);
  const [notice, setNotice] = useState("");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sessionRef = useRef<ProctorState | null>(null);
  const awayRef = useRef(false);
  const lastSentRef = useRef<Record<string, number>>({});
  const terminatedRef = useRef(false);
  const onTerminateRef = useRef(onTerminate);
  onTerminateRef.current = onTerminate;
  // An assessment attempt is started on the link's page, where the learner agreed.
  const presetRef = useRef(Boolean(sessionId && isFreshSession(sessionId)));

  const settings = session?.settings ?? PRACTICE_SETTINGS;

  const applyState = useCallback((next: ProctorState) => {
    const previous = sessionRef.current;
    sessionRef.current = next;
    setSession(next);
    if (next.terminated && !terminatedRef.current) {
      terminatedRef.current = true;
      onTerminateRef.current();
    } else if (previous && next.warnings > previous.warnings && !next.terminated) {
      setNotice(next.warnings_left > 0
        ? `Warning ${next.warnings} of ${next.max_warnings}. ${next.warnings_left} left before the test ends.`
        : "Final warning: one more and the test ends.");
    }
  }, []);

  const report = useCallback((kind: ProctorEventKind, detail = "") => {
    const current = sessionRef.current;
    if (!current || current.status !== "active") return;
    const now = Date.now();
    if (kind !== "focus_lost" && kind !== "fullscreen_exit" && now - (lastSentRef.current[kind] ?? 0) < REPEAT_MS) return;
    lastSentRef.current[kind] = now;
    sendProctorEvents(current.id, [{ kind, detail }]).then(applyState).catch(() => { /* Kept server-side next time. */ });
  }, [applyState]);

  const attachCamera = useCallback((stream: MediaStream) => {
    streamRef.current = stream;
    setCameraLost(false);
    if (videoRef.current) videoRef.current.srcObject = stream;
    stream.getVideoTracks().forEach((track) => {
      track.onended = () => {
        setCameraLost(true);
        report("camera_off", "The camera stopped.");
      };
    });
  }, [report]);

  async function start() {
    setError("");
    const wanted = sessionRef.current?.settings ?? (presetRef.current ? null : PRACTICE_SETTINGS);
    // Full screen needs this click, so it is asked for before anything is awaited.
    if (!wanted || wanted.fullscreen) requestFullscreen();
    setPhase("starting");
    try {
      const state = presetRef.current && sessionId
        ? await fetchProctorState(sessionId)
        : await startProctoring(agentName, refId);
      presetRef.current = false;
      if (sessionId) forgetFreshSession(sessionId);
      if (state.settings.webcam && !streamRef.current) attachCamera(await openCamera());
      if (!state.settings.fullscreen && document.fullscreenElement) document.exitFullscreen().catch(() => {});
      applyState(state);
      setPhase("live");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Proctoring could not start.");
      setPhase("consent");
    }
  }

  // An assessment attempt agreed on the link's page starts straight away;
  // one reopened later shows its own rules on the consent screen.
  useEffect(() => {
    if (presetRef.current) void start();
    else if (sessionId) {
      fetchProctorState(sessionId).then((state) => {
        if (!sessionRef.current) { sessionRef.current = state; setSession(state); }
      }).catch(() => { /* The practice rules are shown instead. */ });
    }
    // Only on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Watching the tab, full screen and copy/paste while live.
  useEffect(() => {
    if (phase !== "live") return;
    const liveAt = Date.now();
    const away = (why: string) => {
      if (awayRef.current || !settings.tab || Date.now() - liveAt < SETTLE_MS) return;
      awayRef.current = true;
      report("focus_lost", why);
    };
    const back = () => { awayRef.current = false; };
    const onVisibility = () => (document.hidden ? away("Switched to another tab or app.") : back());
    const onBlur = () => away("Clicked outside the test window.");
    const onFullscreen = () => {
      const active = Boolean(document.fullscreenElement);
      setIsFullscreen(active);
      if (!active && settings.fullscreen && fullscreenSupported()) report("fullscreen_exit", "Left full screen.");
    };
    const block = (kind: ProctorEventKind) => (event: Event) => {
      if (!settings.copy_paste) return;
      event.preventDefault();
      report(kind);
    };
    const onCopy = block("copy");
    const onCut = block("cut");
    const onPaste = block("paste");
    const onMenu = block("context_menu");
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", back);
    document.addEventListener("fullscreenchange", onFullscreen);
    document.addEventListener("copy", onCopy, true);
    document.addEventListener("cut", onCut, true);
    document.addEventListener("paste", onPaste, true);
    document.addEventListener("contextmenu", onMenu, true);
    setIsFullscreen(Boolean(document.fullscreenElement));
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", back);
      document.removeEventListener("fullscreenchange", onFullscreen);
      document.removeEventListener("copy", onCopy, true);
      document.removeEventListener("cut", onCut, true);
      document.removeEventListener("paste", onPaste, true);
      document.removeEventListener("contextmenu", onMenu, true);
    };
  }, [phase, settings.tab, settings.fullscreen, settings.copy_paste, report]);

  // A webcam photo about once a minute.
  useEffect(() => {
    if (phase !== "live" || !settings.webcam) return;
    const canvas = document.createElement("canvas");
    const snap = () => {
      const video = videoRef.current;
      const current = sessionRef.current;
      if (!video || !current || current.status !== "active" || video.readyState < 2 || !video.videoWidth) return;
      canvas.width = 320;
      canvas.height = Math.round(320 * (video.videoHeight / video.videoWidth)) || 240;
      canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
      sendProctorSnapshot(current.id, canvas.toDataURL("image/jpeg", 0.6)).then(applyState).catch(() => {});
    };
    const first = window.setTimeout(snap, FIRST_SNAPSHOT_MS);
    const every = window.setInterval(snap, SNAPSHOT_EVERY_MS);
    return () => { window.clearTimeout(first); window.clearInterval(every); };
  }, [phase, settings.webcam, applyState]);

  // The camera preview element appears after the stream: connect them.
  useEffect(() => {
    if (videoRef.current && streamRef.current && videoRef.current.srcObject !== streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  });

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 6_000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  // Leaving the test (it ended, or another chat was opened): camera off, full screen closed.
  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    streamRef.current = null;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  }, []);

  async function restartCamera() {
    try {
      attachCamera(await openCamera());
    } catch (failure) {
      setNotice(failure instanceof Error ? failure.message : "The camera could not be started.");
      report("camera_blocked", "The camera could not be turned back on.");
    }
  }

  if (phase !== "live") {
    const lines = ruleLines(settings);
    return (
      <div className="proctor-consent" role="dialog" aria-labelledby="proctor-consent-title">
        <span className="proctor-badge">Proctored test</span>
        <h3 id="proctor-consent-title">{label}</h3>
        <p className="proctor-lead">This test is proctored. Before you start, please read how it works.</p>
        <ul className="proctor-rules">{lines.map((line) => <li key={line}>{line}</li>)}</ul>
        <p className="proctor-privacy">
          Your camera photos and the warnings are kept for 30 days and are seen only by you, DigiDARA and,
          if you belong to an organization, its admins. Nothing is recorded until you agree below.
        </p>
        {error && <p className="proctor-error" role="alert">{error}</p>}
        {!presetRef.current && (
          <label className="proctor-agree">
            <input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} />
            <span>I agree to camera proctoring and the rules above.</span>
          </label>
        )}
        <button type="button" className="btn btn-primary" disabled={phase === "starting" || (!agreed && !presetRef.current)} onClick={() => void start()}>
          {phase === "starting" ? "Starting…" : settings.fullscreen ? "Start in full screen" : "Start test"}
        </button>
      </div>
    );
  }

  const ended = session?.terminated;
  const needFullscreen = settings.fullscreen && fullscreenSupported() && !isFullscreen && !ended;
  return (
    <div className="proctor-live">
      <div className="proctor-bar" aria-live="polite">
        <span className="proctor-dot" aria-hidden="true" />
        <span>Proctored</span>
        {session && <span className="proctor-meta">Warnings {session.warnings}/{session.max_warnings}</span>}
        {notice && <span className="proctor-notice" role="alert">{notice}</span>}
      </div>
      {ended
        ? <div className="proctor-ended" role="alert"><strong>The test has ended.</strong> There were too many warnings, so your answers so far were submitted.</div>
        : children}
      {settings.webcam && !ended && (
        <div className={`proctor-cam${cameraLost ? " lost" : ""}`}>
          <video ref={videoRef} autoPlay muted playsInline aria-label="Your camera" />
          {cameraLost && <button type="button" className="btn btn-primary btn-sm" onClick={() => void restartCamera()}>Turn camera on</button>}
        </div>
      )}
      {needFullscreen && (
        <div className="proctor-overlay" role="dialog" aria-modal="true" aria-labelledby="proctor-fs-title">
          <div className="proctor-overlay-card">
            <h3 id="proctor-fs-title">Return to full screen</h3>
            <p>This test runs in full screen. Leaving it counts as a warning.</p>
            {session && <p className="proctor-meta">Warnings so far: {session.warnings} of {session.max_warnings}</p>}
            <button type="button" className="btn btn-primary" onClick={requestFullscreen}>Continue in full screen</button>
          </div>
        </div>
      )}
    </div>
  );
}
