---
name: agent-memory
description: 在 HarnessAgent 项目中构建 Agent 的记忆、RAG 检索和上下文管理系统。Use when: (1) 为 Agent 添加记忆能力(工作记忆/情景记忆/语义记忆), (2) 构建 RAG 知识库和检索管道, (3) 设计 ContextBuilder 管理 Token 预算, (4) 实现记忆的存储/检索/遗忘/整合, (5) 将 Memory 和 RAG 集成为 Agent 工具, (6) 设计多工具协同工作流(记忆+检索+上下文)。
---

# Agent Memory — 记忆、RAG 与上下文工程

## 概述

本技能覆盖 Agent 的记忆系统设计——从当前会话的工作记忆到跨会话的持久记忆，从文档检索增强生成(RAG)到 Token 预算管理(Context Engineering)。Memory 是 Agent 的"海马体"——本技能确保 Agent 记得该记的、忘记该忘的、检索到需要的。

## 系统架构

```
用户查询
    ↓
ContextBuilder（Token预算管理）
    ├── 从 MemoryTool 检索相关记忆
    ├── 从 RAGTool 检索相关知识
    ├── 压缩、过滤、排序
    └── 构建最终上下文 → 注入 LLM System Message
           ↓
    LLM 推理 → 生成回复
           ↓
    自动更新记忆（remember/forget/consolidate）
```

## 快速决策：记忆类型选择

| 数据特征 | 记忆类型 | 生命周期 | 检索方式 |
|---------|---------|---------|---------|
| 当前任务上下文、推理中间状态 | `working` | 单次会话 | 顺序读最近的 |
| 历史会话摘要、关键决策、经验教训 | `episodic` | 跨会话 | 语义搜索 |
| 用户偏好、项目知识、事实性信息 | `semantic` | 永久 | 精确匹配+语义 |
| 文档阅读、操作记录等感知数据 | `perceptual` | 按需保留 | 时间+关联 |

## Memory 三层架构

### 记忆模型

```python
@dataclass
class MemoryItem:
    id: str
    content: str              # 记忆内容
    memory_type: str          # working | episodic | semantic | perceptual
    importance: float         # 0.0-1.0，影响保留优先级
    created_at: float         # 创建时间戳
    last_accessed: float      # 最后访问时间
    access_count: int         # 访问次数
    tags: list[str]           # 标签（便于分类检索）
    embedding: Optional[list[float]]  # 向量嵌入（语义检索用）
    metadata: dict            # 额外元数据

class MemoryConfig:
    working_memory_capacity: int = 10      # 最近 N 条
    working_memory_tokens: int = 2000      # Token 上限
    episodic_memory_capacity: int = 100    # 长期记忆条数
    enable_forgetting: bool = True         # 启用遗忘机制
    forgetting_threshold: float = 0.3      # 重要性低于此值可遗忘
    auto_consolidate: bool = True          # 自动整合相似记忆
```

### MemoryTool 统一接口

```python
class MemoryTool(Tool):
    """Agent 的记忆工具——统一的 CRUD + 管理接口"""

    name = "memory"
    description = (
        "管理 Agent 的记忆。支持添加/搜索/更新/删除记忆，"
        "以及统计、摘要、遗忘和整合操作。"
    )

    def __init__(self, user_id: str,
                 memory_types=None,
                 config: MemoryConfig = MemoryConfig()):
        self.user_id = user_id
        self.memory_types = memory_types or ["working", "episodic", "semantic"]
        self.config = config
        self._store: dict[str, list[MemoryItem]] = {
            t: [] for t in self.memory_types
        }

    def run(self, params: dict) -> str:
        action = params.get("action")
        if action == "add":
            return self._remember(params)
        elif action == "search":
            return self._recall(params)
        elif action == "update":
            return self._update(params)
        elif action == "remove":
            return self._forget_single(params)
        elif action == "stats":
            return self._stats()
        elif action == "summary":
            return self._summary()
        elif action == "forget":
            return self._forget_batch(params)
        elif action == "consolidate":
            return self._consolidate(params)
        return f"未知操作: {action}"

    def _remember(self, params: dict) -> str:
        """添加新记忆"""
        content = params["content"]
        mem_type = params.get("memory_type", "working")
        importance = float(params.get("importance", 0.5))
        tags = params.get("tags", "").split(",") if params.get("tags") else []

        item = MemoryItem(
            id=generate_id(),
            content=content,
            memory_type=mem_type,
            importance=importance,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=0,
            tags=tags,
            metadata=params.get("metadata", {})
        )
        self._store[mem_type].append(item)
        return f"记忆已保存 (id={item.id}, type={mem_type})"

    def _recall(self, params: dict) -> str:
        """检索记忆——支持关键词和语义搜索"""
        query = params.get("query", "")
        mem_type = params.get("memory_type", "all")
        limit = int(params.get("limit", 5))

        results = self._search(query, mem_type, limit)
        if not results:
            return "未找到相关记忆。"

        lines = [f"找到 {len(results)} 条记忆:"]
        for i, item in enumerate(results, 1):
            lines.append(f"{i}. [{item.memory_type}] {item.content} "
                         f"(重要性:{item.importance:.2f}, "
                         f"标签:{','.join(item.tags)})")
        return "\n".join(lines)
```

