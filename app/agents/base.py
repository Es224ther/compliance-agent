"""Minimal ReAct agent base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolResult:
    """Result of a single tool invocation inside an agent loop."""

    name: str
    tool_input: dict[str, Any] | None = None
    output: Any = None
    raw_response: Any = None
    is_final: bool = False
    error: str | None = None


@dataclass(slots=True)
class AgentOutput:
    """Structured outcome of an agent run."""

    final_output: Any
    thoughts: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    steps: int = 0


class ReActAgent(ABC):
    """Minimal ReAct loop abstraction."""

    def __init__(self, tools: list[dict[str, Any]] | None = None) -> None:
        self.tools = tools or []

    @abstractmethod
    def think(self, context: Any) -> str:
        """Generate the next thought from current context."""

    @abstractmethod
    def act(self, thought: str, tools: list[dict[str, Any]]) -> ToolResult:
        """Execute the next action using available tools."""

    @abstractmethod
    def observe(self, result: ToolResult) -> str:
        """Produce an observation from the action result."""

    def run(self, input: Any, max_steps: int = 5) -> AgentOutput:
        """Execute the ReAct loop until a final result or step budget is reached."""

        context: Any = input
        thoughts: list[str] = []
        observations: list[str] = []
        tool_results: list[ToolResult] = []

        for step in range(1, max_steps + 1):
            thought = self.think(context)
            thoughts.append(thought)

            result = self.act(thought, self.tools)
            tool_results.append(result)

            observation = self.observe(result)
            observations.append(observation)

            if result.is_final or result.error:
                return AgentOutput(
                    final_output=result.output,
                    thoughts=thoughts,
                    observations=observations,
                    tool_results=tool_results,
                    steps=step,
                )

            context = {
                "input": input,
                "last_thought": thought,
                "last_observation": observation,
                "step": step,
            }

        return AgentOutput(
            final_output=tool_results[-1].output if tool_results else None,
            thoughts=thoughts,
            observations=observations,
            tool_results=tool_results,
            steps=max_steps,
        )
