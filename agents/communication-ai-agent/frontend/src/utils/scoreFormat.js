export function scoreToTen(score) {
  if (score == null || score === "") return null;
  const value = Number(score);
  if (Number.isNaN(value)) return null;
  const normalized = value > 10 ? value / 10 : value;
  return Math.max(0, Math.min(normalized, 10));
}

export function formatScore10(score, empty = "-") {
  const value = scoreToTen(score);
  return value == null ? empty : `${value.toFixed(1)} / 10`;
}

export function formatScoreNumber(score, empty = "-") {
  const value = scoreToTen(score);
  return value == null ? empty : value.toFixed(1);
}
