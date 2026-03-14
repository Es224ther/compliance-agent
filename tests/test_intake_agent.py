from agents.intake_agent import IntakeAgent
from app.schemas import ScenarioInput, SharedState
from config.settings import Settings


def test_intake_agent_loads_prompt_and_validates_tool_output(mock_llm_client) -> None:
    client = mock_llm_client(
        {
            "region": "EU",
            "data_types": ["Personal"],
            "cross_border": True,
            "third_party_model": True,
            "aigc_output": True,
            "data_volume_level": "Huge",
        }
    )
    settings = Settings.model_construct(
        api_key="test-key",
        model_name="claude-sonnet-4-20250514",
    )

    agent = IntakeAgent(settings=settings)
    output = agent.run(
        ScenarioInput(
            raw_text="We send EU user names to a third-party model and return generated answers."
        )
    )

    assert "AI 产品合规分析助手" in agent.system_prompt
    assert len(agent.few_shot_examples) == 3
    assert output.final_output.parsed_fields.region == "EU"
    assert output.final_output.parsed_fields.data_volume_level is None
    assert output.final_output.invalid_fields == ["data_volume_level"]
    assert output.final_output.requires_followup is False
    assert client.messages.calls[0]["tool_choice"] == {
        "type": "tool",
        "name": "parse_scenario",
    }
    schema = client.messages.calls[0]["tools"][0]["input_schema"]
    assert schema["additionalProperties"] is False
    assert schema["propertyOrdering"][0] == "region"


def test_intake_agent_generates_followup_when_required_fields_are_missing(
    mock_llm_client,
) -> None:
    mock_llm_client(
        {
            "region": None,
            "data_types": ["Personal"],
            "cross_border": None,
            "third_party_model": True,
            "aigc_output": True,
            "data_volume_level": "Medium",
        }
    )
    settings = Settings.model_construct(
        api_key="test-key",
        model_name="claude-sonnet-4-20250514",
    )

    agent = IntakeAgent(settings=settings)
    output = agent.run(ScenarioInput(raw_text="Scenario with missing region and transfer flow."))

    assert output.final_output.requires_followup is True
    assert output.final_output.missing_fields == ["region", "cross_border"]
    assert "1. 你的业务主要涉及哪个法域？" in output.final_output.followup_prompt
    assert output.final_output.shared_state.followup_rounds == 1


def test_intake_agent_stops_followup_after_two_rounds(mock_llm_client) -> None:
    mock_llm_client(
        {
            "region": None,
            "data_types": None,
            "cross_border": None,
            "third_party_model": None,
            "aigc_output": None,
            "data_volume_level": None,
        }
    )
    settings = Settings.model_construct(
        api_key="test-key",
        model_name="claude-sonnet-4-20250514",
    )

    agent = IntakeAgent(settings=settings)
    state = SharedState(
        raw_input=ScenarioInput(raw_text="Still unclear after follow-up."),
        followup_rounds=2,
    )
    output = agent.run(state)

    assert output.final_output.requires_followup is False
    assert output.final_output.followup_prompt is None
    assert output.final_output.shared_state.missing_fields == [
        "region",
        "data_types",
        "cross_border",
    ]


def test_extract_tool_use_reads_anthropic_tool_use_block() -> None:
    from types import SimpleNamespace

    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name="parse_scenario",
                input={
                    "region": "EU",
                    "data_types": ["Personal"],
                    "cross_border": True,
                },
            )
        ]
    )

    tool_use = IntakeAgent._extract_tool_use(response)

    assert tool_use == {
        "name": "parse_scenario",
        "input": {
            "region": "EU",
            "data_types": ["Personal"],
            "cross_border": True,
        },
    }