### 记忆操作触发时机

| 操作 | 触发条件 | 说明 |
|------|---------|------|
| `remember` | Agent 检测到重要信息 | 自动：任务结论、用户偏好、重要发现 |
| `recall` | 每次用户输入时 | 自动：注入相关记忆到上下文 |
| `update` | 发现冲突或补充信息 | 手动：用户纠正或新信息覆盖旧记忆 |
| `forget` | 定期后台清理 | 自动：低重要性记忆过期删除 |
| `consolidate` | 后台异步任务 | 自动：合并相似记忆，升华为语义记忆 |

### 遗忘与整合策略

```python
def _forget_batch(self, params: dict) -> str:
    """批量遗忘低价值记忆"""
    strategy = params.get("strategy", "importance_based")
    threshold = float(params.get("threshold", self.config.forgetting_threshold))

    removed = 0
    if strategy == "importance_based":
        for mem_type in self._store:
            before = len(self._store[mem_type])
            self._store[mem_type] = [
                m for m in self._store[mem_type]
                if m.importance >= threshold
            ]
            removed += before - len(self._store[mem_type])

    elif strategy == "age_based":
        max_age = float(params.get("max_age_days", 30))
        cutoff = time.time() - max_age * 86400
        for mem_type in self._store:
            before = len(self._store[mem_type])
            self._store[mem_type] = [
                m for m in self._store[mem_type]
                if m.last_accessed >= cutoff
            ]
            removed += before - len(self._store[mem_type])

    elif strategy == "capacity_based":
        for mem_type in self._store:
            capacity = self.config.episodic_memory_capacity
            if len(self._store[mem_type]) > capacity:
                # 按重要性排序，保留前 capacity 条
                self._store[mem_type].sort(
                    key=lambda m: (m.importance, m.last_accessed), reverse=True
                )
                removed += len(self._store[mem_type]) - capacity
                self._store[mem_type] = self._store[mem_type][:capacity]

    return f"已遗忘 {removed} 条记忆"

def _consolidate(self, params: dict) -> str:
    """将工作记忆升华为情景/语义记忆"""
    from_type = params.get("from_type", "working")
    to_type = params.get("to_type", "episodic")
    importance_threshold = float(params.get("importance_threshold", 0.6))

    consolidated = 0
    for item in self._store[from_type]:
        if item.importance >= importance_threshold:
            item.memory_type = to_type
            self._store[to_type].append(item)
            consolidated += 1

    # 从原类型移除
    self._store[from_type] = [
        m for m in self._store[from_type]
        if m.importance < importance_threshold
    ]
    return f"已整合 {consolidated} 条从 {from_type} 到 {to_type}"
```

## RAG 检索管道

### 完整 RAG Pipeline

```
文档摄入 → 格式解析 → 语义分块 → Embedding → 向量库
                                                 ↓
用户查询 → 查询重写 → 混合检索 → 重排序 → 上下文注入
```

### RAGTool 统一接口

