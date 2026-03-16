"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { getReportList } from "@/lib/api";
import type { ReportSummary } from "@/lib/types";
import RiskBadge from "@/components/risk-badge";

type FilterLevel = "All" | "Low" | "Medium" | "High" | "Critical";

const TABS: { value: FilterLevel; label: string }[] = [
  { value: "All", label: "全部" },
  { value: "Low", label: "低风险" },
  { value: "Medium", label: "中等" },
  { value: "High", label: "高风险" },
  { value: "Critical", label: "极高" },
];

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function truncate(text: string, max = 80): string {
  return text.length > max ? text.slice(0, max) + "…" : text;
}

function SkeletonRow() {
  return (
    <div
      className="glass-card p-4 flex items-center gap-4"
      style={{ animation: "pulse 2s ease-in-out infinite" }}
      aria-hidden="true"
    >
      <div className="flex-1 flex flex-col gap-2">
        <div className="h-3.5 rounded w-2/3" style={{ background: "rgba(255,255,255,0.06)" }} />
        <div className="h-3 rounded w-full" style={{ background: "rgba(255,255,255,0.04)" }} />
      </div>
      <div className="h-6 w-16 rounded-full shrink-0" style={{ background: "rgba(255,255,255,0.06)" }} />
      <div className="h-3 w-20 rounded shrink-0" style={{ background: "rgba(255,255,255,0.04)" }} />
    </div>
  );
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [filter, setFilter] = useState<FilterLevel>("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const level = filter === "All" ? undefined : filter;
      const data = await getReportList(level);
      setReports(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const isEmpty = !loading && !error && reports.length === 0;

  return (
    <div className="min-h-dvh flex flex-col" style={{ position: "relative" }}>
      {/* Ambient blobs */}
      <div className="ambient-blob ambient-blob-1" aria-hidden="true" />
      <div className="ambient-blob ambient-blob-2" aria-hidden="true" />

      {/* Navbar */}
      <header className="glass-nav sticky top-0 z-50" role="banner">
        <nav className="max-w-3xl mx-auto px-6 h-14 flex items-center justify-between" aria-label="主导航">
          <div className="flex items-center gap-2.5">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span className="text-sm font-semibold tracking-tight" style={{ color: "#fafafa" }}>AI 合规预检</span>
          </div>
          <Link href="/analyze" className="btn-accent px-3 py-1.5 text-xs" style={{ borderRadius: "8px" }}>
            新建评估
          </Link>
        </nav>
      </header>

      <main className="flex-1 relative z-10 max-w-3xl mx-auto w-full px-4 py-10 flex flex-col gap-6" id="main-content">
        {/* Page header */}
        <div className="animate-fadeInUp">
          <h1 className="text-[1.75rem] font-semibold tracking-tight mb-1.5" style={{ color: "#fafafa" }}>
            评估历史
          </h1>
          <p className="text-sm" style={{ color: "#71717a" }}>
            查看所有已生成的合规报告，按创建时间倒序排列
          </p>
        </div>

        {/* Filter tabs */}
        <div
          className="flex items-center gap-1 overflow-x-auto animate-fadeInUp"
          style={{ animationDelay: "60ms", borderBottom: "1px solid var(--border)", paddingBottom: "1px" }}
          role="tablist"
          aria-label="按风险等级筛选"
        >
          {TABS.map((tab) => {
            const active = filter === tab.value;
            return (
              <button
                key={tab.value}
                role="tab"
                aria-selected={active}
                className="px-4 py-2.5 text-sm whitespace-nowrap transition-colors duration-150"
                style={{
                  background: "transparent",
                  color: active ? "#fafafa" : "#71717a",
                  borderBottom: active ? "1px solid rgba(255,255,255,0.7)" : "1px solid transparent",
                  marginBottom: "-1px",
                  cursor: "pointer",
                  fontWeight: active ? 500 : 400,
                }}
                onClick={() => setFilter(tab.value)}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Error state */}
        {error && (
          <div
            className="glass-card p-5 flex items-center gap-3"
            style={{ borderColor: "rgba(248,113,113,0.3)" }}
            role="alert"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <path d="M15 9l-6 6M9 9l6 6" />
            </svg>
            <p className="text-sm flex-1" style={{ color: "#f87171" }}>{error}</p>
            <button
              className="btn-secondary text-xs px-3 py-1.5 shrink-0"
              onClick={fetchReports}
              aria-label="重新加载"
            >
              重试
            </button>
          </div>
        )}

        {/* Skeleton */}
        {loading && (
          <div className="flex flex-col gap-3" aria-label="加载中" aria-busy="true">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {isEmpty && (
          <div
            className="glass-card p-12 flex flex-col items-center gap-5 text-center animate-fadeInUp"
            role="status"
            aria-label="暂无数据"
          >
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center"
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)" }}
              aria-hidden="true"
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#71717a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </div>

            <div>
              <h2 className="text-lg font-semibold mb-2" style={{ color: "#fafafa" }}>
                {filter === "All" ? "暂无评估记录" : `暂无${{ Low: "低", Medium: "中", High: "高", Critical: "极高" }[filter]}风险报告`}
              </h2>
              <p className="text-sm" style={{ color: "#8a8f98" }}>
                {filter === "All"
                  ? "去提交一个 AI 场景，开始你的第一次合规评估"
                  : "当前筛选条件下没有匹配的报告"}
              </p>
            </div>

            <div className="flex items-center gap-3">
              {filter !== "All" && (
                <button
                  className="btn-secondary px-4 py-2 text-sm"
                  onClick={() => setFilter("All")}
                  aria-label="清除筛选"
                >
                  查看全部
                </button>
              )}
              <Link
                href="/analyze"
                className="btn-accent px-5 py-2.5 text-sm inline-flex items-center gap-2"
                aria-label="去提交一个场景"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
                提交一个场景试试
              </Link>
            </div>
          </div>
        )}

        {/* Report list */}
        {!loading && !error && reports.length > 0 && (
          <ul
            className="flex flex-col gap-3 animate-fadeInUp"
            style={{ animationDelay: "80ms" }}
            role="list"
            aria-label="报告列表"
          >
            {reports.map((r, idx) => (
              <li key={r.report_id} style={{ animationDelay: `${idx * 40}ms` }}>
                <Link
                  href={`/reports/${r.report_id}`}
                  className="glass-card p-4 flex items-center gap-4 group block transition-all duration-150 hover:border-opacity-30 cursor-pointer"
                  style={{ textDecoration: "none" }}
                  aria-label={`查看报告 ${r.report_id}，风险等级 ${r.risk_level}`}
                >
                  {/* Left: summary + ID */}
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-sm font-medium mb-1 transition-colors duration-150"
                      style={{ color: "#ededef", lineHeight: 1.6 }}
                    >
                      {truncate(r.summary)}
                    </p>
                    <div className="flex items-center gap-3">
                      <span
                        className="text-xs font-mono"
                        style={{ color: "#4b5563" }}
                      >
                        {r.report_id}
                      </span>
                      <span className="text-xs" style={{ color: "#6b7280" }}>
                        {formatDate(r.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* Right: badge + arrow */}
                  <div className="flex items-center gap-3 shrink-0">
                    <RiskBadge level={r.risk_level} size="sm" />
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="#4b5563"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="transition-all duration-150 group-hover:translate-x-0.5"
                      style={{ color: "#4b5563" }}
                      aria-hidden="true"
                    >
                      <path d="M9 18l6-6-6-6" />
                    </svg>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}

        {/* Record count */}
        {!loading && !error && reports.length > 0 && (
          <p className="text-center text-xs" style={{ color: "#4b5563" }}>
            共 {reports.length} 条记录
            {filter !== "All" && `（已筛选：${TABS.find((t) => t.value === filter)?.label}）`}
          </p>
        )}
      </main>

      <footer
        className="relative z-10 text-center py-6 text-xs"
        style={{ color: "#4b5563", borderTop: "1px solid rgba(255,255,255,0.04)" }}
      >
        <p>本工具仅供参考，不构成正式法律建议。</p>
      </footer>
    </div>
  );
}
