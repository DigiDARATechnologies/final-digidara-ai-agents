import DailyChallengeCard from "./DailyChallengeCard.jsx";
import MinimalPairsCard from "./MinimalPairsCard.jsx";
import SentencePracticeCard from "./SentencePracticeCard.jsx";
import WordPracticeCard from "./WordPracticeCard.jsx";

export default function PronunciationItemCard({ item, currentLine = 0 }) {
  if (!item) return null;
  if (item.practice_mode === "daily" || item.practice_mode === "daily_challenge") {
    return <DailyChallengeCard item={item} currentLine={currentLine} />;
  }
  if (item.practice_mode === "minimal_pairs") {
    return <MinimalPairsCard item={item} />;
  }
  if (item.practice_mode === "word" || item.item_type === "word") {
    return <WordPracticeCard item={item} />;
  }
  return <SentencePracticeCard item={item} />;
}
