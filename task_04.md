# Compliance Agent — Day 4 Vibe Coding Prompt

## 你的角色

你是一位资深全栈工程师，正在为「Compliance Agent」构建 API 接口层和前端核心页面。

Day 1-3 已完成：项目骨架、PII 脱敏、Intake Agent、RAG 知识库、风险分析 Agent、护栏系统、Orchestrator Pipeline、报告生成器。今天的任务是把后端 Pipeline 通过 FastAPI 暴露为 REST + WebSocket 接口，并用 Next.js 实现 3 个核心页面。

你需要严格按照以下技术规范进行实现，确保前后端联调可用。

## 核心执行规则 (Rules for Agent)

1. **分步执行**：本需求文档包含多个任务，严格按照顺序执行。你**绝对不能**一次性把所有阶段的代码都写完。
2. **强制暂停与汇报**：每当你完成一个阶段的代码编写或终端命令执行后，你**必须立刻停下来**。
3. **汇报格式**：停下来时，向我简短汇报：
   - 本阶段完成了什么文件/功能。
   - 是否遇到了潜在风险。
   - 询问我：“请问老板是否可以进入下一阶段？”

---

## 今天的目标（严格按顺序执行）

### 任务 1：FastAPI 后端接口（~2h）

实现 `app/api/` 模块下的完整后端接口：

**1. `app/api/routes.py`：REST Endpoints**

```python
# POST /analyze
# 请求体：{ "scenario_text": str }
# 流程：
#   1. 生成 session_id（UUID）
#   2. 调用 orchestrator/pipeline.py 的 run_pipeline()
#   3. 返回 { "session_id": str, "report_id": str, "status": "processing" }
#
# GET /reports/{report_id}
# 返回完整报告（同时支持 Markdown 和 JSON 格式）
# Query Parameter: format=markdown|json（默认 markdown）
# 响应体：AuditReport Schema（schemas/report.py）
#
# PATCH /reports/{report_id}/feedback
# 请求体：{ "section": str, "rating": "helpful"|"unhelpful"|"needs_edit", "comment": str | null }
# 用于收集用户对报告每条建议的反馈
#
# GET /reports
# 返回当前用户的报告历史列表
# Query Parameters: risk_level=Low|Medium|High|Critical（可选过滤）
# 按创建时间倒序排列
```

**2. `app/api/websocket.py`：实时进度推送**

```python
# WebSocket /ws/{session_id}
# 
# Pipeline 执行过程中，通过 WebSocket 向前端推送进度事件：
# 
# 事件格式（JSON）：
# { "step": str, "status": "running"|"completed"|"error", "message": str }
#
# 推送的步骤序列：
# 1. { "step": "pii_sanitization", "status": "running", "message": "正在进行数据脱敏..." }
# 2. { "step": "pii_sanitization", "status": "completed", "message": "脱敏完成" }
# 3. { "step": "scenario_parsing", "status": "running", "message": "正在解析业务场景..." }
# 4. { "step": "scenario_parsing", "status": "completed", "message": "场景解析完成" }
# 5. { "step": "followup", "status": "waiting", "message": "需要补充信息",
#      "data": { "questions": [...] } }                          ← 仅在追问触发时
# 6. { "step": "rag_retrieval", "status": "running", "message": "正在检索法规依据..." }
# 7. { "step": "rag_retrieval", "status": "completed", "message": "找到 N 条相关法规" }
# 8. { "step": "risk_analysis", "status": "running", "message": "正在进行风险分析..." }
# 9. { "step": "report_generation", "status": "running", "message": "正在生成审计报告..." }
# 10. { "step": "completed", "status": "completed", "message": "报告生成完成",
#       "data": { "report_id": str } }
#
# 实现要点：
# - 使用 FastAPI 的 WebSocket 原生支持
# - Pipeline 中每个步骤执行前后，通过回调函数发送事件
# - 在 orchestrator/pipeline.py 的 run_pipeline() 中注入 progress_callback 参数
```

**3. `app/api/middleware.py`：中间件**

