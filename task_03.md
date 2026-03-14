# Compliance Agent — Day 3 Vibe Coding Prompt（修订版）

## 前置确认
在开始之前，请确认 Day 2 的以下产出已就绪：
- `tools/rag_retriever.py` 封装完成，接口可被 Agent 调用
- `schemas/evidence.py` 中 EvidenceChunk 已定义，且包含以下字段：
  regulation / article / jurisdiction / text / summary / rerank_score / tags

## 执行约束（重要，请先读完再开始写代码）
请分 4 个 Phase 实现，每完成一个 Phase 先确保对应测试通过，
再进入下一阶段。不要一次性生成所有文件后再统一调试。

Phase A：Schemas + Risk Scorer
Phase B：Risk Agent + Confidence Gate
Phase C：Report Generator + Disclaimers + Output Filter
Phase D：Orchestrator + Integration Tests

---

## Phase A：Schemas + Risk Scorer

### A-1. 补全 Risk 相关 Schemas（schemas/risk.py / schemas/report.py）

`schemas/risk.py`：

```python
from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal

class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

class RemediationAction(BaseModel):
    role: Literal["PM", "Dev", "Security"]
    action: str
    priority: Literal["Immediate", "Short-term", "Long-term"]
    regulation_ref: str   # 触发该建议的法规条款，如 "GDPR Art.46"

class EscalationResult(BaseModel):
    requires_escalation: bool
    reasons: list[str]          # 所有触发原因，按严重性降序排列
    primary_reason: str         # reasons[0]，前端展示用

    # 优先级规则（由 escalation_checker.py 执行）：
    # 1. Critical 风险     → 最高优先级
    # 2. 低置信度          → 次优先级
    # 3. 关键字段缺失      → 最低优先级
    # 多条件同时触发时，reasons 包含全部原因，primary_reason 取最高优先级

class RiskAssessment(BaseModel):
    risk_level: RiskLevel
    risk_summary: str               # 一句话风险概述
    reasoning: str                  # 风险推理依据（XAI 可解释性）
    jurisdictions_covered: list[Literal["EU", "CN"]]  # 实际覆盖的法域
    evidence: list[EvidenceChunk]
    remediation: list[RemediationAction]
    low_confidence_items: list[str]
    requires_escalation: bool

    # 风险评分因子（来自 risk_scorer.py，结构化记录）
    scoring_factors: list[dict]
    # 格式：[{"rule": "biometric_force_critical",
    #          "description": "Biometric data → force Critical",
    #          "impact": "force Critical"}, ...]
```

`schemas/report.py`：

```python
from uuid import uuid4
from datetime import datetime
from pydantic import BaseModel, Field

class AuditReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    session_id: str

    # 5 段式结构（对应 PRD FR6）
    summary: str                                      # 段落 1：场景摘要
    risk_level: RiskLevel                             # 段落 2：风险等级
    risk_overview: str                                # 段落 2：一句话概述
    evidence_citations: list[EvidenceChunk]           # 段落 3：证据引用
    uncertainties: list[str]                          # 段落 4：不确定项
    remediation_actions: list[RemediationAction]      # 段落 5：整改建议

    # 元信息
    parsed_fields: ParsedFields
    jurisdictions_covered: list[Literal["EU", "CN"]]
    requires_escalation: bool
    escalation_result: EscalationResult | None
    disclaimer: str                  # 单一字段，to_markdown() 负责顶部底部各渲染一次

    def to_markdown(self) -> str:
        # 结构：
        # {disclaimer}          ← 顶部渲染
        # ## 场景摘要
        # ## 风险等级
        # ## 法规证据
        # ## 不确定项
        # ## 整改建议
        # {disclaimer}          ← 底部再次渲染
        ...

    def to_json(self) -> dict:
        return self.model_dump()
```

Phase A 完成标准：
- `python -c "from schemas.risk import RiskAssessment; print('ok')"` 无报错
- `AuditReport.to_markdown()` 输出中，disclaimer 在顶部和底部各出现一次
- 所有 Pydantic 模型可正常实例化，无 ValidationError

---

### A-2. 风险评分工具（tools/risk_scorer.py）

**职责边界（硬约束）：**
risk_level 的最终值必须以 risk_scorer.py 的输出为唯一来源。
LLM 在 Phase B 中不得自行判断或覆盖风险等级，
LLM 仅负责：组织 reasoning 文本、生成 remediation、
提取 low_confidence_items、整理 evidence 到 Schema。

