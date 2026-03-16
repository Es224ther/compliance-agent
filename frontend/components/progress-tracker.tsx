"use client";

import type { ProgressEvent } from "@/lib/types";

export type StepStatus = "pending" | "running" | "completed" | "error";

const STEP_DEFS = [
  { key: "pii_sanitization",  label: "数据脱敏" },
  { key: "scenario_parsing",  label: "场景解析" },
  { key: "rag_retrieval",     label: "法规检索" },
  { key: "risk_analysis",     label: "风险分析" },
  { key: "report_generation", label: "生成报告" },
];

function buildSteps(events: ProgressEvent[]) {
  const map = new Map(events.map((e) => [e.step, e]));
  return STEP_DEFS.map((d) => {
    const ev = map.get(d.key);
    return { ...d, status: normalizeStatus(ev?.status), message: ev?.message };
  });
}

function normalizeStatus(status: string | undefined): StepStatus {
  switch ((status || "").toLowerCase()) {
    case "completed":
    case "done":
      return "completed";
    case "running":
    case "in_progress":
    case "processing":
      return "running";
    case "error":
    case "failed":
      return "error";
    default:
      return "pending";
  }
}

function StatusDot({ status }: { status: StepStatus }) {
  if (status === "completed") {
    return (
      <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center" style={{ background: "rgba(74,222,128,0.12)", border: "1px solid rgba(74,222,128,0.3)" }}>
        <svg className="step-completed" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-label="已完成">
          <path d="M20 6L9 17l-5-5" />
        </svg>
      </span>
    );
  }
  if (status === "running") {
    return (
      <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.12)" }}>
        <svg className="step-running spin" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-label="进行中">
          <path d="M21 12a9 9 0 11-6.219-8.56" strokeLinecap="round" />
        </svg>
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)" }}>
        <svg className="step-error" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-label="出错">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </span>
    );
  }
  return (
    <span className="shrink-0 w-5 h-5 rounded-full" style={{ border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.02)" }} aria-label="待处理" />
  );
}

export default function ProgressTracker({ events }: { events: ProgressEvent[] }) {
  const steps = buildSteps(events);
  const done = steps.filter((s) => s.status === "completed").length;

  return (
    <div className="glass-card p-5 flex flex-col gap-4 animate-fadeInUp">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-widest" style={{ color: "#52525b", letterSpacing: "0.1em" }}>
          执行进度
        </span>
        <span className="text-xs tabular-nums" style={{ color: "#52525b" }}>
          {done} / {steps.length}
        </span>
      </div>

      {/* Track bar */}
      <div
        className="h-px rounded-full overflow-hidden"
        style={{ background: "rgba(255,255,255,0.06)" }}
        role="progressbar"
        aria-valuenow={Math.round((done / steps.length) * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`总进度 ${Math.round((done / steps.length) * 100)}%`}
      >
        <div className="progress-fill h-full" style={{ width: `${(done / steps.length) * 100}%` }} />
      </div>

      {/* Steps */}
      <ul className="flex flex-col gap-2.5" role="list">
        {steps.map((s) => (
          <li key={s.key} className="flex items-center gap-3" style={{ opacity: s.status === "pending" ? 0.35 : 1, transition: "opacity 250ms ease" }}>
            <StatusDot status={s.status} />
            <div className="flex-1 min-w-0 flex items-center gap-2">
              <span className="text-sm" style={{ color: s.status === "pending" ? "#52525b" : "#e4e4e7" }}>
                {s.label}
              </span>
              {s.status === "running" && (
                <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(255,255,255,0.03)", color: "#d4d4d8", border: "1px solid rgba(255,255,255,0.12)" }}>
                  进行中
                </span>
              )}
            </div>
            {s.message && s.status !== "pending" && (
              <span className="text-xs truncate max-w-[180px]" style={{ color: "#52525b" }}>
                {s.message}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
