from app.schemas import ParsedFields
from guards.field_rules import REQUIRED_FIELDS, check_completeness, generate_followup_prompt


def test_required_fields_are_checked_for_completeness() -> None:
    missing_fields = check_completeness(
        ParsedFields(region=None, data_types=["Personal"], cross_border=None)
    )

    assert REQUIRED_FIELDS == ["region", "data_types", "cross_border"]
    assert missing_fields == ["region", "cross_border"]


def test_followup_prompt_uses_template_and_caps_at_three_questions() -> None:
    prompt = generate_followup_prompt(
        ["region", "data_types", "cross_border", "third_party_model"]
    )

    assert "请补充以下关键信息" in prompt
    assert "1. 你的业务主要涉及哪个法域？" in prompt
    assert "2. 本次场景明确处理了哪些数据类型？" in prompt
    assert "3. 是否存在跨境传输或境外访问？" in prompt
    assert "第三方模型" not in prompt
