import type { ChatOption } from "../types";

/** Static reference files for the Capstone agent: a filled-in report (a PDF,
 * so it reads as a reference rather than a template to edit) and the matching
 * project zip, built once by scripts/build_capstone_examples.py and served from
 * public/capstone-examples/. They are the same for everyone and are never
 * regenerated per student. The student's own report is still a .docx.
 *
 * Digital Marketing and Prompt Engineering projects are not programs, so they
 * get their own pair (a campaign with a landing page; a tested prompt pack)
 * instead of the Python example. Every other course gets the code example. */
export type CapstoneExampleTrack = "code" | "digital-marketing" | "prompt-engineering";

export interface CapstoneExampleFile {
  href: string;
  download: string;
  label: string;
  description: string;
}

const TRACK_FILES: Record<CapstoneExampleTrack, readonly CapstoneExampleFile[]> = {
  code: [
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
  ],
  "digital-marketing": [
    {
      href: "/capstone-examples/capstone-example-report-digital-marketing.pdf",
      download: "capstone-example-report-digital-marketing.pdf",
      label: "Download example report (.pdf)",
      description: "A filled-in campaign report: Problem Statement, Approach (keywords, flyer, landing page, tracking, ads) and Conclusion with results.",
    },
    {
      href: "/capstone-examples/capstone-example-project-digital-marketing.zip",
      download: "capstone-example-project-digital-marketing.zip",
      label: "Download example project (.zip)",
      description: "The matching campaign: landing page in src/, flyer, keyword plan, ad copy, UTM links, results, and output_screenshots/ (page, flyer, Google Ads, GA4).",
    },
  ],
  "prompt-engineering": [
    {
      href: "/capstone-examples/capstone-example-report-prompt-engineering.pdf",
      download: "capstone-example-report-prompt-engineering.pdf",
      label: "Download example report (.pdf)",
      description: "A filled-in report: Problem Statement, Approach (test set, checks, prompt versions) and Conclusion with the scores.",
    },
    {
      href: "/capstone-examples/capstone-example-project-prompt-engineering.zip",
      download: "capstone-example-project-prompt-engineering.zip",
      label: "Download example project (.zip)",
      description: "The matching project: prompt versions in src/prompts/, test cases, saved outputs, the evaluation script, results and output_screenshots/.",
    },
  ],
};

const DIGITAL_MARKETING = /\b(digital marketing|marketing|seo|sem|ppc|google ads|social media|ad campaign|campaign|branding|content marketing|email marketing|google analytics|ga4)\b/i;
const PROMPT_ENGINEERING = /\b(prompt engineering|prompt engineer|prompts?|prompting)\b/i;

function trackOf(text: string): CapstoneExampleTrack | null {
  if (PROMPT_ENGINEERING.test(text)) return "prompt-engineering";
  if (DIGITAL_MARKETING.test(text)) return "digital-marketing";
  return null;
}

/** The track for a project. `focus` is what the student asked for (their
 * course or role) and decides it; the topic is only looked at when there is
 * no focus, so a Python student's "SEO checker tool" still gets the code
 * example. */
export function capstoneExampleTrack(focus?: string | null, topic?: string | null): CapstoneExampleTrack {
  if (focus && focus.trim()) return trackOf(focus) ?? "code";
  return (topic && trackOf(topic)) || "code";
}

export function capstoneExampleFiles(track: CapstoneExampleTrack = "code"): readonly CapstoneExampleFile[] {
  return TRACK_FILES[track];
}

export function capstoneExampleOptions(track: CapstoneExampleTrack = "code"): ChatOption[] {
  return TRACK_FILES[track].map((file) => ({
    value: `example:${file.download}`,
    label: file.label,
    description: file.description,
    href: file.href,
    download: file.download,
  }));
}

/** The code example, for callers that do not know the project's track. */
export const CAPSTONE_EXAMPLE_FILES = TRACK_FILES.code;
export const CAPSTONE_EXAMPLE_OPTIONS: ChatOption[] = capstoneExampleOptions("code");
