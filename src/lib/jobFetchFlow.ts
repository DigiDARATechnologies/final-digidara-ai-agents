import type { ChatOption, User } from "../types";
import {
  chatWithJobAgent,
  ensureJobFetchProfile,
  getJobFeed,
  getJobFetchProfile,
  jobFetchAction,
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
  experienceYears?: number;
  planTier: string;
  resumeOriginalName?: string;
  feed: JobFeedItem[];
  selectedJobId?: number;
}

export function safeJobApplyUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function createInitialState(): JobFetchFlowState {
  return {
    step: "browsing",
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
    return {
      text: `${intro}\n\n*No matching jobs found right now.* Tell me your preferred skills or cities (e.g. Chennai, Coimbatore, Bangalore, Remote), and I'll find fresh matches for you!`,
      options: [
        { label: "🎓 Show fresher jobs", value: "Show me fresher jobs" },
        { label: "🔍 Show Chennai jobs", value: "Show me jobs in Chennai" },
        { label: "📍 Show Coimbatore jobs", value: "Show me jobs in Coimbatore" },
        { label: "💼 Show Python jobs", value: "Show me Python developer jobs" },
      ],
    };
  }
  const top = feed.slice(0, 5);
  const lines = top.map(
    (job, index) => {
      const tierBadge = job.seniority_tier === "entry" ? "🎓 [Entry-Level]" : "🚀 [Growth]";
      const trustBadge = job.trust_badge ? ` • ${job.trust_badge}` : "";
      const skillsText = job.skills?.length ? `\n   • 🛠️ **Skills:** ${job.skills.slice(0, 5).join(", ")}` : "";
      const expText = (job.experience_min != null || job.experience_max != null)
        ? `\n   • ⏳ **Exp:** ${job.experience_min ?? 0}-${job.experience_max ?? 2} yrs`
        : "\n   • ⏳ **Exp:** Fresher / Entry";
      const salaryText = job.salary_text ? ` | 💰 **Salary:** ${job.salary_text}` : "";
      const safeUrl = safeJobApplyUrl(job.apply_url);
      const applyLink = safeUrl ? `\n   • 🔗 [Apply on Official Portal ↗](${safeUrl})` : "";
      return `${index + 1}. **${job.title}** @ **${job.company}**${job.location ? ` (${job.location})` : ""}\n   • ${tierBadge} • **Match ${job.match_score}%**${trustBadge}${expText}${salaryText}${skillsText}${applyLink}`;
    },
  );
  const tierNote = planTier === "free" ? "\n\n*(Curated 70% entry-level & 30% growth verified matches across Tamil Nadu & tech hubs.)*" : "";
  return {
    text: `${intro}\n\n${lines.join("\n\n")}${tierNote}\n\nPick a job below to view details, verify authenticity, save, or apply directly:`,
    options: top.map((job) => ({
      label: `${job.title} @ ${job.company}`,
      value: `detail:${job.id}`,
      description: `Match ${job.match_score}% • ${job.seniority_tier === "entry" ? "Entry-Level" : "Growth"}`,
    })),
  };
}

function jobDetailMessage(job: JobFeedItem, feed: JobFeedItem[]): JobFetchFlowMessage {
  const safeApplyUrl = safeJobApplyUrl(job.apply_url);
  const tierText = job.seniority_tier === "entry" ? "🎓 Entry-Level / College Fresher" : "🚀 Career Growth / Next-Step Role";
  const trustText = job.trust_badge ? `🛡️ **Authenticity:** ${job.trust_badge} (${job.trust_score ?? 92}% Trust Score)` : null;
  const salaryText = job.salary_text ? `💰 **Salary / Compensation:** ${job.salary_text}` : `💰 **Salary / Compensation:** Undisclosed by employer in listing`;
  const expText = (job.experience_min != null || job.experience_max != null)
    ? `⏳ **Experience Required:** ${job.experience_min ?? 0} to ${job.experience_max ?? 2} years`
    : null;

  const lines = [
    `### **${job.title}** @ **${job.company}**`,
    job.location ? `📍 **Location:** ${job.location}` : null,
    job.work_mode ? `🏢 **Work mode:** ${job.work_mode}` : null,
    `🎯 **Role Level:** ${tierText}`,
    trustText,
    salaryText,
    expText,
    job.skills.length ? `🛠️ **Skills:** ${job.skills.join(", ")}` : null,
    `🎯 **Match Score:** ${job.match_score}% — *${job.match_reasons.join("; ")}*`,
    job.description ? `\n📝 **Job Summary:**\n${job.description.slice(0, 600)}...` : null,
    safeApplyUrl ? `\n🔗 **Application URL:** [Apply on Employer Portal](${safeApplyUrl})` : null,
  ].filter(Boolean);

  const options: ChatOption[] = [];
  if (safeApplyUrl) {
    options.push({ label: "Apply now ↗", value: `open:${safeApplyUrl}` });
  }
  options.push(
    { label: "❓ Salary & role details", value: `What is the salary and description for ${job.company}?` },
    { label: "🛡️ Check authenticity & safety", value: `Is the job at ${job.company} genuine and trusted?` },
    { label: job.is_saved ? "⭐ Unsave" : "⭐ Save job", value: job.is_saved ? `unsave:${job.id}` : `save:${job.id}` },
    { label: job.application_status === "applied" ? "✅ Applied (mark again)" : "✅ Mark as applied", value: `apply:${job.id}` },
    { label: "❌ Hide from feed", value: `hide:${job.id}` },
  );

  const currentIndex = feed.findIndex((item) => item.id === job.id);
  if (currentIndex >= 0 && currentIndex < feed.length - 1) {
    options.push({ label: "Next match →", value: "next" });
  }
  options.push({ label: "🔙 Back to list", value: "back" });
  return { text: lines.join("\n"), options };
}

