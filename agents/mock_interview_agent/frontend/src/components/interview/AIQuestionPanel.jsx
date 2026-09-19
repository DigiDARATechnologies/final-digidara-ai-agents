import { INTERVIEW_ICONS } from "../../utils/icons";
const InterviewerIcon = INTERVIEW_ICONS.interviewer;
export default function AIQuestionPanel({ question, isFrequentlyAsked, voiceState, voiceStateLabel }) {
  return <section className={`interview-panel ai-panel voice-state-${voiceState}`}><div className="panel-title-row"><div className="ai-avatar" aria-hidden="true"><InterviewerIcon size={24} strokeWidth={2} /></div><div><p className="eyebrow">AI Interviewer</p><h3>{voiceStateLabel}</h3></div></div>{question ? <>{isFrequentlyAsked && <span className="frequently-asked-badge" aria-label="Frequently asked interview question">⭐ Frequently asked</span>}<p className="question-text">{question}</p></> : <p className="subtle">Loading your first question...</p>}</section>;
}