```python
# 实现以下中间件：
# 1. CORS：允许 http://localhost:3000（前端开发服务器）
# 2. RequestLoggerMiddleware：记录每个请求的 method、path、耗时、状态码
# 3. RateLimitMiddleware：简单的内存级限流，每 IP 每分钟最多 10 次 /analyze 请求
#    （使用 dict + timestamp，不需要 Redis）
```

**4. 修改 `app/main.py`：**

```python
# FastAPI 应用初始化：
# - 注册 routes.py 中的路由（APIRouter prefix="/api/v1"）
# - 注册 websocket.py 中的 WebSocket 路由
# - 加载 middleware.py 中的中间件
# - 添加 /health endpoint（返回 {"status": "ok", "version": "0.4.0"}）
# - 使用 lifespan 事件初始化 ChromaDB 连接和嵌入模型（避免每次请求重新加载）
```

**完成标准：**
- `make dev` 启动后端，使用 curl 测试：
  - `curl -X POST http://localhost:8000/api/v1/analyze -H "Content-Type: application/json" -d '{"scenario_text": "我们计划把欧洲用户上传的短视频素材传回国内服务器，用于训练一个 AI 视频剪辑模型。"}'` → 返回 `{"session_id": "...", "report_id": "...", "status": "processing"}`
  - `curl http://localhost:8000/api/v1/reports/{report_id}` → 返回完整 5 段式报告
- 使用 websocat 或 Python websockets 客户端连接 `ws://localhost:8000/ws/{session_id}`，可收到实时进度事件
- 3 个 PRD 场景（A/B/C）均可通过 API 成功返回报告

---

### 任务 2：前端——场景提交页（~2h）

**依赖**：Day 4 前端基于 Next.js 14（App Router）+ TypeScript + CSS。

首先确认 `frontend/` 目录已初始化：
```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir=false
npm install
```

**1. `frontend/lib/api.ts`：后端请求封装**

```typescript
// API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"
//
// submitScenario(text: string): Promise<{ session_id: string, report_id: string }>
//   → POST /analyze
//
// getReport(reportId: string, format?: "markdown" | "json"): Promise<AuditReport>
//   → GET /reports/{reportId}
//
// getReportList(riskLevel?: string): Promise<ReportSummary[]>
//   → GET /reports
//
// submitFeedback(reportId: string, feedback: FeedbackPayload): Promise<void>
//   → PATCH /reports/{reportId}/feedback
//
// connectWebSocket(sessionId: string, onMessage: (event: ProgressEvent) => void): WebSocket
//   → ws://localhost:8000/ws/{sessionId}
//   → 返回 WebSocket 实例，前端组件负责在 useEffect cleanup 中关闭连接
```

**2. `frontend/lib/types.ts`：类型定义**

```typescript
// 与后端 schemas/ 对齐的 TypeScript 类型：
//
// interface ParsedFields {
//   region: "EU" | "CN" | "Global" | "EU+CN" | null;
//   data_types: ("Personal" | "Behavioral" | "Biometric" | "Financial")[] | null;
//   cross_border: boolean | null;
//   third_party_model: boolean | null;
//   aigc_output: boolean | null;
//   data_volume_level: "Small" | "Medium" | "Large" | null;
// }
//
// interface EvidenceChunk {
//   regulation: string;
//   article_id: string;
//   chapter: string;
//   text_excerpt: string;
//   relevance_score: number;
// }
//
// interface AuditReport {
//   report_id: string;
//   summary: string;
//   risk_level: "Low" | "Medium" | "High" | "Critical";
//   risk_overview: string;
//   evidence_citations: EvidenceChunk[];
//   uncertainties: string[];
//   remediation_actions: {
//     role: "ProductManager" | "Developer" | "Security";
//     actions: string[];
//   }[];
//   disclaimer: string;
//   created_at: string;
// }
//
// interface ProgressEvent {
//   step: string;
//   status: "running" | "completed" | "waiting" | "error";
//   message: string;
//   data?: any;
// }
//
// interface FollowUpQuestion {
//   field: string;
//   question: string;
//   options: string[];
// }
```

**3. `frontend/app/analyze/page.tsx`：场景提交页**