```python
def calculate_risk_level(
    evidence: list[EvidenceChunk],
    parsed_fields: ParsedFields
) -> tuple[RiskLevel, str, list[dict]]:
    # 返回：(risk_level, reasoning_summary, scoring_factors)
```

评分逻辑（纯规则引擎，不调用 LLM）：

**Step 1 — 基础分（取命中法规条款的最高严重度）：**

命中以下关键词 → Critical 起步：
  "biometric" / "生物特征" / "人脸识别" / "adequacy decision" /
  "数据出境安全评估" / "Standard Contractual Clauses"

命中以下关键词 → High 起步：
  "cross-border transfer" / "third country" / "跨境传输" / "数据出境"

命中以下关键词 → Medium 起步：
  "consent" / "同意" / "transparency" / "透明度" / "告知"

其他命中 → Low

**Step 2 — 加权调整（叠加在基础分之上）：**

rule: "cross_border_plus_third_party"
  条件：cross_border=True AND third_party_model=True
  impact: +1 级

rule: "biometric_force_critical"
  条件：data_types 包含 "Biometric"
  impact: 强制 Critical（忽略当前基础分，直接置顶）

rule: "aigc_cn_regulation"
  条件：aigc_output=True AND region 包含 "CN"
  impact: +1 级
  说明：《AIGC 标识办法》2025 年 9 月全面生效，CN 强监管

rule: "dual_jurisdiction_complexity"
  条件：region == "EU+CN"
  impact: +1 级（合规复杂度叠加）

**Step 3 — 上限：** Critical 不再上升。

**scoring_factors 输出格式：**

```python
[
    {
        "rule": "biometric_force_critical",
        "description": "Biometric data present → force Critical",
        "impact": "force Critical"
    },
    {
        "rule": "dual_jurisdiction_complexity",
        "description": "Region EU+CN → +1 complexity adjustment",
        "impact": "+1 level (capped at Critical)"
    }
]
```

Phase A 完成标准（新增）：
- `pytest tests/unit/test_risk_scorer.py -v` 全部通过，包含：
  - test_scenario_a → Critical（含 Biometric）
  - test_scenario_b → High（EU，第三方模型）
  - test_scenario_c → High 或 Critical（EU+CN，AIGC）
  - test_deterministic：同一输入多次运行结果完全一致
  - test_biometric_force_critical：无论基础分，含 Biometric 必为 Critical

---

## Phase B：Risk Agent + Confidence Gate

### B-1. Risk Agent（agents/risk_agent.py）

继承 `agents/base.py` 的 ReAct 基类。

**执行限制（两个维度同时约束）：**

```python
MAX_RETRIEVAL_ACTIONS = 2   # 检索动作上限（initial + 1 supplemental）
MAX_REACT_STEPS = 6         # 总步数上限（含所有 Think / Observe）
```

超过任一限制时，强制终止循环并标记 requires_escalation=True，
reason="ReAct 循环达到上限，分析结论可能不完整"。

**ReAct 循环设计：**

```
Think-1：
  分析 ParsedFields，制定检索策略
  - 确定 jurisdiction（EU / CN / All）
  - 提取检索关键词（从字段映射：Biometric→"生物特征 biometric",
    cross_border→"跨境传输 cross-border transfer" 等）
  - 判断是否需要分法域检索（region="EU+CN" 时必须覆盖两个法域）

Act-1（第一次检索，必做）：
  调用 tools/rag_retriever.py
  输入：query（自然语言）+ parsed_fields

Observe-1：
  评估证据充分性：
  - 证据数量 ≥ 3 且最高 rerank_score ≥ 0.6 → 充分
  - region="EU+CN" 且 jurisdictions_covered 只有一个法域 → 不充分
  - 证据数量 < 3 或最高 rerank_score < 0.6 → 不充分

Act-2（第二次检索，条件触发）：
  仅在 Observe-1 判定不充分时执行，换关键词或切换法域
  这是最后一次允许的检索动作

Observe-2：
  记录最终证据列表，更新 jurisdictions_covered

Act-3：
  调用 tools/risk_scorer.py
  输入：evidence + parsed_fields
  输出：(risk_level, reasoning_summary, scoring_factors)
  ⚠️ 此处 risk_level 即为最终风险等级，LLM 不得修改

Think-2：
  基于证据和 risk_scorer 结果，生成：
  - reasoning（跨法域场景分段书写，见下方格式要求）
  - remediation（按 PM / Dev / Security 分组）
  - low_confidence_items（证据不足或字段缺失的判断点）
```

