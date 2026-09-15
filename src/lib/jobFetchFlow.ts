import type { ChatOption, User } from "../types";
import {
  ensureJobFetchProfile,
  getJobFeed,
  getJobFetchProfile,
  jobFetchAction,
  updateJobFetchProfile,
  uploadJobFetchResume,
  type JobFeedItem,
} from "./jobFetchApi";

export type JobFetchStep =
  | "collecting_name"
  | "collecting_skills"
  | "collecting_titles"
  | "collecting_locations"
  | "collecting_work_mode"
  | "collecting_experience"
  | "collecting_resume"
  | "browsing";

export interface JobFetchFlowMessage {
  text: string;
  options?: ChatOption[];
}

export interface JobFetchFlowState {
  step: JobFetchStep;
  fullName: string;
  skills: string[];
  preferredTitles: string[];
  preferredLocations: string[];
  preferredWorkMode: string;
  planTier: string;
  resumeOriginalName?: string;
  feed: JobFeedItem[];
  selectedJobId?: number;
}

const WORK_MODE_OPTIONS: ChatOption[] = [
  { label: "Remote", value: "remote" },
  { label: "Hybrid", value: "hybrid" },
  { label: "Onsite", value: "onsite" },
  // Option clicks flow through the shared chat sender, which intentionally
  // rejects an empty message. Keep a non-empty UI action and translate it
  // back to the empty (unrestricted) persisted work-mode value below.
  { label: "Any", value: "any" },
];

export function safeJobApplyUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function splitList(text: string): string[] {
  return text.split(/[,;\n]/).map((item) => item.trim()).filter(Boolean).slice(0, 20);
}

function createInitialState(): JobFetchFlowState {
  return {
    step: "collecting_name",
    fullName: "",
    skills: [],
    preferredTitles: [],
    preferredLocations: [],
    preferredWorkMode: "",
    planTier: "free",
    feed: [],
  };
}

function feedMessage(feed: JobFeedItem[], planTier: string, intro: string): JobFetchFlowMessage {
  if (!feed.length) {
    return { text: `${intro}\n\nNo matching jobs yet — try broader skills/titles, or check back soon as new postings are collected.` };
  }
  const top = feed.slice(0, 10);
  const lines = top.map(
    (job, index) =>
      `${index + 1}. ${job.title} @ ${job.company}${job.location ? ` (${job.location})` : ""} — match ${job.match_score}%`,
  );
  const tierNote = planTier === "free" ? "\n\n(Free plan — showing your top matches. Upgrade for the full feed.)" : "";
  return {
    text: `${intro}\n\n${lines.join("\n")}${tierNote}\n\nPick a job to view details, save it, or apply.`,
    options: top.map((job) => ({ label: `${job.title} @ ${job.company}`, value: `detail:${job.id}`, description: `Match ${job.match_score}%` })),
  };
}

function jobDetailMessage(job: JobFeedItem, feed: JobFeedItem[]): JobFetchFlowMessage {
  const lines = [
    `${job.title} @ ${job.company}`,
    job.location ? `Location: ${job.location}` : null,
    job.work_mode ? `Work mode: ${job.work_mode}` : null,
    job.skills.length ? `Skills: ${job.skills.join(", ")}` : null,
    `Match: ${job.match_score}% — ${job.match_reasons.join("; ")}`,
    job.description ? `\n${job.description.slice(0, 600)}` : null,
    `\nApply here: ${job.apply_url}`,
  ].filter(Boolean);
  // "open:" is a client-side-only convention App.tsx intercepts to open the
  // real apply page in a new tab, instead of sending it as a chat turn —
  // this is the one-click fix for the apply link previously being inert text.
  const options: ChatOption[] = [
    { label: "Apply now ↗", value: `open:${job.apply_url}` },
    { label: job.is_saved ? "Unsave" : "Save", value: job.is_saved ? `unsave:${job.id}` : `save:${job.id}` },
    { label: job.application_status === "applied" ? "Applied ✓ (mark again)" : "Mark as applied", value: `apply:${job.id}` },
    // Not a match for you — removes it from this feed. Reversible from the
    // dashboard's "Hidden jobs" section (Unhide), which is the only other
    // place a hidden job is ever listed again.
    { label: "Not interested (hide)", value: `hide:${job.id}` },
  ];
  // Lets the learner move through every match one at a time without
  // detouring back to the full list between each one.
  const currentIndex = feed.findIndex((item) => item.id === job.id);
  if (currentIndex >= 0 && currentIndex < feed.length - 1) {
    options.push({ label: "Next match →", value: "next" });
  }
  options.push({ label: "Back to list", value: "back" });
  return { text: lines.join("\n"), options };
}

async function loadFeed(state: JobFetchFlowState, query: Record<string, unknown> = {}) {
  const result = await getJobFeed(query as any);
  return { ...state, step: "browsing" as const, feed: result.jobs, planTier: result.plan_tier };
}

