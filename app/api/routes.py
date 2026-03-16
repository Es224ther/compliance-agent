"""FastAPI route definitions for the Compliance Agent API."""

from __future__ import annotations

import asyncio
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.api.store import store
from app.api.websocket import ws_manager
from orchestrator.pipeline import run_pipeline
from schemas.report import AuditReport
from schemas.scenario import ScenarioInput

router = APIRouter(tags=["api"])


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    scenario_text: str


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(strict=False)

    session_id: str
    report_id: str
    status: str


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    section: str
    rating: Literal["helpful", "unhelpful", "needs_edit"]
    comment: str | None = None


class ReportSummary(BaseModel):
    model_config = ConfigDict(strict=False)

    report_id: str
    created_at: str
    risk_level: str
    risk_overview: str
    session_id: str


@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    session_id = str(uuid4())
    report_id = str(uuid4())
    await store.create_session(session_id, report_id, request.scenario_text)
    asyncio.create_task(
        _process_analysis(
            ScenarioInput(raw_text=request.scenario_text, session_id=session_id),
            report_id=report_id,
        )
    )
    return AnalyzeResponse(session_id=session_id, report_id=report_id, status="processing")


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    format: Literal["markdown", "json"] = Query(default="markdown"),
):
    report = await store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if format == "json":
        return report.to_json()
    return Response(content=report.to_markdown(), media_type="text/markdown; charset=utf-8")


@router.patch("/reports/{report_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(report_id: str, feedback: FeedbackRequest) -> Response:
    report = await store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await store.add_feedback(report_id, feedback.model_dump(mode="json"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/reports", response_model=list[ReportSummary])
async def list_reports(
    risk_level: Literal["Low", "Medium", "High", "Critical"] | None = Query(default=None),
) -> list[ReportSummary]:
    reports = await store.list_reports(risk_level=risk_level)
    return [
        ReportSummary(
            report_id=report.report_id,
            created_at=report.created_at.isoformat(),
            risk_level=report.risk_level.value,
            risk_overview=report.risk_overview,
            session_id=report.session_id,
        )
        for report in reports
    ]


@router.get("/evidence/{chunk_id}")
async def get_evidence_full_text(chunk_id: str, request: Request) -> dict[str, str]:
    """Return full evidence text by chunk_id for on-demand UI expansion."""

    vector_store = getattr(request.app.state, "vector_store", None)
    if vector_store is None:
        raise HTTPException(status_code=503, detail="Knowledge base unavailable")

    chunk = vector_store.get_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return {"chunk_id": chunk_id, "full_text": str(chunk.get("text", ""))}


async def _process_analysis(scenario_input: ScenarioInput, report_id: str) -> None:
    state = await run_pipeline(
        scenario_input,
        progress_callback=lambda event: ws_manager.broadcast(scenario_input.session_id, event),
        report_id=report_id,
    )
    await store.set_session_state(scenario_input.session_id, state, state.status.value.lower())
    if isinstance(state.report, AuditReport):
        await store.complete_report(state.report)
