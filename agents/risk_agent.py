"""Risk analysis agent with bounded ReAct retrieval loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from agents.base import ReActAgent, ToolResult
from schemas.evidence import EvidenceChunk
from schemas.risk import RemediationAction, RiskAssessment, RiskLevel
from schemas.scenario import ParsedFields
from tools.rag_retriever import rag_retriever
from tools.risk_scorer import calculate_risk_level

MAX_RETRIEVAL_ACTIONS = 2
MAX_REACT_STEPS = 6
DEFAULT_MODEL_NAME = "claude-sonnet-4-20250514"
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system" / "risk.txt"
FEW_SHOT_PATH = PROMPTS_DIR / "few_shot" / "risk_examples.json"
LIMIT_REASON = "ReAct 循环达到上限，分析结论可能不完整"


def load_few_shot_examples() -> list[dict[str, Any]]:
    with FEW_SHOT_PATH.open(encoding="utf-8") as f:
        examples = json.load(f)
    return [{k: v for k, v in ex.items() if k != "rationale"} for ex in examples]


class RiskAgent(ReActAgent):
    """Agent responsible for retrieval-driven risk analysis."""

    def __init__(
        self,
        retriever: Callable[[str, ParsedFields], list[EvidenceChunk]] | None = None,
        scorer: Callable[
            [list[EvidenceChunk], ParsedFields], tuple[RiskLevel, str, list[dict[str, Any]]]
        ]
        | None = None,
    ) -> None:
        super().__init__(tools=[])
        self.retriever = retriever or rag_retriever
        self.scorer = scorer or calculate_risk_level
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        self.few_shot_examples = load_few_shot_examples()
        self.model_name = DEFAULT_MODEL_NAME
        self.last_retrieval_actions = 0
        self.last_react_steps = 0

    # Compatibility implementations for abstract ReAct interface.
    def think(self, context: Any) -> str:
        return f"Analyze parsed fields for retrieval strategy: {context}"

    def act(self, thought: str, tools: list[dict[str, Any]]) -> ToolResult:
        return ToolResult(name="noop", output=thought, is_final=False)

    def observe(self, result: ToolResult) -> str:
        return str(result.output)

    async def run(self, parsed_fields: ParsedFields) -> RiskAssessment:
        self.last_react_steps = 0
        self.last_retrieval_actions = 0
        low_confidence_items: list[str] = []
        requires_escalation = False

        try:
            self._tick_step()  # Think-1
            query = self._build_query(parsed_fields, mode="initial")
            evidence = self._retrieve(query, parsed_fields)

            self._tick_step()  # Observe-1
            is_sufficient, insufficiency_reasons = self._is_evidence_sufficient(
                evidence, parsed_fields
            )
            low_confidence_items.extend(insufficiency_reasons)

            if not is_sufficient:
                self._tick_step()  # Act-2
                supplemental_query = self._build_query(parsed_fields, mode="supplemental")
                supplemental = self._retrieve(supplemental_query, parsed_fields)
                evidence = self._merge_evidence(evidence, supplemental)

                self._tick_step()  # Observe-2
                _, reasons_after_retry = self._is_evidence_sufficient(evidence, parsed_fields)
                low_confidence_items.extend(reasons_after_retry)

            self._tick_step()  # Act-3
            risk_level, risk_summary, scoring_factors = self.scorer(evidence, parsed_fields)

            self._tick_step()  # Think-2
            jurisdictions_covered = self._extract_jurisdictions(evidence)
            reasoning = self._compose_reasoning(
                parsed_fields=parsed_fields,
                risk_summary=risk_summary,
                evidence=evidence,
            )
            remediation = self._build_remediation(risk_level, evidence)

        except RuntimeError:
            requires_escalation = True
            low_confidence_items.append(LIMIT_REASON)
            risk_level = RiskLevel.HIGH
            risk_summary = LIMIT_REASON
            evidence = []
            scoring_factors = []
            jurisdictions_covered = self._default_jurisdictions(parsed_fields)
            reasoning = "证据链因循环上限中断，当前结论仅供前置风险参考。"
            remediation = self._build_remediation(risk_level, evidence)

        payload = {
            "risk_level": risk_level,
            "risk_summary": risk_summary,
            "reasoning": reasoning,
            "jurisdictions_covered": jurisdictions_covered,
            "evidence": evidence,
            "remediation": remediation,
            "low_confidence_items": _dedupe(low_confidence_items),
            "requires_escalation": requires_escalation or bool(low_confidence_items),
            "scoring_factors": scoring_factors,
        }
        try:
            return RiskAssessment.model_validate(payload)
        except ValidationError as exc:
            fallback = payload | {
                "risk_level": RiskLevel.HIGH,
                "risk_summary": "风险评估结果结构校验失败，建议人工复核。",
                "reasoning": "模型输出结构异常，当前结果仅供前置排查。",
                "low_confidence_items": _dedupe(
                    low_confidence_items + [f"RiskAssessment 校验失败: {exc.errors()[0]['msg']}"]
                ),
                "requires_escalation": True,
            }
            return RiskAssessment.model_validate(fallback)

    def _tick_step(self) -> None:
        self.last_react_steps += 1
        if self.last_react_steps > MAX_REACT_STEPS:
            raise RuntimeError(LIMIT_REASON)

    def _retrieve(self, query: str, parsed_fields: ParsedFields) -> list[EvidenceChunk]:
        self.last_retrieval_actions += 1
        if self.last_retrieval_actions > MAX_RETRIEVAL_ACTIONS:
            raise RuntimeError(LIMIT_REASON)
        return list(self.retriever(query, parsed_fields))

    def _build_query(self, parsed_fields: ParsedFields, mode: str) -> str:
        keywords: list[str] = []
        keyword_map = {
            "Biometric": "生物特征 biometric",
            "Personal": "personal data",
            "Behavioral": "behavioral profiling",
            "Financial": "financial data",
        }
        for data_type in parsed_fields.data_types or []:
            if data_type in keyword_map:
                keywords.append(keyword_map[data_type])
        if parsed_fields.cross_border:
            keywords.append("跨境传输 cross-border transfer")
        if parsed_fields.third_party_model:
            keywords.append("third-party model processor")
        if parsed_fields.aigc_output:
            keywords.append("AIGC 生成式内容标识")

        if parsed_fields.region == "EU":
            keywords.append("GDPR Art.46")
        elif parsed_fields.region == "CN":
            keywords.append("PIPL 第38条")
        elif parsed_fields.region == "EU+CN":
            keywords.extend(["GDPR Art.46", "PIPL 第38条"])
        else:
            keywords.extend(["GDPR", "PIPL"])

        if mode == "supplemental":
            keywords.append("补充法规证据")
        return " ".join(_dedupe(keywords)) or "AI compliance regulation evidence"

    def _is_evidence_sufficient(
        self,
        evidence: list[EvidenceChunk],
        parsed_fields: ParsedFields,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        top_score = max((chunk.rerank_score or 0.0) for chunk in evidence) if evidence else 0.0
        if len(evidence) < 3:
            reasons.append("证据数量不足（<3）")
        if top_score < 0.6:
            reasons.append("证据重排分最高值低于 0.6")

        jurisdictions = set(self._extract_jurisdictions(evidence))
        if parsed_fields.region == "EU+CN" and jurisdictions != {"EU", "CN"}:
            reasons.append("EU+CN 场景下法域覆盖不完整")

        return not reasons, reasons

    @staticmethod
    def _extract_jurisdictions(evidence: list[EvidenceChunk]) -> list[str]:
        found = []
        for chunk in evidence:
            jurisdiction = str(chunk.jurisdiction).upper()
            if jurisdiction in {"EU", "CN"} and jurisdiction not in found:
                found.append(jurisdiction)
        return found

    def _default_jurisdictions(self, parsed_fields: ParsedFields) -> list[str]:
        if parsed_fields.region == "EU":
            return ["EU"]
        if parsed_fields.region == "CN":
            return ["CN"]
        return ["EU", "CN"]

    @staticmethod
    def _merge_evidence(
        existing: list[EvidenceChunk],
        supplemental: list[EvidenceChunk],
    ) -> list[EvidenceChunk]:
        merged: dict[str, EvidenceChunk] = {}
        for chunk in existing + supplemental:
            key = f"{chunk.chunk_id or ''}|{chunk.regulation}|{chunk.article}|{chunk.text}"
            merged[key] = chunk
        return list(merged.values())

    def _compose_reasoning(
        self,
        *,
        parsed_fields: ParsedFields,
        risk_summary: str,
        evidence: list[EvidenceChunk],
    ) -> str:
        eu_refs = [
            f"{chunk.regulation} {chunk.article}"
            for chunk in evidence
            if str(chunk.jurisdiction).upper() == "EU"
        ]
        cn_refs = [
            f"{chunk.regulation} {chunk.article}"
            for chunk in evidence
            if str(chunk.jurisdiction).upper() == "CN"
        ]
        eu_text = "、".join(_dedupe(eu_refs)) or "当前检索未覆盖 EU 关键条款"
        cn_text = "、".join(_dedupe(cn_refs)) or "当前检索未覆盖 CN 关键条款"

        if parsed_fields.region == "EU+CN":
            return (
                "【EU 合规要求】\n"
                f"基于 {eu_text}，需评估跨境传输与处理基础。{risk_summary}\n\n"
                "【CN 合规要求】\n"
                f"基于 {cn_text}，需关注数据出境与个人信息处理约束。{risk_summary}\n\n"
                "【跨法域注意事项】\n"
                "GDPR 对传输机制与保障措施有要求，PIPL 对出境路径和安全评估有并行义务。"
            )
        if parsed_fields.region == "CN":
            return f"【CN 合规要求】\n基于 {cn_text}，当前风险判断为：{risk_summary}"
        return f"【EU 合规要求】\n基于 {eu_text}，当前风险判断为：{risk_summary}"

    @staticmethod
    def _build_remediation(
        risk_level: RiskLevel,
        evidence: list[EvidenceChunk],
    ) -> list[RemediationAction]:
        first_ref = (
            f"{evidence[0].regulation} {evidence[0].article}" if evidence else "Regulatory evidence"
        )
        immediate = "Immediate" if risk_level == RiskLevel.CRITICAL else "Short-term"
        return [
            RemediationAction(
                role="PM",
                action="梳理跨法域数据流与用户告知口径，形成发布前合规检查清单。",
                priority=immediate,
                regulation_ref=first_ref,
            ),
            RemediationAction(
                role="Dev",
                action="补齐跨境传输与第三方模型调用的技术控制点，并保留审计日志。",
                priority=immediate,
                regulation_ref=first_ref,
            ),
            RemediationAction(
                role="Security",
                action="建立高风险场景人工复核闸口，确保上线前完成安全与合规联审。",
                priority=immediate,
                regulation_ref=first_ref,
            ),
        ]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
