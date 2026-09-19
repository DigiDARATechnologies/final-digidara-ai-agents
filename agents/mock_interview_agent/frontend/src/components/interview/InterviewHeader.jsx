export default function InterviewHeader({ realQuestionIndex, totalQuestions, timeLeft, progressPct, isExiting, onExit }) {
  return <>
    <header className="live-interview-header"><div><p className="eyebrow">Live voice interview</p><h2>AI Mock Interview</h2><div className="interview-session-meta" aria-label="Interview session details"><span>Voice round</span><span>Adaptive question flow</span><span>Question {realQuestionIndex} of {totalQuestions}</span></div></div><div className="interview-header-metrics"><div><span>Progress</span><strong>Question {realQuestionIndex} of {totalQuestions}</strong></div><div className="timer-card"><span>Remaining</span><strong className={`timer ${timeLeft <= 15 ? "timer-warn" : ""}`}>{timeLeft}s</strong></div><button className="exit-btn" onClick={onExit} disabled={isExiting} aria-label="Exit interview">{isExiting ? "Exiting..." : "Exit Interview"}</button></div></header>
    <div className="progress-track"><div className="progress-fill" style={{ width: `${progressPct}%` }} /></div>
  </>;
}
