import { useEffect, useState } from "react";
import client from "../api/client";
import PronunciationHistoryDetails from "../components/pronunciation/PronunciationHistoryDetails.jsx";
import SessionResultDashboard from "../components/SessionResultDashboard.jsx";
import { formatScore10 } from "../utils/scoreFormat.js";

export default function History() {
  const [items, setItems] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState("");
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [listError, setListError] = useState("");

  useEffect(() => {
    setItems(null);
    setListError("");
    setExpanded(null);
    setDetail(null);
    client
      .get("/history", {
        params: {
          page,
          per_page: 10,
          type: filter,
        },
      })
      .then((res) => {
        setItems(res.data.items || []);
        setPagination(res.data.pagination || null);
      })
      .catch((err) => {
        setItems([]);
        setPagination(null);
        setListError(err.response?.data?.message || "Could not load history. Please try again.");
      });
  }, [filter, page]);

  const openDetail = async (item) => {
    if (expanded === `${item.type}-${item.id}`) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(`${item.type}-${item.id}`);
    setDetail(null);
    setDetailError("");
    try {
      const res = await client.get(`/history/${item.type}/${item.id}`);
      setDetail(res.data.data?.session || res.data);
    } catch (err) {
      setDetailError(err.response?.data?.message || "Could not load this session. Please try again.");
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <h1 className="text-2xl font-bold text-slate-900">Conversation History</h1>
      <p className="mt-1 text-sm text-slate-500">Review your past speaking and writing sessions.</p>

      <div className="mt-5 flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1 sm:inline-flex">
        {[
          { key: "all", label: "All" },
          { key: "speaking", label: "Speaking" },
          { key: "writing", label: "Writing" },
          { key: "pronunciation", label: "Pronunciation" },
        ].map((item) => (
          <button
            key={item.key}
            onClick={() => {
              setFilter(item.key);
              setPage(1);
            }}
            className={`min-h-10 rounded-lg px-4 py-2 text-sm font-semibold transition ${
              filter === item.key ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-5 space-y-3">
        {items === null && <p className="text-sm text-slate-400">Loading history...</p>}
        {listError && <p className="text-sm font-medium text-red-500">{listError}</p>}
        {items && items.length === 0 && !listError && (
          <p className="text-sm text-slate-400">No sessions here yet. Go complete a practice session.</p>
        )}

        {items?.map((item) => {
          const key = `${item.type}-${item.id}`;
          const isOpen = expanded === key;
          return (
            <div key={key} className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
              <button onClick={() => openDetail(item)} className="flex w-full flex-col gap-3 p-4 text-left sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 break-words">
                  <p className="text-sm font-semibold leading-6 text-slate-800">
                    {item.type === "speaking" ? "Speaking" : item.type === "writing" ? "Writing" : "Pronunciation"}:{" "}
                    {item.topic_title}
                  </p>
                  <p className="mt-0.5 break-words text-xs leading-5 text-slate-400">
                    {item.type === "pronunciation"
                      ? `${item.item_type || "Practice"} - ${item.match_percentage ?? 0}% match - Attempt ${item.attempt_number}`
                      : item.mode === "topic"
                      ? "Topic-wise"
                      : "Daily conversation"}{" "}
                    {item.mode === "topic" ? `- ${item.difficulty} - ` : "- "}
                    {new Date(item.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex shrink-0 items-center justify-between gap-3 sm:justify-end">
                  <span className="text-base font-bold text-slate-700">{formatScore10(item.overall_score)}</span>
                  <span className="text-slate-300">{isOpen ? "▲" : "▼"}</span>
                </div>
              </button>

              {isOpen && detail && (
                <div className="border-t border-slate-100 p-4">
                  {item.type === "pronunciation" ? (
                    <PronunciationHistoryDetails detail={detail} />
                  ) : (
                    <SessionResultDashboard session={{ ...detail, type: item.type }} type={item.type} showActions={false} embedded />
                  )}
                </div>
              )}
              {isOpen && !detail && !detailError && (
                <div className="border-t border-slate-100 p-4 text-sm text-slate-400">Loading session details...</div>
              )}
              {isOpen && detailError && (
                <div className="border-t border-slate-100 p-4 text-sm font-medium text-red-500">{detailError}</div>
              )}
            </div>
          );
        })}
      </div>

      {pagination && pagination.total > 0 && (
        <div className="mt-5 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs font-semibold text-slate-500">
            Page {pagination.page} of {pagination.pages} - {pagination.total} sessions
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              disabled={!pagination.has_prev}
              className="min-h-10 rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((value) => value + 1)}
              disabled={!pagination.has_next}
              className="min-h-10 rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
