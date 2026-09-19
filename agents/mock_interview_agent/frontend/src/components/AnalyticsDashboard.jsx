import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  getAnalyticsDaily,
  getAnalyticsInterviews,
  getAnalyticsMonthly,
  getAnalyticsQuestions,
  getAnalyticsRecent,
  getAnalyticsSummary,
  getAnalyticsTokenBreakdown,
} from "../api";
import { reportClientError } from "../utils/clientLogger";
import EmptyState from "./ui/EmptyState";
import SectionCard from "./ui/SectionCard";
import Skeleton, { SkeletonStack } from "./ui/Skeleton";
import StatBox from "./ui/StatBox";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 4 });
const integer = new Intl.NumberFormat("en-US");

function LineChart({ data, valueKey, label }) {
  if (!data.length) return <p className="subtle">No usage data in this period.</p>;
  const width = 620;
  const height = 210;
  const padding = 28;
  const values = data.map((item) => Number(item[valueKey]) || 0);
  const maximum = Math.max(...values, 1);
  const x = (index) => padding + (data.length === 1 ? (width - padding * 2) / 2 : index * (width - padding * 2) / (data.length - 1));
  const y = (value) => height - padding - value / maximum * (height - padding * 2);
  const points = values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
  return <svg className="analytics-line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}><title>{label}</title><line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="analytics-axis" /><polyline points={points} fill="none" className="analytics-line" />{data.map((item, index) => <circle key={item.date} cx={x(index)} cy={y(values[index])} r="4" className="analytics-point"><title>{`${item.date}: ${valueKey === "estimated_cost" ? usd.format(values[index]) : integer.format(values[index])}`}</title></circle>)}</svg>;
}

function TokenBreakdown({ data }) {
  const prompt = Number(data?.prompt_tokens) || 0;
  const completion = Number(data?.completion_tokens) || 0;
  const total = prompt + completion;
  const promptPct = total ? Math.round(prompt / total * 100) : 0;
  return <div className="token-breakdown"><div className="token-donut" style={{ background: `conic-gradient(#2563eb 0 ${promptPct}%, #8b5cf6 ${promptPct}% 100%)` }} aria-label={`Prompt tokens ${prompt}, completion tokens ${completion}`}><span>{integer.format(total)}</span><small>tokens</small></div><div className="token-legend"><span><i className="prompt-swatch" />Prompt <strong>{integer.format(prompt)}</strong></span><span><i className="completion-swatch" />Completion <strong>{integer.format(completion)}</strong></span></div></div>;
}

