from types import SimpleNamespace

import pytest


class StubMessagesAPI:
    def __init__(self, response: object | None = None) -> None:
        self.response = response
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.response is None:
            raise AssertionError("Stub LLM response was not configured.")
        return self.response


class StubAnthropicClient:
    def __init__(self, response: object | None = None) -> None:
        self.messages = StubMessagesAPI(response=response)


@pytest.fixture
def mock_llm_client(monkeypatch):
    client = StubAnthropicClient()

    def _set_response(payload: dict) -> StubAnthropicClient:
        client.messages.response = SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    name="parse_scenario",
                    input=payload,
                )
            ]
        )
        return client

    monkeypatch.setattr("agents.intake_agent.get_client", lambda: client)
    return _set_response
