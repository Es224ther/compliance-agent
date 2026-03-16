"use client";

import ReactMarkdown from "react-markdown";
import type { AuditReport } from "@/lib/types";
import RiskBadge from "./risk-badge";
import FeedbackWidget from "./feedback-widget";

interface ReportViewerProps {
  report: AuditReport;
}

const ROLE_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
  PM: {
    label: "产品经理",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  ProductManager: {
    label: "产品经理",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  Dev: {
    label: "研发工程师",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </svg>
    ),
  },
  Developer: {
    label: "研发工程师",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </svg>
    ),
  },
  Security: {
    label: "安全治理",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
};

function SectionCard({
  icon,
  title,
  children,
  accent,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  accent?: string;
}) {
  return (
    <section
      className="glass-card p-6 flex flex-col gap-3 animate-fadeInUp"
      aria-label={title}
      style={accent ? { borderColor: accent } : undefined}
    >
      <div className="flex items-center gap-2">
        <span aria-hidden="true">{icon}</span>
        <h2 className="text-sm font-semibold tracking-wide uppercase" style={{ color: "#8a8f98", letterSpacing: "0.08em" }}>
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

function SectionIcon({ d, color = "#818cf8" }: { d: string; color?: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

const proseStyle: React.CSSProperties = {
  color: "#b0b5bf",
  lineHeight: 1.75,
  fontSize: "15px",
};

export default function ReportViewer({ report }: ReportViewerProps) {
  return (
    <div className="flex flex-col gap-4">
      {/* 1. Summary */}
      <SectionCard
        icon={<SectionIcon d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2" />}
        title="场景摘要"
      >
        <div style={proseStyle}>
          <ReactMarkdown>{report.summary}</ReactMarkdown>
        </div>
      </SectionCard>

      {/* 2. Risk overview */}
      <SectionCard
        icon={<SectionIcon d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" color="#fb923c" />}
        title="风险等级"
        accent="rgba(249,115,22,0.2)"
      >
        <div className="flex items-start gap-3 flex-wrap">
          <RiskBadge level={report.risk_level} size="lg" />
        </div>
        <div style={proseStyle}>
          <ReactMarkdown>{report.risk_overview}</ReactMarkdown>
        </div>
      </SectionCard>

      {/* 3. Uncertainties */}
      {report.uncertainties.length > 0 && (
        <SectionCard
          icon={<SectionIcon d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" color="#facc15" />}
          title="不确定项"
          accent="rgba(234,179,8,0.15)"
        >
          <ul className="flex flex-col gap-2" role="list">
            {report.uncertainties.map((u, i) => (
              <li key={i} className="flex items-start gap-2" style={{ color: "#b0b5bf", fontSize: "14px", lineHeight: 1.7 }}>
                <span
                  className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold mt-0.5"
                  style={{ background: "rgba(234,179,8,0.12)", color: "#facc15", border: "1px solid rgba(234,179,8,0.25)" }}
                  aria-hidden="true"
                >
                  {i + 1}
                </span>
                {u}
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {/* 4. Remediation actions */}
      <SectionCard
        icon={<SectionIcon d="M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" color="#4ade80" />}
        title="整改建议"
        accent="rgba(34,197,94,0.12)"
      >
        <div className="flex flex-col gap-4">
          {report.remediation_actions.map((rem, i) => {
            const meta = ROLE_LABELS[rem.role] ?? { label: rem.role, icon: null };
            return (
              <div key={i}>
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="w-6 h-6 rounded-md flex items-center justify-center"
                    style={{ background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.2)", color: "#818cf8" }}
                    aria-hidden="true"
                  >
                    {meta.icon}
                  </span>
                  <span className="text-sm font-semibold" style={{ color: "#ededef" }}>
                    {meta.label}
                  </span>
                </div>

                <ul className="flex flex-col gap-1.5 pl-2" role="list">
                  {(rem.actions ?? (rem.action ? [rem.action] : [])).map((action, j) => (
                    <li
                      key={j}
                      className="flex items-start gap-2"
                      style={{ color: "#b0b5bf", fontSize: "14px", lineHeight: 1.7 }}
                    >
                      <svg
                        className="shrink-0 mt-1"
                        width="12"
                        height="12"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#4ade80"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M5 12h14M12 5l7 7-7 7" />
                      </svg>
                      {action}
                    </li>
                  ))}
                </ul>

                <FeedbackWidget
                  reportId={report.report_id}
                  section={`remediation_${rem.role}`}
                  label={`${meta.label}整改建议`}
                />
              </div>
            );
          })}
        </div>
      </SectionCard>

      {/* 5. Disclaimer */}
      <SectionCard
        icon={<SectionIcon d="M3 6h18M3 12h18M3 18h18" color="#8a8f98" />}
        title="免责声明"
      >
        <p className="text-xs leading-relaxed" style={{ color: "#6b7280" }}>
          {report.disclaimer}
        </p>
      </SectionCard>
    </div>
  );
}
