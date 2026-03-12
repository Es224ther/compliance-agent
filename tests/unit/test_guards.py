from app.schemas import ParsedFields, ScenarioInput, SharedState
from guards.field_rules import check_completeness, generate_followup_prompt


def test_missing_region_triggers_followup() -> None:
    parsed_fields = ParsedFields(
        region=None,
        data_types=["Personal"],
        cross_border=True,
    )

    missing_fields = check_completeness(parsed_fields)
    prompt = generate_followup_prompt(missing_fields)

    assert missing_fields == ["region"]
    assert "你的业务主要涉及哪个法域？" in prompt


def test_complete_fields_no_followup() -> None:
    parsed_fields = ParsedFields(
        region="EU",
        data_types=["Personal"],
        cross_border=False,
    )

    missing_fields = check_completeness(parsed_fields)

    assert missing_fields == []


def test_max_rounds_marks_missing() -> None:
    state = SharedState(
        raw_input=ScenarioInput(raw_text="Unknown scenario"),
        parsed_fields=ParsedFields(region=None, data_types=None, cross_border=None),
        followup_rounds=2,
    )

    state.missing_fields = check_completeness(state.parsed_fields)

    assert state.followup_rounds == 2
    assert state.missing_fields == ["region", "data_types", "cross_border"]
