import type { ChatOption, User } from "../types";
import {
  chatWithJobAgent,
  ensureJobConversation,
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
  profileCompleted: boolean;
  experienceProvided: boolean;
  fullName: string;
  skills: string[];
  preferredTitles: string[];
  preferredLocations: string[];
  preferredWorkMode: string;
  experienceYears?: number;
  planTier: string;
  resumeOriginalName?: string;
  feed: JobFeedItem[];
  feedOffset?: number;
  hasMore?: boolean;
  selectedJobId?: number;
  conversationId?: string;
  contextualSearch?: boolean;
  searchLabel?: string;
  pendingChat?: { message: string; clientMessageId: string };
}

const WORK_MODE_OPTIONS: ChatOption[] = [
  { label: "Remote", value: "remote" },
  { label: "Hybrid", value: "hybrid" },
  { label: "Office", value: "office" },
  { label: "Any", value: "any" },
];

function splitList(text: string): string[] {
  return text.split(/[,;\n]/).map((item) => item.trim()).filter(Boolean).slice(0, 20);
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
    profileCompleted: false,
    experienceProvided: false,
    fullName: "",
    skills: [],
    preferredTitles: [],
    preferredLocations: [],
    preferredWorkMode: "",
    planTier: "free",
    feed: [],
    feedOffset: 0,
    hasMore: false,
  };
}

