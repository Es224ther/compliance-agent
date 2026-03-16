"use client";

import type { AuditReport } from "@/lib/types";

type RiskLevel = AuditReport["risk_level"];

const CONFIG: Record<
  RiskLevel,
  { label: string; bg: string; text: string; border: string; dot: string }
> = {
  Low: {
    label: "低风险",
    bg: "rgba(34,197,94,0.12)",
    text: "#4ade80",
    border: "rgba(34,197,94,0.3)",
    dot: "#4ade80",
  },
  Medium: {
    label: "中等风险",
    bg: "rgba(234,179,8,0.12)",
    text: "#facc15",
    border: "rgba(234,179,8,0.3)",
    dot: "#facc15",
  },
  High: {
    label: "高风险",
    bg: "rgba(249,115,22,0.12)",
    text: "#fb923c",
    border: "rgba(249,115,22,0.3)",
    dot: "#fb923c",
  },
  Critical: {
    label: "极高风险",
    bg: "rgba(239,68,68,0.12)",
    text: "#f87171",
    border: "rgba(239,68,68,0.3)",
    dot: "#f87171",
  },
};

interface RiskBadgeProps {
  level: RiskLevel;
  size?: "sm" | "md" | "lg";
}

export default function RiskBadge({ level, size = "md" }: RiskBadgeProps) {
  const c = CONFIG[level];
  const padding = size === "sm" ? "4px 10px" : size === "lg" ? "8px 18px" : "6px 14px";
  const fontSize = size === "sm" ? "11px" : size === "lg" ? "15px" : "13px";
  const dotSize = size === "sm" ? 6 : size === "lg" ? 9 : 7;

  return (
    <span
      className="inline-flex items-center gap-1.5 font-semibold rounded-full"
      style={{
        background: c.bg,
        color: c.text,
        border: `1px solid ${c.border}`,
        padding,
        fontSize,
        lineHeight: 1,
      }}
      aria-label={`风险等级：${c.label}`}
    >
      {/* Pulsing dot for High/Critical */}
      <span
        className="inline-block rounded-full shrink-0"
        style={{
          width: dotSize,
          height: dotSize,
          background: c.dot,
          boxShadow: level === "Critical" || level === "High"
            ? `0 0 6px ${c.dot}`
            : "none",
        }}
        aria-hidden="true"
      />
      {c.label}
    </span>
  );
}
