/**
 * Dates and times in the learner's chosen time zone and date format
 * (Settings > General). App.tsx calls setDatePrefs whenever they change;
 * everything else just calls formatDate / formatDateTime / formatTime.
 */
import type { DateFormat } from "./accountApi";

let zone: string | undefined;
let format: DateFormat = "auto";

/** `timeZone` "" follows the device. An unknown zone falls back to the device too. */
export function setDatePrefs(timeZone: string, dateFormat: DateFormat): void {
  zone = timeZone && isValidTimeZone(timeZone) ? timeZone : undefined;
  format = dateFormat;
}

export function isValidTimeZone(timeZone: string): boolean {
  try {
    new Intl.DateTimeFormat("en", { timeZone });
    return true;
  } catch {
    return false;
  }
}

/** The device's own zone, e.g. "Asia/Kolkata". */
export function deviceTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/** Every zone the browser knows, for the Settings list. */
export function allTimeZones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  try {
    const zones = intl.supportedValuesOf?.("timeZone");
    if (zones?.length) return zones;
  } catch {
    /* older browser */
  }
  return ["Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Europe/London", "Europe/Berlin", "America/New_York", "America/Los_Angeles", "Australia/Sydney", "UTC"];
}

function toDate(value: Date | number | string): Date {
  return value instanceof Date ? value : new Date(value);
}

function parts(date: Date): { day: string; month: string; year: string } {
  const found: Record<string, string> = {};
  for (const part of new Intl.DateTimeFormat("en-GB", { timeZone: zone, day: "2-digit", month: "2-digit", year: "numeric" }).formatToParts(date)) {
    found[part.type] = part.value;
  }
  return { day: found.day ?? "", month: found.month ?? "", year: found.year ?? "" };
}

export function formatDate(value: Date | number | string): string {
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return "";
  if (format === "auto") return date.toLocaleDateString([], { timeZone: zone });
  const { day, month, year } = parts(date);
  return format === "dmy" ? `${day}/${month}/${year}` : format === "mdy" ? `${month}/${day}/${year}` : `${year}-${month}-${day}`;
}

export function formatTime(value: Date | number | string): string {
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { timeZone: zone, hour: "2-digit", minute: "2-digit" });
}

export function formatDateTime(value: Date | number | string): string {
  const date = toDate(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${formatDate(date)}, ${formatTime(date)}`;
}

/** "YYYY-MM-DD" of a moment in the chosen zone (for date pickers). */
export function isoDay(value: Date | number | string): string {
  const { day, month, year } = parts(toDate(value));
  return `${year}-${month}-${day}`;
}
