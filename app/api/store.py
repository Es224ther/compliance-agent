"""In-memory persistence for API-facing session and report state."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.schemas import AuditReport, SharedState


@dataclass
class SessionRecord:
    session_id: str
    report_id: str
    scenario_text: str
    status: str = "processing"
    state: SharedState | None = None
    event_history: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class InMemoryApiStore:
    def __init__(self) -> None:
        self._reports: dict[str, AuditReport] = {}
        self._sessions: dict[str, SessionRecord] = {}
        self._feedback: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str, report_id: str, scenario_text: str) -> None:
        async with self._lock:
            self._sessions[session_id] = SessionRecord(
                session_id=session_id,
                report_id=report_id,
                scenario_text=scenario_text,
            )

    async def append_event(self, session_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return
            record.event_history.append(dict(event))

    async def get_event_history(self, session_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return []
            return [dict(item) for item in record.event_history]

    async def set_session_state(self, session_id: str, state: SharedState, status: str) -> None:
        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return
            record.state = state
            record.status = status
            record.error = state.error

    async def get_session_state(self, session_id: str) -> SharedState | None:
        async with self._lock:
            record = self._sessions.get(session_id)
            return record.state if record is not None else None

    async def complete_report(self, report: AuditReport) -> None:
        async with self._lock:
            self._reports[report.report_id] = report
            record = self._sessions.get(report.session_id)
            if record is not None:
                record.status = "completed"
                if record.state is not None:
                    record.state.report = report

    async def get_report(self, report_id: str) -> AuditReport | None:
        async with self._lock:
            return self._reports.get(report_id)

    async def list_reports(self, risk_level: str | None = None) -> list[AuditReport]:
        async with self._lock:
            reports = list(self._reports.values())
        if risk_level:
            reports = [report for report in reports if report.risk_level.value == risk_level]
        reports.sort(key=lambda report: report.created_at, reverse=True)
        return reports

    async def add_feedback(
        self,
        report_id: str,
        payload: dict[str, Any],
    ) -> None:
        async with self._lock:
            self._feedback[report_id].append(payload)

    async def get_feedback(self, report_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            return list(self._feedback.get(report_id, []))

    async def get_session_record(self, session_id: str) -> SessionRecord | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def clear(self) -> None:
        async with self._lock:
            self._reports.clear()
            self._sessions.clear()
            self._feedback.clear()


store = InMemoryApiStore()
