/** Bulk member import for organizations: one learner per line as
 * "name, email, roll number" (comma, tab or semicolon separated, any column
 * order as long as the email has an @). A "name, email, ..." header line is
 * skipped. Kept apart from learnerApi so it has no network dependencies. */
export function parseMemberLines(text: string): { name: string; email: string; external_id?: string }[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.split(/[,\t;]/).map((cell) => cell.trim()))
    .filter((cells) => cells.some(Boolean))
    .map((cells) => {
      const emailIndex = cells.findIndex((cell) => cell.includes("@"));
      const email = emailIndex >= 0 ? cells[emailIndex] : "";
      const rest = cells.filter((_, index) => index !== emailIndex);
      return { name: rest[0] ?? "", email, external_id: rest[1] || undefined };
    })
    .filter((row) => row.email || !/^name$/i.test(row.name));
}
