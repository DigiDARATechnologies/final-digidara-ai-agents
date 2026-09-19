export const AVATAR_COLORS = ["#4dd8c8", "#f2a65a", "#f27a7a", "#7c8cff", "#9f7aea", "#3fbf7f"];

export function getInitials(name, email) {
  const source = (name || email || "Student").trim();
  const words = source.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
}
