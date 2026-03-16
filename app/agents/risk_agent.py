"""Risk analysis agent with bounded ReAct retrieval loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from app.agents.base import ReActAgent, ToolResult
from app.schemas.evidence import EvidenceChunk
from app.schemas.risk import RemediationAction, RiskAssessment, RiskLevel
from app.schemas.scenario import ParsedFields
from app.tools.rag_retriever import rag_retriever
from app.tools.risk_scorer import build_risk_debug_trace, calculate_risk_level

MAX_RETRIEVAL_ACTIONS = 2
MAX_REACT_STEPS = 6
DEFAULT_MODEL_NAME = "qwen-plus"
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
            debug_trace = build_risk_debug_trace(evidence, risk_level, scoring_factors)

            self._tick_step()  # Think-2
            jurisdictions_covered = self._extract_jurisdictions(evidence)
            reasoning = self._compose_reasoning(
                parsed_fields=parsed_fields,
                risk_summary=risk_summary,
                evidence=evidence,
            )
            reasoning = f"{reasoning}\n\n【Scoring Debug】\n{debug_trace}"
            remediation = self._build_remediation(risk_level, parsed_fields, evidence)

        except RuntimeError:
            requires_escalation = True
            low_confidence_items.append(LIMIT_REASON)
            risk_level = RiskLevel.HIGH
            risk_summary = LIMIT_REASON
            evidence = []
            scoring_factors = []
            jurisdictions_covered = self._default_jurisdictions(parsed_fields)
            reasoning = "证据链因循环上限中断，当前结论仅供前置风险参考。"
            remediation = self._build_remediation(risk_level, parsed_fields, evidence)

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
        parsed_fields: ParsedFields,
        evidence: list[EvidenceChunk],
    ) -> list[RemediationAction]:
        immediate = (
            "Immediate"
            if risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH}
            else "Short-term"
        )
        has_cn = (
            parsed_fields.region in {"CN", "EU+CN", "Global"}
            or any(str(chunk.jurisdiction).upper() == "CN" for chunk in evidence)
        )
        has_cross_border = bool(parsed_fields.cross_border)
        has_biometric = "Biometric" in (parsed_fields.data_types or [])

        data_element = "视频素材及其中的人脸生物特征信息" if has_biometric else "用户上传内容与个人信息"
        transfer_target = "中国境内训练集群" if has_cn else "目标训练集群"

        pm_ref_primary = (
            "GDPR Article 9, PIPL 第十四条"
            if has_biometric and has_cn
            else "GDPR Article 7"
        )
        pm_ref_secondary = "GDPR Article 13/14, PIPL 第十七条" if has_cn else "GDPR Article 13/14"
        dev_ref_primary = "GDPR Article 25"
        dev_ref_secondary = "GDPR Article 32, PIPL 第五十一条" if has_cn else "GDPR Article 32"
        security_ref_primary = "GDPR Article 35"
        security_ref_secondary = (
            "PIPL 第三十八条, DSL 第二十四条"
            if has_cn and has_cross_border
            else ("PIPL 第五十五条" if has_cn else "GDPR Article 30")
        )

        dev_action_primary = (
            "在上传管道增加人脸检测与最小化处理步骤：对包含人脸帧的素材先做模糊化或分段加密，再进入跨境传输链路。"
            if has_biometric
            else "在上传与训练前处理链路增加字段级最小化与脱敏策略，仅保留完成模型训练所必需的数据特征。"
        )
        security_action_primary = (
            "启动 DPIA，重点评估大规模处理生物特征数据的必要性、比例性、数据主体权利影响与剩余风险处置方案。"
            if has_biometric
            else "启动 DPIA，评估跨境训练场景下数据主体权利影响、处理必要性以及风险缓解措施的充分性。"
        )

        return [
            RemediationAction(
                role="PM",
                action=(
                    f"在用户上传入口增加单独授权弹窗，明确告知 {data_element} "
                    f"将跨境传输至 {transfer_target} 用于模型训练，并提供拒绝后仍可使用基础功能的替代路径。"
                ),
                priority=immediate,
                regulation_ref=pm_ref_primary,
            ),
            RemediationAction(
                role="PM",
                action=(
                    "在隐私政策新增“跨境传输与模型训练”专章，逐项披露接收方、处理目的、保留期限、"
                    "撤回同意入口和删除请求路径。"
                ),
                priority=immediate,
                regulation_ref=pm_ref_secondary,
            ),
            RemediationAction(
                role="Dev",
                action=dev_action_primary,
                priority=immediate,
                regulation_ref=dev_ref_primary,
            ),
            RemediationAction(
                role="Dev",
                action=(
                    "跨境传输链路统一启用 TLS 1.3，落盘使用 AES-256；同时记录传输日志（时间、数据量、目标节点、任务 ID）并保留审计记录。"
                ),
                priority=immediate,
                regulation_ref=dev_ref_secondary,
            ),
            RemediationAction(
                role="Security",
                action=security_action_primary,
                priority=immediate,
                regulation_ref=security_ref_primary,
            ),
            RemediationAction(
                role="Security",
                action=(
                    "针对数据出境链路建立季度合规复核机制；若触发敏感个人信息或大规模阈值，"
                    "向主管部门启动数据出境安全评估/备案流程并跟踪整改闭环。"
                ),
                priority=immediate,
                regulation_ref=security_ref_secondary,
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