**跨法域 reasoning 格式（region="EU+CN" 时强制执行）：**

```
【EU 合规要求】
基于 GDPR Art.46：...

【CN 合规要求】
基于 PIPL 第38条：...

【跨法域注意事项】
GDPR 要求 SCC 而 PIPL 要求安全评估，两者并行义务，不可相互替代。
```

**System Prompt（prompts/system/risk.txt）：**

```
你是一位专注于中欧数据合规的法律分析助手。
你的任务是基于检索到的法规证据，对 AI 产品功能场景进行风险分析。

职责边界（严格遵守）：
- 风险等级 risk_level 已由规则引擎确定，你不得修改
- 你只负责：组织 reasoning、生成 remediation、
  提取 low_confidence_items、整理 evidence 到 Schema
- 所有判断必须有法规条款作为依据，不得凭空推断
- 证据不足的判断点，明确标注为 low_confidence_items，不强行给出结论
- 中欧双法域场景下，分别呈现各法域要求，不合并处理
- 你的输出是「前置风控参考」，不使用绝对化表述
  （不写"必须"、"违法"、"违规"等词）

输出格式：严格按照 RiskAssessment Schema 输出 JSON，不加任何额外说明。
```

**Few-shot（prompts/few_shot/risk_examples.json）：**

提供 3 条示例，每条包含：
- input：ParsedFields（JSON）+ EvidenceChunk 列表 + risk_scorer 输出
- output：完整 RiskAssessment（JSON）
- rationale：推理说明（运行时过滤，不传入 LLM context）

示例覆盖：
- 示例 1：场景 A（EU+CN 跨境训练，Biometric）→ Critical，reasoning 分段
- 示例 2：场景 B（第三方模型 API，EU）→ High
- 示例 3：场景 C（AIGC 广告视频，EU+CN）→ High

**运行时过滤 rationale 的代码：**

```python
def load_few_shot_examples() -> list[dict]:
    with open("prompts/few_shot/risk_examples.json") as f:
        examples = json.load(f)
    # 过滤 rationale 字段，避免占用 token
    return [
        {k: v for k, v in ex.items() if k != "rationale"}
        for ex in examples
    ]
```

Phase B 完成标准：
- 场景 A：risk_level=Critical，evidence 包含 GDPR 和 PIPL 各至少 1 条，
  reasoning 包含「EU 合规要求」和「CN 合规要求」两个段落
- 场景 A：scoring_factors 包含 "biometric_force_critical" 规则记录
- ReAct 循环步数 ≤ MAX_REACT_STEPS，检索动作 ≤ MAX_RETRIEVAL_ACTIONS
- `pytest tests/unit/test_risk_scorer.py tests/integration/test_risk_agent.py -v`
  全部通过

---

### B-2. Confidence Gate（guards/confidence_gate.py）

```python
def evaluate_confidence(
    evidence: list[EvidenceChunk],
    parsed_fields: ParsedFields
) -> ConfidenceResult:
```

判断逻辑（任一触发即为 low_confidence）：

条件 1：所有 EvidenceChunk 的 rerank_score < 0.6

条件 2：Top-3 Chunks 来自 3 个不同法规且 tags 无交集

条件 3：parsed_fields.missing_fields 数量 ≥ 2

触发时：low_confidence=True，附带具体 reason 字符串。

```python
class ConfidenceResult(BaseModel):
    low_confidence: bool
    reason: str | None      # 低置信度时说明原因
    triggered_conditions: list[str]  # 触发的条件列表，便于调试
```

**跨法域完整性检查（region="EU+CN" 专项）：**

```python
def check_jurisdiction_completeness(
    evidence: list[EvidenceChunk],
    parsed_fields: ParsedFields
) -> bool:
    # 返回 False（不完整）的条件：
    # region="EU+CN" 但 evidence 中只包含单一法域的 Chunks
    # → 触发 low_confidence，reason="EU+CN 场景仅检索到单一法域证据"
```

Phase B 完成标准（新增测试）：
- test_low_confidence_empty_evidence：空 evidence → low_confidence=True
- test_cross_jurisdiction_completeness：
  region="EU+CN" + 仅 EU evidence → low_confidence=True
- test_confidence_gate_triggers_escalation：
  low_confidence=True → 后续 escalation_checker 正确接收

---

## Phase C：Report Generator + Disclaimers + Output Filter

### C-1. Output Filter（tools/output_filter.py）

