"""Legal disclaimer injection for generated audit reports."""

from __future__ import annotations

from app.schemas.report import AuditReport
from app.schemas.risk import RiskLevel

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
    text = DISCLAIMER_STANDARD
    if report.risk_level == RiskLevel.CRITICAL or report.requires_escalation:
        text = DISCLAIMER_CRITICAL
    updated = report.model_copy(deep=True)
    updated.disclaimer = text.strip()
    return updated
