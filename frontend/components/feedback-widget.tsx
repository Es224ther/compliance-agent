"use client";

import { useState } from "react";
import { submitFeedback } from "@/lib/api";
import type { FeedbackPayload } from "@/lib/types";

interface FeedbackWidgetProps {
  reportId: string;
  section: string;
  label?: string;
}

type Rating = FeedbackPayload["rating"];

const BUTTONS: { rating: Rating; label: string; icon: React.ReactNode; activeColor: string }[] = [
  {
    rating: "helpful",
    label: "有帮助",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
        <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
      </svg>
    ),
    activeColor: "rgba(52,211,153,0.15)",
  },
  {
    rating: "unhelpful",
    label: "无帮助",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
        <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
      </svg>
    ),
    activeColor: "rgba(248,113,113,0.15)",
  },
  {
    rating: "needs_edit",
    label: "需修改",
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
      </svg>
    ),
    activeColor: "rgba(251,191,36,0.15)",
  },
];

export default function FeedbackWidget({ reportId, section, label }: FeedbackWidgetProps) {
  const [submitted, setSubmitted] = useState<Rating | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleRate(rating: Rating) {
    if (submitted || loading) return;
    setLoading(true);
    try {
      await submitFeedback(reportId, { section, rating, comment: null });
      setSubmitted(rating);
    } catch {
      // silent fail — feedback is non-critical
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="flex items-center gap-2 flex-wrap mt-3 pt-3"
      style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      role="group"
      aria-label={`对"${label || section}"的评价`}
    >
      <span className="text-xs shrink-0" style={{ color: "#8a8f98" }}>
        {submitted ? "感谢反馈" : "这条建议对你有帮助吗？"}
      </span>

      <div className="flex items-center gap-1.5">
        {BUTTONS.map((btn) => {
          const isActive = submitted === btn.rating;
          const isDisabled = submitted !== null || loading;

          return (
            <button
              key={btn.rating}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-150"
              style={{
                background: isActive ? btn.activeColor : "rgba(255,255,255,0.04)",
                border: isActive
                  ? "1px solid rgba(255,255,255,0.2)"
                  : "1px solid rgba(255,255,255,0.08)",
                color: isDisabled && !isActive ? "#4b5563" : "#8a8f98",
                cursor: isDisabled ? "default" : "pointer",
                opacity: isDisabled && !isActive ? 0.4 : 1,
              }}
              onClick={() => handleRate(btn.rating)}
              disabled={isDisabled}
              aria-pressed={isActive}
              aria-label={btn.label}
            >
              {btn.icon}
              {btn.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
