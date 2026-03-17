<div align="center">

# Compliance Agent

**面向全球化 AI 产品的合规预检助手**

通过自然语言描述业务场景，30 秒内获得AI产品的合规预检报告

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[快速开始](#快速开始) · [功能特性](#核心功能) · [技术架构](#技术架构) · [开发说明](#开发说明) · [免责声明](#免责声明)

**[English](README_EN.md)**

</div>

---

## 概述

AI 产品出海过程中，合规评估是最常见的瓶颈之一，产品经理写完需求，需要等法务审核后才知道能不能做。Compliance Agent 把这个环节前置：在功能设计阶段，用一段话描述项目的业务场景，30 秒内拿到一份带法规引用的合规预检报告，包含风险定级和按角色分组的整改建议。

> ⚠️ 本工具输出不构成法律意见，仅作为前置风控参考。详见[免责声明](#%EF%B8%8F-免责声明)。

---

## 核心功能

| 功能 | 说明 |
|:-----|:-----|
| 🗣️ **自然语言输入** | 无需填写问卷，直接描述业务场景即可 |
| 🔒 **本地 PII 脱敏** | Microsoft Presidio + 中文 NER 扩展，原始敏感信息不出域 |
| 🧩 **结构化场景解析** | LLM Function Calling 提取 `region`、`data_types`、`cross_border` 等强类型字段 |
| 🤖 **智能追问** | 关键字段缺失时自动追问（≤ 2 轮 × 3 题），拒绝在信息模糊时给出判断 |
| 🔍 **混合 RAG 检索** | 语义检索 + BM25 关键词 + Cross-Encoder 重排序，覆盖中英双语法规 |
| 📊 **四级风险定级** | Low / Medium / High / Critical，附可解释的判定依据 |
| 📋 **5 段式审计报告** | 场景摘要 → 风险等级 → 法规引用 → 不确定项 → 整改建议 |
| 👥 **角色差异化建议** | 产品经理 / 研发工程师 / 安全治理专员各获得对应的可执行建议 |
| 📤 **多格式导出** | Markdown / JSON 导出 + 可分享链接 |

---

## 技术架构

```
用户输入
  │
  ▼
┌─────────────────┐
│  本地 PII 脱敏   │ ← Presidio + 中文 PatternRecognizer
└────────┬────────┘
         ▼
┌─────────────────┐
│  LLM 场景解析    │ ← LLM（Function Calling）
└────────┬────────┘
         ▼
┌─────────────────┐    字段缺失    ┌──────────────┐
│  字段完整性校验   │ ──────────→  │  智能追问 ≤2轮 │
└────────┬────────┘              └──────┬───────┘
         │ ◄─────────────────────────────┘
         ▼
┌─────────────────┐
│  RAG 法规检索    │ ← ChromaDB + BM25 + bge-reranker-v2-m3
└────────┬────────┘
         ▼
┌─────────────────┐    低置信度    ┌───────────────┐
│  置信度校验      │ ──────────→  │  标记需人工复核  │
└────────┬────────┘              └───────────────┘
         ▼
┌─────────────────┐
│  风险分析 + 报告  │ ← ReAct Agent + 5 段式报告
└────────┬────────┘
         ▼
┌─────────────────┐
│  WebSocket 推送   │ → Next.js 前端实时渲染
└─────────────────┘
```
---

## 目录结构

<details>
<summary>点击展开完整目录</summary>

```
compliance-agent/
├── app/                          # Python 后端（唯一包）
│   ├── main.py                   # FastAPI 应用入口
│   ├── api/                      # API 路由（routes / websocket / middleware）
│   ├── agent/                    # LLM Agent 编排（planner / runner / guards / state）
│   ├── agents/                   # 业务 Agent 实现
│   │   ├── base.py               # ReAct Agent 基类
│   │   ├── intake_agent.py       # 场景摄入 Agent
│   │   └── risk_agent.py         # 风险评估 Agent
│   ├── guards/                   # 护栏与安全校验
│   │   ├── field_rules.py        # 字段完整性规则
│   │   ├── confidence_gate.py    # 置信度阈值校验
│   │   └── legal_disclaimer.py   # 免责声明注入
│   ├── orchestrator/             # 流水线编排
│   │   ├── pipeline.py           # 主流水线
│   │   └── router.py             # 请求路由
│   ├── rag/                      # RAG 子系统
│   │   ├── ingest/               # 法规摄入（chunker / metadata / cross_ref / summary）
│   │   ├── kb/                   # 知识库（ChromaDB 向量存储）
│   │   └── retriever/            # 检索器（semantic / keyword / hybrid / reranker）
│   ├── schemas/                  # 数据模型（场景 / 证据 / 风险 / 报告 / 状态）
│   ├── processors/               # 后处理
│   │   ├── report_generator.py   # 报告生成
│   │   └── escalation_checker.py # Escalation 检查
│   ├── sanitizer/                # 本地 PII 脱敏
│   │   ├── engine.py             # Presidio 引擎封装
│   │   ├── anonymizer.py         # 匿名化处理
│   │   └── cn_*.py               # 中文 PII 识别器（手机 / 身份证 / 姓名）
│   ├── tools/                    # 工具函数
│   │   ├── rag_retriever.py      # RAG 检索工具
│   │   ├── risk_scorer.py        # 风险评分
│   │   ├── schema_validator.py   # Schema 校验
│   │   ├── output_filter.py      # 输出过滤
│   │   ├── retrieval_tool.py     # Agent 检索工具
│   │   ├── risk_scoring_tool.py  # Agent 风险工具
│   │   ├── remediation_tool.py   # 整改建议工具
│   │   └── registry.py           # 工具注册表
│   ├── config/                   # 配置
│   │   ├── settings.py           # 环境变量与应用配置
│   │   ├── llm.py                # LLM 客户端配置
│   │   └── thresholds.py         # 风险 / 置信度阈值
│   ├── prompts/                  # LLM 提示词模板
│   │   ├── system/               # 系统提示词
│   │   ├── few_shot/             # Few-shot 示例
│   │   └── templates/            # 动态模板
│   └── observability/            # 日志与链路追踪
│       ├── logger.py
│       └── tracer.py
├── frontend/                     # Next.js 前端
│   ├── app/                      # 页面路由
│   │   ├── page.tsx              # 首页（场景输入）
│   │   ├── analyze/              # 分析 / 追问页
│   │   └── reports/              # 报告列表与详情页
│   ├── components/               # UI 组件
│   │   ├── scenario-input.tsx    # 场景输入框
│   │   ├── progress-tracker.tsx  # 进度指示器
│   │   ├── report-viewer.tsx     # 报告展示
│   │   ├── citation-panel.tsx    # 法规引用面板
│   │   ├── followup-card.tsx     # 追问卡片
│   │   ├── feedback-widget.tsx   # 用户反馈
│   │   └── risk-badge.tsx        # 风险等级标签
│   └── lib/                      # 前端工具库（api.ts / types.ts）
├── data/
│   └── regulations/              # 法规原文
├── tests/                        # 测试套件
│   ├── integration/              # 集成测试（api / pipeline / report / risk_agent）
│   └── unit/                     # 单元测试（guards / sanitizer / schemas 等）
├── eval/                         # 检索评估工具与测试集
├── scripts/                      # 工具脚本
│   ├── ingest_regulations.py     # 法规知识库摄入
│   └── prepare_regulations.py    # 法规预处理
├── samples/                      # 示例输入与报告
├── docker/                       # Docker 配置
├── docs/                         # 文档与截图
├── Makefile                      # 常用命令（dev / test / ingest）
├── pyproject.toml                # Python 项目配置（Poetry）
└── requirements.txt              # Python 依赖
```

</details>

---

## 快速开始

### 前置条件

- Python ≥ 3.11
- Node.js ≥ 18
- Docker（可选，推荐）
- API KEY

### 方式一：Docker 一键启动

```bash
git clone <repo-url> && cd compliance-agent
cp .env.example .env
# 编辑 .env

docker compose up --build
```

服务启动后访问 http://localhost:3000 即可使用。

### 方式二：本地开发

```bash
# 1. 安装依赖
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env

# 3. 摄入法规知识库（首次必须执行）
make ingest

# 4. 启动后端（http://localhost:8000）
make dev

# 5. 启动前端（另开终端，http://localhost:3000）
cd frontend && npm run dev
```

### 验证安装

```bash
# 健康检查
curl http://localhost:8000/health
# → {"status": "ok"}

# 运行测试
make test
```

---

## 法规覆盖范围

### Phase 1（当前版本）

| 法规 | 法域 | 语言 | 条款数 |
|:-----|:-----|:-----|:-------|
| GDPR — 通用数据保护条例 | 🇪🇺 EU | EN | ~99 |
| EU AI Act — 欧盟人工智能法案 | 🇪🇺 EU | EN | ~113 + 附件 |
| PIPL — 个人信息保护法 | 🇨🇳 CN | ZH | ~74 |
| DSL — 数据安全法 | 🇨🇳 CN | ZH | ~55 |
| CSL — 网络安全法 | 🇨🇳 CN | ZH | ~79 |
| 《人工智能生成合成内容标识办法》 | 🇨🇳 CN | ZH | ~25 |

> 知识库总计约 450+ 条款、2000–3000 个 Chunks，采用层级感知切片 + 摘要增强（SAC）策略。

### Phase 2 规划

- 🇺🇸 美国：CCPA、Colorado AI Act
- 🌏 亚太：新加坡 PDPA、日本 APPI

---

## 使用场景示例

### 场景 A：跨境数据训练

> "我们计划把欧洲用户上传的短视频素材传回国内服务器，用于训练一个 AI 视频剪辑模型。训练完成后模型部署在国内，服务全球用户。"

**预期输出**：风险等级 High / Critical，可能涉及 GDPR Art.46（跨境传输保障）+ PIPL 第三十八条（出境安全评估）。

### 场景 B：第三方模型 API 调用

> "我们的产品打算接入 GPT-4o 的 API 来处理欧洲用户提交的文本和图片，主要是做内容摘要和智能标签。用户数据会直接发送到 OpenAI 的服务器进行处理，处理完的结果返回给我们的应用展示给用户。"

**预期输出**：风险等级 High，可能涉及 PIPL 第二十三条（第三方提供）+ GDPR Art.28（数据处理者义务）。

### 场景 C：AIGC 内容标识

> "我们正在开发一个面向欧洲 B 端客户的 API 服务，客户可以通过这个 API 自动生成广告短视频。生成的视频会直接由客户投放到 Instagram、TikTok 等社交平台上。"

**预期输出**：风险等级 Medium，可能涉及 EU AI Act Art.50（透明度义务）+ AIGC 标识办法第七条（元数据标签）。

---

## 开发说明

```bash
make dev      # 启动后端
make test     # 运行测试
make ingest   # 摄入法规知识库
make eval     # 运行评测

- 新法规放入 data/regulations/
- 修改配置见 app/config/
- 评测集见 eval/
```
---

## Roadmap

- [✓] Phase 0 — 原型验证：RAG Pipeline + 3 个核心场景端到端
- [✓] Phase 1 — MVP：6 部法规、前端完整交互
- [ ] Phase 2 — 扩展法域（美国 CCPA / Colorado AI Act）+ PDF 报告导出
- [ ] Phase 3 — 平台化：与 API、Jira / Confluence 集成

---

## 免责声明

**本工具输出的所有报告仅作为业务前置风控的初步参考，不构成任何具有法律效力的正式法律意见。**

- High / Critical 风险报告会强制标注"需人工法务复核"
- 法规解读存在上下文依赖，实际合规义务以专业法律意见为准
- 本工具不替代正式的 DPIA（数据保护影响评估）或法务审批流程
- 知识库存在更新时滞，当前法规版本以 `config/regulations.py` 中标注的 `effective_date` 为准

---

## License

[MIT](LICENSE)