async function loadFeed(state: JobFetchFlowState, query: Record<string, unknown> = {}) {
  const result = await getJobFeed(query as any);
  return { ...state, step: "browsing" as const, feed: result.jobs, planTier: result.plan_tier };
}

export async function openJobFetchChat(user: User): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  const base = createInitialState();
  try {
    await ensureJobFetchProfile();
    const profile = await getJobFetchProfile();
    const withFeed = await loadFeed({
      ...base,
      fullName: profile.full_name || user.name,
      skills: profile.skills,
      preferredTitles: profile.preferred_titles,
      preferredLocations: profile.preferred_locations,
      preferredWorkMode: profile.preferred_work_mode,
      experienceYears: profile.experience_years,
      resumeOriginalName: profile.resume_original_name || undefined,
      planTier: profile.plan_tier,
    });

    const firstName = (profile.full_name || user.name || "there").split(" ")[0];
    const isProfileComplete = Boolean(profile.profile_completed);

    // IF USER HAS NOT COMPLETED ONBOARDING YET:
    if (!isProfileComplete) {
      const welcomeText = `👋 Hi ${firstName}! I'm your **Job Agent**.\n\nHow can I assist you with your career search today?\n\nTo get started, please enter your **full name**.`;

      return {
        state: withFeed,
        messages: [{ text: welcomeText, options: [] }],
      };
    }

    // IF USER ALREADY HAS PROFILE INFO:
    const intro = `👋 Welcome back, ${firstName}! Here are your latest curated matches based on your profile:`;
    const initialMsg = feedMessage(withFeed.feed, withFeed.planTier, intro);

    const quickActions: ChatOption[] = [
      { label: "🎓 Fresher jobs", value: "Show me fresher jobs" },
      { label: "🔍 Chennai jobs", value: "Show me jobs in Chennai" },
      { label: "💼 Top matches", value: "What are my best matching jobs?" },
      { label: "🔄 Update skills", value: "I'd like to update my skills" },
    ];

    initialMsg.options = [
      ...(initialMsg.options || []),
      ...quickActions,
    ];

    return { state: withFeed, messages: [initialMsg] };
  } catch (error) {
    return {
      state: base,
      messages: [{ text: `I could not connect to the Job Agent: ${(error as Error).message}`, options: [{ label: "Try again", value: "retry" }] }],
    };
  }
}

/** Called from App.tsx when the user attaches or drops a resume file at ANY point. */
export async function submitJobFetchResume(
  state: JobFetchFlowState,
  file: File,
): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  try {
    const result = await uploadJobFetchResume(file);
    const withFeed = await loadFeed({ ...state, resumeOriginalName: result.filename });
    const text = `🎉 **Awesome! Resume uploaded successfully!**\n\nI've saved **"${result.filename}"** to your profile. I'll use it to match you against all verified postings from employers across Tamil Nadu, Bangalore, and Remote.\n\nTell me: what specific roles or cities (e.g. Chennai, Coimbatore, Madurai, Trichy, Bangalore) would you like to prioritize?`;
    const options: ChatOption[] = [
      { label: "💼 Show best matches", value: "What are my best matching jobs?" },
      { label: "🔍 Show Chennai jobs", value: "Show me jobs in Chennai" },
      { label: "📍 Show Remote jobs", value: "Show me remote jobs" },
    ];
    return { state: withFeed, messages: [{ text, options }] };
  } catch (error) {
    return { state, messages: [{ text: `Resume upload failed: ${(error as Error).message}. You can try again anytime using the attachment icon.` }] };
  }
}

