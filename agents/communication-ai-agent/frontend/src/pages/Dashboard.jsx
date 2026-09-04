import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, Award, BookOpenCheck, CalendarCheck2, CheckCircle2, Circle, History,
  Lightbulb, Mic2, PenLine, Sparkles, Target, TrendingUp,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import client from "../api/client";
import ScoreRing from "../components/ScoreRing.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { formatScore10, formatScoreNumber, scoreToTen } from "../utils/scoreFormat.js";

const SKILLS = [
  { key: "speaking", label: "Speaking", route: "/speaking", icon: Mic2, color: "#6366f1", caption: "Conversation confidence" },
  { key: "writing", label: "Writing", route: "/writing", icon: PenLine, color: "#0284c7", caption: "Clear written answers" },
  { key: "pronunciation", label: "Pronunciation", route: "/pronunciation", icon: Target, color: "#059669", caption: "Speech match and clarity" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [progressData, setProgressData] = useState({
    pronunciation: [],
    speaking: [],
    writing: [],
  });
  const [focusAreas, setFocusAreas] = useState([]);
  const [streak, setStreak] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const firstName = user?.name?.split(" ")[0] || "Learner";

  useEffect(() => {
    Promise.all([
      client.get("/dashboard"),
      client.get("/pronunciation/progress").catch(() => ({ data: { progress: [] } })),
      client.get("/speaking/progress").catch(() => ({ data: { progress: [] } })),
      client.get("/writing/progress").catch(() => ({ data: { progress: [] } })),
      client.get("/writing/insights").catch(() => ({ data: { weak_areas: [] } })),
      client.get("/pronunciation/insights").catch(() => ({ data: { insights: [] } })),
      client.get("/pronunciation/streak").catch(() => ({ data: { streak_count: 0 } })),
      client.get("/daily-challenges/today").catch(() => ({ data: null })),
    ])
      .then(([dashRes, pronunciationProgRes, speakingProgRes, writingProgRes, writingInsightsRes, pronunciationInsightsRes, streakRes, dailyChallengeRes]) => {
        setData(normalizeDashboard(dashRes.data, dailyChallengeRes.data));
        setProgressData({
          pronunciation: pronunciationProgRes.data?.progress || [],
          speaking: speakingProgRes.data?.progress || [],
          writing: writingProgRes.data?.progress || [],
        });
        setFocusAreas(normalizeFocusAreas(writingInsightsRes.data, pronunciationInsightsRes.data));
        setStreak(Number(streakRes.data?.streak_count) || 0);
      })
      .catch(() => setError("Dashboard data is unavailable. Confirm the backend and MySQL are running, then refresh."))
      .finally(() => setLoading(false));
  }, []);

  const skillRows = useMemo(() => buildSkillRows(data), [data]);
  const bestSkill = data?.best_skill || (skillRows.length ? skillRows.reduce((best, item) => (item.score > best.score ? item : best), skillRows[0]) : null);
  const needsWork = data?.needs_work || (skillRows.length > 1 ? skillRows.reduce((lowest, item) => (item.score < lowest.score ? item : lowest), skillRows[0]) : null);
  const hasAnySessions = (data?.sessions_completed || 0) > 0;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white p-5 shadow-soft sm:p-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-brand-100 bg-brand-50 px-3 py-1 text-xs font-bold text-brand-700">
                <Sparkles className="h-3.5 w-3.5" /> AI learning hub
              </span>
              {streak > 0 && (
                <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-700">
                  <CalendarCheck2 className="h-3.5 w-3.5" /> {streak}-day streak
                </span>
              )}
            </div>
            <h1>Hi {firstName}, ready to practise?</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
              See your speaking, writing and pronunciation progress in one place, then choose the next activity that helps most.
            </p>
          </div>
          {!hasAnySessions && !loading && (
            <div className="rounded-2xl border border-sky-100 bg-sky-50 p-4 text-sm font-semibold text-sky-800 lg:w-[320px]">
              Start your first practice below. Your scores, focus areas and progress chart will appear here after you complete activities.
            </div>
          )}
        </div>
      </section>

      {loading ? (
        <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 text-sm font-semibold text-slate-500 shadow-soft">
          Loading your dashboard...
        </div>
      ) : error || !data ? (
        <div className="mt-6 rounded-3xl border border-amber-200 bg-amber-50 p-5 text-sm font-medium text-amber-800">
          {error || "Dashboard data is unavailable. Confirm the backend and MySQL are running, then refresh."}
        </div>
      ) : (
        <>
          <section className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard title="Overall Score" icon={<TrendingUp className="h-5 w-5" />}>
              <div className="flex items-center gap-4">
                <ScoreRing score={data.overall_score} size={72} stroke={7} />
                <p className="text-sm leading-6 text-slate-500">Average across completed modules.</p>
              </div>
            </StatCard>
            <StatCard title="Sessions Completed" icon={<BookOpenCheck className="h-5 w-5" />}>
              <p className="text-4xl font-bold text-slate-900">{data.sessions_completed}</p>
              <p className="mt-1 text-sm text-slate-500">Speaking + Writing + Pronunciation</p>
            </StatCard>
            <StatCard title="Best Skill" icon={<Award className="h-5 w-5" />}>
              <SkillCallout item={bestSkill} kind="best" empty="Complete a session to find your strongest skill." />
            </StatCard>
            <StatCard title="Needs Work" icon={<Lightbulb className="h-5 w-5" />}>
              <SkillCallout item={needsWork} kind="needs_work" empty="Complete a session to see what to practise next." />
            </StatCard>
          </section>

          {data.today_communication_challenge && (
            <TodayCommunicationChallengeCard challenge={data.today_communication_challenge} />
          )}

          <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
              <div className="mb-4">
                <h2 className="text-lg font-bold text-slate-900">Skill comparison</h2>
                <p className="text-sm text-slate-500">Averages from completed practice sessions.</p>
              </div>
              {skillRows.length > 0 ? (
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={skillRows} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                      <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} />
                      <YAxis domain={[0, 10]} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} />
                      <Tooltip
                        formatter={(value) => [`${Number(value).toFixed(1)} / 10`, "Average"]}
                        contentStyle={{ borderRadius: "14px", border: "1px solid #e2e8f0", boxShadow: "0 12px 30px rgba(30,41,59,.12)" }}
                      />
                      <Bar dataKey="score" radius={[12, 12, 0, 0]} fill="#6366f1" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyPanel>Start your first practice below to unlock your skill comparison.</EmptyPanel>
              )}
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
              <div className="mb-4">
                <h2 className="text-lg font-bold text-slate-900">Focus areas</h2>
                <p className="text-sm text-slate-500">Based on available evaluated writing and pronunciation insight data.</p>
              </div>
              {focusAreas.length > 0 ? (
                <div className="space-y-3">
                  {focusAreas.map((area) => (
                    <div key={`${area.module}-${area.tag}`} className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-bold text-slate-800">{area.tag}</p>
                          <p className="mt-0.5 text-xs text-slate-500">{area.module}</p>
                        </div>
                        <span className="learning-badge">{area.count}x</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyPanel>No focus-area patterns yet. They will appear after evaluated writing or pronunciation attempts.</EmptyPanel>
              )}
            </div>
          </section>

          <section className="mt-6">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Continue practising</h2>
                <p className="text-sm text-slate-500">Choose a module and keep your learning loop moving.</p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {SKILLS.map((skill) => (
                <PracticeCard key={skill.key} skill={skill} data={data} />
              ))}
            </div>
          </section>

          <section className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <ProgressTrendChart
              title="Pronunciation progress trend"
              average={data.pronunciation_average}
              completed={data.pronunciation_completed}
              best={data.pronunciation_best}
              progress={progressData.pronunciation}
              route="/pronunciation"
              emptyText="Complete a pronunciation item to start seeing progress here."
            />
            <ProgressTrendChart
              title="Speaking progress trend"
              average={data.speaking_average}
              completed={data.speaking_completed}
              best={data.speaking_best}
              progress={progressData.speaking}
              route="/speaking"
              emptyText="Complete a speaking session to start seeing progress here."
            />
            <ProgressTrendChart
              title="Writing progress trend"
              average={data.writing_average}
              completed={data.writing_completed}
              best={data.writing_best}
              progress={progressData.writing}
              route="/writing"
              emptyText="Complete a writing session to start seeing progress here."
            />
            <RecentActivityCard data={data} />
          </section>
        </>
      )}
    </div>
  );
}

function ProgressTrendChart({ title, average, completed, best, progress, route, emptyText }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-bold text-slate-900">{title}</p>
          <p className="mt-1 text-xs text-slate-500">
            Average: {formatScore10(average)} | Completed: {completed} | Best: {formatScore10(best)}
          </p>
        </div>
        <Link to={route} className="min-h-11 rounded-xl bg-brand-600 px-4 py-2.5 text-center text-sm font-bold text-white">
          Continue Practice
        </Link>
      </div>

      {progress.length > 0 ? (
        <div className="mt-6 h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={progress}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} dy={10} />
              <YAxis domain={[0, 10]} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} dx={-10} />
              <Tooltip
                contentStyle={{ borderRadius: "14px", border: "1px solid #e2e8f0", boxShadow: "0 12px 30px rgba(30,41,59,.12)" }}
                labelStyle={{ fontWeight: "bold", color: "#0F172A", marginBottom: "4px" }}
                itemStyle={{ color: "#4f46e5", fontWeight: "bold" }}
              />
              <Line type="monotone" dataKey="average_score" stroke="#4f46e5" strokeWidth={3} dot={{ r: 4, fill: "#4f46e5", strokeWidth: 0 }} activeDot={{ r: 6, strokeWidth: 0 }} name="Score" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="mt-6 rounded-2xl bg-slate-50 p-4 text-sm text-slate-500">{emptyText}</p>
      )}
    </div>
  );
}