**重要约束：**
output_filter 只处理指定的文本字段，
不得处理 evidence 原文摘要，避免篡改法规引用内容。

```python
# 允许过滤的字段白名单
FILTERABLE_FIELDS = {
    "summary",
    "risk_overview",
    "uncertainties",          # list[str]，逐项过滤
    "remediation_actions",    # 只过滤 action 字段
    "reasoning",
}

# 禁止过滤的字段（法规原文，不得修改）
PROTECTED_FIELDS = {
    "evidence_citations",     # EvidenceChunk.text / EvidenceChunk.summary
    "disclaimer",             # 免责声明本身不过滤
}

REPLACEMENTS = {
    # 中文
    "贵司必须": "建议贵司",
    "违法": "可能不符合相关法规要求",
    "违规": "存在合规风险",
    "必须立即": "建议尽快",
    "严重违反": "可能违反",
    "必须遵守": "需关注",
    # 英文
    "must": "should consider",
    "illegal": "potentially non-compliant",
    "must immediately": "should prioritize",
    "strictly prohibited": "generally not recommended",
}

def filter_report_fields(report: AuditReport) -> AuditReport:
    # 按字段白名单处理，返回新的 AuditReport 实例
    # 每次替换记录日志到 observability/logger.py：
    # {"field": "summary", "original": "...", "filtered": "...", "rule": "贵司必须"}
```

### C-2. Disclaimer（guards/legal_disclaimer.py）

```python
DISCLAIMER_STANDARD = """
⚠️ 免责声明：本报告由 AI 系统自动生成，仅作为业务前置风控参考，
不构成具有法律效力的正式合规意见。实际合规义务可能因具体业务上下文
而异，建议结合专业法务意见综合判断。
"""

DISCLAIMER_CRITICAL = """
🚨 高风险提示：本场景涉及高风险合规判断，AI 系统评估存在较高不确定性。
强烈建议在推进相关功能前，提交专业法务团队进行人工复核，
切勿仅凭本报告做出业务决策。
"""

def inject_disclaimer(report: AuditReport) -> AuditReport:
    # Critical 或 requires_escalation=True → DISCLAIMER_CRITICAL
    # 其他 → DISCLAIMER_STANDARD
    # disclaimer 字段存储一份文本
    # to_markdown() 负责在顶部和底部各渲染一次（不改 schema）
```

### C-3. Escalation Checker（processors/escalation_checker.py）

纯规则引擎，不调用 LLM。

```python
def check_escalation(
    risk_assessment: RiskAssessment,
    parsed_fields: ParsedFields,
    confidence_result: ConfidenceResult
) -> EscalationResult:
```

**优先级规则（高优先级排在 reasons 列表前面）：**

```
优先级 1（最高）— Critical 风险：
  条件：risk_assessment.risk_level == RiskLevel.CRITICAL
  reason: "高风险场景（Critical），需人工法务复核"

优先级 2 — 低置信度：
  条件：confidence_result.low_confidence == True
  reason: confidence_result.reason

优先级 3（最低）— 关键字段缺失：
  条件：parsed_fields.missing_fields 包含 "region" 或 "data_types"
  reason: "关键字段缺失（{missing}），评估结论存在重大不确定性"
```

多条件同时触发时：
- `reasons` 包含全部触发原因（按优先级降序）
- `primary_reason` = reasons[0]（最高优先级原因）
- `requires_escalation` = True（任一触发即为 True）

### C-4. Report Generator（processors/report_generator.py）

```python
async def generate_report(
    state: SharedState,
    risk_assessment: RiskAssessment,
    escalation_result: EscalationResult
) -> AuditReport:
```

System Prompt（prompts/templates/report.txt）：

```
请根据以下结构化分析结果，生成一份 5 段式合规审计报告。

核心约束（严格遵守）：
报告生成阶段不得新增 RiskAssessment 中不存在的法规结论、风险点
或整改义务。只能重组、归纳和表述已有结构化结果。
已标注为 low_confidence_items 的判断点，在报告中必须呈现为
「待定项」，不得转化为确定性结论。

各段落要求：
- 段落 1（场景摘要）：3-5 句话客观复述用户场景，不加主观判断
- 段落 2（风险等级）：{risk_level}，附一句话概述最主要风险点
- 段落 3（证据引用）：每条法规依据格式为
  「[法规名 条款号] 条款摘要」，严格来自 evidence_citations，不扩展
- 段落 4（不确定项）：列举所有 low_confidence_items 和 missing_fields，
  明确标注「以下内容因信息不足，结论存在不确定性」
- 段落 5（整改建议）：按 PM / 研发 / 安全治理三组呈现，
  每条建议必须对应 remediation_actions 中的条目，不新增

语言：与用户输入语言一致（中文输入 → 中文报告）
输出格式：严格按 AuditReport Schema 输出 JSON，不加任何额外说明
```

