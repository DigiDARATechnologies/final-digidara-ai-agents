import JSZip from "jszip";
import { parseCsv, parseLinkedInExport } from "../../src/lib/linkedinExport";

describe("parseCsv", () => {
  test("handles quoted fields, embedded commas, escaped quotes and newlines", () => {
    const csv = 'Name,Title\n"Doe, Jane","VP of ""Growth"""\nAcme,"Line one\nLine two"';
    expect(parseCsv(csv)).toEqual([
      { Name: "Doe, Jane", Title: 'VP of "Growth"' },
      { Name: "Acme", Title: "Line one\nLine two" },
    ]);
  });

  test("strips a UTF-8 BOM and ignores blank rows", () => {
    const csv = "﻿Name,Skill\n\nAsha,SQL\n";
    expect(parseCsv(csv)).toEqual([{ Name: "Asha", Skill: "SQL" }]);
  });

  test("an empty file parses to no rows", () => {
    expect(parseCsv("")).toEqual([]);
  });
});

async function zipFile(entries: Record<string, string>): Promise<File> {
  const zip = new JSZip();
  for (const [name, content] of Object.entries(entries)) zip.file(name, content);
  const blob = await zip.generateAsync({ type: "blob" });
  return new File([blob], "Basic_LinkedInDataExport.zip", { type: "application/zip" });
}

describe("parseLinkedInExport", () => {
  test("reads profile, positions, education, skills and certifications into the resume shape", async () => {
    const file = await zipFile({
      "Profile.csv": 'First Name,Last Name,Headline,Summary\nAsha,Rao,"Data Analyst","Loves clean dashboards."',
      "Positions.csv": 'Company Name,Title,Description,Started On,Finished On\nAcme,Data Analyst,"Built dashboards",Jan 2022,Present',
      "Education.csv": "School Name,Degree Name,Field Of Study\nState University,BSc,Statistics",
      "Skills.csv": "Name\nSQL\nPython",
      "Certifications.csv": "Name,Authority,Url\nAWS Certified,Amazon,https://aws.example/cert",
    });

    const { input, counts } = await parseLinkedInExport(file);

    expect(input.title).toBe("Asha Rao Resume");
    expect(input.target_role).toBe("Data Analyst");
    expect(input.summary).toBe("Loves clean dashboards.");
    expect(input.experience).toEqual([{ company: "Acme", role: "Data Analyst", raw_input: "Data Analyst at Acme\nJan 2022 - Present\nBuilt dashboards" }]);
    expect(input.education).toEqual([{ school: "State University", degree: "BSc", field: "Statistics" }]);
    expect(input.skills).toEqual([{ skill_name: "SQL" }, { skill_name: "Python" }]);
    expect(input.certifications).toEqual([{ name: "AWS Certified", issuer: "Amazon", credential_url: "https://aws.example/cert" }]);
    expect(counts).toEqual({ experience: 1, education: 1, skills: 2, certifications: 1 });
  });

  test("finds the CSVs regardless of folder nesting or case", async () => {
    const file = await zipFile({ "Basic Export/profile.CSV": "First Name,Last Name\nAsha,Rao" });
    const { input } = await parseLinkedInExport(file);
    expect(input.title).toBe("Asha Rao Resume");
  });

  test("a ZIP with none of the expected files yields nothing, not a crash", async () => {
    const file = await zipFile({ "readme.txt": "hello" });
    const { input, counts } = await parseLinkedInExport(file);
    expect(input).toEqual({ title: undefined, target_role: undefined, summary: undefined, experience: undefined, education: undefined, skills: undefined, certifications: undefined });
    expect(counts).toEqual({ experience: 0, education: 0, skills: 0, certifications: 0 });
  });
});
