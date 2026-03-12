# Compliance Agent — Day 2 Vibe Coding Prompt

## 核心执行规则 (Rules for Agent)

1. **分步执行**：本需求文档包含多个任务，严格按照顺序执行。你**绝对不能**一次性把所有阶段的代码都写完。
2. **强制暂停与汇报**：每当你完成一个阶段的代码编写或终端命令执行后，你**必须立刻停下来**。
3. **汇报格式**：停下来时，向我简短汇报：
   - 本阶段完成了什么文件/功能。
   - 是否遇到了潜在风险。
   - 询问我：“请问老板是否可以进入下一阶段？”

### 任务 1：法规文档准备（~1h）

在 `data/regulations/` 下整理 6 部法规的 Markdown 原文：

目录结构：
data/regulations/
├── eu/
│   ├── gdpr_full.md
│   └── eu_ai_act_full.md
└── cn/
    ├── pipl_full.md
    ├── dsl_full.md
    ├── csl_full.md
    └── aigc_marking_full.md

**格式统一规范（chunker.py 依赖此格式）：**

欧盟法规（英文）使用以下分隔符：
## Article 1: Subject-matter and objectives
## Article 2: Material scope

中国法规（中文）使用以下分隔符：
## 第一条
## 第二条

每条条款内容紧跟在标题下方，条款之间不加额外空行。
每个文件顶部加元信息注释块：

<!-- 
regulation: GDPR
jurisdiction: EU
language: en
version: 2016/679
effective_date: 2018-05-25
-->

**法规条款数量参考（PRD §8.4）：**
- GDPR：~99 条
- EU AI Act：~113 条 + 附件
- PIPL：~74 条
- DSL：~55 条
- CSL：~79 条
- AIGC 标识办法：~25 条

完成标准：运行 `python scripts/ingest_regulations.py --dry-run` 可识别所有 6 个文件并输出条款统计。

---

### 任务 2：层级感知切片（~1h）

实现 `rag/ingest/chunker.py`：

**核心逻辑：**
- 以「条」（Article / 第X条）为切片单元，每条形成一个独立 Chunk
- 保留条款标题、所属章节标题（向上查找最近的 # 或 ## 章节标题）
- 对超长条款（> 800 tokens）按「款」（paragraph）进一步拆分，
  子 Chunk 的 article_id 标注为 "Article_46_1"、"Article_46_2" 等
- 对过短条款（< 50 tokens，通常是定义条款的引用项）与相邻条款合并

数据结构（每个 Chunk 输出为 dict）：
{
  "chunk_id": "gdpr_art46",
  "regulation": "GDPR",
  "jurisdiction": "EU",
  "language": "en",
  "article_id": "Article 46",
  "article_title": "Transfers subject to appropriate safeguards",
  "chapter": "Chapter V: Transfers of personal data to third countries",
  "text": "...",        # 原文
  "token_count": 312
}

实现 `rag/ingest/metadata.py`：

为每个 Chunk 注入关键词标签（tags 字段），基于规则映射：
- 包含 "cross-border" / "transfer" / "third country" / "跨境" / "出境" → ["cross_border_transfer"]
- 包含 "consent" / "同意" → ["consent"]
- 包含 "biometric" / "生物特征" / "人脸" → ["biometric"]
- 包含 "AI" / "artificial intelligence" / "人工智能" → ["ai_governance"]
- 包含 "generate" / "synthetic" / "生成" / "合成" → ["aigc"]
- 包含 "third party" / "第三方" → ["third_party"]
- 包含 "assessment" / "评估" / "DPIA" → ["risk_assessment"]

tags 可多值，例：["cross_border_transfer", "third_party"]

完成标准：
- `python -c "from rag.ingest.chunker import chunk_regulation; print(len(chunk_regulation('data/regulations/eu/gdpr_full.md')))"` 
  输出 90-110 之间的数字
- 每个 Chunk dict 包含所有必填字段且无 None 值

---

### 任务 3：摘要增强（SAC）（~0.5h）

实现 `rag/ingest/summary_augmenter.py`：

**功能：** 为每个 Chunk 调用 LLM 生成约 150 字的法规级摘要，
附加到 Chunk 的 `summary` 字段。摘要用于帮助检索模型理解
该条款在整体法规中的定位（而非只看条款原文）。