**生成完成后的处理顺序（顺序不可颠倒）：**

```python
report = await llm_generate(prompt, risk_assessment)
report = output_filter.filter_report_fields(report)    # Step 1：先过滤
report = legal_disclaimer.inject_disclaimer(report)    # Step 2：再注入免责声明
# ⚠️ 顺序说明：必须先过滤再注入，避免免责声明本身被 output_filter 处理
```

Phase C 完成标准：
- 场景 A 报告：to_markdown() 输出中 disclaimer 在顶部和底部各出现一次
- 场景 A 报告：evidence_citations 中的法规原文未被 output_filter 修改
- 含「贵司必须」的文本经 filter_report_fields 后，相关字段已替换，
  evidence 字段未变动
- 报告 JSON 通过 AuditReport.model_validate() 无 ValidationError

---

## Phase D：Orchestrator + Integration Tests

### D-1. Router（orchestrator/router.py）

```python
def route_by_region(
    parsed_fields: ParsedFields
) -> list[Literal["EU", "CN"]]:
    # EU       → ["EU"]
    # CN       → ["CN"]
    # EU+CN    → ["EU", "CN"]
    # Global   → ["EU", "CN"]
    # None     → ["EU", "CN"]（保守策略：两个法域都检索）

    # ⚠️ 注意：None 时的保守策略是检索策略，不代表最终法域结论
    # 当 parsed_fields.region 为 None 时，
    # 必须在 AuditReport.uncertainties 中添加：
    # "用户所在法域未明确，当前报告按中欧双法域保守评估，
    #  实际适用法域请结合业务确认"
```

### D-2. Pipeline（orchestrator/pipeline.py）

**返回类型统一为 SharedState（解决原版类型不一致问题）：**

约定：
- `state.status == COMPLETED` 且 `state.report is not None`：成功完成
- `state.status == AWAITING_FOLLOWUP`：挂起，等待用户补充信息
- `state.status == FAILED`：失败，`state.error` 中保留错误上下文

```python
async def run_pipeline(
    scenario_input: ScenarioInput,
    on_progress: Callable[[PipelineStatus, str], Awaitable[None]] | None = None
) -> SharedState:   # 统一返回 SharedState，不再返回 AuditReport

    state = SharedState(session_id=scenario_input.session_id)

    try:
        # Step 1: PII 脱敏（同步，asyncio.to_thread 包装）
        await update(state, SANITIZING, "正在进行数据脱敏处理...", on_progress)
        sanitized_text, pii_map = await asyncio.to_thread(
            sanitizer.anonymize, scenario_input.raw_text
        )
        state.pii_map = pii_map

        # Step 2: 场景解析
        await update(state, PARSING, "正在解析业务场景...", on_progress)
        parsed_fields, followup_questions = await intake_agent.run(sanitized_text)
        state.parsed_fields = parsed_fields

        # Step 3: 追问（最多 2 轮，由 IntakeAgent 内部管理轮次）
        if followup_questions:
            state.followup_questions = followup_questions
            await update(state, AWAITING_FOLLOWUP, "需要补充信息...", on_progress)
            return state   # 挂起，等待 API 层恢复

        # Step 4: 法规检索 + 风险分析
        jurisdictions = router.route_by_region(parsed_fields)
        await update(
            state, RETRIEVING,
            f"正在检索 {' + '.join(jurisdictions)} 法规...",
            on_progress
        )
        await update(state, ANALYZING, "正在进行风险分析...", on_progress)
        risk_assessment = await risk_agent.run(parsed_fields)
        state.risk_assessment = risk_assessment

        # Step 5: 护栏校验
        confidence_result = confidence_gate.evaluate_confidence(
            risk_assessment.evidence, parsed_fields
        )
        escalation_result = escalation_checker.check_escalation(
            risk_assessment, parsed_fields, confidence_result
        )
        state.escalation_result = escalation_result

        # Step 6: 报告生成
        await update(state, GENERATING, "正在生成审计报告...", on_progress)
        report = await report_generator.generate_report(
            state, risk_assessment, escalation_result
        )
        state.report = report
        await update(state, COMPLETED, "报告已生成", on_progress)

    except Exception as e:
        state.status = PipelineStatus.FAILED
        state.error = str(e)
        logger.error(f"Pipeline failed: {e}", exc_info=True)

    return state


async def resume_pipeline(
    state: SharedState,
    user_followup: str,
    on_progress: Callable | None = None
) -> SharedState:
    # 追问完成后由 API 层调用，从 AWAITING_FOLLOWUP 处恢复
    # 将用户补充信息合并回 ParsedFields，继续执行 Step 4 起的流程
    assert state.status == PipelineStatus.AWAITING_FOLLOWUP
    ...
```