```
页面结构：
┌─────────────────────────────────────────────┐
│  🛡️ AI 合规预检助手                         │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  请描述你的 AI 功能场景，包括：     │    │
│  │  涉及哪些用户数据、数据在哪些地区   │    │
│  │  流转、是否使用第三方模型、AI 生成  │    │
│  │  内容是否面向终端用户。             │    │
│  │                                     │    │
│  │  （大文本输入框，最少 20 字）       │    │
│  └─────────────────────────────────────┘    │
│                                             │
│           [ 🚀 开始评估 ]                    │
│                                             │
│  ┌─ 执行进度 ─────────────────────────┐    │
│  │  ✅ 数据脱敏完成                    │    │
│  │  ✅ 场景解析完成                    │    │
│  │  🔄 正在检索法规依据...             │    │
│  │  ⬜ 风险分析                        │    │
│  │  ⬜ 生成报告                        │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─ 追问卡片（条件显示）──────────────┐    │
│  │  为了给出准确评估，请补充以下信息：  │    │
│  │  1. 视频是否包含人脸？ [是/否/不确定]│    │
│  │  2. 是否已取得用户同意？ [已/未/部分]│    │
│  │          [ 提交补充信息 ]            │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

实现要点：
- `components/scenario-input.tsx`：受控组件，输入框最少 20 字才启用提交按钮
- `components/progress-tracker.tsx`：基于 WebSocket 事件实时更新步骤状态
  - 每个步骤显示状态图标：✅（completed）、🔄（running）、⬜（pending）、❌（error）
  - 使用 `useEffect` 管理 WebSocket 生命周期，组件卸载时关闭连接
- `components/followup-card.tsx`：当 WebSocket 收到 `step: "followup"` 事件时渲染
  - 每个问题渲染为单选按钮组
  - 提交后通过 WebSocket 发送用户回答，Pipeline 继续执行
- 提交后自动跳转或滚动到进度区域
- 报告生成完成后（收到 `step: "completed"` 事件），显示「查看报告」按钮，点击跳转到 `/reports/{report_id}`

**完成标准：**
- 输入场景 A 描述，点击"开始评估"后进度条正常推进
- 追问卡片在字段缺失时正确显示（测试：输入一句模糊描述"我们想用 AI 处理用户数据"）
- 报告完成后可正常跳转到报告详情页

---

### 任务 3：前端——报告详情页（~2h）

**1. `frontend/app/reports/[id]/page.tsx`：报告详情页**

```
页面结构：
┌──────────────────────────────────────────────────────┐
│  ← 返回历史    报告 #RPT-20250313-001                │
├──────────────────────┬───────────────────────────────┤
│                      │                               │
│  📋 场景摘要         │  📜 法规引用面板               │
│  ──────────          │  ──────────────               │
│  （Summary 段落）    │  ▶ GDPR Art.46               │
│                      │    "Transfers subject to      │
│  🔴 风险等级: High   │     appropriate safeguards"   │
│  ──────────          │    相关度: 0.87               │
│  （Risk Overview）   │                               │
│                      │  ▶ PIPL 第三十八条            │
│  📎 证据引用         │    "关键信息基础设施运营者和   │
│  ──────────          │     处理个人信息达到..."      │
│  （Evidence 列表）   │    相关度: 0.82               │
│                      │                               │
│  ⚠️ 不确定项         │  ▶ DSL 第三十一条             │
│  ──────────          │    （点击展开原文）           │
│  （Uncertainties）   │                               │
│                      │                               │
│  ✅ 整改建议         │                               │
│  ──────────          │                               │
│  👤 产品经理:        │                               │
│    - 补充授权弹窗    │                               │
│  👨‍💻 研发工程师:      │                               │
│    - 增加脱敏管道    │                               │
│  🔒 安全治理:        │                               │
│    - 启动 DPIA       │                               │
│                      │                               │
│  ⚖️ 免责声明         │                               │
├──────────────────────┴───────────────────────────────┤
│  [ 导出 Markdown ]  [ 导出 JSON ]  [ 🔗 复制链接 ]  │
│                                                      │
│  对这份报告的评价：                                   │
│  每条建议旁：[ 👍 有帮助 ] [ 👎 无帮助 ] [ ✏️ 需修改 ] │
└──────────────────────────────────────────────────────┘
```

实现要点：

- `components/report-viewer.tsx`：接收 AuditReport 数据，渲染 5 段式结构
  - 使用 `react-markdown` 渲染 Markdown 文本段落
  - 每个段落使用 Tailwind 的卡片样式（`rounded-lg border p-6`）

- `components/risk-badge.tsx`：风险等级徽章组件
  ```
  颜色映射：
  Low      → green-100 / green-800
  Medium   → yellow-100 / yellow-800
  High     → orange-100 / orange-800
  Critical → red-100 / red-800
  ```

- `components/citation-panel.tsx`：右侧法规引用折叠面板
  - 默认折叠，点击条款标题展开原文摘要
  - 显示法规名称、条款编号、相关度分数（进度条形式）
  - 使用 `<details>` / `<summary>` 或 Tailwind 手动实现折叠

- `components/feedback-widget.tsx`：反馈组件
  - 每条整改建议旁渲染三个按钮：有帮助 / 无帮助 / 需修改
  - 点击后调用 `PATCH /reports/{id}/feedback`
  - 已反馈的建议灰显按钮，防止重复提交

- 导出功能：
  - 「导出 Markdown」：使用 `Blob` + `URL.createObjectURL` 下载 `.md` 文件
  - 「导出 JSON」：同上，下载 `.json` 文件
  - 「复制链接」：调用 `navigator.clipboard.writeText(window.location.href)`

**完成标准：**
- 3 个场景（A/B/C）的报告均可正常渲染，5 个段落完整显示
- 风险等级徽章颜色与风险等级对应
- 法规引用面板可折叠展开
- 导出按钮均可正常工作

---

### 任务 4：前端——历史记录 + 反馈（~1h）

**1. `frontend/app/reports/page.tsx`：报告列表页**

```typescript
// 功能：
// - 调用 GET /reports 获取历史报告列表
// - 每条记录显示：报告 ID、场景摘要（截断前 80 字）、风险等级徽章、创建时间
// - 支持按风险等级筛选（顶部 Tab：全部 / Low / Medium / High / Critical）
// - 点击某行跳转到 /reports/{id}
// - 空状态显示："暂无评估记录，去提交一个场景试试？" + 跳转按钮
```

**完成标准：**
- 历史页面正确显示已生成的报告列表
- 筛选功能可用（选择 "High" 后仅显示 High 风险报告）
- 反馈操作调用后端 `PATCH /reports/{id}/feedback` 成功

---

### 任务 5：Docker Compose 联调（~1h）

**1. `docker/Dockerfile`：后端镜像**

```dockerfile
# 基础镜像：python:3.11-slim
# 安装系统依赖（用于 spaCy 中文模型）
# 复制 requirements.txt，pip install
# 下载 spaCy 模型：en_core_web_lg + zh_core_web_trf（如体积太大，用 zh_core_web_sm 替代）
# 复制项目代码
# 暴露端口 8000
# 启动命令：uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**2. `docker/docker-compose.yml`：三服务编排**