function TodayCommunicationChallengeCard({ challenge }) {
  const activities = Array.isArray(challenge?.activities) ? challenge.activities : [];
  const completed = Number(challenge?.completed_count || 0);
  const total = Number(challenge?.total_count || activities.length || 3);
  const progressPercent = total > 0 ? Math.round((completed / total) * 100) : 0;
  const challengeDate = challenge?.challenge_date
    ? new Date(`${challenge.challenge_date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
    : "Today";

  return (
    <section className="mt-6 rounded-3xl border border-brand-100 bg-brand-50 p-5 shadow-soft">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-600">Today's Required Communication Challenges</p>
          <h2 className="mt-1 text-xl font-extrabold text-slate-900">{completed}/{total} completed</h2>
          <p className="mt-1 text-sm text-slate-600">
            {challengeDate} - Complete Daily Speaking Challenge, Daily Writing Challenge and Daily Pronunciation Challenge once today to maintain your streak and earn the {challenge.daily_bonus_xp || 20} XP completion bonus.
          </p>
        </div>
        <span className={`inline-flex min-h-10 items-center rounded-xl px-4 py-2 text-sm font-bold ${challenge.all_completed ? "bg-emerald-100 text-emerald-700" : "bg-white text-brand-700"}`}>
          {challenge.all_completed ? "Daily challenge complete" : `${progressPercent}% complete`}
        </span>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white" aria-label={`${completed} of ${total} daily activities completed`}>
        <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${progressPercent}%` }} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        {activities.map((activity) => (
          <div key={activity.activity_type} className="rounded-2xl border border-brand-100 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex gap-3">
                <span className={`mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${activity.status === "completed" ? "bg-emerald-50 text-emerald-700" : activity.status === "in_progress" ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-500"}`} aria-hidden="true">
                  {activity.status === "completed" ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
                </span>
                <div>
                  <p className="text-sm font-bold text-slate-900">{activity.title}</p>
                  <p className="mt-1 text-xs font-semibold capitalize text-slate-500">
                    {activity.module} - Required today - {activity.xp_reward} XP
                  </p>
                </div>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold capitalize ${activity.status === "completed" ? "bg-emerald-50 text-emerald-700" : activity.status === "in_progress" ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
                {String(activity.status || "not_started").replace("_", " ")}
              </span>
            </div>
            <Link to={activity.route || "/"} aria-label={`${dailyActionLabel(activity.status)} ${activity.title}`} className={`mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl px-3 py-2 text-sm font-bold transition ${activity.status === "completed" ? "bg-emerald-600 text-white hover:bg-emerald-700" : "bg-brand-600 text-white hover:bg-brand-700"}`}>
              {dailyActionLabel(activity.status)}
            </Link>
          </div>
        ))}
      </div>

      <div className={`mt-4 rounded-2xl border p-4 text-sm font-semibold ${challenge.all_completed ? "border-emerald-100 bg-emerald-50 text-emerald-800" : "border-amber-100 bg-amber-50 text-amber-800"}`}>
        {challenge.all_completed
          ? `Daily challenge completed! +${challenge.bonus_xp_awarded || challenge.daily_bonus_xp || 20} bonus XP. Your streak is maintained${challenge.streak_count ? ` (${challenge.streak_count}-day streak)` : ""}.`
          : `Complete all three to maintain your streak. ${completed}/${total} finished today.`}
      </div>
    </section>
  );
}

