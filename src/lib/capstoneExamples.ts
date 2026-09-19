import type { ChatOption } from "../types";

/** Static reference files for the Capstone agent: a filled-in report and the
 * matching source zip, built once by scripts/build_capstone_examples.py and
 * served from public/capstone-examples/. They are the same for everyone and
 * are never regenerated per student. */
export const CAPSTONE_EXAMPLE_FILES = [
  {
    href: "/capstone-examples/capstone-example-report.docx",
    download: "capstone-example-report.docx",
    label: "Download example report (.docx)",
    description: "A filled-in report: Problem Statement, Approach, Code, Output Screenshots, Conclusion.",
  },
  {
    href: "/capstone-examples/capstone-example-project.zip",
    download: "capstone-example-project.zip",
    label: "Download example project (.zip)",
    description: "The matching source folder: src/, tests/, README, requirements and output_screenshots/.",
  },
] as const;

export const CAPSTONE_EXAMPLE_OPTIONS: ChatOption[] = CAPSTONE_EXAMPLE_FILES.map((file) => ({
  value: `example:${file.download}`,
  label: file.label,
  description: file.description,
  href: file.href,
  download: file.download,
}));
