"""Field completeness rules and follow-up prompt generation."""

from __future__ import annotations

from pathlib import Path
from string import ascii_uppercase
from typing import Any

from app.schemas import ParsedFields

REQUIRED_FIELDS = ["region", "data_types", "cross_border"]
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "templates" / "followup.txt"

QUESTION_BANK = {
    "region": {
        "question": "你的业务主要涉及哪个法域？",
        "options": ["仅 EU", "仅 CN", "同时涉及 EU 和 CN", "面向全球多个地区"],
    },
    "data_types": {
        "question": "本次场景明确处理了哪些数据类型？",
        "options": ["Personal", "Behavioral", "Biometric", "Financial"],
    },
    "cross_border": {
        "question": "是否存在跨境传输或境外访问？",
        "options": ["是", "否", "目前不确定"],
    },
    "third_party_model": {
        "question": "是否调用第三方模型或外部模型服务？",
        "options": ["是", "否", "目前不确定"],
    },
    "aigc_output": {
        "question": "是否向终端用户输出 AI 生成内容？",
        "options": ["是", "否", "目前不确定"],
    },
    "data_volume_level": {
        "question": "数据规模更接近哪一档？",
        "options": ["Small", "Medium", "Large", "目前不确定"],
    },
}

FIELD_UNCERTAINTY_MAP = {
    "aigc_output": (
        "用户未明确说明 AI 生成内容是否面向终端用户。若生成内容面向公众，"
        "可能触发 EU AI Act 第 50 条透明度义务和《AIGC 标识办法》的标识要求。"
    ),
    "data_volume_level": (
        "用户未说明数据处理规模。若处理超过 10 万人个人信息或 1 万人敏感个人信息，"
        "可能触发 PIPL 第四十条的数据出境安全评估申报义务。"
    ),
    "third_party_model": (
        "用户未明确是否涉及第三方模型调用。若涉及第三方处理，需额外评估数据共享的合规要求。"
    ),
}

HEDGING_PATTERNS = [
    ("可能", '用户描述中使用了"可能"，对应内容的确定性不足'),
    ("也许", '用户描述中使用了"也许"，对应内容的确定性不足'),
    ("不确定", "用户表示不确定"),
    ("暂时", "用户描述为暂时性方案，最终方案可能变化"),
]


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
    selected_fields = _select_known_fields(missing_fields)
    questions = [
        f"{index}. {_question_block(field_name)}"
        for index, field_name in enumerate(selected_fields, start=1)
    ]
    return template.format(questions="\n\n".join(questions))


def generate_followup_questions(missing_fields: list[str]) -> list[dict[str, Any]]:
    """Build structured follow-up questions for frontend rendering."""

    questions: list[dict[str, Any]] = []
    for field_name in _select_known_fields(missing_fields):
        config = QUESTION_BANK[field_name]
        options = [f"{ascii_uppercase[idx]}. {value}" for idx, value in enumerate(config["options"])]
        questions.append(
            {
                "field": field_name,
                "question": config["question"],
                "options": options,
            }
        )
    return questions


def generate_uncertainties(parsed_fields: ParsedFields, raw_text: str) -> list[str]:
    """Generate uncertainty items from null fields and hedging words in raw text."""

    uncertainties: list[str] = []
    fields_dict = parsed_fields.model_dump() if hasattr(parsed_fields, "model_dump") else vars(parsed_fields)

    for field_name, description in FIELD_UNCERTAINTY_MAP.items():
        if fields_dict.get(field_name) is None:
            uncertainties.append(f"[{field_name}] {description}")

    for keyword, description in HEDGING_PATTERNS:
        idx = raw_text.find(keyword)
        if idx < 0:
            continue
        left = max(0, idx - 20)
        right = min(len(raw_text), idx + len(keyword) + 20)
        context = raw_text[left:right].strip()
        uncertainties.append(f'[描述模糊] "{context}" — {description}')

    return uncertainties


def _select_known_fields(missing_fields: list[str]) -> list[str]:
    return [field_name for field_name in missing_fields if field_name in QUESTION_BANK][:3]


def _question_block(field_name: str) -> str:
    config = QUESTION_BANK[field_name]
    lines = [config["question"]]
    for idx, option in enumerate(config["options"]):
        lines.append(f"{ascii_uppercase[idx]}. {option}")
    return "\n".join(lines)
