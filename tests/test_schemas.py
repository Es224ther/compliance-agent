from app.schemas import ParsedFields, ScenarioInput, SharedState


def test_scenario_input_generates_session_id() -> None:
    scenario = ScenarioInput(raw_text="User data from EU is sent to an external model.")

    assert scenario.raw_text == "User data from EU is sent to an external model."
    assert isinstance(scenario.session_id, str)
    assert scenario.session_id


def test_parsed_fields_accept_expected_literals() -> None:
    parsed = ParsedFields(
        region="EU+CN",
        data_types=["Personal", "Financial"],
        cross_border=True,
        third_party_model=True,
        aigc_output=False,
        data_volume_level="Large",
    )

    assert parsed.region == "EU+CN"
    assert parsed.data_types == ["Personal", "Financial"]
    assert parsed.cross_border is True
    assert parsed.third_party_model is True
    assert parsed.aigc_output is False
    assert parsed.data_volume_level == "Large"


def test_shared_state_defaults_are_pipeline_safe() -> None:
    state = SharedState(raw_input=ScenarioInput(raw_text="Draft a marketing summary."))

    assert state.parsed_fields == ParsedFields()
    assert state.pii_map == {}
    assert state.followup_rounds == 0
    assert state.followup_prompt is None
    assert state.missing_fields == []
    assert state.risk_level is None
    assert state.evidence == []
    assert state.report is None