```python
class RAGTool(Tool):
    """Agent 的 RAG 工具——文档管理和智能检索"""

    name = "rag"
    description = "管理和检索知识库文档。支持添加文本/文件、语义搜索和问答。"

    def __init__(self, knowledge_base_path: str, rag_namespace: str = "default"):
        self.kb_path = knowledge_base_path
        self.namespace = rag_namespace
        self.embedding_model = None  # 延迟加载
        self.vector_store = None     # ChromaDB / FAISS
        self.bm25_index = None       # 稀疏检索

    def run(self, params: dict) -> str:
        action = params.get("action")
        if action == "add_text":
            return self._add_text(params)
        elif action == "add_file":
            return self._add_file(params)
        elif action == "search":
            return self._search(params)
        elif action == "ask":
            return self._ask(params)
        elif action == "stats":
            return self._stats()
        return f"未知操作: {action}"

    def _search(self, params: dict) -> str:
        """混合检索——Dense(向量) + Sparse(BM25)"""
        query = params["query"]
        limit = int(params.get("limit", 5))

        # 1. 查询重写
        rewritten_query = self._rewrite_query(query)

        # 2. Dense 检索（向量相似度）
        dense_results = self._dense_search(rewritten_query, limit * 2)

        # 3. Sparse 检索（BM25 关键词）
        sparse_results = self._sparse_search(rewritten_query, limit * 2)

        # 4. 融合排序（RRF: Reciprocal Rank Fusion）
        merged = self._reciprocal_rank_fusion(dense_results, sparse_results)

        # 5. 重排序（Cross-encoder 精排）
        reranked = self._rerank(query, merged[:limit])

        return self._format_search_results(reranked)
```

### 关键技术详解

| 技术 | 作用 | 实现 |
|------|------|------|
| 语义分块 | 按语义边界切分文档，保证块完整性 | 按段落/标题边界，目标 256-512 tokens/块 |
| 查询重写 | LLM 优化用户查询，提高召回率 | "怎么修bug" → "Python 代码调试方法和常见错误修复" |
| 混合检索 | Dense + Sparse 互补 | 向量检索语义相关 + BM25 检索关键词精确匹配 |
| RRF 融合 | 合并两种检索结果 | `score = Σ 1/(k + rank_i)`，k=60 |
| Cross-encoder 重排 | 对 Top-K 精排 | 用 cross-encoder 模型逐对打分 |
| HyDE | 先假设答案再检索 | LLM 生成假设答案 → 用答案向量检索 → 提高召回 |

### 文档摄入

```python
def _add_file(self, params: dict) -> str:
    """摄入文档文件到知识库"""
    file_path = params["file_path"]

    # 1. 格式解析
    text = self._parse_document(file_path)  # 支持 .md/.pdf/.txt/.html

    # 2. 语义分块
    chunks = self._semantic_chunk(text, target_size=512)

    # 3. 生成 Embedding
    embeddings = self.embedding_model.encode(chunks)

    # 4. 存入向量库
    ids = self.vector_store.add(embeddings, chunks,
                                 metadata={"source": file_path})

    # 5. 更新 BM25 索引
    self.bm25_index.add(chunks)

    return f"已摄入 {file_path}: {len(chunks)} 个块"
```

## Context 工程

### ContextBuilder

```python
from hello_agents.context import ContextBuilder, ContextConfig

@dataclass
class ContextConfig:
    max_tokens: int = 3000          # 上下文区的 Token 预算
    reserve_ratio: float = 0.2      # 预留 20% 给模型回复
    min_relevance: float = 0.3      # 低于此分数的信息丢弃
    enable_compression: bool = True # 启用长文本压缩
    max_history_turns: int = 10     # 最多保留最近 N 轮对话

class ContextBuilder:
    """构建 Agent 的上下文——控制注入 LLM 的信息量和质量"""

    def __init__(self, memory_tool: MemoryTool = None,
                 rag_tool: RAGTool = None,
                 config: ContextConfig = ContextConfig()):
        self.memory_tool = memory_tool
        self.rag_tool = rag_tool
        self.config = config

    def build(self, user_query: str,
              conversation_history: list = None,
              system_instructions: str = "",
              additional_packets: list = None) -> str:
        """构建最终上下文——这是注入 LLM system message 的内容"""

        packets = []  # (content, relevance_score, source) 三元组

        # 1. 系统指令（最高优先级，不压缩）
        if system_instructions:
            packets.append((system_instructions, 1.0, "system"))

        # 2. 从记忆检索
        if self.memory_tool:
            memories = self.memory_tool._recall({
                "query": user_query, "limit": 5
            })
            packets.append((memories, 0.8, "memory"))

        # 3. 从 RAG 检索
        if self.rag_tool:
            docs = self.rag_tool._search({
                "query": user_query, "limit": 3
            })
            packets.append((docs, 0.7, "rag"))

        # 4. 额外上下文包
        if additional_packets:
            for pkt in additional_packets:
                packets.append((pkt["content"], pkt.get("relevance", 0.5),
                                pkt.get("source", "extra")))

        # 5. 按相关性排序、过滤、Token 预算控制
        context = self._assemble(packets)
        return context

    def _assemble(self, packets: list) -> str:
        """组装最终上下文——Token 预算管理"""
        packets.sort(key=lambda p: p[1], reverse=True)  # 按相关性降序

        budget = self.config.max_tokens
        sections = []

        for content, relevance, source in packets:
            if relevance < self.config.min_relevance:
                continue  # 低相关性丢弃

            token_count = self._estimate_tokens(content)

            if self.config.enable_compression and token_count > budget * 0.3:
                content = self._compress(content, max_tokens=int(budget * 0.3))

            if token_count <= budget:
                sections.append(f"[{source}]\n{content}")
                budget -= token_count
            else:
                sections.append(f"[{source}]\n{content[:budget]}")
                break

        return "\n\n---\n\n".join(sections)
```

