import LearningHub from "./LearningHub";
import "../LearningDashboard.css";

/** The Courses page: the Learning Hub (tutorials, aptitude, interview questions). */
export default function CoursesHome({ onBack, onOpenAgent, onBuyCoins }: { onBack?: () => void; onOpenAgent?: (agentId: string) => void; onBuyCoins?: () => void }) {
  return (
    <div className="pv-page ld-page lh-page">
      <div className="pv-inner ld-inner">
        {onBack && <button className="hp-back" onClick={onBack}>← Back</button>}
        <LearningHub onOpenAgent={onOpenAgent} onBuyCoins={onBuyCoins} />
      </div>
    </div>
  );
}
