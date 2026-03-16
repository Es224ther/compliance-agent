"use client";

import { useState } from "react";
import type { EvidenceChunk } from "@/lib/types";

interface CitationPanelProps {
  citations: EvidenceChunk[];
}

function CitationItem({ chunk, index }: { chunk: EvidenceChunk; index: number }) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(chunk.relevance_score * 100);

  const scoreColor =
    pct >= 85 ? "#4ade80" : pct >= 70 ? "#facc15" : "#fb923c";

  return (
    <div
      className="glass-card overflow-hidden"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <button
        className="w-full text-left px-4 py-3 flex items-start gap-3 cursor-pointer transition-colors duration-150"
        style={{ background: "transparent" }}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={`citation-body-${index}`}
      >
        {/* Expand icon */}
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#818cf8"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          className="shrink-0 mt-0.5 transition-transform duration-200"
          style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}
        >
          <path d="M9 18l6-6-6-6" />
        </svg>

        <div className="flex-1 min-w-0">
          {/* Regulation + article */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold" style={{ color: "#ededef" }}>
              {chunk.regulation}
            </span>
            <span
              className="text-xs px-2 py-0.5 rounded"
              style={{
                background: "rgba(99,102,241,0.15)",
                color: "#818cf8",
                border: "1px solid rgba(99,102,241,0.25)",
                fontFamily: "monospace",
              }}
            >
              {chunk.article_id}
            </span>
          </div>

          {/* Chapter */}
          <p className="text-xs mt-0.5 truncate" style={{ color: "#8a8f98" }}>
            {chunk.chapter}
          </p>

          {/* Relevance bar */}
          <div className="flex items-center gap-2 mt-2">
            <div
              className="flex-1 h-1 rounded-full overflow-hidden"
              style={{ background: "rgba(255,255,255,0.06)" }}
              role="progressbar"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`相关度 ${pct}%`}
            >
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, background: scoreColor }}
              />
            </div>
            <span
              className="text-xs tabular-nums shrink-0 font-medium"
              style={{ color: scoreColor }}
            >
              {chunk.relevance_score.toFixed(2)}
            </span>
          </div>
        </div>
      </button>

      {/* Expanded excerpt */}
      {open && (
        <div
          id={`citation-body-${index}`}
          className="px-4 pb-4 animate-fadeInUp"
          style={{ animationDuration: "200ms" }}
        >
          <div
            className="text-sm leading-relaxed p-3 rounded-lg"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.07)",
              color: "#b0b5bf",
            }}
          >
            <p className="text-xs mb-2 font-medium" style={{ color: "#8a8f98" }}>
              原文摘录
            </p>
            {chunk.text_excerpt}
          </div>
        </div>
      )}
    </div>
  );
}

export default function CitationPanel({ citations }: CitationPanelProps) {
  if (citations.length === 0) {
    return (
      <div
        className="glass-card p-6 text-center"
        style={{ color: "#8a8f98" }}
      >
        <svg
          width="32"
          height="32"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="mx-auto mb-2 opacity-40"
          aria-hidden="true"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" strokeLinecap="round" strokeLinejoin="round" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
        <p className="text-sm">暂无法规引用</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 mb-1">
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#818cf8"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
        <h2 className="text-sm font-medium" style={{ color: "#8a8f98" }}>
          法规引用 ({citations.length})
        </h2>
      </div>

      {citations.map((c, i) => (
        <CitationItem key={`${c.regulation}-${c.article_id}-${i}`} chunk={c} index={i} />
      ))}
    </div>
  );
}