function dailyActionLabel(status) {
  if (status === "completed") return "Review";
  if (status === "in_progress") return "Continue";
  return "Start";
}

function StatCard({ title, icon, children }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="mb-4 flex items-center gap-2">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-700">{icon}</span>
        <p className="text-sm font-bold text-slate-900">{title}</p>
      </div>
      {children}
    </div>
  );
}

function SkillCallout({ item, kind, empty }) {
  if (!item) return <p className="text-sm leading-6 text-slate-500">{empty}</p>;
  if (item.status === "no_data") return <p className="text-sm leading-6 text-slate-500">{item.label}</p>;
  if (item.status === "insufficient_data") {
    return (
      <div>
        <p className="text-2xl font-bold text-slate-900">{item.label}</p>
        <p className="mt-1 text-sm leading-6 text-slate-500">Complete Speaking and Writing sessions to identify a focus area.</p>
      </div>
    );
  }
  if (item.status === "tied") {
    return (
      <div>
        <p className="text-2xl font-bold text-slate-900">{item.label}</p>
        <p className="mt-1 text-sm leading-6 text-slate-500">Your available skill averages are tied at {formatScoreNumber(item.average)} / 10.</p>
      </div>
    );
  }
  return (
    <div>
      <p className="text-2xl font-bold text-slate-900">{item.label}</p>
      <p className="mt-1 text-sm text-slate-500">{formatScoreNumber(item.average ?? item.score)} / 10 average - {item.completed || 0} completed</p>
      {kind === "needs_work" && <Link to={`/${item.key}`} className="mt-2 inline-flex text-xs font-bold text-brand-700 hover:underline">Complete another {item.label} practice session <ArrowRight className="ml-1 h-3.5 w-3.5" /></Link>}
      {kind === "best" && <p className="mt-2 text-xs font-semibold text-emerald-700">Keep building on this strength.</p>}
    </div>
  );
}

