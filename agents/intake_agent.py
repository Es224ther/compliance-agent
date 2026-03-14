"""Intake agent for structured scenario parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from agents.base import ReActAgent, ToolResult
from app.schemas import ParsedFields, ScenarioInput, SharedState
from config.llm import get_client
from config.settings import Settings, get_settings
from guards.field_rules import check_completeness, generate_followup_prompt
from tools.schema_validator import SchemaValidationResult, validate_parse_scenario_output

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system" / "intake.txt"
FEW_SHOT_PATH = PROMPTS_DIR / "few_shot" / "intake_examples.json"
DEFAULT_MODEL_NAME = "claude-sonnet-4-20250514"


@dataclass(slots=True)
class IntakeResult:
    """Validated output of the intake parsing stage."""

    parsed_fields: ParsedFields
    invalid_fields: list[str]
    missing_fields: list[str]
    requires_followup: bool
    followup_prompt: str | None
    shared_state: SharedState
    raw_tool_input: dict[str, Any]


class IntakeAgent(ReActAgent):
    """Agent which parses a user scenario into deterministic fields."""

    def __init__(
        self,
        client: Anthropic | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.system_prompt = self._load_text(SYSTEM_PROMPT_PATH)
        self.few_shot_examples = self._load_examples(FEW_SHOT_PATH)
        tools = [self._build_parse_tool_schema()]
        super().__init__(tools=tools)
        self.client = client or get_client()
        self._current_state: SharedState | None = None

    def think(self, context: ScenarioInput | SharedState | dict[str, Any]) -> str:
        """Prepare the user message sent to the model."""

        state = self._coerce_state(context)
        self._current_state = state
        examples_json = json.dumps(self.few_shot_examples, ensure_ascii=False, indent=2)
        return (
            "请参考以下 few-shot 示例，并解析最后的用户场景。\n\n"
            f"Few-shot examples:\n{examples_json}\n\n"
            f"User scenario:\n{state.raw_input.raw_text}"
        )

    def act(self, thought: str, tools: list[dict[str, Any]]) -> ToolResult:
        """Call Claude with forced tool use and capture the tool input."""

        response = self.client.messages.create(
            model=self.settings.model_name or DEFAULT_MODEL_NAME,
            max_tokens=512,
            system=self.system_prompt,
            messages=[{"role": "user", "content": thought}],
            tools=tools,
            tool_choice={"type": "tool", "name": "parse_scenario"},
        )
        tool_use = self._extract_tool_use(response)

        validated = validate_parse_scenario_output(tool_use["input"])
        shared_state = self._build_shared_state(validated)

        return ToolResult(
            name=tool_use["name"],
            tool_input=tool_use["input"],
            output=IntakeResult(
                parsed_fields=validated.parsed_fields,
                invalid_fields=validated.invalid_fields,
                missing_fields=shared_state.missing_fields,
                requires_followup=bool(shared_state.followup_prompt),
                followup_prompt=shared_state.followup_prompt,
                shared_state=shared_state,
                raw_tool_input=tool_use["input"],
            ),
            raw_response=response,
            is_final=True,
        )

    def observe(self, result: ToolResult) -> str:
        """Summarize the validation outcome for the run loop."""

        if result.error:
            return result.error

        intake_result: IntakeResult = result.output
        if intake_result.requires_followup and intake_result.followup_prompt:
            return intake_result.followup_prompt
        if intake_result.invalid_fields:
            invalid = ", ".join(intake_result.invalid_fields)
            return f"Validated parse_scenario output; invalid fields reset to null: {invalid}"
        return "Validated parse_scenario output with no invalid fields."

    def _coerce_state(
        self, context: ScenarioInput | SharedState | dict[str, Any]
    ) -> SharedState:
        if isinstance(context, SharedState):
            return context
        if isinstance(context, ScenarioInput):
            return SharedState(raw_input=context)

        input_value = context["input"]
        if isinstance(input_value, SharedState):
            return input_value
        if isinstance(input_value, ScenarioInput):
            return SharedState(raw_input=input_value)
        raise TypeError("IntakeAgent expects ScenarioInput or SharedState as input.")

    def _build_shared_state(
        self, validated: SchemaValidationResult
    ) -> SharedState:
        if self._current_state is None:
            raise RuntimeError("IntakeAgent state was not initialized before act().")

        shared_state = self._current_state.model_copy(deep=True)
        shared_state.parsed_fields = validated.parsed_fields

        missing_fields = check_completeness(validated.parsed_fields)
        if missing_fields and shared_state.followup_rounds < 2:
            shared_state.followup_rounds += 1
            shared_state.missing_fields = missing_fields
            shared_state.followup_prompt = generate_followup_prompt(missing_fields)
            return shared_state

        shared_state.missing_fields = missing_fields
        shared_state.followup_prompt = None
        return shared_state

    @staticmethod
    def _load_text(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _load_examples(path: Path) -> list[dict[str, Any]]:
        examples = json.loads(path.read_text(encoding="utf-8"))
        return examples[:3]

    @staticmethod
    def _build_parse_tool_schema() -> dict[str, Any]:
        schema = IntakeAgent._parse_payload_json_schema()
        schema["additionalProperties"] = False
        schema["propertyOrdering"] = [
            "region",
            "data_types",
            "cross_border",
            "third_party_model",
            "aigc_output",
            "data_volume_level",
        ]
        return {
            "name": "parse_scenario",
            "description": "Parse a compliance scenario into structured fields.",
            "input_schema": schema,
        }

    @staticmethod
    def _extract_tool_use(response: Any) -> dict[str, Any]:
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) != "tool_use":
                continue
            return {
                "name": getattr(block, "name", "parse_scenario"),
                "input": dict(getattr(block, "input", {}) or {}),
            }

        preview = repr(response).replace("\n", "\\n")
        raise ValueError(
            "Claude response did not include a parse_scenario tool call. "
            f"Response preview: {preview[:240]}"
        )

    @staticmethod
    def _parse_payload_json_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "region": {
                    "type": ["string", "null"],
                    "enum": ["EU", "CN", "Global", "EU+CN", None],
                    "description": "Legal jurisdiction of the scenario",
                },
                "data_types": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "string",
                        "enum": ["Personal", "Behavioral", "Biometric", "Financial"],
                    },
                    "description": "Categories of data being processed",
                },
                "cross_border": {
                    "type": ["boolean", "null"],
                    "description": "Whether data crosses jurisdictional borders",
                },
                "third_party_model": {
                    "type": ["boolean", "null"],
                    "description": "Whether a third-party model API is used",
                },
                "aigc_output": {
                    "type": ["boolean", "null"],
                    "description": "Whether the feature produces AI-generated content",
                },
                "data_volume_level": {
                    "type": ["string", "null"],
                    "enum": ["Small", "Medium", "Large", None],
                    "description": "Volume of data processed",
                },
            },
            "required": [],
        }