System Prompt：
"""
你是一位专业的数据合规律师助手。
请用 150 字以内（中文）概括以下法规条款的核心要求和适用场景。
要求：直接说明该条款规定了什么义务、针对哪类主体、在什么条件下触发。
不要使用"本条款"开头，直接描述内容。
"""

**成本控制（重要）：**
- 批量生成时使用异步并发，max_concurrent=5，避免速率限制
- 加入本地缓存：以 chunk_id 为 key，存入 `data/kb/summary_cache.json`
  重复运行时跳过已缓存的 Chunk，避免重复消耗 API 额度
- 预估：450 个 Chunk × ~200 tokens/次 ≈ 90K tokens，约 $0.05（claude-haiku）

完成标准：运行后 `data/kb/summary_cache.json` 包含 ≥ 90% Chunk 的摘要。

---

### 任务 4：交叉引用解析（~0.5h）

实现 `rag/ingest/cross_ref.py`：

**功能：** 解析条款内文本中的法规引用，建立引用关系图。

识别模式（正则）：
- 英文：`Article \d+`, `Art\. \d+`, `paragraph \d+`
- 中文：`第[零一二三四五六七八九十百\d]+条`, `本法第`, `依据第`

输出格式（存入每个 Chunk 的 `cross_refs` 字段）：
{
  "chunk_id": "gdpr_art49",
  "cross_refs": [
    {"regulation": "GDPR", "article_id": "Article 46", "ref_type": "cites"},
    {"regulation": "GDPR", "article_id": "Article 47", "ref_type": "cites"}
  ]
}

同时生成全局引用关系图，存入 `data/kb/cross_ref_graph.json`，
格式为邻接表：{"gdpr_art49": ["gdpr_art46", "gdpr_art47"], ...}

完成标准：GDPR Art.49 的 cross_refs 中包含对 Art.46 的引用。

---

### 任务 5：向量入库（~1h）

实现 `rag/kb/vector_store.py`：

使用 ChromaDB（本地持久化模式），封装以下接口：
- `upsert(chunks: list[dict])` → 批量写入，自动处理重复
- `query(embedding: list[float], n_results: int, filter: dict) -> list[dict]`
- `delete(chunk_ids: list[str])` → 支持增量更新
- `count() -> int` → 返回当前 collection 中的 Chunk 数量

ChromaDB Collection 命名规范：
- `compliance_eu`：存放 GDPR + EU AI Act 的 Chunks
- `compliance_cn`：存放 PIPL + DSL + CSL + AIGC 标识办法的 Chunks
- 分 Collection 存储便于 router.py 按法域过滤

嵌入模型选型（按优先级）：
1. `BAAI/bge-m3`（首选，支持中英双语，768 维）
2. `intfloat/multilingual-e5-large`（备选）
3. OpenAI `text-embedding-3-small`（如本地资源不足时的云端方案）

加载方式（sentence-transformers）：
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-m3')
embedding = model.encode(text, normalize_embeddings=True)

实现 `scripts/ingest_regulations.py`：

串联完整入库流水线：
原文 → chunker → metadata → summary_augmenter → cross_ref → vector_store

支持命令行参数：
- `--dry-run`：只切片，不写入向量库
- `--skip-summary`：跳过摘要生成（调试时节省 API 额度）
- `--regulation gdpr`：只处理指定法规

完成标准：
- `make ingest` 成功完成，ChromaDB 中 compliance_eu + compliance_cn
  合计 Chunk 数量在 400-500 之间
- `python -c "from rag.kb.vector_store import VectorStore; print(VectorStore().count())"` 
  输出合理数字

---

### 任务 6：混合检索实现（~1.5h）

实现 `rag/retriever/semantic.py`：

def semantic_search(
    query: str,
    jurisdiction: Literal["EU", "CN", "All"] = "All",
    n_results: int = 10,
    tag_filter: list[str] | None = None
) -> list[dict]:

- 将 query 用嵌入模型转为向量
- 在对应 Collection 中检索 Top-n
- 支持按 tags 字段过滤（ChromaDB where 条件）
- 返回 Chunk 列表，含 distance 字段

实现 `rag/retriever/keyword.py`：

