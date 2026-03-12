# Compliance Agent — 改进版项目结构

## 设计原则

1. **只在需要多步推理的地方用 ReAct Agent**，其余用 Tool 或 Processor
2. **PII 脱敏模块独立且前置**，确保 LLM 永远不接触原始 PII
3. **编排逻辑独立于 Agent**，Orchestrator 是一等公民
4. **配置集中管理**，不散落在代码中

---

## 目录结构

```
compliance-agent/
├── README.md
├── requirements.txt
├── pyproject.toml                       # Poetry 或 pip 依赖管理
├── .env.example
├── Makefile                             # 常用命令：make dev, make eval, make ingest
│
├── config/
│   ├── settings.py                      # Pydantic BaseSettings，集中管理所有配置
│   ├── llm.py                           # LLM 选型 & 参数（模型名、温度、max_tokens）
│   ├── thresholds.py                    # 业务阈值（置信度、追问轮次上限、超时时间）
│   └── regulations.py                   # 法规知识库元数据（法规列表、语言、版本）
│
├── app/
│   ├── main.py                          # FastAPI 应用入口（仅初始化，不含业务逻辑）
│   │
│   ├── api/
│   │   ├── routes.py                    # REST endpoints：/analyze, /reports/{id}
│   │   ├── websocket.py                 # WebSocket：实时推送 Agent 执行进度
│   │   └── middleware.py                # 请求日志、CORS、限流
│   │
│   │
│   │  ============================================
│   │  核心层：Orchestrator（编排） + Agents + Processors
│   │  ============================================
│   │
│   ├── orchestrator/
│   │   ├── pipeline.py                  # 核心编排逻辑：定义 Agent 调用顺序与条件分支
│   │   ├── state.py                     # SharedState：Agent 间共享的结构化状态对象
│   │   └── router.py                    # 法域路由：根据 region 字段决定激活哪些分析路径
│   │
│   ├── agents/                          # 真正需要 ReAct 多步推理的 Agent（只有 2 个）
│   │   ├── base.py                      # ReAct loop 基类：Think → Act → Observe 循环
│   │   ├── intake_agent.py              # 场景解析 Agent：自然语言 → 结构化字段
│   │   │                                #   - Think: 分析用户描述，识别关键实体
│   │   │                                #   - Act:  调用 Schema Validator 检查字段完整性
│   │   │                                #   - Observe: 字段缺失 → 生成追问；完整 → 传递下游
│   │   │
│   │   └── risk_agent.py                # 风险分析 Agent：RAG 检索 + 法规推理
│   │                                    #   - Think: 基于结构化字段制定检索策略
│   │                                    #   - Act:  调用 RAG Retriever 获取法规证据
│   │                                    #   - Observe: 评估证据充分性，必要时补充检索
│   │                                    #   - Act:  调用 Risk Scorer 计算风险等级
│   │                                    #   注意：跨境场景可能需要 2 轮检索（EU + CN）
│   │
│   ├── processors/                      # 确定性处理器（不需要 ReAct，单次调用即可）
│   │   ├── report_generator.py          # 报告生成：模板填充，一次 LLM 调用
│   │   │                                #   输入：SharedState（含风险等级 + 证据 + 建议）
│   │   │                                #   输出：5 段式 Markdown/JSON 报告
│   │   │
│   │   └── escalation_checker.py        # 升级判断：纯规则引擎，无需 LLM
│   │                                    #   规则：confidence < 0.6 → 标记人工复核
│   │                                    #          risk_level == "Critical" → 强制免责声明
│   │                                    #          missing_fields > 0 → 标记信息不足
│   │
│   │
│   │  ============================================
│   │  安全层：PII 脱敏（本地执行，LLM 调用前的第一道关）
│   │  ============================================
│   │
│   ├── sanitizer/
│   │   ├── engine.py                    # Presidio AnalyzerEngine 封装 + 中文扩展
│   │   ├── recognizers/
│   │   │   ├── cn_phone.py              # 中国手机号识别器（1[3-9]\d{9}）
│   │   │   ├── cn_id_card.py            # 身份证号识别器（18 位 + 校验位）
│   │   │   └── cn_name.py               # 中文姓名识别器（基于 spaCy zh_core_web_trf）
│   │   ├── anonymizer.py               # 脱敏执行：PII → 占位符（[PERSON_1]、[EMAIL_1]）
│   │   └── pii_map.py                   # 占位符 ↔ 原始值映射表（仅本地存储）
│   │
│   │
│   │  ============================================
│   │  工具层：Agent 可调用的工具集
│   │  ============================================
│   │
│   ├── tools/
│   │   ├── registry.py                  # 工具注册表：每个工具的名称、描述、输入输出 Schema
│   │   ├── schema_validator.py          # 校验 LLM 输出的结构化字段是否符合 JSON Schema
│   │   ├── rag_retriever.py             # 封装 RAG 检索调用（语义 + BM25 + 重排序）
│   │   ├── risk_scorer.py               # 风险评分计算（基于命中法规条款数 × 严重度权重）
│   │   └── output_filter.py             # 输出安全过滤（拦截"贵司必须"等绝对化用语）
│   │
│   │
│   │  ============================================
│   │  RAG 层：法规知识库构建与检索
│   │  ============================================
│   │
│   ├── rag/
│   │   ├── ingest/
│   │   │   ├── chunker.py               # 层级感知切片：以"条"（Article）为单元
│   │   │   ├── metadata.py              # 元数据注入：法规名、条款号、法域、关键词标签
│   │   │   ├── summary_augmenter.py     # SAC：为每个 Chunk 生成 ~150 字法规级摘要
│   │   │   └── cross_ref.py             # 交叉引用解析：建立条款间引用关系图
│   │   │
│   │   ├── retriever/
│   │   │   ├── semantic.py              # 语义检索（multilingual-e5-large / bge-m3）
│   │   │   ├── keyword.py               # BM25 关键词检索
│   │   │   ├── reranker.py              # Cross-Encoder 重排序（bge-reranker-v2-m3）
│   │   │   └── hybrid.py                # 混合检索编排：semantic + keyword → rerank → Top-5
│   │   │
│   │   └── kb/                          # 知识库存储（向量数据库 + 元数据索引）
│   │       ├── vector_store.py          # 向量数据库接口（ChromaDB / FAISS）
│   │       └── metadata_index.py        # 结构化元数据检索（SQLite / JSON 索引）
│   │
│   │
│   │  ============================================
│   │  Prompt 层 + Schema 层
│   │  ============================================
│   │
│   ├── prompts/
│   │   ├── system/
│   │   │   ├── intake.txt               # Intake Agent 系统提示词
│   │   │   └── risk.txt                 # Risk Agent 系统提示词
│   │   ├── templates/
│   │   │   ├── followup.txt             # 追问模板（最多 3 个问题的格式）
│   │   │   └── report.txt               # 5 段式报告模板
│   │   └── few_shot/
│   │       ├── intake_examples.json     # 结构化解析的 Few-shot 示例
│   │       └── risk_examples.json       # 风险分析的 Few-shot 示例
│   │
│   ├── schemas/
│   │   ├── scenario.py                  # Pydantic Model：ScenarioInput, ParsedFields
│   │   ├── evidence.py                  # Pydantic Model：EvidenceChunk, Citation
│   │   ├── risk.py                      # Pydantic Model：RiskAssessment, RemediationAction
│   │   ├── report.py                    # Pydantic Model：AuditReport (5 段式)
│   │   └── shared_state.py              # Pydantic Model：SharedState（Agent 间共享状态）
│   │
│   │
│   │  ============================================
│   │  可观测性 + 护栏
│   │  ============================================
│   │
│   ├── observability/
│   │   ├── logger.py                    # 结构化日志（JSON 格式）
│   │   ├── tracer.py                    # Agent 执行链路追踪（每步 Think/Act/Observe 记录）
│   │   └── metrics.py                   # Prometheus 指标：延迟、LLM 调用次数、Token 消耗
│   │
│   └── guards/
│       ├── field_rules.py               # 必填字段校验规则（region、data_types、cross_border）
│       ├── confidence_gate.py           # 置信度阈值门控（< 0.6 → Escalation）
│       └── legal_disclaimer.py          # 免责声明注入（每份报告顶部/底部）
│
│
│  ================================================================
│  前端层（Next.js + TypeScript + Tailwind）
│  ================================================================
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   │
│   ├── app/
│   │   ├── layout.tsx                   # 全局布局 + 导航
│   │   ├── page.tsx                     # 首页：产品介绍 + CTA
│   │   ├── globals.css
│   │   │
│   │   ├── analyze/
│   │   │   └── page.tsx                 # 场景提交页：输入框 + 引导语 + "开始评估"
│   │   │
│   │   ├── reports/
│   │   │   ├── page.tsx                 # 报告列表页（历史记录）
│   │   │   └── [id]/
│   │   │       └── page.tsx             # 报告详情页：5 段式报告 + 法规折叠面板
│   │   │
│   │   └── demo/
│   │       └── page.tsx                 # 演示页：预设 3 个 Scenario 一键体验
│   │
│   ├── components/
│   │   ├── scenario-input.tsx           # 场景输入表单 + Placeholder 引导
│   │   ├── followup-card.tsx            # 追问卡片（选择题 + 补充输入）
│   │   ├── progress-tracker.tsx         # Agent 执行进度（WebSocket 实时更新）
│   │   ├── report-viewer.tsx            # 报告渲染（Markdown → React 组件）
│   │   ├── risk-badge.tsx               # 风险等级徽章（Low/Medium/High/Critical）
│   │   ├── citation-panel.tsx           # 法规引用折叠面板
│   │   ├── feedback-widget.tsx          # "有帮助/无帮助/需修改"反馈组件
│   │   └── ui/                          # 通用 UI 原子组件
│   │
│   └── lib/
│       ├── api.ts                       # FastAPI 请求封装 + WebSocket 客户端
│       ├── types.ts                     # 前端 TypeScript 类型（与后端 Schema 对齐）
│       └── constants.ts
│
│
│  ================================================================
│  数据 + 评测 + 文档
│  ================================================================
│
├── data/
│   ├── regulations/                     # 法规原文（用于 ingest 切片）
│   │   ├── eu/
│   │   │   ├── gdpr_full.md
│   │   │   └── eu_ai_act_full.md
│   │   └── cn/
│   │       ├── pipl_full.md
│   │       ├── dsl_full.md
│   │       ├── csl_full.md
│   │       └── aigc_marking_full.md
│   │
│   ├── kb/                              # 切片后的知识库（ingest 输出）
│   │   ├── chunks.jsonl                 # 所有 Chunks（含元数据）
│   │   └── vectors/                     # 向量索引文件
│   │
│   └── demo/
│       └── scenarios.json               # 3 个演示场景的预设输入
│
├── eval/
│   ├── test_cases/
│   │   ├── parsing_tests.csv            # 结构化解析测试集（50+ 用例）
│   │   ├── retrieval_tests.csv          # RAG 检索测试集
│   │   ├── guardrail_tests.csv          # 追问触发测试集（故意缺失字段）
│   │   └── expert_baseline.csv          # 法务专家基线评估（20 个场景）
│   │
│   ├── run_eval.py                      # 评测运行脚本
│   └── results/                         # 评测结果输出
│
├── docs/
│   ├── PRD.md                           # 产品需求文档
│   ├── architecture.md                  # 架构说明（配图）
│   ├── diagrams/
│   │   ├── system_architecture.png      # 系统架构图
│   │   ├── agent_flow.png               # Agent 编排流程图
│   │   └── rag_pipeline.png             # RAG 检索流程图
│   └── screenshots/
│
├── scripts/
│   ├── ingest_regulations.py            # 法规入库脚本：原文 → 切片 → 向量化
│   └── seed_demo.py                     # 初始化演示数据
│
├── tests/
│   ├── unit/
│   │   ├── test_sanitizer.py            # PII 脱敏单元测试
│   │   ├── test_chunker.py              # 切片逻辑测试
│   │   ├── test_schema_validator.py     # 字段校验测试
│   │   └── test_guards.py               # 护栏规则测试
│   │
│   ├── integration/
│   │   ├── test_intake_agent.py         # Intake Agent 集成测试
│   │   ├── test_risk_agent.py           # Risk Agent 集成测试
│   │   └── test_pipeline.py             # 端到端 Pipeline 测试
│   │
│   └── conftest.py                      # pytest fixtures（Mock LLM、测试知识库）
│
└── docker/
    ├── Dockerfile
    └── docker-compose.yml               # 后端 + 前端 + ChromaDB 一键启动
```