```yaml
# services:
#   backend:
#     build: ../
#     dockerfile: docker/Dockerfile
#     ports: ["8000:8000"]
#     env_file: ../.env
#     depends_on: [chromadb]
#     volumes:
#       - ../data/kb:/app/data/kb          # 知识库持久化
#
#   frontend:
#     build: ../frontend
#     ports: ["3000:3000"]
#     environment:
#       NEXT_PUBLIC_API_URL: http://backend:8000/api/v1
#       NEXT_PUBLIC_WS_URL: ws://backend:8000
#
#   chromadb:
#     image: chromadb/chroma:latest
#     ports: ["8001:8000"]
#     volumes:
#       - chroma_data:/chroma/chroma       # 向量数据库持久化
#
# volumes:
#   chroma_data:
```

**3. 前端 Dockerfile（`frontend/Dockerfile`）：**

```dockerfile
# 基于 node:20-alpine
# 多阶段构建：
#   Stage 1 (builder)：npm install → npm run build
#   Stage 2 (runner)：复制 .next/standalone + .next/static，启动 node server.js
# next.config.ts 中启用 output: "standalone"
```

**完成标准：**
- `docker-compose up --build` 后：
  - 访问 http://localhost:3000 可使用完整功能
  - 前端页面可正常调用后端 API
  - WebSocket 进度推送正常工作
