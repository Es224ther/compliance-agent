"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getReport } from "@/lib/api";
import type { AuditReport } from "@/lib/types";
import ReportViewer from "@/components/report-viewer";
import CitationPanel from "@/components/citation-panel";
import RiskBadge from "@/components/risk-badge";

function ExportIcon({ path }: { path: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function buildMarkdown(report: AuditReport): string {
  const lines: string[] = [
    `# 合规报告 ${report.report_id}`,
    `\n**风险等级：** ${report.risk_level}`,
    `**生成时间：** ${new Date(report.created_at).toLocaleString("zh-CN")}`,
    `\n## 场景摘要\n\n${report.summary}`,
    `\n## 风险概述\n\n${report.risk_overview}`,
  ];

  if (report.uncertainties.length > 0) {
    lines.push(`\n## 不确定项\n`);
    report.uncertainties.forEach((u, i) => lines.push(`${i + 1}. ${u}`));
  }

  if (report.remediation_actions.length > 0) {
    lines.push(`\n## 整改建议\n`);
    report.remediation_actions.forEach((rem) => {
      lines.push(`### ${rem.role}\n`);
      (rem.actions ?? (rem.action ? [rem.action] : [])).forEach((a) => lines.push(`- ${a}`));
    });
  }

  if (report.evidence_citations.length > 0) {
    lines.push(`\n## 法规引用\n`);
    report.evidence_citations.forEach((c) => {
      const article = c.article_id || c.article || "条款未标注";
      const chapter = c.chapter || "章节未标注";
      const excerpt = c.text_excerpt || c.text || c.summary || "暂无摘录";
      const score = Number(c.relevance_score ?? c.rerank_score ?? 0);
      const safeScore = Number.isFinite(score) ? Math.max(0, Math.min(1, score)) : 0;
      lines.push(`### ${c.regulation} ${article}`);
      lines.push(`*${chapter}*\n`);
      lines.push(`> ${excerpt}`);
      lines.push(`\n相关度：${safeScore.toFixed(2)}\n`);
    });
  }

  lines.push(`\n---\n\n${report.disclaimer}`);
  return lines.join("\n");
}

export default function ReportDetailPage() {
  const params = useParams<{ id: string }>();
  const id = typeof params?.id === "string" ? params.id : "";
  const [report, setReport] = useState<AuditReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const loading = id ? isLoading : false;
  const viewError = id ? error : "无效的报告 ID";

  useEffect(() => {
    if (!id) return;
    getReport(id)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"))
      .finally(() => setIsLoading(false));
  }, [id]);

  function handleExportMarkdown() {
    if (!report) return;
    downloadBlob(buildMarkdown(report), `report-${report.report_id}.md`, "text/markdown");
  }

  function handleExportJson() {
    if (!report) return;
    downloadBlob(JSON.stringify(report, null, 2), `report-${report.report_id}.json`, "application/json");
  }

  async function handleCopyLink() {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="min-h-dvh flex flex-col" style={{ position: "relative" }}>
      {/* Ambient blobs */}
      <div className="ambient-blob ambient-blob-1" aria-hidden="true" />
      <div className="ambient-blob ambient-blob-2" aria-hidden="true" />

      {/* Navbar */}
      <header className="glass-nav sticky top-0 z-50" role="banner">
        <nav className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between" aria-label="主导航">
          <div className="flex items-center gap-3">
            <Link
              href="/reports"
              className="flex items-center gap-1.5 text-sm transition-colors duration-150 hover:text-white"
              style={{ color: "#8a8f98" }}
              aria-label="返回历史记录"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M19 12H5M12 5l-7 7 7 7" />
              </svg>
              返回历史
            </Link>

            {report && (
              <>
                <span style={{ color: "#374151" }} aria-hidden="true">/</span>
                <span className="text-sm font-medium font-mono truncate max-w-[200px]" style={{ color: "#ededef" }}>
                  {report.report_id}
                </span>
              </>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/analyze"
              className="btn-secondary px-3 py-1.5 text-sm flex items-center gap-1.5"
              aria-label="新建评估"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 5v14M5 12h14" />
              </svg>
              新建评估
            </Link>
          </div>
        </nav>
      </header>

      <main className="flex-1 relative z-10 max-w-7xl mx-auto w-full px-4 py-8" id="main-content">
        {/* Loading skeleton */}
        {loading && (
          <div className="flex flex-col gap-4" aria-label="加载中" aria-busy="true">
            {[240, 180, 320].map((h, i) => (
              <div
                key={i}
                className="glass-card"
                style={{ height: h, background: "rgba(255,255,255,0.03)", animation: "pulse 2s ease-in-out infinite" }}
              />
            ))}
          </div>
        )}

        {/* Error state */}
        {viewError && !loading && (
          <div
            className="glass-card p-8 flex flex-col items-center gap-4 text-center max-w-lg mx-auto mt-12"
            style={{ borderColor: "rgba(248,113,113,0.3)" }}
            role="alert"
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <path d="M15 9l-6 6M9 9l6 6" />
            </svg>
            <div>
              <h2 className="text-lg font-semibold mb-1" style={{ color: "#f87171" }}>报告加载失败</h2>
              <p className="text-sm" style={{ color: "#8a8f98" }}>{viewError}</p>
            </div>
            <Link href="/reports" className="btn-secondary px-4 py-2 text-sm">返回列表</Link>
          </div>
        )}

        {/* Report content */}
        {report && !loading && (
          <div className="flex flex-col gap-6">
            {/* Page header */}
            <div className="flex items-start justify-between gap-4 flex-wrap animate-fadeInUp">
              <div>
                <h1 className="text-xl font-bold mb-2" style={{ color: "#ededef" }}>
                  合规报告
                </h1>
                <div className="flex items-center gap-3 flex-wrap">
                  <RiskBadge level={report.risk_level} />
                  <span className="text-xs" style={{ color: "#8a8f98" }}>
                    {new Date(report.created_at).toLocaleString("zh-CN")}
                  </span>
                  <span className="text-xs font-mono" style={{ color: "#4b5563" }}>
                    {report.report_id}
                  </span>
                </div>
              </div>

              {/* Export actions */}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  className="btn-secondary px-3 py-2 text-xs flex items-center gap-1.5"
                  onClick={handleExportMarkdown}
                  aria-label="导出 Markdown 文件"
                >
                  <ExportIcon path="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8" />
                  导出 Markdown
                </button>
                <button
                  className="btn-secondary px-3 py-2 text-xs flex items-center gap-1.5"
                  onClick={handleExportJson}
                  aria-label="导出 JSON 文件"
                >
                  <ExportIcon path="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  导出 JSON
                </button>
                <button
                  className="btn-secondary px-3 py-2 text-xs flex items-center gap-1.5"
                  onClick={handleCopyLink}
                  aria-label="复制页面链接"
                  aria-live="polite"
                >
                  {copied ? (
                    <>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                      <span style={{ color: "#4ade80" }}>已复制</span>
                    </>
                  ) : (
                    <>
                      <ExportIcon path="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                      复制链接
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Two-column layout */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5 items-start">
              {/* Left: report sections */}
              <div>
                <ReportViewer report={report} />
              </div>

              {/* Right: citation panel (sticky on large screens) */}
              <aside
                className="lg:sticky lg:top-24"
                aria-label="法规引用面板"
              >
                <CitationPanel citations={report.evidence_citations} />
              </aside>
            </div>
          </div>
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
