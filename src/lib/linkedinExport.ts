import JSZip from "jszip";
import type { ResumeCreateInput } from "./resumeBuilderApi";

/** LinkedIn's own "Get a copy of your data" export (Settings & Privacy > Data
 * privacy) -- a ZIP of CSVs the member downloads themselves. This is the
 * legitimate way to bring LinkedIn content in: LinkedIn's own feature, the
 * member's own data, no scraping and no third-party data broker involved.
 * (There is no official real-time "fetch my profile" API for third-party apps --
 * see the resume canvas's own start screen for why.) */

/** A tiny RFC4180-ish CSV parser: handles quoted fields, escaped quotes ("")
 * and commas/newlines inside quotes. LinkedIn's export CSVs are small (well
 * under a thousand rows), so simplicity over streaming performance is fine. */
export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  const pushField = () => { row.push(field); field = ""; };
  const pushRow = () => { pushField(); rows.push(row); row = []; };
  const clean = text.replace(/^﻿/, "").replace(/\r\n/g, "\n");
  for (let i = 0; i < clean.length; i++) {
    const char = clean[i];
    if (inQuotes) {
      if (char === '"') {
        if (clean[i + 1] === '"') { field += '"'; i++; } else { inQuotes = false; }
      } else field += char;
    } else if (char === '"') inQuotes = true;
    else if (char === ",") pushField();
    else if (char === "\n") pushRow();
    else field += char;
  }
  if (field || row.length) pushRow();
  const [header, ...body] = rows.filter((cols) => cols.some((cell) => cell.trim() !== ""));
  if (!header) return [];
  return body.map((cols) => Object.fromEntries(header.map((key, index) => [key.trim(), (cols[index] ?? "").trim()])));
}

function findEntry(zip: JSZip, ...names: string[]): JSZip.JSZipObject | undefined {
  const wanted = new Set(names.map((name) => name.toLowerCase()));
  return Object.values(zip.files).find((entry) => {
    const base = entry.name.split("/").pop() || "";
    return wanted.has(base.toLowerCase());
  });
}

async function readCsv(zip: JSZip, ...names: string[]): Promise<Record<string, string>[]> {
  const entry = findEntry(zip, ...names);
  if (!entry) return [];
  return parseCsv(await entry.async("string"));
}

function cell(row: Record<string, string>, ...keys: string[]): string {
  for (const key of keys) if (row[key]) return row[key];
  // LinkedIn has changed a header's spelling/case between export versions before --
  // fall back to a normalized match so a minor rename doesn't silently drop the field.
  const normalized = new Map(Object.entries(row).map(([k, v]) => [k.toLowerCase().replace(/[^a-z]/g, ""), v]));
  for (const key of keys) {
    const value = normalized.get(key.toLowerCase().replace(/[^a-z]/g, ""));
    if (value) return value;
  }
  return "";
}

export interface LinkedInImportResult {
  input: Partial<ResumeCreateInput>;
  /** Counts of what was actually found, so the UI can say what came in. */
  counts: { experience: number; education: number; skills: number; certifications: number };
}

/** Reads a LinkedIn data-export ZIP into the same shape createResume() expects.
 * Dates are kept as free text in `raw_input` rather than parsed into start/end
 * fields -- LinkedIn's date formatting has varied across export versions, and a
 * failed date parse must never break the whole import over one field. */
export async function parseLinkedInExport(file: File): Promise<LinkedInImportResult> {
  const zip = await JSZip.loadAsync(file);

  const profileRows = await readCsv(zip, "Profile.csv");
  const profile = profileRows[0] ?? {};
  const firstName = cell(profile, "First Name");
  const lastName = cell(profile, "Last Name");
  const headline = cell(profile, "Headline");
  const summary = cell(profile, "Summary");

  const positions = await readCsv(zip, "Positions.csv");
  const experience = positions.map((row) => {
    const company = cell(row, "Company Name", "Company");
    const title = cell(row, "Title");
    const started = cell(row, "Started On", "Start Date");
    const finished = cell(row, "Finished On", "End Date");
    const description = cell(row, "Description");
    const period = [started, finished].filter(Boolean).join(" - ");
    return {
      company: company || "Company", role: title || "Role",
      raw_input: [title && company ? `${title} at ${company}` : title || company, period, description].filter(Boolean).join("\n"),
    };
  });

  const educationRows = await readCsv(zip, "Education.csv");
  const education = educationRows.map((row) => ({
    school: cell(row, "School Name", "School") || "School",
    degree: cell(row, "Degree Name", "Degree"),
    field: cell(row, "Field Of Study"),
  }));

  const skillRows = await readCsv(zip, "Skills.csv");
  const skills = skillRows.map((row) => ({ skill_name: cell(row, "Name") })).filter((skill) => skill.skill_name);

  const certificationRows = await readCsv(zip, "Certifications.csv");
  const certifications = certificationRows.map((row) => ({
    name: cell(row, "Name") || "Certification",
    issuer: cell(row, "Authority", "Issuing Organization"),
    credential_url: cell(row, "Url"),
  })).filter((certification) => certification.name);

  const title = [firstName, lastName].filter(Boolean).join(" ").trim();
  return {
    input: {
      title: title ? `${title} Resume` : undefined,
      target_role: headline || undefined,
      summary: summary || undefined,
      experience: experience.length ? experience : undefined,
      education: education.length ? education : undefined,
      skills: skills.length ? skills : undefined,
      certifications: certifications.length ? certifications : undefined,
    },
    counts: { experience: experience.length, education: education.length, skills: skills.length, certifications: certifications.length },
  };
}

export function isLikelyLinkedInExport(file: File): boolean {
  return file.name.toLowerCase().endsWith(".zip");
}
