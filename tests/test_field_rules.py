from app.schemas import ParsedFields
from guards.field_rules import (
    REQUIRED_FIELDS,
    check_completeness,
    generate_followup_prompt,
    generate_uncertainties,
)


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


def test_generate_uncertainties_from_null_fields_and_hedging_words() -> None:
    parsed_fields = ParsedFields(
        region="EU+CN",
        data_types=["Personal", "Biometric"],
        cross_border=True,
        third_party_model=None,
        aigc_output=None,
        data_volume_level=None,
    )
    raw_text = (
        "我们计划把欧洲用户视频传回国内训练模型，视频中可能包含用户人脸，"
        "AIGC 是否对外展示暂时不确定。"
    )

    uncertainties = generate_uncertainties(parsed_fields, raw_text)
    joined = " ".join(uncertainties)

    assert "[aigc_output]" in joined
    assert "[data_volume_level]" in joined
    assert "[third_party_model]" in joined
    assert "[描述模糊]" in joined
    assert "可能" in joined
    assert "不确定" in joined
    assert "暂时" in joined
