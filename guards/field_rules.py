"""Field completeness rules and follow-up prompt generation."""

from __future__ import annotations

from pathlib import Path

from app.schemas import ParsedFields

REQUIRED_FIELDS = ["region", "data_types", "cross_border"]
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "templates" / "followup.txt"

QUESTION_BANK = {
    "region": (
        "你的业务主要涉及哪个法域？\n"
        "A. 仅 EU\n"
        "B. 仅 CN\n"
        "C. 同时涉及 EU 和 CN\n"
        "D. 面向全球多个地区"
    ),
    "data_types": (
        "本次场景明确处理了哪些数据类型？\n"
        "A. Personal\n"
        "B. Behavioral\n"
        "C. Biometric\n"
        "D. Financial"
    ),
    "cross_border": (
        "是否存在跨境传输或境外访问？\n"
        "A. 是\n"
        "B. 否\n"
        "C. 目前不确定"
    ),
    "third_party_model": (
        "是否调用第三方模型或外部模型服务？\n"
        "A. 是\n"
        "B. 否\n"
        "C. 目前不确定"
    ),
    "aigc_output": (
        "是否向终端用户输出 AI 生成内容？\n"
        "A. 是\n"
        "B. 否\n"
        "C. 目前不确定"
    ),
    "data_volume_level": (
        "数据规模更接近哪一档？\n"
        "A. Small\n"
        "B. Medium\n"
        "C. Large\n"
        "D. 目前不确定"
    ),
}


def check_completeness(parsed_fields: ParsedFields) -> list[str]:
    """Return missing required fields."""

    return [
        field_name
        for field_name in REQUIRED_FIELDS
        if getattr(parsed_fields, field_name) in (None, [])
    ]


def generate_followup_prompt(missing_fields: list[str]) -> str:
    """Generate up to three multiple-choice follow-up questions."""

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    selected_fields = missing_fields[:3]
    questions = [
        f"{index}. {QUESTION_BANK[field_name]}"
        for index, field_name in enumerate(selected_fields, start=1)
    ]
    return template.format(questions="\n\n".join(questions))