---

## 与原始结构的关键差异

| 改动 | 原始结构 | 改进版 | 理由 |
|------|---------|-------|------|
| Agent 数量 | 4 个 ReAct Agent | 2 个 ReAct Agent + 2 个 Processor | report 和 escalation 不需要多步推理循环 |
| 命名混淆 | `agents/` + `agent/` | `agents/` + `processors/` + `orchestrator/` | 消除歧义，职责清晰 |
| PII 脱敏 | 缺失 | 独立 `sanitizer/` 模块 | PRD FR1 核心安全要求 |
| 编排逻辑 | 藏在 main.py | 独立 `orchestrator/` | 编排是核心业务逻辑，需要独立测试 |
| RAG 结构 | 扁平 3 个文件 | `ingest/` + `retriever/` 子目录 | 混合检索方案需要更多组件 |
| 配置管理 | 仅 .env | `config/` 目录集中管理 | 阈值、模型参数、法规元数据需要结构化配置 |
| Prompt 管理 | 4 个 txt 文件平铺 | `system/` + `templates/` + `few_shot/` | 系统提示、模板、示例是不同类型的 prompt |
| 测试 | 仅 eval/ | `tests/unit/` + `tests/integration/` + `eval/` | 工程测试（unit/integration）和产品评测（eval）分开 |
| 护栏 | 仅 guards.py | `guards/` 目录多文件 | 字段规则、置信度门控、免责声明是不同类型的护栏 |
