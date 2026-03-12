# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered compliance audit agent for evaluating EU (GDPR, EU AI Act) and Chinese (PIPL, DSL, CSL) regulatory compliance of AI features and data processing scenarios. Built on FastAPI + Anthropic Claude SDK with a ReAct agent pattern.

## Commands

```bash
# Environment setup
poetry install
cp .env.example .env  # Set API_KEY and MODEL_NAME

# Development
make dev              # Run FastAPI dev server (uvicorn app.main:app)
make test             # Run pytest
make ingest           # Ingest regulations into ChromaDB

# Testing
pytest                          # All tests
pytest -v                       # Verbose
pytest tests/test_intake_agent.py                     # Specific file
pytest tests/test_intake_agent.py::test_name          # Single test
```

**Required environment variables:**
- `API_KEY` — Anthropic API key
- `MODEL_NAME` — defaults to `claude-sonnet-4-20250514`

## Architecture

### Core Pattern: ReAct Agent Loop

The system uses a **Minimal ReAct (Reasoning + Acting)** loop defined in `agents/base.py`:
1. **Think** — Generate next reasoning step from context
2. **Act** — Call Claude with forced tool selection (`tool_choice={"type": "tool", "name": "..."}`)
3. **Observe** — Validate and interpret tool results
4. Loop until final result or step budget exhausted

### Primary Data Flow

```
User Input (Natural Language)
    → PII Anonymization (sanitizer/)       # MUST happen before any LLM call
    → IntakeAgent.run(ScenarioInput)       # agents/intake_agent.py
        → Claude parses into ParsedFields  # 6 structured fields
        → Field validation (guards/)
        → Follow-up questions if required fields missing (max 2 rounds)
    → [Planned] Risk Analysis + RAG retrieval
    → [Planned] Report generation
```

### ParsedFields Schema (app/schemas/scenario.py)

The 6 core structured fields extracted from natural language:
- `region`: `"EU" | "CN" | "Global" | "EU+CN" | None`
- `data_types`: `list[Literal["Personal", "Behavioral", "Biometric", "Financial"]] | None`
- `cross_border`: `bool | None`
- `third_party_model`: `bool | None`
- `aigc_output`: `bool | None`
- `data_volume_level`: `"Small" | "Medium" | "Large" | None`

Required fields: `region`, `data_types`, `cross_border` (defined in `guards/field_rules.py`).

### PII Sanitization (sanitizer/)

**Security-critical**: All text must pass through `PIIAnonymizer` before reaching the LLM. Placeholders (`[PERSON_1]`, `[CN_PHONE_1]`, `[CN_ID_1]`) are used in LLM calls; originals stored in `InMemoryPiiMap`. Custom recognizers for Chinese ID cards (`cn_id_card.py`), phone numbers (`cn_phone.py`), and names (`cn_name.py`) extend Presidio.

### Key File Locations

| Component | Path |
|-----------|------|
| ReAct base agent | `agents/base.py` |
| Intake agent (main logic) | `agents/intake_agent.py` |
| PII engine | `sanitizer/engine.py`, `sanitizer/anonymizer.py` |
| Field validation guards | `guards/field_rules.py` |
| Tool output schema validator | `tools/schema_validator.py` |
| Pydantic schemas | `app/schemas/` |
| System prompt (Chinese) | `prompts/system/intake.txt` |
| Few-shot examples | `prompts/few_shot/intake_examples.json` |
| LLM client factory | `config/llm.py` |
| API routes | `app/api/routes.py` |
| pytest fixtures | `tests/conftest.py` (StubAnthropicClient mock) |

### SharedState Pipeline

All pipeline stages carry a `SharedState` dataclass (`app/schemas/state.py`) that accumulates results across agents: raw input → parsed fields → PII map → risk level → evidence → final report.

### Skeleton Components (Not Yet Implemented)

The following are architecturally planned but contain only stubs:
- `app/agent/` — planner, runner, state, guards
- `app/tools/` — registry, retrieval, risk scoring, remediation
- `app/rag/` — ingest, retriever
- `app/observability/` — logger, tracer, metrics
- Full API endpoints beyond `/health`