- ChromaDB 数据在 `docker-compose down` + `docker-compose up` 后仍然保留

---

## 技术约束

- 后端 API 统一返回 JSON，错误响应格式：`{"error": str, "detail": str, "status_code": int}`
- WebSocket 消息统一为 JSON 格式，前端使用 `JSON.parse()` 解析
- 前端所有 API 调用走 `lib/api.ts` 封装，不在组件中直接使用 `fetch`
- 前端使用 Next.js App Router（不使用 Pages Router），所有页面为 Client Component（`"use client"`），因为需要 WebSocket 和浏览器 API
- Tailwind CSS 直接使用 utility class，不引入额外 UI 库（如 shadcn 或 MUI），保持轻量
- 报告存储使用内存字典（`dict[str, AuditReport]`）作为 Phase 1 方案，Phase 2 迁移到 SQLite/PostgreSQL
- 所有异步操作使用 `async/await`，Pipeline 执行使用 `asyncio.create_task()` 在后台运行，不阻塞 API 响应

---

## 完成标准 Checklist

今天结束前，以下验收点应全部通过：

- [ ] `make dev` → 后端启动，`curl http://localhost:8000/health` 返回 `{"status": "ok"}`
- [ ] `curl -X POST /api/v1/analyze` → 3 个场景均返回 report_id
- [ ] `curl GET /api/v1/reports/{id}` → 返回完整 5 段式报告 JSON
- [ ] WebSocket 连接可实时接收进度事件（至少 5 个步骤事件）
- [ ] `cd frontend && npm run dev` → http://localhost:3000/analyze 页面正常渲染
- [ ] 输入场景 A 描述 → 进度条推进 → 报告页正常显示
- [ ] 报告页：风险徽章颜色正确、法规面板可折叠、导出按钮可用
- [ ] 历史记录页正确显示已生成的报告列表
- [ ] `docker-compose up --build` → http://localhost:3000 可使用完整功能
- [ ] `git commit -m "feat: Day4 API + WebSocket + frontend core pages"`

---

## 测试用的 3 个场景

**场景 A（跨境数据训练）：**
"我们计划把欧洲用户上传的短视频素材传回国内服务器，用于训练一个 AI 视频剪辑模型。训练完成后模型部署在国内，服务全球用户。视频中可能包含用户人脸。"
→ 预期：risk_level = High/Critical，引用 GDPR Art.46 + PIPL 第三十八条

**场景 B（第三方模型 API）：**
"我们的产品需要接入第三方大模型 API（如 GPT-4）来处理用户提交的文本和图片内容，生成摘要和标签。用户数据会发送到第三方 API 服务器。"
→ 预期：risk_level = Medium/High，引用 PIPL 第二十三条（第三方提供）+ GDPR Art.28（处理者）

**场景 C（AIGC 内容标识）：**
"我们计划向欧洲 B 端客户提供 AI 自动生成广告视频的 API。生成的视频将直接用于社交媒体投放。"
→ 预期：risk_level = Medium/High，引用 EU AI Act Art.50（透明度义务）+ AIGC 标识办法相关条款

---

## 💡 Day 4 Vibe Coding 使用建议

- **先完成后端 API，再做前端**。用 curl/Postman 确认 API 正常后再开始写前端，避免前后端同时调试
- **WebSocket 是最容易出 Bug 的部分**。建议先用 Python 脚本测试 WebSocket 连接，再在 React 中集成：
  ```python
  import asyncio, websockets
  async def test():
      async with websockets.connect("ws://localhost:8000/ws/test-session") as ws:
          async for msg in ws:
              print(msg)
  asyncio.run(test())
  ```
- **前端先用 Mock 数据开发 UI**，报告页可以先 hardcode 一份 AuditReport JSON，把渲染逻辑调好后再接真实 API
- **Docker Compose 放在最后**，确保本地开发环境（后端 + 前端分别 `npm run dev` / `make dev`）联调通过后再容器化
- Day 4 结束时进行一次 git commit，标注「feat: Day4 API + WebSocket + frontend core pages」