### Token 预算分配策略

```
总 Token 预算示例 (8000 tokens):
├── System Prompt 固定部分:    500 tokens (6%)
├── 工具描述:                 1000 tokens (13%)
├── ContextBuilder 上下文区:   3000 tokens (38%) ← 本技能管理
├── 对话历史 (滑动窗口):       2000 tokens (25%)
└── 模型回复预留:             1500 tokens (19%) ← reserve_ratio
```

### 上下文压缩策略

| 策略 | 适用场景 | 实现 |
|------|---------|------|
| 滑动窗口 | 长对话 | 只保留最近 N 轮，旧对话丢弃或摘要 |
| 重要性评分 | 记忆管理 | 低重要性记忆不注入上下文 |
| 摘要替换 | 长文档 | 用 LLM 将长文档压缩为 2-3 句摘要 |
| 相关性过滤 | 检索结果 | 低于 min_relevance 的信息丢弃 |

## Agent 工具集成

### 完整初始化模式

```python
class AgentWithMemory:
    """集成记忆和 RAG 的完整 Agent 示例"""

    def __init__(self, user_id: str, kb_path: str = "./kb"):
        # 1. 创建工具
        self.memory_tool = MemoryTool(
            user_id=user_id,
            memory_types=["working", "episodic", "semantic", "perceptual"]
        )
        self.rag_tool = RAGTool(
            knowledge_base_path=kb_path,
            rag_namespace="agent_kb"
        )

        # 2. 创建上下文构建器
        self.context_builder = ContextBuilder(
            memory_tool=self.memory_tool,
            rag_tool=self.rag_tool,
            config=ContextConfig(max_tokens=3000)
        )

        # 3. 创建工具注册表
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_tool(self.memory_tool)
        self.tool_registry.register_tool(self.rag_tool)

        # 4. 创建 Agent
        self.agent = MyAgent(
            name="记忆增强助手",
            llm=HelloAgentsLLM(),
            tool_registry=self.tool_registry
        )

    def run(self, user_input: str) -> str:
        # 构建增强上下文
        context = self.context_builder.build(
            user_query=user_input,
            conversation_history=self.agent.get_history(),
            system_instructions=self.agent._build_system_prompt()
        )

        # 注入上下文执行
        result = self.agent.run(user_input, context_override=context)

        # 自动更新记忆
        self.memory_tool.run({
            "action": "add",
            "content": f"Q: {user_input}\nA: {result}",
            "memory_type": "episodic",
            "importance": self._assess_importance(user_input, result)
        })

        return result
```

### 工具协同工作流

```
学习场景:
  1. RAG: 存储学习资料 → rag.run({"action":"add_text",...})
  2. Memory: 记录学习活动 → memory.run({"action":"add","type":"episodic",...})

回顾场景:
  1. Memory: 检索学习历史 → memory.run({"action":"search",...})
  2. RAG: 获取知识补充 → rag.run({"action":"search",...})

规划场景:
  1. Memory: 查看历史笔记 → memory.run({"action":"summary"})
  2. RAG: 查询领域知识 → rag.run({"action":"ask",...})
  3. Memory: 记录新计划 → memory.run({"action":"add",...})
```

## 参考资源

| 文件 | 内容 | 何时查阅 |
|------|------|---------|
| [memory-system.md](references/memory-system.md) | MemoryTool 完整实现、遗忘/整合策略、记忆类型管理 | 设计记忆系统时 |
| [rag-pipeline.md](references/rag-pipeline.md) | RAG 完整管道、分块/嵌入/混合检索/重排序 | 构建 RAG 系统时 |
| [context-engineering.md](references/context-engineering.md) | ContextBuilder、Token 预算、压缩策略、集成模式 | 设计上下文管理时 |

> 📌 本技能覆盖 Hello Agent 教程 Ch8,9。Agent 核心范式见 agent-builder 技能，工具系统见 agent-tools 技能。