Phase D 完成标准：

**集成测试（tests/integration/test_pipeline.py）：**

```python
# 使用 conftest.py 的 mock_llm + mock_rag fixtures

# 1. Happy path
def test_pipeline_scenario_a(mock_llm, mock_rag):
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    assert state.status == PipelineStatus.COMPLETED
    assert state.report.risk_level == RiskLevel.CRITICAL
    assert state.report.requires_escalation == True
    assert "高风险提示" in state.report.disclaimer
    assert len(state.report.evidence_citations) >= 2
    assert len(state.report.remediation_actions) >= 3
    assert {"EU", "CN"}.issubset(set(state.report.jurisdictions_covered))

# 2. 追问挂起
def test_pipeline_awaiting_followup(mock_llm):
    state = asyncio.run(run_pipeline(VAGUE_INPUT))
    assert state.status == PipelineStatus.AWAITING_FOLLOWUP
    assert state.followup_questions is not None

# 3. Schema contract test
def test_report_schema_contract(mock_llm, mock_rag):
    state = asyncio.run(run_pipeline(SCENARIO_B_INPUT))
    report_json = state.report.to_json()
    AuditReport.model_validate(report_json)   # 格式错误立即暴露

# 4. Escalation priority test
def test_escalation_priority(mock_llm, mock_rag_critical):
    # mock_rag_critical 返回 Critical 场景的 evidence
    # 同时命中 Critical + low_confidence + missing_fields
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    escalation = state.escalation_result
    assert escalation.requires_escalation == True
    assert "Critical" in escalation.primary_reason   # 最高优先级
    assert len(escalation.reasons) >= 2               # 多条原因均记录

# 5. Cross-jurisdiction completeness test
def test_cross_jurisdiction_eu_cn(mock_llm, mock_rag_eu_only):
    # mock_rag_eu_only 只返回 EU 法规的 evidence
    # region="EU+CN" 场景应触发 low_confidence
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    assert state.report.requires_escalation == True
    uncertainty_text = " ".join(state.report.uncertainties)
    assert "单一法域" in uncertainty_text or "EU" in uncertainty_text

# 6. Pipeline failure handling
def test_pipeline_failure_handling(mock_llm_raises):
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    assert state.status == PipelineStatus.FAILED
    assert state.error is not None
    assert state.report is None   # 失败时不返回部分报告
```

---

## 全局技术约束

- RiskAgent 统一使用 claude-sonnet-4-20250514，不降级为 Haiku
- ReAct 循环：MAX_RETRIEVAL_ACTIONS=2，MAX_REACT_STEPS=6，
  超出任一限制强制终止并标记 escalation
- output_filter 必须在 legal_disclaimer 注入之前执行，顺序不可颠倒
- pipeline.py 中所有 LLM 调用使用 async/await，
  同步函数（PII 脱敏、BM25）用 asyncio.to_thread 包装
- 所有 Agent 输出必须经过 Pydantic model_validate 校验，
  ValidationError 触发 escalation 而非直接抛出异常
- evidence 字段内容（法规原文）在任何处理阶段均不得被修改或过滤

## 最终完成标准 Checklist

- [ ] `pytest tests/ -v` 全部通过（unit + integration，含 Day 1/2 测试）
- [ ] 场景 A 端到端：status=COMPLETED，risk_level=Critical，
      双法域证据引用，DISCLAIMER_CRITICAL
- [ ] 场景 C 报告：reasoning 包含「EU 合规要求」「CN 合规要求」
      「跨法域注意事项」三个段落
- [ ] output_filter 验证：evidence 原文未被修改，summary 中
      「贵司必须」已替换
- [ ] escalation priority 验证：Critical + low_confidence 同时触发时，
      primary_reason 为 Critical 相关原因
- [ ] `git commit -m "feat: Day3 risk_agent + guardrails + orchestrator"`
```