function Table({ title, columns, rows, empty }) {
  return <SectionCard className="analytics-table-card" title={title}>{rows.length ? <div className="analytics-table-scroll"><table className="analytics-table"><thead><tr>{columns.map((column) => <th key={column.label}>{column.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={row.id || row.interview_id || row.question_id || index}>{columns.map((column) => <td key={column.label}>{column.value(row)}</td>)}</tr>)}</tbody></table></div> : <p className="subtle">{empty}</p>}</SectionCard>;
}

export default function AnalyticsDashboard({ studentId }) {
  const [filters, setFilters] = useState({});
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const fetchAnalytics = useCallback(async () => {
    const [summary, daily, monthly, breakdown, interviews, questions, recent] = await Promise.all([
      getAnalyticsSummary(studentId, filters), getAnalyticsDaily(studentId, filters), getAnalyticsMonthly(studentId, filters), getAnalyticsTokenBreakdown(studentId, filters), getAnalyticsInterviews(studentId, filters), getAnalyticsQuestions(studentId, filters), getAnalyticsRecent(studentId, filters),
    ]);
    return { summary, daily, monthly, breakdown, interviews, questions, recent };
  }, [studentId, filters]);
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAnalytics());
    } catch (requestError) {
      reportClientError("analytics_load_failed", requestError, { student_id: studentId });
      setError(requestError.message || "Unable to load AI usage analytics. Please try again.");
    } finally { setLoading(false); }
  }, [fetchAnalytics, studentId]);
  useEffect(() => {
    let isMounted = true;
    fetchAnalytics()
      .then((analyticsData) => { if (isMounted) setData(analyticsData); })
      .catch((requestError) => {
        reportClientError("analytics_load_failed", requestError, { student_id: studentId });
        if (isMounted) setError(requestError.message || "Unable to load AI usage analytics. Please try again.");
      })
      .finally(() => { if (isMounted) setLoading(false); });
    return () => { isMounted = false; };
  }, [fetchAnalytics, studentId]);
  const rangeLabel = useMemo(() => data?.summary?.range ? `${data.summary.range.start_date} to ${data.summary.range.end_date}` : "Last 30 days", [data]);
  if (loading) return <div className="page analytics-page"><div className="stat-grid dashboard-stat-grid">{Array.from({ length: 7 }, (_, index) => <Skeleton key={index} className="stat-skeleton" />)}</div><SkeletonStack rows={5} /></div>;
  if (error) return <div className="page analytics-page"><SectionCard className="dashboard-state dashboard-error"><p className="error-text" role="alert">{error}</p><button className="secondary-btn" onClick={load}>Retry</button></SectionCard></div>;
  const summary = data.summary.summary;
  const today = data.summary.today;
  const hasUsage = Number(summary.total_requests) > 0;
  return <div className="page analytics-page"><section className="analytics-hero"><div><p className="eyebrow">AI billing and analytics</p><h2>Usage you can understand</h2><p>Provider-reported token usage and estimated API cost for {rangeLabel}.</p></div><div className="analytics-filters"><label>From<input type="date" value={filters.start_date || ""} onChange={(event) => setFilters((current) => ({ ...current, start_date: event.target.value }))} /></label><label>To<input type="date" value={filters.end_date || ""} onChange={(event) => setFilters((current) => ({ ...current, end_date: event.target.value }))} /></label><button className="secondary-btn compact-btn" onClick={() => setFilters({})}>Last 30 days</button></div></section><div className="stat-grid dashboard-stat-grid"><StatBox value={summary.total_interviews} label="Total Interviews" /><StatBox value={integer.format(summary.total_requests)} label="AI Requests" /><StatBox value={integer.format(summary.total_tokens)} label="Total Tokens" /><StatBox value={usd.format(summary.estimated_cost)} label="Estimated Cost" /><StatBox value={integer.format(today.tokens)} label="Today's Tokens" /><StatBox value={usd.format(today.estimated_cost)} label="Today's Cost" /><StatBox value={today.interviews} label="Today's Interviews" /></div>{!hasUsage ? <EmptyState title="No AI usage yet" message="Complete an interview to see provider-reported token usage and cost estimates here." /> : <><div className="analytics-chart-grid"><SectionCard title="Token Breakdown" subtitle="Prompt versus completion tokens."><TokenBreakdown data={data.breakdown} /></SectionCard><SectionCard title="Daily Token Usage" subtitle="Provider-reported tokens by day."><LineChart data={data.daily.items} valueKey="total_tokens" label="Daily token usage" /></SectionCard><SectionCard title="Daily Cost Trend" subtitle="Estimated API cost by day."><LineChart data={data.daily.items} valueKey="estimated_cost" label="Daily estimated cost" /></SectionCard></div><Table title="Interview Analytics" empty="No interviews in this period." rows={data.interviews.items} columns={[{ label: "Interview", value: (row) => row.subject || (row.round_type === "hr" ? "HR" : "Interview") }, { label: "Tokens", value: (row) => integer.format(row.total_tokens) }, { label: "Cost", value: (row) => usd.format(row.estimated_cost) }, { label: "Questions", value: (row) => row.questions }, { label: "Duration", value: (row) => row.duration_seconds ? `${row.duration_seconds}s` : "—" }]} /><Table title="Question Analytics" empty="No question usage in this period." rows={data.questions.items} columns={[{ label: "Question", value: (row) => row.question }, { label: "Prompt", value: (row) => integer.format(row.prompt_tokens) }, { label: "Completion", value: (row) => integer.format(row.completion_tokens) }, { label: "Total", value: (row) => integer.format(row.total_tokens) }, { label: "Cost", value: (row) => usd.format(row.estimated_cost) }]} /><div className="analytics-chart-grid"><Table title="Recent AI Requests" empty="No requests in this period." rows={data.recent.items} columns={[{ label: "Time", value: (row) => row.created_at?.replace("T", " ") || "—" }, { label: "Request", value: (row) => row.request_type }, { label: "Model", value: (row) => row.model_name }, { label: "Tokens", value: (row) => integer.format(row.total_tokens) }, { label: "Cost", value: (row) => usd.format(row.estimated_cost) }]} /><Table title="Monthly Summary" empty="No monthly usage yet." rows={data.monthly.items} columns={[{ label: "Month", value: (row) => row.month }, { label: "Interviews", value: (row) => row.interviews }, { label: "Tokens", value: (row) => integer.format(row.total_tokens) }, { label: "Cost", value: (row) => usd.format(row.estimated_cost) }, { label: "Avg / Interview", value: (row) => integer.format(row.average_tokens_per_interview) }]} /></div></>}</div>;
}
