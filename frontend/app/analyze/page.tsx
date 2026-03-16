"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import ScenarioInput from "@/components/scenario-input";
import ProgressTracker from "@/components/progress-tracker";
import FollowUpCard from "@/components/followup-card";
import { submitScenario, connectWebSocket } from "@/lib/api";
import type { ProgressEvent, FollowUpQuestion } from "@/lib/types";

type PageState = "idle" | "loading" | "follow_up" | "in_progress" | "done" | "error";

/* ── Shared nav ── */
function Navbar() {
  return (
    <header className="glass-nav sticky top-0 z-50" role="banner">
      <nav className="max-w-3xl mx-auto px-6 h-14 flex items-center justify-between" aria-label="主导航">
        <div className="flex items-center gap-2.5">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span className="text-sm font-semibold tracking-tight" style={{ color: "#fafafa" }}>
            AI 合规预检
          </span>
        </div>
        <Link
          href="/reports"
          className="btn-secondary px-3 py-1.5 text-xs"
          style={{ borderRadius: "8px" }}
        >
          历史记录
        </Link>
      </nav>
    </header>
  );
}

export default function AnalyzePage() {
  const [text, setText] = useState("");
  const [pageState, setPageState] = useState<PageState>("idle");
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [followUpQuestions, setFollowUpQuestions] = useState<FollowUpQuestion[]>([]);
  const [reportId, setReportId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const progressRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => { wsRef.current?.close(); }, []);

  const appendEvent = useCallback((ev: ProgressEvent) => {
    setEvents((prev) => {
      const idx = prev.findIndex((e) => e.step === ev.step);
      if (idx !== -1) { const n = [...prev]; n[idx] = ev; return n; }
      return [...prev, ev];
    });
  }, []);

  const handleMessage = useCallback((ev: ProgressEvent) => {
    appendEvent(ev);
    if (ev.step === "followup" && ev.status === "waiting") {
      setFollowUpQuestions(ev.data?.questions ?? []);
      setPageState("follow_up");
    } else if (ev.step === "completed" && ev.status === "completed") {
      const rid = ev.data?.report_id as string | undefined;
      if (rid) setReportId(rid);
      setPageState("done");
      wsRef.current?.close();
    } else if (ev.status === "error") {
      setErrorMsg(ev.message);
      setPageState("error");
      wsRef.current?.close();
    } else {
      setPageState("in_progress");
    }
  }, [appendEvent]);

  async function handleSubmit() {
    if (pageState === "loading" || pageState === "in_progress") return;
    try {
      setPageState("loading");
      setEvents([]); setFollowUpQuestions([]); setReportId(null); setErrorMsg(null);
      const { session_id, report_id } = await submitScenario(text);
      setReportId(report_id);
      setTimeout(() => progressRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
      wsRef.current = connectWebSocket(session_id, handleMessage);
      setPageState("in_progress");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "提交失败，请重试");
      setPageState("error");
    }
  }

  function handleFollowUpSubmit(answers: Record<string, string>) {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "followup_answers", answers }));
    setFollowUpQuestions([]);
    setPageState("in_progress");
  }

  function handleReset() {
    wsRef.current?.close(); wsRef.current = null;
    setPageState("idle"); setEvents([]); setFollowUpQuestions([]);
    setReportId(null); setErrorMsg(null); setText("");
  }

  const showProgress = pageState !== "idle" && pageState !== "loading";
  const isSubmitting = pageState === "loading" || pageState === "in_progress" || pageState === "follow_up";

  return (
    <div className="min-h-dvh flex flex-col" style={{ position: "relative" }}>
      <div className="ambient-blob ambient-blob-1" aria-hidden="true" />
      <div className="ambient-blob ambient-blob-2" aria-hidden="true" />

      <Navbar />

      <main className="flex-1 relative z-10 max-w-3xl mx-auto w-full px-4 py-14 flex flex-col gap-10" id="main-content">

        {/* ── Hero ── */}
        <div className="text-center animate-fadeInUp">
          <h1 className="text-[2rem] font-semibold tracking-tight leading-tight mb-3" style={{ color: "#fafafa" }}>
            描述你的 AI 业务场景
          </h1>
          <p className="text-sm max-w-md mx-auto" style={{ color: "#71717a", lineHeight: 1.8 }}>
            输入场景描述，系统将自动检索 GDPR、PIPL、DSL、EU AI Act
            等法规，生成结构化合规报告。
          </p>
        </div>

        {/* ── Input card ── */}
        <div className="glass-card p-6 animate-fadeInUp" style={{ animationDelay: "60ms" }}>
          <label className="block text-xs mb-3 uppercase tracking-widest" style={{ color: "#71717a", letterSpacing: "0.1em" }}>
            场景描述
          </label>
          <ScenarioInput
            value={text}
            onChange={setText}
            onSubmit={handleSubmit}
            isLoading={isSubmitting}
          />
        </div>

        {/* ── Error ── */}
        {pageState === "error" && errorMsg && (
          <div
            className="glass-card px-5 py-4 flex items-center gap-4 animate-fadeInUp"
            style={{ borderColor: "rgba(239,68,68,0.25)" }}
            role="alert"
            aria-live="assertive"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0" aria-hidden="true">
              <circle cx="12" cy="12" r="10" /><path d="M15 9l-6 6M9 9l6 6" />
            </svg>
            <p className="flex-1 text-sm" style={{ color: "#fca5a5" }}>{errorMsg}</p>
            <button className="btn-secondary text-xs px-3 py-1.5 shrink-0" style={{ borderRadius: "8px" }} onClick={handleReset}>
              重试
            </button>
          </div>
        )}

        {/* ── Progress ── */}
        {showProgress && (
          <div ref={progressRef}>
            <ProgressTracker events={events} />
          </div>
        )}

        {/* ── Follow-up ── */}
        {pageState === "follow_up" && followUpQuestions.length > 0 && (
          <FollowUpCard questions={followUpQuestions} onSubmit={handleFollowUpSubmit} />
        )}

        {/* ── Done ── */}
        {pageState === "done" && reportId && (
          <div
            className="glass-card px-6 py-8 flex flex-col items-center gap-5 text-center animate-fadeInUp pulse-border"
            style={{ borderColor: "rgba(34,197,94,0.25)" }}
            role="status"
            aria-live="polite"
          >
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.25)" }}
              aria-hidden="true"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
            <div>
              <p className="text-base font-semibold mb-1" style={{ color: "#fafafa" }}>合规报告已生成</p>
              <p className="text-xs font-mono" style={{ color: "#52525b" }}>{reportId}</p>
            </div>
            <div className="flex items-center gap-2.5">
              <Link href={`/reports/${reportId}`} className="btn-accent px-5 py-2.5 text-sm">
                查看报告
              </Link>
              <button className="btn-secondary px-4 py-2.5 text-sm" onClick={handleReset}>
                新建评估
              </button>
            </div>
          </div>
        )}

        {/* ── Feature hints (idle only) ── */}
        {pageState === "idle" && (
          <div className="grid grid-cols-1 gap-px sm:grid-cols-3 animate-fadeInUp overflow-hidden" style={{ animationDelay: "120ms", borderRadius: "12px", border: "1px solid var(--border)" }}>
            {[
              { title: "多法规覆盖", desc: "GDPR · PIPL · DSL · EU AI Act" },
              { title: "语义检索",   desc: "向量数据库精准匹配法规条款" },
              { title: "实时进度",   desc: "WebSocket 推送，全程透明" },
            ].map((f, i) => (
              <div
                key={f.title}
                className="px-5 py-5 flex flex-col gap-1.5"
                style={{
                  background: "rgba(255,255,255,0.02)",
                  borderRight: i < 2 ? "1px solid var(--border)" : "none",
                }}
              >
                <p className="text-sm font-medium" style={{ color: "#e4e4e7" }}>{f.title}</p>
                <p className="text-xs" style={{ color: "#52525b" }}>{f.desc}</p>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="relative z-10 text-center pb-8 text-xs" style={{ color: "#3f3f46" }}>
        本工具仅供参考，不构成正式法律建议
      </footer>
    </div>
  );
}