function PracticeCard({ skill, data }) {
  const Icon = skill.icon;
  const average = data?.[`${skill.key}_average`];
  const best = data?.[`${skill.key}_best`];
  return (
    <Link to={skill.route} className="learning-card">
      <div>
        <div className="flex items-start justify-between gap-3">
          <span className="learning-card-icon"><Icon className="h-5 w-5" /></span>
          <span className="learning-badge">Avg {formatScore10(average)}</span>
        </div>
        <h3 className="mt-4 text-base font-bold text-slate-900">{skill.label}</h3>
        <p className="mt-2 text-sm leading-6 text-slate-500">{skill.caption}</p>
        {best != null && <p className="mt-3 text-xs font-bold text-emerald-700">Best: {formatScore10(best)}</p>}
      </div>
      <span className="mt-5 inline-flex items-center gap-1 text-sm font-bold text-brand-700">
        Continue <ArrowRight className="h-4 w-4" />
      </span>
    </Link>
  );
}

function RecentActivityCard({ data }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-bold text-slate-900">Recent activity</p>
        <Link to="/history" className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline">
          View all <History className="h-3.5 w-3.5" />
        </Link>
      </div>
      {data.recent_activity.length === 0 ? (
        <p className="text-sm text-slate-500">No sessions yet. Start your first practice above.</p>
      ) : (
        <div className="space-y-3">
          {data.recent_activity.slice(0, 5).map((item) => (
            <div key={`${item.type}-${item.id}`} className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words text-sm font-bold text-slate-800">
                    {item.type === "speaking" ? (item.mode === "daily_conversation" ? "Daily Speaking Challenge" : "Speaking") : item.type === "writing" ? "Writing" : "Pronunciation"}
                  </p>
                  <p className="mt-0.5 break-words text-xs leading-5 text-slate-500">{item.topic_title}</p>
                </div>
                <span className="shrink-0 text-xs font-bold text-brand-700">{formatScore10(item.overall_score)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyPanel({ children }) {
  return <p className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-500">{children}</p>;
}

function buildSkillRows(data) {
  if (!data) return [];
  return SKILLS.map((skill) => ({
    ...skill,
    score: scoreToTen(data[`${skill.key}_average`]),
  })).filter((skill) => skill.score != null);
}

function normalizeFocusAreas(writingData, pronunciationData) {
  const writing = (writingData?.weak_areas || []).map((item) => ({
    module: "Writing",
    tag: item.tag,
    count: item.count ?? 1,
  }));
  const pronunciation = (pronunciationData?.insights || []).map((item) => ({
    module: "Pronunciation",
    tag: item.tag,
    count: item.count ?? 1,
  }));
  return [...writing, ...pronunciation]
    .filter((item) => item.tag)
    .sort((a, b) => Number(b.count || 0) - Number(a.count || 0))
    .slice(0, 6);
}

function normalizeDashboard(payload, dailyChallengePayload = null) {
  const data = payload.data || payload;
  return {
    sessions_completed: toCount(data.sessions_completed),
    overall_score: toNullableScore(data.overall_score),
    speaking_average: toNullableScore(data.speaking_average),
    speaking_completed: toCount(data.speaking_completed),
    speaking_best: toNullableScore(data.speaking_best),
    writing_average: toNullableScore(data.writing_average),
    writing_completed: toCount(data.writing_completed),
    writing_best: toNullableScore(data.writing_best),
    pronunciation_average: toNullableScore(data.pronunciation_average),
    pronunciation_completed: toCount(data.pronunciation_completed),
    pronunciation_best: toNullableScore(data.pronunciation_best),
    best_skill: normalizeSelection(data.best_skill),
    needs_work: normalizeSelection(data.needs_work),
    pronunciation_daily_ready: Boolean(data.pronunciation_daily_ready),
    today_communication_challenge: dailyChallengePayload || data.today_communication_challenge || null,
    recent_activity: data.recent_activity ?? data.recentActivities ?? [],
  };
}

function toNullableScore(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 && number <= 100 ? scoreToTen(number) : null;
}

function toCount(value) {
  const number = Number(value);
  return Number.isInteger(number) && number >= 0 ? number : 0;
}

function normalizeSelection(value) {
  if (!value || typeof value !== "object") return null;
  return {
    key: value.key ?? null,
    label: value.label || "No data yet",
    average: toNullableScore(value.average),
    completed: toCount(value.completed),
    status: value.status || "available",
  };
}
