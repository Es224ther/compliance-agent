<div align="center">

# Compliance Agent

**AI Compliance Pre-Check Assistant for Global Products**

Describe your business scenario in plain language and get an AI product compliance pre-check report in 30 seconds

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[Quick Start](#quick-start) · [Features](#core-features) · [Architecture](#technical-architecture) · [Development](#development) · [Disclaimer](#disclaimer)

**[中文文档](README.md)**

</div>

---

## Overview

Compliance review is one of the most common bottlenecks when AI products go global — product managers finish writing requirements, then wait for legal to sign off before knowing whether a feature is feasible. Compliance Agent moves this step earlier: during the feature design phase, describe your business scenario in a few sentences and get a compliance pre-check report with regulatory citations in 30 seconds, including a risk rating and role-specific remediation recommendations.

> ⚠️ The output of this tool does not constitute legal advice and is intended solely as an early-stage risk reference. See the [Disclaimer](#%EF%B8%8F-disclaimer) for details.

---

## Core Features

| Feature | Description |
|:--------|:------------|
| 🗣️ **Natural Language Input** | No questionnaires — just describe your business scenario |
| 🔒 **Local PII Sanitization** | Microsoft Presidio + Chinese NER extension; raw sensitive data never leaves the local environment |
| 🧩 **Structured Scene Parsing** | LLM Function Calling extracts strongly-typed fields: `region`, `data_types`, `cross_border`, and more |
| 🤖 **Smart Follow-up Questions** | Automatically asks for missing critical fields (≤ 2 rounds × 3 questions); refuses to make judgments when information is ambiguous |
| 🔍 **Hybrid RAG Retrieval** | Semantic search + BM25 keyword matching + Cross-Encoder reranking, covering bilingual (Chinese & English) regulations |
| 📊 **4-Level Risk Rating** | Low / Medium / High / Critical, with explainable reasoning (XAI) |
| 📋 **5-Section Audit Report** | Scene summary → Risk level → Regulatory citations → Uncertainties → Remediation actions |
| 👥 **Role-Differentiated Recommendations** | Separate actionable advice for Product Managers, Engineers, and Security/Governance teams |
| 📤 **Multiple Export Formats** | Markdown / JSON export + shareable report links |

---

## Technical Architecture

```
User Input
  │
  ▼
┌─────────────────┐
│  Local PII      │ ← Presidio + Chinese PatternRecognizer
│  Sanitization   │
└────────┬────────┘
         ▼
┌─────────────────┐
│  LLM Scene      │ ← LLM (Function Calling)
│  Parsing        │
└────────┬────────┘
         ▼
┌─────────────────┐   Missing Fields   ┌──────────────────┐
│  Field          │ ────────────────→  │  Smart Follow-up  │
│  Completeness   │                    │  (≤ 2 rounds)     │
└────────┬────────┘                    └────────┬─────────┘
         │ ◄──────────────────────────────────────┘
         ▼
┌─────────────────┐
│  RAG Regulatory │ ← ChromaDB + BM25 + bge-reranker-v2-m3
│  Retrieval      │
└────────┬────────┘
         ▼
┌─────────────────┐   Low Confidence   ┌───────────────────┐
│  Confidence     │ ────────────────→  │  Flag for Manual   │
│  Check          │                    │  Legal Review      │
└────────┬────────┘                    └───────────────────┘
         ▼
┌─────────────────┐
│  Risk Analysis  │ ← ReAct Agent + 5-Section Report
│  + Report       │
└────────┬────────┘
         ▼
┌─────────────────┐
│  WebSocket Push │ → Next.js Frontend (real-time rendering)
└─────────────────┘
```

---

## Directory Structure

<details>
<summary>Click to expand full directory</summary>

```
compliance-agent/
├── app/                          # Python backend (single package)
│   ├── main.py                   # FastAPI application entry point
│   ├── api/                      # API routes (routes / websocket / middleware)
│   ├── agent/                    # LLM Agent orchestration (planner / runner / guards / state)
│   ├── agents/                   # Business Agent implementations
│   │   ├── base.py               # ReAct Agent base class
│   │   ├── intake_agent.py       # Scene intake Agent
│   │   └── risk_agent.py         # Risk assessment Agent
│   ├── guards/                   # Guardrails and safety checks
│   │   ├── field_rules.py        # Field completeness rules
│   │   ├── confidence_gate.py    # Confidence threshold check
│   │   └── legal_disclaimer.py   # Disclaimer injection
│   ├── orchestrator/             # Pipeline orchestration
│   │   ├── pipeline.py           # Main pipeline
│   │   └── router.py             # Request router
│   ├── rag/                      # RAG subsystem
│   │   ├── ingest/               # Regulation ingestion (chunker / metadata / cross_ref / summary)
│   │   ├── kb/                   # Knowledge base (ChromaDB vector store)
│   │   └── retriever/            # Retrievers (semantic / keyword / hybrid / reranker)
│   ├── schemas/                  # Data models (scene / evidence / risk / report / state)
│   ├── processors/               # Post-processing
│   │   ├── report_generator.py   # Report generation
│   │   └── escalation_checker.py # Escalation check
│   ├── sanitizer/                # Local PII sanitization
│   │   ├── engine.py             # Presidio engine wrapper
│   │   ├── anonymizer.py         # Anonymization processor
│   │   └── cn_*.py               # Chinese PII recognizers (phone / ID card / name)
│   ├── tools/                    # Tool functions
│   │   ├── rag_retriever.py      # RAG retrieval tool
│   │   ├── risk_scorer.py        # Risk scoring
│   │   ├── schema_validator.py   # Schema validation
│   │   ├── output_filter.py      # Output filtering
│   │   ├── retrieval_tool.py     # Agent retrieval tool
│   │   ├── risk_scoring_tool.py  # Agent risk tool
│   │   ├── remediation_tool.py   # Remediation recommendation tool
│   │   └── registry.py           # Tool registry
│   ├── config/                   # Configuration
│   │   ├── settings.py           # Environment variables and app config
│   │   ├── llm.py                # LLM client configuration
│   │   └── thresholds.py         # Risk / confidence thresholds
│   ├── prompts/                  # LLM prompt templates
│   │   ├── system/               # System prompts
│   │   ├── few_shot/             # Few-shot examples
│   │   └── templates/            # Dynamic templates
│   └── observability/            # Logging and tracing
│       ├── logger.py
│       └── tracer.py
├── frontend/                     # Next.js frontend
│   ├── app/                      # Page routes
│   │   ├── page.tsx              # Home page (scene input)
│   │   ├── analyze/              # Analysis / follow-up page
│   │   └── reports/              # Report list and detail pages
│   ├── components/               # UI components
│   │   ├── scenario-input.tsx    # Scene input box
│   │   ├── progress-tracker.tsx  # Progress indicator
│   │   ├── report-viewer.tsx     # Report display
│   │   ├── citation-panel.tsx    # Regulatory citation panel
│   │   ├── followup-card.tsx     # Follow-up question card
│   │   ├── feedback-widget.tsx   # User feedback
│   │   └── risk-badge.tsx        # Risk level badge
│   └── lib/                      # Frontend utilities (api.ts / types.ts)
├── data/
│   └── regulations/              # Regulation source texts
├── tests/                        # Test suite
│   ├── integration/              # Integration tests (api / pipeline / report / risk_agent)
│   └── unit/                     # Unit tests (guards / sanitizer / schemas, etc.)
├── eval/                         # Retrieval evaluation tools and test sets
├── scripts/                      # Utility scripts
│   ├── ingest_regulations.py     # Regulation knowledge base ingestion
│   └── prepare_regulations.py    # Regulation preprocessing
├── samples/                      # Sample inputs and reports
├── docker/                       # Docker configuration
├── docs/                         # Documentation and screenshots
├── Makefile                      # Common commands (dev / test / ingest)
├── pyproject.toml                # Python project config (Poetry)
└── requirements.txt              # Python dependencies
```

</details>

---

## Quick Start

### Prerequisites

- Python ≥ 3.11
- Node.js ≥ 18
- Docker (optional, recommended)
- API Key

### Option 1: One-Command Docker Start

```bash
git clone <repo-url> && cd compliance-agent
cp .env.example .env
# Edit .env with your API key

docker compose up --build
```

Once the services are running, visit http://localhost:3000.

### Option 2: Local Development

```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. Configure environment variables
cp .env.example .env
# Edit .env with your API key

# 3. Ingest the regulatory knowledge base (required on first run)
make ingest

# 4. Start backend (http://localhost:8000)
make dev

# 5. Start frontend in a new terminal (http://localhost:3000)
cd frontend && npm run dev
```

### Verify Installation

```bash
# Health check
curl http://localhost:8000/health
# → {"status": "ok"}

# Run tests
make test
```

---

## Regulatory Coverage

### Phase 1 (Current)

| Regulation | Jurisdiction | Language | Articles |
|:-----------|:-------------|:---------|:---------|
| GDPR — General Data Protection Regulation | 🇪🇺 EU | EN | ~99 |
| EU AI Act — Artificial Intelligence Act | 🇪🇺 EU | EN | ~113 + Annexes |
| PIPL — Personal Information Protection Law | 🇨🇳 CN | ZH | ~74 |
| DSL — Data Security Law | 🇨🇳 CN | ZH | ~55 |
| CSL — Cybersecurity Law | 🇨🇳 CN | ZH | ~79 |
| Measures for Labeling AI-Generated Synthetic Content | 🇨🇳 CN | ZH | ~25 |

> The knowledge base covers 450+ articles across ~2,000–3,000 chunks, using a hierarchy-aware chunking strategy with Summary-Augmented Chunking (SAC).

### Phase 2 Planned

- 🇺🇸 United States: CCPA, Colorado AI Act
- 🌏 Asia-Pacific: Singapore PDPA, Japan APPI

---

## Example Use Cases

### Scenario A: Cross-Border Data Training

> "We plan to transfer short video clips uploaded by European users to our domestic servers in China for training an AI video editing model. After training, the model will be deployed domestically and serve users globally."

**Expected output**: Risk level High / Critical, likely citing GDPR Art. 46 (cross-border transfer safeguards) + PIPL Article 38 (outbound security assessment).

### Scenario B: Third-Party Model API Integration

> "Our product plans to integrate the GPT-4o API to process text and images submitted by European users — mainly for content summarization and smart tagging. User data will be sent directly to OpenAI's servers for processing, and the results will be returned to our application for display."

**Expected output**: Risk level High, likely citing PIPL Article 23 (third-party data provision) + GDPR Art. 28 (data processor obligations).

### Scenario C: AI-Generated Content Labeling

> "We are building an API service for European B2B customers that automatically generates advertising short videos. The generated videos will be published directly by customers on platforms such as Instagram and TikTok."

**Expected output**: Risk level Medium, likely citing EU AI Act Art. 50 (transparency obligations) + AIGC Labeling Measures Article 7 (metadata tags).

---

## Development

```bash
make dev      # Start backend
make test     # Run tests
make ingest   # Ingest regulatory knowledge base
make eval     # Run evaluation

- Add new regulations to data/regulations/
- Modify configuration in app/config/
- Evaluation test sets in eval/
```

---

## Roadmap

- [x] Phase 0 — Prototype: RAG Pipeline + 3 core scenarios end-to-end
- [x] Phase 1 — MVP: 6 regulations, complete frontend interaction
- [ ] Phase 2 — Extended jurisdictions (US CCPA / Colorado AI Act) + PDF report export
- [ ] Phase 3 — Platform: API access, Jira / Confluence integration

---

## Disclaimer

**All reports generated by this tool are intended solely as preliminary references for early-stage business risk assessment and do not constitute any legally binding legal opinion.**

- High / Critical risk reports are always flagged with a "requires manual legal review" notice
- Regulatory interpretation is context-dependent; actual compliance obligations should be confirmed with professional legal counsel
- This tool does not replace a formal DPIA (Data Protection Impact Assessment) or legal approval process
- The knowledge base may lag behind regulatory updates; see the `effective_date` field in `config/regulations.py` for the version of each regulation currently in use

---

## License

[MIT](LICENSE)
