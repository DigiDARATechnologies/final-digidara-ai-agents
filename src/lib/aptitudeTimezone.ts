/** Attach the browser's IANA timezone to test creation and report requests. */
export function aptitudeTimezonePayload(action: string, payload: Record<string, unknown>): Record<string, unknown> {
  if (action !== "create_test" && action !== "download_report") return payload;
  let timezone: string | undefined;
  try { timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || undefined; } catch { timezone = undefined; }
  // Chromium/ICU on some systems still exposes this legacy IANA alias.
  if (timezone === "Asia/Calcutta") timezone = "Asia/Kolkata";
  return { ...payload, timezone: payload.timezone || timezone };
}