使用 rank_bm25 库实现 BM25 检索：
- 在内存中维护 BM25 索引（启动时从 ChromaDB 全量加载 text 字段）
- 支持中英文混合 tokenize（jieba 分词 + 英文空格分词）
- 返回 Top-n Chunk，含 bm25_score 字段

def keyword_search(
    query: str,
    jurisdiction: Literal["EU", "CN", "All"] = "All",
    n_results: int = 10
) -> list[dict]:

实现 `rag/retriever/reranker.py`：

使用 `BAAI/bge-reranker-v2-m3` Cross-Encoder 精排：

def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5
) -> list[dict]:

- 对每个候选 Chunk 计算 (query, chunk_text) 的相关度分数
- 按分数降序排列，返回 Top-k
- 每个返回 Chunk 附带 rerank_score 字段
- rerank_score < 0.6 时在 Chunk 中标记 low_confidence: true

实现 `rag/retriever/hybrid.py`：

def hybrid_search(
    query: str,
    parsed_fields: ParsedFields,
    top_k: int = 5
) -> list[EvidenceChunk]:

编排逻辑：
1. 从 parsed_fields.region 确定 jurisdiction（EU / CN / All）
2. 从 parsed_fields 提取 tag_filter（如 cross_border=True → ["cross_border_transfer"]）
3. 并发执行 semantic_search + keyword_search，各取 Top-10
4. 合并去重（按 chunk_id），共 ≤ 20 个候选
5. 调用 rerank，返回 Top-5
6. 将结果转换为 EvidenceChunk（schemas/evidence.py 中定义）

实现 `tools/rag_retriever.py`：

封装 hybrid_search 为标准 Agent 工具接口：
- 输入：query: str, parsed_fields: ParsedFields
- 输出：list[EvidenceChunk]
- 供 risk_agent.py 直接调用

完成标准：
- 输入「欧洲用户视频跨境传输训练模型」，Top-5 结果中包含
  GDPR Art.46（跨境传输适当保障）
- 输入「人工智能生成内容标识」，Top-5 结果中包含
  《AIGC 标识办法》相关条款
- 中文 Query 能匹配英文法规条款（双语检索验证）

---

### 任务 7：RAG 检索测试（~0.5h）

创建 `eval/test_cases/retrieval_tests.csv`，包含 20 条测试用例：
- 字段：query, expected_regulation, expected_article_id, jurisdiction
- 覆盖：跨境传输、同意机制、AIGC 标识、生物特征、第三方模型 5 个主题
- 各主题 EU 和 CN 场景各 2 条

运行检索评测：
python eval/run_eval.py --mode retrieval

输出指标：
- Top-5 命中率（expected_article_id 在返回的 Top-5 中）：目标 ≥ 70%
- 平均 rerank_score：目标 ≥ 0.5
- 双语命中率（中文 query 命中英文条款）：目标 ≥ 60%

---

## 技术约束

- ChromaDB 使用本地持久化模式，数据目录固定为 `data/kb/vectors/`
  不使用内存模式（重启后数据丢失）
- 嵌入模型首次运行时自动下载，建议提前 `huggingface-cli download BAAI/bge-m3`
- summary_augmenter 使用 `claude-haiku-3` 而非 Sonnet，节省成本
- BM25 索引在 `keyword.py` 模块初始化时构建，存入内存；
  若 ChromaDB 数据量 > 5000 Chunks 则改为持久化索引
- 所有检索函数均为同步函数，pipeline.py 中用 asyncio.to_thread 包装

## 其他要求
1. 每个 Chunk 必须生成 `search_text`，由 regulation + article_id + article_title + chapter + tags + summary + text 组成；embedding 与 BM25 均基于 search_text。
2. 永远保留 canonical article chunk，不在入库阶段把短条款与相邻条款合并；如需补上下文，使用 expanded_context 或 retrieval-time neighbor expansion。
3. chunk_id 必须使用稳定命名（如 gdpr_art46 / pipl_art38_p1），不得使用随机值或内容哈希作为主 ID。

## 完成标准 Checklist

今天结束前，以下命令应全部可执行：
- [ ] `make ingest` → 全量入库，无报错，输出 Chunk 统计
- [ ] `python eval/run_eval.py --mode retrieval` → Top-5 命中率 ≥ 70%
- [ ] 双语检索测试通过：中文 Query 命中英文法规
- [ ] `git commit -m "feat: Day2 RAG pipeline + hybrid retrieval"`