export async function handleJobFetchText(
  state: JobFetchFlowState,
  text: string,
  history: Array<{ role: string; content: string }> = [],
): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  const trimmed = text.trim();

  // 1. URL opening no-op
  if (trimmed.startsWith("open:")) {
    return { state, messages: [] };
  }

  // 2. Navigation & list controls
  if (/^back$/i.test(trimmed)) {
    return {
      state: { ...state, selectedJobId: undefined },
      messages: [feedMessage(state.feed, state.planTier, "Here are your matching opportunities:")],
    };
  }

  if (/^(refresh|more|update)$/i.test(trimmed)) {
    const withFeed = await loadFeed(state);
    return { state: withFeed, messages: [feedMessage(withFeed.feed, withFeed.planTier, "Refreshed your live job feed:")] };
  }

  if (/^next$/i.test(trimmed)) {
    const currentIndex = state.feed.findIndex((item) => item.id === state.selectedJobId);
    const nextJob = state.feed[currentIndex + 1];
    if (!nextJob) {
      return {
        state,
        messages: [{ text: "That was the last match in this feed.", options: [{ label: "Back to list", value: "back" }] }],
      };
    }
    return { state: { ...state, selectedJobId: nextJob.id }, messages: [jobDetailMessage(nextJob, state.feed)] };
  }

  // 3. Detail view
  const detailMatch = trimmed.match(/^detail:(\d+)$/);
  if (detailMatch) {
    const job = state.feed.find((item) => item.id === Number(detailMatch[1]));
    if (!job) return { state, messages: [{ text: "That job is no longer available in the active feed." }] };
    return { state: { ...state, selectedJobId: job.id }, messages: [jobDetailMessage(job, state.feed)] };
  }

  // 4. Job Actions (Save, Unsave, Hide, Apply)
  const actionMatch = trimmed.match(/^(save|unsave|hide|unhide|apply):(\d+)$/);
  if (actionMatch) {
    const [, action, idText] = actionMatch;
    const jobId = Number(idText);
    try {
      await jobFetchAction(jobId, action as "save" | "unsave" | "hide" | "unhide" | "apply");
      const targetJob = state.feed.find((item) => item.id === jobId);
      const nextFeed = action === "hide"
        ? state.feed.filter((job) => job.id !== jobId)
        : state.feed.map((job) =>
            job.id === jobId
              ? {
                  ...job,
                  is_saved: action === "save" ? 1 : action === "unsave" ? 0 : job.is_saved,
                  application_status: action === "apply" ? "applied" : job.application_status,
                }
              : job,
          );

      let confirmText = `Job ${action === "save" ? "saved" : "unsaved"}.`;
      if (action === "apply") {
        const userName = (state.fullName || "there").split(" ")[0];
        confirmText =
          `🎉 **Congratulations ${userName}! You took action and applied!**\n\n` +
          (targetJob ? `Application for **${targetJob.title}** at **${targetJob.company}** is marked.\n\n` : "") +
          `🌟 Applying consistently is how you land your dream tech role. Be sure to review the core requirements and polish a 2-minute overview of your relevant projects.\n\n` +
          `Would you like to review more jobs, or discuss interview tips for this role?`;
      } else if (action === "hide") {
        confirmText = "Got it — hidden from your feed. You can restore it anytime in your dashboard.";
      } else if (action === "unhide") {
        confirmText = "Job unhidden.";
      }

      const currentIndex = nextFeed.findIndex((item) => item.id === jobId);
      const options: ChatOption[] = [];
      if (action === "apply" && targetJob?.apply_url) {
        const safeUrl = safeJobApplyUrl(targetJob.apply_url);
        if (safeUrl) options.push({ label: "Open application page ↗", value: `open:${safeUrl}` });
      }
      if (action !== "hide" && currentIndex >= 0 && currentIndex < nextFeed.length - 1) {
        options.push({ label: "Next match →", value: "next" });
      }
      options.push({ label: "🔙 Back to list", value: "back" });
      options.push({ label: "💼 More matches", value: "Show me more jobs" });

      return {
        state: { ...state, feed: nextFeed, selectedJobId: action === "hide" ? undefined : jobId },
        messages: [{ text: confirmText, options }],
      };
    } catch (error) {
      return { state, messages: [{ text: `Action could not be completed: ${(error as Error).message}` }] };
    }
  }

  // 5. Intelligent Multi-Turn Conversational Interaction via DigiDARA Job Agent!
  try {
    let targetJobId = state.selectedJobId;
    if (!targetJobId && state.feed.length > 0) {
      const lower = trimmed.toLowerCase();
      const matched = state.feed.find(
        (j) => (j.company && lower.includes(j.company.toLowerCase())) ||
               (j.title && lower.includes(j.title.toLowerCase()))
      );
      if (matched) targetJobId = matched.id;
    }

    const chatRes = await chatWithJobAgent(trimmed, history, targetJobId);

    let nextState = { ...state };
    if (chatRes.updated_profile) {
      nextState = {
        ...nextState,
        skills: chatRes.updated_profile.skills || nextState.skills,
        preferredLocations: chatRes.updated_profile.preferred_locations || nextState.preferredLocations,
        preferredTitles: chatRes.updated_profile.preferred_titles || nextState.preferredTitles,
        preferredWorkMode: chatRes.updated_profile.preferred_work_mode || nextState.preferredWorkMode,
        experienceYears: chatRes.updated_profile.experience_years ?? nextState.experienceYears,
      };
    }

    if (chatRes.matched_jobs && chatRes.matched_jobs.length > 0) {
      nextState.feed = chatRes.matched_jobs;
    }

    const options: ChatOption[] = [];

    // Clickable options for recommended jobs
    if (chatRes.matched_jobs && chatRes.matched_jobs.length > 0) {
      for (const j of chatRes.matched_jobs.slice(0, 3)) {
        if (j && j.title) {
          options.push({
            label: `${j.title} @ ${j.company || "Employer"}`,
            value: `detail:${j.id}`,
            description: `Match ${j.match_score ?? 80}%`,
          });
        }
      }
    }

    // Suggested conversational actions from AI
    if (Array.isArray(chatRes.suggested_actions)) {
      for (const act of chatRes.suggested_actions as Array<any>) {
        if (!act) continue;
        const label = typeof act === "string" ? act.trim() : String(act.label || "").trim();
        const value = typeof act === "string" ? act.trim() : String(act.value || act.label || "").trim();
        if (label && value && label.length > 1 && label !== ".") {
          options.push({ label, value });
        }
      }
    }

    // Strictly filter out any empty or blank options
    const validOptions = options.filter(
      (opt) => opt && typeof opt.label === "string" && opt.label.trim().length > 1 && opt.label.trim() !== "."
    );

    let replyText = chatRes.reply;
    if (chatRes.matched_jobs && chatRes.matched_jobs.length > 0 && !replyText.includes("1. **")) {
      const topJobs = chatRes.matched_jobs.slice(0, 4);
      const formattedLines = topJobs.map((job, idx) => {
        const tierBadge = job.seniority_tier === "entry" ? "🎓 [Entry-Level]" : "🚀 [Growth]";
        const trustBadge = job.trust_badge ? ` • ${job.trust_badge}` : "";
        const skillsText = job.skills?.length ? `\n   • 🛠️ **Skills:** ${job.skills.slice(0, 5).join(", ")}` : "";
        const expText = (job.experience_min != null || job.experience_max != null)
          ? `\n   • ⏳ **Exp:** ${job.experience_min ?? 0}-${job.experience_max ?? 2} yrs`
          : "\n   • ⏳ **Exp:** Fresher / Entry";
        const salaryText = job.salary_text ? ` | 💰 **Salary:** ${job.salary_text}` : "";
        const safeUrl = safeJobApplyUrl(job.apply_url);
        const applyLink = safeUrl ? `\n   • 🔗 [Apply on Official Portal ↗](${safeUrl})` : "";
        return `${idx + 1}. **${job.title}** @ **${job.company}**${job.location ? ` (${job.location})` : ""}\n   • ${tierBadge} • **Match ${job.match_score}%**${trustBadge}${expText}${salaryText}${skillsText}${applyLink}`;
      }).join("\n\n");

      const cleanIntro = replyText.trim().replace(/:?\s*$/, "");
      replyText = `${cleanIntro}:\n\n${formattedLines}\n\n💡 *Tip: Tap any option below to view full details, check authenticity, or save.*`;
    }

    return {
      state: nextState,
      messages: [{ text: replyText, options: validOptions.length ? validOptions : undefined }],
    };
  } catch (error: any) {
    const errMsg = String(error?.message || "");
    if (
      errMsg.toLowerCase().includes("insufficient_tokens") ||
      errMsg.toLowerCase().includes("top up") ||
      errMsg.includes("402")
    ) {
      return {
        state,
        messages: [
          {
            text: `💡 **You've reached your free daily quota!**\n\nTo discover more verified fresher opportunities or continue chatting with DigiDARA Job Agent, you can top up tokens on the platform (**₹1.00 = 1,000 tokens**).\n\nTap below to top up your balance:`,
            options: [
              { label: "💳 Top Up Tokens", value: "action:open_billing" },
              { label: "🔙 View My Saved Jobs", value: "Show me my saved jobs" },
            ],
          },
        ],
      };
    }
    // Graceful fallback to search feed if network issue occurs
    try {
      const withFeed = await loadFeed(state, { q: trimmed });
      return {
        state: withFeed,
        messages: [feedMessage(withFeed.feed, withFeed.planTier, `Here are matching jobs for "${trimmed}":`)],
      };
    } catch {
      return {
        state,
        messages: [{ text: "Unable to load matching jobs right now. Please try again in a moment." }],
      };
    }
  }
}
