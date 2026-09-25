import type { ChatOption } from "../types";

/** Static reference files for the Capstone agent: a filled-in report (a PDF,
 * so it reads as a reference rather than a template to edit) and the matching
 * source zip, built once by scripts/build_capstone_examples.py and served from
 * public/capstone-examples/. They are the same for everyone and are never
 * regenerated per student. The student's own report is still a .docx. */
export const CAPSTONE_EXAMPLE_FILES = [
  {
    href: "/capstone-examples/capstone-example-report.pdf",
    download: "capstone-example-report.pdf",
    label: "Download example report (.pdf)",
    description: "A filled-in report with the three sections you need: Problem Statement, Approach, Conclusion.",
  },
  {
    href: "/capstone-examples/capstone-example-project.zip",
    download: "capstone-example-project.zip",
    label: "Download example project (.zip)",
    description: "The matching project: src/, tests/, README, requirements and output_screenshots/ (the screenshots go in the zip, not the report).",
  },
] as const;

export const CAPSTONE_EXAMPLE_OPTIONS: ChatOption[] = CAPSTONE_EXAMPLE_FILES.map((file) => ({
  value: `example:${file.download}`,
  label: file.label,
  description: file.description,
  href: file.href,
  download: file.download,
}));
