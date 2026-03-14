"""End-to-end compliance pipeline orchestration."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any

from agents.intake_agent import IntakeAgent
from agents.risk_agent import RiskAgent
from app.observability.logger import get_logger
from guards.confidence_gate import evaluate_confidence
from orchestrator import router
from processors import escalation_checker, report_generator
from schemas.scenario import ParsedFields, ScenarioInput
from schemas.state import PipelineStatus, SharedState

logger = get_logger()

_intake_agent_instance: IntakeAgent | None = None
_risk_agent_instance: RiskAgent | None = None


def _get_intake_agent() -> IntakeAgent:
    global _intake_agent_instance
    if _intake_agent_instance is None:
        _intake_agent_instance = IntakeAgent()
    return _intake_agent_instance


def _get_risk_agent() -> RiskAgent:
    global _risk_agent_instance
    if _risk_agent_instance is None:
        _risk_agent_instance = RiskAgent()
    return _risk_agent_instance


async def _update(
    state: SharedState,
    status: PipelineStatus,
    message: str,
    on_progress: Callable[[PipelineStatus, str], Awaitable[None]] | None,
) -> None:
    state.status = status
    if on_progress is not None:
        await on_progress(status, message)


async def run_pipeline(
    scenario_input: ScenarioInput,
    on_progress: Callable[[PipelineStatus, str], Awaitable[None]] | None = None,
    progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    report_id: str | None = None,
) -> SharedState:
    state = SharedState(
        session_id=scenario_input.session_id,
        report_id=report_id,
        raw_input=scenario_input,
    )

    try:
        await _emit_event(
            progress_callback,
            {"step": "pii_sanitization", "status": "running", "message": "正在进行数据脱敏..."},
        )
        await _update(state, PipelineStatus.SANITIZING, "正在进行数据脱敏处理...", on_progress)
        sanitized_text, pii_map = await asyncio.to_thread(_anonymize_text, scenario_input.raw_text)
        state.pii_map = pii_map
        await _emit_event(
            progress_callback,
            {"step": "pii_sanitization", "status": "completed", "message": "脱敏完成"},
        )

        await _emit_event(
            progress_callback,
            {"step": "scenario_parsing", "status": "running", "message": "正在解析业务场景..."},
        )
        await _update(state, PipelineStatus.PARSING, "正在解析业务场景...", on_progress)
        parse_output = await asyncio.to_thread(
            _get_intake_agent().run,
            ScenarioInput(raw_text=sanitized_text, session_id=scenario_input.session_id),
        )
        intake_result = parse_output.final_output
        state.parsed_fields = intake_result.parsed_fields
        state.missing_fields = intake_result.missing_fields
        await _emit_event(
            progress_callback,
            {"step": "scenario_parsing", "status": "completed", "message": "场景解析完成"},
        )

        if intake_result.requires_followup and intake_result.followup_prompt:
            state.followup_questions = [intake_result.followup_prompt]
            await _emit_event(
                progress_callback,
                {
                    "step": "followup",
                    "status": "waiting",
                    "message": "需要补充信息",
                    "data": {"questions": state.followup_questions},
                },
            )
            await _update(state, PipelineStatus.AWAITING_FOLLOWUP, "需要补充信息...", on_progress)
            return state

        return await _continue_from_analysis(state, on_progress, progress_callback)

    except Exception as exc:  # pragma: no cover - guarded by integration tests
        state.status = PipelineStatus.FAILED
        state.error = str(exc)
        state.report = None
        await _emit_event(
            progress_callback,
            {"step": "completed", "status": "error", "message": f"处理失败: {exc}"},
        )
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        return state


async def resume_pipeline(
    state: SharedState,
    user_followup: str,
    on_progress: Callable[[PipelineStatus, str], Awaitable[None]] | None = None,
    progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> SharedState:
    assert state.status == PipelineStatus.AWAITING_FOLLOWUP

    try:
        await _emit_event(
            progress_callback,
            {"step": "pii_sanitization", "status": "running", "message": "正在进行数据脱敏..."},
        )
        await _update(state, PipelineStatus.SANITIZING, "正在进行数据脱敏处理...", on_progress)
        sanitized_followup, followup_pii = await asyncio.to_thread(_anonymize_text, user_followup)
        state.pii_map.update(followup_pii)
        await _emit_event(
            progress_callback,
            {"step": "pii_sanitization", "status": "completed", "message": "脱敏完成"},
        )

        await _emit_event(
            progress_callback,
            {"step": "scenario_parsing", "status": "running", "message": "正在解析业务场景..."},
        )
        base_text = state.raw_input.raw_text if state.raw_input else ""
        merged_text = f"{base_text}\n补充信息：{sanitized_followup}".strip()
        state.raw_input = ScenarioInput(raw_text=merged_text, session_id=state.session_id or "")

        await _update(state, PipelineStatus.PARSING, "正在解析补充信息...", on_progress)
        parse_output = await asyncio.to_thread(_get_intake_agent().run, state)
        intake_result = parse_output.final_output
        state.parsed_fields = _merge_parsed_fields(state.parsed_fields, intake_result.parsed_fields)
        state.missing_fields = intake_result.missing_fields
        await _emit_event(
            progress_callback,
            {"step": "scenario_parsing", "status": "completed", "message": "场景解析完成"},
        )

        if intake_result.requires_followup and intake_result.followup_prompt:
            state.followup_questions = [intake_result.followup_prompt]
            await _emit_event(
                progress_callback,
                {
                    "step": "followup",
                    "status": "waiting",
                    "message": "需要补充信息",
                    "data": {"questions": state.followup_questions},
                },
            )
            await _update(state, PipelineStatus.AWAITING_FOLLOWUP, "需要继续补充信息...", on_progress)
            return state

        return await _continue_from_analysis(state, on_progress, progress_callback)

    except Exception as exc:  # pragma: no cover
        state.status = PipelineStatus.FAILED
        state.error = str(exc)
        state.report = None
        await _emit_event(
            progress_callback,
            {"step": "completed", "status": "error", "message": f"处理失败: {exc}"},
        )
        logger.error("Pipeline resume failed: %s", exc, exc_info=True)
        return state


async def _continue_from_analysis(
    state: SharedState,
    on_progress: Callable[[PipelineStatus, str], Awaitable[None]] | None = None,
    progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> SharedState:
    parsed_fields = state.parsed_fields
    jurisdictions = router.route_by_region(parsed_fields)
    await _emit_event(
        progress_callback,
        {"step": "rag_retrieval", "status": "running", "message": "正在检索法规依据..."},
    )
    await _update(
        state,
        PipelineStatus.RETRIEVING,
        f"正在检索 {' + '.join(jurisdictions)} 法规...",
        on_progress,
    )
    risk_assessment = await _get_risk_agent().run(parsed_fields)
    await _emit_event(
        progress_callback,
        {
            "step": "rag_retrieval",
            "status": "completed",
            "message": f"找到 {len(risk_assessment.evidence)} 条相关法规",
        },
    )
    await _emit_event(
        progress_callback,
        {"step": "risk_analysis", "status": "running", "message": "正在进行风险分析..."},
    )
    await _update(state, PipelineStatus.ANALYZING, "正在进行风险分析...", on_progress)
    state.risk_assessment = risk_assessment
    state.evidence = risk_assessment.evidence
    state.risk_level = risk_assessment.risk_level.value

    confidence_result = evaluate_confidence(risk_assessment.evidence, parsed_fields)
    escalation_result = escalation_checker.check_escalation(
        risk_assessment, parsed_fields, confidence_result
    )
    state.escalation_result = escalation_result

    await _emit_event(
        progress_callback,
        {"step": "report_generation", "status": "running", "message": "正在生成审计报告..."},
    )
    await _update(state, PipelineStatus.GENERATING, "正在生成审计报告...", on_progress)
    report = await report_generator.generate_report(state, risk_assessment, escalation_result)
    state.report = report
    state.report_id = report.report_id

    await _emit_event(
        progress_callback,
        {
            "step": "completed",
            "status": "completed",
            "message": "报告生成完成",
            "data": {"report_id": report.report_id},
        },
    )

    await _update(state, PipelineStatus.COMPLETED, "报告已生成", on_progress)
    return state


def _merge_parsed_fields(base: ParsedFields, incoming: ParsedFields) -> ParsedFields:
    merged = base.model_dump()
    for key, value in incoming.model_dump().items():
        if value in (None, [], ""):
            continue
        merged[key] = value
    return ParsedFields.model_validate(merged)


def _anonymize_text(text: str) -> tuple[str, dict[str, str]]:
    """Lightweight fallback anonymizer used by pipeline tests."""

    pii_map: dict[str, str] = {}
    sanitized = text

    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    phone_pattern = re.compile(r"\b1[3-9]\d{9}\b")

    def _replace(pattern: re.Pattern[str], placeholder_prefix: str, source: str) -> str:
        counter = 0

        def repl(match: re.Match[str]) -> str:
            nonlocal counter
            counter += 1
            placeholder = f"[{placeholder_prefix}_{counter}]"
            pii_map[placeholder] = match.group(0)
            return placeholder

        return pattern.sub(repl, source)

    sanitized = _replace(email_pattern, "EMAIL", sanitized)
    sanitized = _replace(phone_pattern, "CN_PHONE", sanitized)
    return sanitized, pii_map


async def _emit_event(
    progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None,
    event: dict[str, Any],
) -> None:
    if progress_callback is not None:
        await progress_callback(event)
