"use client";

import { useState } from "react";
import type { FollowUpQuestion } from "@/lib/types";

interface FollowUpCardProps {
  questions: FollowUpQuestion[];
  onSubmit: (answers: Record<string, string>) => void;
  isSubmitting?: boolean;
}

export default function FollowUpCard({ questions, onSubmit, isSubmitting = false }: FollowUpCardProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const allAnswered = questions.every((q) => answers[q.field] !== undefined);

  return (
    <div
      className="glass-card p-5 flex flex-col gap-5 animate-fadeInUp"
      style={{ borderColor: "rgba(234,179,8,0.2)" }}
      role="region"
      aria-label="补充信息"
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#eab308" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
          <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" />
        </svg>
        <div>
          <p className="text-sm font-medium" style={{ color: "#fafafa" }}>需要补充信息</p>
          <p className="text-xs mt-0.5" style={{ color: "#71717a" }}>为了给出准确评估，请补充以下信息</p>
        </div>
      </div>

      <div className="divider" />

      {/* Questions */}
      <div className="flex flex-col gap-4">
        {questions.map((q, i) => (
          <fieldset key={q.field}>
            <legend className="text-sm mb-2.5" style={{ color: "#e4e4e7" }}>
              <span className="mr-1.5 text-xs" style={{ color: "#52525b" }}>{i + 1}.</span>
              {q.question}
            </legend>
            <div className="flex flex-wrap gap-2">
              {q.options.map((opt) => {
                const selected = answers[q.field] === opt;
                return (
                  <button
                    key={opt}
                    type="button"
                    className={`radio-option${selected ? " selected" : ""}`}
                    onClick={() => setAnswers((p) => ({ ...p, [q.field]: opt }))}
                    aria-pressed={selected}
                  >
                    <span
                      className="inline-block w-3 h-3 rounded-full shrink-0"
                      style={{ border: selected ? "3.5px solid #6366f1" : "1.5px solid rgba(255,255,255,0.2)", transition: "border 120ms ease" }}
                    />
                    {opt}
                  </button>
                );
              })}
            </div>
          </fieldset>
        ))}
      </div>

      <button
        className="btn-accent py-2.5 text-sm"
        onClick={() => onSubmit(answers)}
        disabled={!allAnswered || isSubmitting}
      >
        {isSubmitting
          ? <><svg className="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M21 12a9 9 0 11-6.219-8.56" strokeLinecap="round" /></svg>提交中…</>
          : "提交补充信息"
        }
      </button>
    </div>
  );
}
