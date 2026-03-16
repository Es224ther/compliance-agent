import type { AuditReport, ReportSummary, FeedbackPayload, ProgressEvent } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export async function submitScenario(
  text: string
): Promise<{ session_id: string; report_id: string }> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_text: text }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function getReport(
  reportId: string,
  format: "markdown" | "json" = "json"
): Promise<AuditReport> {
  const res = await fetch(`${API_BASE}/reports/${reportId}?format=${format}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function getReportList(riskLevel?: string): Promise<ReportSummary[]> {
  const url = riskLevel
    ? `${API_BASE}/reports?risk_level=${riskLevel}`
    : `${API_BASE}/reports`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function submitFeedback(
  reportId: string,
  feedback: FeedbackPayload
): Promise<void> {
  const res = await fetch(`${API_BASE}/reports/${reportId}/feedback`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(feedback),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Request failed: ${res.status}`);
  }
}

export function connectWebSocket(
  sessionId: string,
  onMessage: (event: ProgressEvent) => void
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/${sessionId}`);
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data) as ProgressEvent;
      onMessage(data);
    } catch {
      // ignore malformed messages
    }
  };
  return ws;
}