function feedMessage(feed: JobFeedItem[], planTier: string, intro: string, filterLabel = ""): JobFetchFlowMessage {
  if (!feed.length) {
    if (filterLabel) {
      return {
        text: `There are no active jobs listed for **${filterLabel}** in the portal right now. I won't substitute jobs from other locations or work modes.`,
      };
    }
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
      const trustBadge = job.trust_badge ? ` • ${candidateTrustBadge(job)}` : "";
      const matchingSkillsText = job.matching_skills?.length
        ? `\n   • ✅ **Matched:** ${job.matching_skills.slice(0, 4).join(", ")}`
        : (job.skills?.length ? `\n   • 🛠️ **Skills:** ${job.skills.slice(0, 5).join(", ")}` : "");
      const missingSkillsText = job.missing_skills?.length
        ? `\n   • ⚠️ **To Learn:** ${job.missing_skills.slice(0, 3).join(", ")}`
        : "";
      const prepTipText = job.preparation_tips ? `\n   • 💡 **Prep Tip:** ${job.preparation_tips}` : "";
      const expText = (job.experience_min != null || job.experience_max != null)
        ? `\n   • ⏳ **Exp:** ${job.experience_min ?? 0}-${job.experience_max ?? 2} yrs`
        : "\n   • ⏳ **Exp:** Fresher / Entry";
      const salaryText = job.salary_text ? ` | 💰 **Salary:** ${job.salary_text}` : "";
      const safeUrl = safeJobApplyUrl(job.apply_url);
      const applyLabel = job.application_label || "Open application page";
      const applyLink = safeUrl ? `\n   • 🔗 [${applyLabel}](${safeUrl})` : "";
      return `${index + 1}. **${job.title}** @ **${job.company}**${job.location ? ` (${job.location})` : ""}\n   • ${tierBadge} • **Match ${job.match_score}%**${trustBadge}${expText}${salaryText}${matchingSkillsText}${missingSkillsText}${prepTipText}${applyLink}`;
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

function candidateTrustBadge(job: JobFeedItem): string {
  return (job.trust_badge || "").replace(/\s*\(via\s+[^)]*\)/gi, "");
}

function jobDetailMessage(job: JobFeedItem, feed: JobFeedItem[]): JobFetchFlowMessage {
  const safeApplyUrl = safeJobApplyUrl(job.apply_url);
  const tierText = job.seniority_tier === "entry" ? "🎓 Entry-Level / College Fresher" : "🚀 Career Growth / Next-Step Role";
  const trustText = job.trust_badge ? `🛡️ **Listing checks:** ${candidateTrustBadge(job)} (${job.trust_score ?? 0}% score)` : null;
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
    job.skills.length ? `🛠️ **Key Skills:** ${job.skills.join(", ")}` : null,
    job.matching_skills?.length ? `✅ **Matching Skills:** ${job.matching_skills.join(", ")}` : null,
    job.missing_skills?.length ? `⚠️ **Skills to Strengthen:** ${job.missing_skills.join(", ")}` : null,
    job.preparation_tips ? `💡 **Preparation Advice:** ${job.preparation_tips}` : null,
    `🎯 **Match Score:** ${job.match_score}% — *${job.match_reasons.join("; ")}*`,
    job.description ? `\n📝 **Job Summary:**\n${job.description.slice(0, 600)}...` : null,
    safeApplyUrl ? `\n🔗 **Application URL:** [${job.application_label || "Open application page"}](${safeApplyUrl})\nApply here: ${safeApplyUrl}` : null,
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

async function loadFeed(state: JobFetchFlowState, query: Record<string, unknown> = {}, append = false) {
  const filters: Record<string, unknown> = { ...query };
  if (!("location" in filters) && state.preferredLocations.length) filters.location = state.preferredLocations.join("|");
  if (!("work_mode" in filters) && state.preferredWorkMode) filters.work_mode = state.preferredWorkMode;
  filters.limit = Number(filters.limit ?? (append ? 5 : 20));
  filters.offset = Number(filters.offset ?? (append ? (state.feedOffset ?? state.feed.length) : 0));
  const result = await getJobFeed(filters as any);
  const feed = append
    ? [...state.feed, ...result.jobs.filter((job) => !state.feed.some((existing) => existing.id === job.id))]
    : result.jobs;
  return {
    ...state,
    step: "browsing" as const,
    feed,
    feedOffset: (result.offset ?? Number(filters.offset) ?? 0) + (result.returned ?? result.jobs.length),
    hasMore: Boolean(result.has_more),
    planTier: result.plan_tier,
  };
}

export async function openJobFetchChat(user: User, conversationId?: string): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  const base = createInitialState();
  try {
    await ensureJobFetchProfile();
    if (conversationId) await ensureJobConversation(conversationId, "Job Agent");
    const profile = await getJobFetchProfile();
    const profileState: JobFetchFlowState = {
      ...base,
      conversationId,
      fullName: profile.full_name || "",
      profileCompleted: Boolean(profile.profile_completed),
      experienceProvided: Boolean(profile.experience_provided),
      skills: profile.skills,
      preferredTitles: profile.preferred_titles,
      preferredLocations: profile.preferred_locations,
      preferredWorkMode: profile.preferred_work_mode,
      experienceYears: profile.experience_years,
      resumeOriginalName: profile.resume_original_name || undefined,
      planTier: profile.plan_tier,
      step: "browsing",
    };

    const firstName = (profile.full_name || user.name || "there").split(" ")[0];
    const isProfileComplete = Boolean(profile.profile_completed);

    // IF USER HAS NOT COMPLETED ONBOARDING YET:
    if (!isProfileComplete) {
      const welcomeText = `👋 Hi ${firstName}! I'm your **Job Agent**.\n\n${profile.onboarding_prompt || "Let’s continue setting up your job-search profile. What would you like to update?"}`;

      return {
        state: profileState,
        messages: [{ text: welcomeText, options: profile.onboarding_step === "resume" ? [{ label: "Skip resume", value: "skip" }] : [] }],
      };
    }

    // IF USER ALREADY HAS PROFILE INFO:
    let withFeed: JobFetchFlowState;
    try {
      withFeed = await loadFeed(profileState);
    } catch {
      return {
        state: profileState,
        messages: [{ text: `Welcome back, ${firstName}. Your job-search profile is available, but I couldn't load your job feed right now. Please try again in a moment.` }],
      };
    }
    const intro = `👋 Welcome back, ${firstName}! Here are your latest curated matches based on your profile:`;
    const filterLabel = withFeed.preferredLocations.join(", ") || withFeed.preferredWorkMode;
    const initialMsg = feedMessage(withFeed.feed, withFeed.planTier, intro, filterLabel);

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
    const withFeed = await loadFeed({ ...state, resumeOriginalName: result.filename, step: "browsing" });
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

async function saveProfileAndShowFeed(state: JobFetchFlowState): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  let saved: Awaited<ReturnType<typeof updateJobFetchProfile>>;
  try {
    saved = await updateJobFetchProfile({
      full_name: state.fullName,
      skills: state.skills,
      preferred_titles: state.preferredTitles,
      preferred_locations: state.preferredLocations,
      preferred_work_mode: state.preferredWorkMode || undefined,
      experience_years: state.experienceYears,
    });
  } catch (error) {
    return { state, messages: [{ text: `I could not save your profile: ${(error as Error).message}. Try again.` }] };
  }
  if (!saved.profile_completed) {
    return { state: { ...state, profileCompleted: false }, messages: [{ text: "Your profile is not complete yet. Please provide the remaining required details before finishing setup." }] };
  }
  const completedState = { ...state, profileCompleted: true };
  try {
    const withFeed = await loadFeed({ ...completedState, step: "browsing" });
    const filterLabel = withFeed.preferredLocations.join(", ") || withFeed.preferredWorkMode;
    return { state: withFeed, messages: [feedMessage(withFeed.feed, withFeed.planTier, "Profile saved! Here are your matched jobs.", filterLabel)] };
  } catch {
    return { state: { ...completedState, step: "browsing" }, messages: [{ text: "Your profile was saved, but I couldn't load matching jobs right now. Please try again in a moment." }] };
  }
}

export async function handleJobFetchText(
  state: JobFetchFlowState,
  text: string,
  history: Array<{ role: string; content: string }> = [],
  conversationId?: string,
): Promise<{ state: JobFetchFlowState; messages: JobFetchFlowMessage[] }> {
  const trimmed = text.trim();
  const activeConversationId = state.conversationId || conversationId;

  // Legacy client-side onboarding also treats social turns as conversation,
  // never as a name, skill, title, or experience value.
  const socialText = trimmed.toLowerCase().replace(/[.!?,\s]+$/g, "").replace(/\s+/g, " ");
  const isCheckIn = ["how are you", "how are you doing", "how's it going", "how is it going", "how r u"].includes(socialText);
  const isHello = ["hi", "hello", "hey", "hi there", "hello there", "good morning", "good afternoon", "good evening", "hi how are you", "hello how are you"].includes(socialText);
  if (state.step !== "browsing" && (isHello || isCheckIn)) {
    const name = state.step === "collecting_name" ? "there" : state.fullName.split(" ")[0] || "there";
    const greeting = isCheckIn ? `I'm here and ready to help, ${name}. Thanks for asking!` : `Hi ${name}! Good to hear from you.`;
    const reminder: Record<Exclude<JobFetchStep, "browsing">, string> = {
      collecting_name: "Whenever you're ready, tell me the name or nickname you'd like me to use.",
      collecting_skills: "Whenever you're ready, share a technical skill you know or are learning.",
      collecting_titles: "Whenever you're ready, tell me which job roles you'd like to find.",
      collecting_locations: "Whenever you're ready, choose a city or work mode such as Remote.",
      collecting_work_mode: "Whenever you're ready, choose a work mode.",
      collecting_experience: "No rush—when you're ready, say **fresher** or share how many years of work experience you have.",
      collecting_resume: "You can attach a resume, or type **skip**; a resume is optional.",
    };
    return { state, messages: [{ text: `${greeting}\n\n${reminder[state.step]}` }] };
  }

  // Onboarding steps
  switch (state.step) {
    case "collecting_name": {
      const mentionsName = /\b(full\s*name|name|nickname)\b/i.test(trimmed);
      if (mentionsName && /\b(why|reason|purpose)\b/i.test(trimmed)) {
        return {
          state,
          messages: [{ text: "I ask for a name or nickname to fill the name section of your job-search profile and address you the way you prefer. Your name doesn't determine which jobs match you, and it doesn't have to be your legal name.\n\nYour profile isn't fully complete yet; the name section is still waiting for your choice. What name or nickname would you like me to use?" }],
        };
      }
      if (mentionsName && /\b(don['’]?t|do not|won['’]?t|prefer not to|skip)\b/i.test(trimmed)) {
        return {
          state,
          messages: [{ text: "That's okay—you decide what to share. A nickname is enough; you don't need to give your legal name. Your profile isn't fully complete yet because your preferred name is still missing. You can return to it later." }],
        };
      }
      if (mentionsName && /\?|\b(should|give|enter|provide|do i|can i)\b/i.test(trimmed)) {
        return { state, messages: [{ text: "Yes—please share the name or nickname you'd like me to use. It doesn't have to be your legal name." }] };
      }
      if (/\b(profile|details|setup)\b/i.test(trimmed) && /\b(complete|incomplete|missing|remaining|pending|ready)\b/i.test(trimmed)) {
        return { state, messages: [{ text: "Your job-search profile isn't fully complete yet. The name section is still waiting for your choice. Your other saved details are kept. You can use a nickname instead of a legal name." }] };
      }
      if (/\b(i\s+(?:do\s*not|don't|dont)\s+have\s+(?:a\s+)?name|no\s+name|what\s+can\s+i\s+do)\b/i.test(trimmed)) {
        return {
          state,
          messages: [{ text: "No problem. Enter any name or nickname you would like me to use; it does not have to be a legal name." }],
        };
      }
      if (/\?|^(why|what|how|should|can|could|do|are)\b/i.test(trimmed)) {
        return { state, messages: [{ text: "I'm filling the name section of your job-search profile. You can use any name or nickname you'd like me to use; a legal name isn't needed. Your profile stays incomplete until the required details are provided." }] };
      }
      if (trimmed.length < 2) return { state, messages: [{ text: "Please enter your full name (at least 2 characters)." }] };
      return {
        state: { ...state, fullName: trimmed.slice(0, 255), step: "collecting_skills" },
        messages: [{ text: `Thanks, ${trimmed.split(" ")[0]}. What skills should I match jobs against? (comma-separated, e.g. "Python, SQL, React")` }],
      };
    }

    case "collecting_skills": {
      if (/role/i.test(trimmed) && /skills?/i.test(trimmed)) {
        return {
          state,
          messages: [{ text: "I’m asking for your skills right now—for example Mathematics, React, Express.js, Python, SQL, or Excel. I’ll ask for your preferred role next." }],
        };
      }
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
      const mode = selected === "onsite"
          ? "office"
        : WORK_MODE_OPTIONS.find((option) => option.value === selected)?.value ?? "";
      return {
        state: { ...state, preferredWorkMode: mode, step: "collecting_experience" },
        messages: [{ text: "Last question — how many years of experience do you have? (enter a number, 0 if none)" }],
      };
    }

    case "collecting_experience": {
      const fresher = /^(?:i(?:'m| am)\s+(?:a\s+)?)?(?:fresher|no\s+(?:work\s+)?experience)$/i.test(trimmed);
      const numericText = trimmed.match(/-?\d+(?:\.\d+)?/)?.[0];
      const years = fresher ? 0 : numericText == null ? Number.NaN : Number(numericText);
      if (Number.isNaN(years)) return { state, messages: [{ text: "Please enter a number, e.g. \"0\", \"2\", or \"2.5\"." }] };
      if (years < 0 || years > 50) {
        return { state, messages: [{ text: "That experience value looks invalid. Please enter a value between 0 and 50 years." }] };
      }
      return {
        state: { ...state, experienceYears: years, experienceProvided: true, step: "collecting_resume" },
        messages: [{ text: "Would you like to upload your resume? Attach a PDF or DOCX file below, or type \"skip\"." }],
      };
    }

    case "collecting_resume": {
      const isProceed = Boolean(state.resumeOriginalName) || /^(skip|done|next|proceed|continue|show jobs|view jobs|best match)/i.test(trimmed);
      if (isProceed) return saveProfileAndShowFeed(state);
      return { state, messages: [{ text: "Attach a PDF/DOCX file using the paperclip button, or type \"skip\" to continue without one." }] };
    }
  }

  // 1. URL opening no-op
  if (trimmed.startsWith("open:")) {
    return { state, messages: [] };
  }

  // 2. Navigation & list controls
  if (/^back$/i.test(trimmed)) {
    return {
      state: { ...state, selectedJobId: undefined },
      messages: [feedMessage(state.feed, state.planTier, "Here are your matching opportunities:", state.searchLabel || state.preferredLocations.join(", ") || state.preferredWorkMode)],
    };
  }

  if (!state.contextualSearch && (state.profileCompleted || state.feed.length > 0) && /^(more|show me more jobs|more matches)$/i.test(trimmed)) {
    if (state.hasMore === false && (state.feedOffset ?? state.feed.length) > 0) {
      const place = state.preferredLocations.join(", ") || state.preferredWorkMode || "your current preferences";
      return { state, messages: [{ text: `There are no more active jobs listed for **${place}** in the portal right now.` }] };
    }
    const previousCount = state.feed.length;
    const withFeed = await loadFeed(state, {}, true);
    const added = withFeed.feed.slice(previousCount);
    const place = state.preferredLocations.join(", ") || state.preferredWorkMode || "your current preferences";
    if (!added.length) {
      return { state: withFeed, messages: [{ text: `There are no more active jobs listed for **${place}** in the portal right now.` }] };
    }
    return { state: withFeed, messages: [feedMessage(added, withFeed.planTier, "Here are your next matching opportunities:")] };
  }

  if (!state.contextualSearch && (state.profileCompleted || state.feed.length > 0) && /^(refresh|update)$/i.test(trimmed)) {
    const withFeed = await loadFeed(state);
    return { state: withFeed, messages: [feedMessage(withFeed.feed, withFeed.planTier, "Refreshed your live job feed:", withFeed.preferredLocations.join(", ") || withFeed.preferredWorkMode)] };
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
  const pendingChat = state.pendingChat?.message === trimmed ? state.pendingChat : {
    message: trimmed,
    clientMessageId: `m_${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(36).slice(2)}`}`,
  };
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

    const chatRes = await chatWithJobAgent(trimmed, history, targetJobId, activeConversationId, pendingChat.clientMessageId);

    let nextState = { ...state, conversationId: activeConversationId, pendingChat: undefined };
    if (chatRes.conversation_id) nextState.conversationId = chatRes.conversation_id;
    if (chatRes.show_jobs) {
      nextState.contextualSearch = Boolean(chatRes.search_context);
      nextState.searchLabel = chatRes.search_context
        ? [chatRes.search_context.role_label, chatRes.search_context.locations.join(", ") || chatRes.search_context.work_mode].filter(Boolean).join(" in ")
        : undefined;
      nextState.selectedJobId = undefined;
    }
    if (chatRes.updated_profile) {
      nextState = {
        ...nextState,
        fullName: chatRes.updated_profile.full_name ?? nextState.fullName,
        skills: chatRes.updated_profile.skills || nextState.skills,
        preferredLocations: chatRes.updated_profile.preferred_locations || nextState.preferredLocations,
        preferredTitles: chatRes.updated_profile.preferred_titles || nextState.preferredTitles,
        preferredWorkMode: chatRes.updated_profile.preferred_work_mode || nextState.preferredWorkMode,
        experienceYears: chatRes.updated_profile.experience_years ?? nextState.experienceYears,
        experienceProvided: chatRes.updated_profile.experience_provided ?? nextState.experienceProvided,
        profileCompleted: chatRes.updated_profile.profile_completed ?? chatRes.profile_status?.completed ?? nextState.profileCompleted,
      };
    }

    if (chatRes.matched_jobs && chatRes.matched_jobs.length > 0) {
      nextState.feed = chatRes.matched_jobs;
      nextState.feedOffset = chatRes.matched_jobs.length;
      nextState.hasMore = true;
    } else if (chatRes.show_jobs) {
      nextState.feed = [];
      nextState.feedOffset = 0;
      nextState.hasMore = false;
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
        const trustBadge = job.trust_badge ? ` • ${candidateTrustBadge(job)}` : "";
        const matchingSkillsText = job.matching_skills?.length
          ? `\n   • ✅ **Matched:** ${job.matching_skills.slice(0, 4).join(", ")}`
          : (job.skills?.length ? `\n   • 🛠️ **Skills:** ${job.skills.slice(0, 5).join(", ")}` : "");
        const missingSkillsText = job.missing_skills?.length
          ? `\n   • ⚠️ **To Learn:** ${job.missing_skills.slice(0, 3).join(", ")}`
          : "";
        const prepTipText = job.preparation_tips ? `\n   • 💡 **Prep Tip:** ${job.preparation_tips}` : "";
        const expText = (job.experience_min != null || job.experience_max != null)
          ? `\n   • ⏳ **Exp:** ${job.experience_min ?? 0}-${job.experience_max ?? 2} yrs`
          : "\n   • ⏳ **Exp:** Fresher / Entry";
        const salaryText = job.salary_text ? ` | 💰 **Salary:** ${job.salary_text}` : "";
        const safeUrl = safeJobApplyUrl(job.apply_url);
        const applyLabel = job.application_label || "Open application page";
        const applyLink = safeUrl ? `\n   • 🔗 [${applyLabel}](${safeUrl})` : "";
        return `${idx + 1}. **${job.title}** @ **${job.company}**${job.location ? ` (${job.location})` : ""}\n   • ${tierBadge} • **Match ${job.match_score}%**${trustBadge}${expText}${salaryText}${matchingSkillsText}${missingSkillsText}${prepTipText}${applyLink}`;
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
            text: `💡 **You've reached your free daily quota!**\n\nTo discover more verified fresher opportunities or continue chatting with DigiDARA Job Agent, you can top up points on the platform.\n\nTap below to top up your points:`,
            options: [
              { label: "💳 Top Up Points", value: "action:open_billing" },
              { label: "🔙 View My Saved Jobs", value: "Show me my saved jobs" },
            ],
          },
        ],
      };
    }
    // A failed conversation is not consent to search the user's words as a
    // job query. Keep their profile and feed unchanged and surface the error.
    return {
      state: { ...state, pendingChat },
      messages: [{ text: "I couldn't confirm a reply from the Job Agent right now. I haven't searched for jobs. Please resend your message in a moment." }],
    };
  }
}
