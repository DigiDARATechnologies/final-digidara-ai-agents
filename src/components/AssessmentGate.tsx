import { useEffect, useRef, useState } from "react";
import { previewAssessment, startAssessment, type AssessmentPreview } from "../lib/proctorApi";
import { formatWhen as when, resultText, ruleLines, type AssessmentLaunch } from "../lib/proctoring";
import "./Proctor.css";

interface Props {
  token: string;
  onClose: () => void;
  /** The attempt started: run its interview. */
  onStart: (launch: AssessmentLaunch) => void;
}

/**
 * What a learner sees on opening an organization's assessment link: the
 * test, its time window and rules, a camera check, and the consent to
 * proctoring. Starting it opens the interview in a new Mock Interview chat.
 */
export default function AssessmentGate({ token, onClose, onStart }: Props) {
  const [preview, setPreview] = useState<AssessmentPreview | null>(null);
  const [error, setError] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [starting, setStarting] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    let active = true;
    previewAssessment(token)
      .then((next) => { if (active) setPreview(next); })
      .catch((failure) => { if (active) setError(failure instanceof Error ? failure.message : "This assessment link could not be opened."); });
    return () => { active = false; };
  }, [token]);

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }
  useEffect(() => stopCamera, []);

  async function checkCamera() {
    setCameraError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser cannot use a camera. Use Chrome or Edge on a laptop.");
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 320 }, height: { ideal: 240 } }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraReady(true);
    } catch (failure) {
      const name = (failure as DOMException)?.name;
      setCameraError(name === "NotAllowedError"
        ? "Camera access was blocked. Allow the camera for this site (the camera icon in the address bar), then check again."
        : failure instanceof Error && failure.message ? failure.message : "The camera could not be started.");
    }
  }

  async function start() {
    if (!preview) return;
    setStarting(true);
    setError("");
    // Full screen needs this click, so it is asked for before anything is awaited.
    if (preview.proctoring.fullscreen && document.fullscreenEnabled && !document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => { /* The test asks again. */ });
    }
    try {
      const started = await startAssessment(token);
      stopCamera();
      const { config } = started.assessment;
      onStart({
        sessionId: started.id, title: started.assessment.title,
        config: { round_type: config.round_type, role_name: config.role_name, subject: config.subject, num_questions: config.num_questions, level: config.level },
      });
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The assessment could not be started.");
      setStarting(false);
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    }
  }

  const needsCamera = Boolean(preview?.proctoring.webcam);
  const config = preview?.config;
  const topic = config ? (config.round_type === "hr" ? "HR interview" : config.role_name ? `${config.role_name} interview` : `${config.subject} interview`) : "";
  const resuming = preview?.attempt?.status === "active";

  return (
    <div className="assess-backdrop" role="dialog" aria-modal="true" aria-labelledby="assess-title">
      <div className="assess-card">
        <span className="proctor-badge">Assessment</span>
        {!preview && !error && <p>Opening the assessment…</p>}
        {!preview && error && (
          <>
            <h2 id="assess-title">This link could not be opened</h2>
            <p className="proctor-error" role="alert">{error}</p>
            <div className="assess-actions"><button type="button" className="btn btn-outline" onClick={onClose}>Close</button></div>
          </>
        )}
        {preview && config && (
          <>
            <h2 id="assess-title">{preview.title}</h2>
            <p className="assess-org">From {preview.organization}</p>
            <div className="assess-facts">
              <div className="assess-fact"><span>Test</span><strong>{topic}</strong></div>
              <div className="assess-fact"><span>Questions</span><strong>{config.num_questions}</strong></div>
              <div className="assess-fact"><span>Level</span><strong>{config.level_label ?? config.level}</strong></div>
              {preview.closes_at && <div className="assess-fact"><span>Closes</span><strong>{when(preview.closes_at)}</strong></div>}
              {preview.window === "not_open" && preview.opens_at && <div className="assess-fact"><span>Opens</span><strong>{when(preview.opens_at)}</strong></div>}
            </div>

            {preview.attempt && preview.attempt.status !== "active" ? (
              <p className="proctor-privacy">
                You took this assessment {preview.attempt.started_at ? `on ${when(preview.attempt.started_at)}` : "earlier"}.
                {" "}Result: {resultText(preview.attempt.result)} · Integrity {preview.attempt.integrity}/100.
              </p>
            ) : null}

            {preview.can_start ? (
              <>
                <h3 style={{ margin: "0 0 6px", fontSize: 15 }}>Rules</h3>
                <ul className="proctor-rules">{ruleLines(preview.proctoring).map((line) => <li key={line}>{line}</li>)}</ul>
                <p className="proctor-privacy">
                  {preview.organization}&apos;s admins will see your score, the warnings and your camera photos.
                  Photos are deleted after 30 days. You can take this assessment once
                  {resuming ? "; you have already started it, so reopening it counts as a warning" : ""}.
                </p>
                {needsCamera && (
                  <div className="assess-camera">
                    <video ref={videoRef} autoPlay muted playsInline aria-label="Camera check" hidden={!cameraReady} />
                    {!cameraReady && <button type="button" className="btn btn-outline" onClick={() => void checkCamera()}>Check my camera</button>}
                    {cameraReady && <span>Camera is working. Make sure your face is clearly visible.</span>}
                  </div>
                )}
                {cameraError && <p className="proctor-error" role="alert">{cameraError}</p>}
                {error && <p className="proctor-error" role="alert">{error}</p>}
                <label className="proctor-agree">
                  <input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} />
                  <span>I agree to the rules and to proctoring, and to {preview.organization} seeing my result.</span>
                </label>
                <div className="assess-actions">
                  <button type="button" className="btn btn-outline" onClick={onClose}>Not now</button>
                  <button type="button" className="btn btn-primary" disabled={!agreed || starting || (needsCamera && !cameraReady)} onClick={() => void start()}>
                    {starting ? "Starting…" : resuming ? "Continue assessment" : "Start assessment"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="proctor-error" role="alert">{preview.reason}</p>
                <div className="assess-actions"><button type="button" className="btn btn-outline" onClick={onClose}>Close</button></div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