export async function openJobFetchChat(user: User): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  const base = createInitialState();
  try {
    const bridged = await ensureJobFetchProfile();
    if (bridged.profile_completed) {
      const profile = await getJobFetchProfile();
      const withFeed = await loadFeed({
        ...base,
        fullName: profile.full_name || user.name,
        skills: profile.skills,
        preferredTitles: profile.preferred_titles,
        preferredLocations: profile.preferred_locations,
        preferredWorkMode: profile.preferred_work_mode,
        resumeOriginalName: profile.resume_original_name || undefined,
        planTier: profile.plan_tier,
      });
      return { state: withFeed, messages: [feedMessage(withFeed.feed, withFeed.planTier, `Welcome back, ${(profile.full_name || user.name).split(" ")[0]}! Here's your latest job feed.`)] };
    }
    return {
      // Login name is often just a nickname or short form — collecting a
      // proper full name here is what actually goes on a job application.
      state: { ...base, planTier: bridged.plan_tier },
      messages: [{ text: `Hi ${user.name.split(" ")[0]}! Let's build your job profile. What's your full name? (this is what goes on your applications)` }],
    };
  } catch (error) {
    return { state: base, messages: [{ text: `I could not connect to the Job Fetching Agent: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }] };
  }
}

async function saveProfileAndShowFeed(state: JobFetchFlowState): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  try {
    await updateJobFetchProfile({
      full_name: state.fullName,
      skills: state.skills,
      preferred_titles: state.preferredTitles,
      preferred_locations: state.preferredLocations,
      preferred_work_mode: state.preferredWorkMode || undefined,
    });
    const withFeed = await loadFeed(state);
    return { state: withFeed, messages: [feedMessage(withFeed.feed, withFeed.planTier, "Profile saved! Here are your matched jobs.")] };
  } catch (error) {
    return { state, messages: [{ text: `I could not save your profile: ${(error as Error).message}. Try again.` }] };
  }
}

/** Called from App.tsx's attach handler when the user drops a file while on
 * `collecting_resume` — mirrors resumeBuilderFlow.ts's single-file import
 * pattern. Upload failure doesn't block the rest of onboarding: the resume
 * is optional, so a failed upload just re-prompts rather than getting the
 * user stuck. */
export async function submitJobFetchResume(
  state: JobFetchFlowState,
  file: File,
): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  if (state.step !== "collecting_resume") {
    return { state, messages: [{ text: "Resume upload is only available while building your profile." }] };
  }
  try {
    const result = await uploadJobFetchResume(file);
    const { state: nextState, messages } = await saveProfileAndShowFeed({ ...state, resumeOriginalName: result.filename });
    return { state: nextState, messages: [{ text: `Resume "${result.filename}" uploaded.` }, ...messages] };
  } catch (error) {
    return { state, messages: [{ text: `Resume upload failed: ${(error as Error).message}. Try again, or type "skip".` }] };
  }
}

export async function handleJobFetchText(
  state: JobFetchFlowState,
  text: string,
): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  const trimmed = text.trim();

  switch (state.step) {
    case "collecting_name": {
      if (trimmed.length < 2) return { state, messages: [{ text: "Please enter your full name (at least 2 characters)." }] };
      return {
        state: { ...state, fullName: trimmed.slice(0, 255), step: "collecting_skills" },
        messages: [{ text: `Thanks, ${trimmed.split(" ")[0]}. What skills should I match jobs against? (comma-separated, e.g. "Python, SQL, React")` }],
      };
    }

    case "collecting_skills": {
      const skills = splitList(trimmed);
      if (!skills.length) return { state, messages: [{ text: "Please list at least one skill, comma-separated." }] };
      return {
        state: { ...state, skills, step: "collecting_titles" },
        messages: [{ text: "Got it. What job titles are you targeting? (comma-separated, e.g. \"Data Analyst, Junior Python Developer\")" }],
      };
    }

    case "collecting_titles": {
      const titles = splitList(trimmed);
      if (!titles.length) return { state, messages: [{ text: "Please list at least one target title, comma-separated." }] };
      return {
        state: { ...state, preferredTitles: titles, step: "collecting_locations" },
        messages: [{ text: "Which locations do you prefer? (comma-separated, or type \"any\")" }],
      };
    }

    case "collecting_locations": {
      const locations = /^any$/i.test(trimmed) ? [] : splitList(trimmed);
      return {
        state: { ...state, preferredLocations: locations, step: "collecting_work_mode" },
        messages: [{ text: "Preferred work mode?", options: WORK_MODE_OPTIONS }],
      };
    }

    case "collecting_work_mode": {
      const selected = trimmed.toLowerCase();
      const mode = selected === "any"
        ? ""
        : WORK_MODE_OPTIONS.find((option) => option.value === selected)?.value ?? "";
      return {
        state: { ...state, preferredWorkMode: mode, step: "collecting_experience" },
        messages: [{ text: "Last question — how many years of experience do you have? (enter a number, 0 if none)" }],
      };
    }

    case "collecting_experience": {
      const years = Number(trimmed.replace(/[^0-9.]/g, ""));
      if (Number.isNaN(years)) return { state, messages: [{ text: "Please enter a number, e.g. \"0\" or \"2\"." }] };
      return {
        state: { ...state, step: "collecting_resume" },
        messages: [{ text: "Would you like to upload your resume? Attach a PDF or DOCX file below, or type \"skip\"." }],
      };
    }

    case "collecting_resume": {
      if (/^skip$/i.test(trimmed)) return saveProfileAndShowFeed(state);
      return { state, messages: [{ text: "Attach a PDF/DOCX file using the paperclip button, or type \"skip\" to continue without one." }] };
    }

    case "browsing": {
      // Defensive no-op: App.tsx intercepts "open:" before it ever becomes a
      // chat turn (see handleChooseOption), so this should never actually
      // run — kept only so a stray one can't get misread as a search query.
      if (trimmed.startsWith("open:")) {
        return { state, messages: [] };
      }
      if (/^back$/i.test(trimmed)) {
        return { state, messages: [feedMessage(state.feed, state.planTier, "Here are your matched jobs.")] };
      }
      if (/^(refresh|more|update)$/i.test(trimmed)) {
        const withFeed = await loadFeed(state);
        return { state: withFeed, messages: [feedMessage(withFeed.feed, withFeed.planTier, "Refreshed your job feed.")] };
      }
      if (/^next$/i.test(trimmed)) {
        const currentIndex = state.feed.findIndex((item) => item.id === state.selectedJobId);
        const nextJob = state.feed[currentIndex + 1];
        if (!nextJob) return { state, messages: [{ text: "That was the last match in this feed.", options: [{ label: "Back to list", value: "back" }] }] };
        return { state: { ...state, selectedJobId: nextJob.id }, messages: [jobDetailMessage(nextJob, state.feed)] };
      }
      const detailMatch = trimmed.match(/^detail:(\d+)$/);
      if (detailMatch) {
        const job = state.feed.find((item) => item.id === Number(detailMatch[1]));
        if (!job) return { state, messages: [{ text: "That job is no longer available." }] };
        return { state: { ...state, selectedJobId: job.id }, messages: [jobDetailMessage(job, state.feed)] };
      }
      const actionMatch = trimmed.match(/^(save|unsave|hide|unhide|apply):(\d+)$/);
      if (actionMatch) {
        const [, action, idText] = actionMatch;
        const jobId = Number(idText);
        try {
          await jobFetchAction(jobId, action as "save" | "unsave" | "hide" | "unhide" | "apply");
          // A hidden job also drops out of the backend feed query, so it
          // must disappear from the local feed too rather than just being
          // flagged in place — otherwise it would keep showing here until
          // the next full refresh.
          const nextFeed = action === "hide"
            ? state.feed.filter((job) => job.id !== jobId)
            : state.feed.map((job) =>
                job.id === jobId
                  ? { ...job, is_saved: action === "save" ? 1 : action === "unsave" ? 0 : job.is_saved, application_status: action === "apply" ? "applied" : job.application_status }
                  : job,
              );
          const confirmText =
            action === "apply" ? "Marked as applied. Good luck!" :
            action === "hide" ? "Got it — hidden. Find it again anytime under Hidden jobs in your dashboard." :
            action === "unhide" ? "Job unhidden." :
            `Job ${action === "save" ? "saved" : "unsaved"}.`;
          // Same "keep moving through matches" option as the detail view —
          // saving/applying no longer dead-ends back at the full list. A
          // hidden job removed itself from nextFeed, so there is no
          // meaningful "next" position to resume from.
          const currentIndex = nextFeed.findIndex((item) => item.id === jobId);
          const options: ChatOption[] = [];
          if (action !== "hide" && currentIndex >= 0 && currentIndex < nextFeed.length - 1) {
            options.push({ label: "Next match →", value: "next" });
          }
          options.push({ label: "Back to list", value: "back" });
          return {
            state: { ...state, feed: nextFeed, selectedJobId: action === "hide" ? undefined : jobId },
            messages: [{ text: confirmText, options }],
          };
        } catch (error) {
          return { state, messages: [{ text: `That didn't work: ${(error as Error).message}` }] };
        }
      }
      // Anything else is treated as a new search query against the feed.
      const withFeed = await loadFeed(state, { q: trimmed });
      return { state: withFeed, messages: [feedMessage(withFeed.feed, withFeed.planTier, `Results for "${trimmed}":`)] };
    }
  }
}
