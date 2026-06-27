# Memory 系统完整实现

## 四种记忆类型对比

| 类型 | 存储内容 | 生命周期 | 容量 | 检索方式 |
|------|---------|---------|------|---------|
| working | 当前任务的推理步骤、中间结果 | 单次会话 | 小(10条) | 顺序读取 |
| episodic | 会话摘要、关键决策、经验教训 | 跨会话 | 中(100条) | 语义搜索 |
| semantic | 用户偏好、项目知识、事实 | 永久 | 大 | 精确+语义 |
| perceptual | 文档摘要、感官记录 | 按需 | 按需 | 关联+时间 |

## MemoryItem 数据结构

```python
from dataclasses import dataclass, field
from typing import Optional
import time
import uuid

@dataclass
class MemoryItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = ""
    memory_type: str = "working"    # working | episodic | semantic | perceptual
    importance: float = 0.5         # 0.0-1.0，影响保留优先级
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)

    def touch(self):
        """更新访问记录"""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> dict:
        return {
            "id": self.id, "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "tags": self.tags, "metadata": self.metadata
        }
```

## MemoryTool 完整实现

```python
class MemoryTool:
    """Agent 记忆工具——完整 CRUD + 管理操作"""

    name = "memory"
    description = (
        "管理 Agent 的记忆系统。操作: add(添加), search(检索), "
        "update(更新), remove(删除), stats(统计), summary(摘要), "
        "forget(批量遗忘), consolidate(整合升维)"
    )

    def __init__(self, user_id: str,
                 memory_types: list[str] = None,
                 embedding_fn=None):
        self.user_id = user_id
        self.memory_types = memory_types or ["working", "episodic", "semantic"]
        self.embedding_fn = embedding_fn
        self._stores: dict[str, list[MemoryItem]] = {
            t: [] for t in self.memory_types
        }

    def run(self, params: dict) -> str:
        action = params.get("action", "search")

        handlers = {
            "add": self._add,
            "search": self._search,
            "update": self._update,
            "remove": self._remove,
            "stats": self._stats,
            "summary": self._summary,
            "forget": self._forget,
            "consolidate": self._consolidate,
        }

        handler = handlers.get(action)
        if not handler:
            return f"未知操作: {action}，可用: {list(handlers.keys())}"
        return handler(params)

    def _add(self, params: dict) -> str:
        content = params.get("content", "")
        if not content:
            return "错误: 记忆内容不能为空"

        mem_type = params.get("memory_type", "working")
        if mem_type not in self._stores:
            return f"错误: 不支持的记忆类型 '{mem_type}'"

        item = MemoryItem(
            content=content,
            memory_type=mem_type,
            importance=float(params.get("importance", 0.5)),
            tags=self._parse_tags(params.get("tags", "")),
            metadata=params.get("metadata", {})
        )

        # 自动生成 embedding
        if self.embedding_fn:
            try:
                item.embedding = self.embedding_fn(content)
            except Exception:
                pass

        self._stores[mem_type].append(item)

        # 容量控制
        self._evict_if_needed(mem_type)

        return f"✅ 记忆已保存 (id={item.id}, type={mem_type}, importance={item.importance:.2f})"

    def _search(self, params: dict) -> str:
        query = params.get("query", "")
        mem_type = params.get("memory_type", "all")
        limit = int(params.get("limit", 5))
        min_importance = float(params.get("min_importance", 0.0))

        # 收集候选
        candidates = []
        if mem_type == "all":
            for store in self._stores.values():
                candidates.extend(store)
        else:
            candidates = self._stores.get(mem_type, [])

        if not candidates:
            return "📭 暂无相关记忆"

        # 排序策略
        if query and self.embedding_fn:
            results = self._semantic_search(query, candidates, limit)
        else:
            results = self._keyword_search(query, candidates, limit)

        # 更新访问记录
        for item in results:
            item.touch()

        return self._format_search_results(results, query)

    def _semantic_search(self, query: str, candidates: list, limit: int) -> list:
        """基于 embedding 的语义搜索"""
        query_emb = self.embedding_fn(query)

        scored = []
        for item in candidates:
            if item.embedding:
                sim = self._cosine_similarity(query_emb, item.embedding)
                score = 0.6 * sim + 0.4 * item.importance  # 语义相关性 + 重要性
                scored.append((score, item))
            else:
                scored.append((item.importance * 0.3, item))  # 无 embedding 降权

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def _keyword_search(self, query: str, candidates: list, limit: int) -> list:
        """关键词匹配搜索"""
        if not query:
            # 无查询 → 按最近访问排序
            candidates.sort(key=lambda x: (x.importance, x.last_accessed), reverse=True)
            return candidates[:limit]

        keywords = set(query.lower().split())
        scored = []
        for item in candidates:
            content_lower = item.content.lower()
            score = sum(1 for kw in keywords if kw in content_lower)
            score += sum(1 for tag in item.tags if any(kw in tag.lower() for kw in keywords))
            if score > 0:
                scored.append((score + item.importance, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def _update(self, params: dict) -> str:
        mem_id = params.get("memory_id", "")
        for store in self._stores.values():
            for item in store:
                if item.id == mem_id:
                    if "content" in params:
                        item.content = params["content"]
                    if "importance" in params:
                        item.importance = float(params["importance"])
                    if "tags" in params:
                        item.tags = self._parse_tags(params["tags"])
                    item.last_accessed = time.time()
                    return f"✅ 记忆 {mem_id} 已更新"
        return f"找不到记忆: {mem_id}"

    def _remove(self, params: dict) -> str:
        mem_id = params.get("memory_id", "")
        for store in self._stores.values():
            for i, item in enumerate(store):
                if item.id == mem_id:
                    store.pop(i)
                    return f"🗑️ 记忆 {mem_id} 已删除"
        return f"找不到记忆: {mem_id}"

    def _stats(self, params: dict = None) -> str:
        lines = [f"📊 {self.user_id} 的记忆统计:"]
        total = 0
        for mem_type in self.memory_types:
            items = self._stores.get(mem_type, [])
            total += len(items)
            avg_imp = sum(i.importance for i in items) / len(items) if items else 0
            lines.append(f"  {mem_type}: {len(items)} 条 (平均重要性: {avg_imp:.2f})")
        lines.append(f"  总计: {total} 条")
        return "\n".join(lines)

    def _summary(self, params: dict = None) -> str:
        """生成记忆摘要——给 LLM 看的概览"""
        lines = ["📋 记忆摘要:"]
        for mem_type in self.memory_types:
            items = self._stores.get(mem_type, [])
            if not items:
                continue
            # 取最重要/最近的几条
            items.sort(key=lambda i: (i.importance, i.last_accessed), reverse=True)
            top = items[:3]
            lines.append(f"\n[{mem_type}]")
            for item in top:
                lines.append(f"  • {item.content[:80]}... (重要性:{item.importance:.2f})")
        return "\n".join(lines)

    # —— 遗忘与整合 ——

    def _forget(self, params: dict) -> str:
        strategy = params.get("strategy", "importance")
        threshold = float(params.get("threshold", 0.3))
        removed_total = 0

        for mem_type, store in self._stores.items():
            before = len(store)
            if strategy == "importance":
                store[:] = [i for i in store if i.importance >= threshold]
            elif strategy == "age":
                max_days = float(params.get("max_age_days", 30))
                cutoff = time.time() - max_days * 86400
                store[:] = [i for i in store if i.last_accessed >= cutoff]
            elif strategy == "capacity":
                cap = int(params.get("capacity", 100))
                if len(store) > cap:
                    store.sort(key=lambda i: (i.importance, i.last_accessed), reverse=True)
                    store[:] = store[:cap]
            removed_total += before - len(store)

        return f"🧹 已遗忘 {removed_total} 条低价值记忆 (策略: {strategy})"

    def _consolidate(self, params: dict) -> str:
        """整合——将高重要性的 working 记忆升级为 episodic/semantic"""
        from_type = params.get("from_type", "working")
        to_type = params.get("to_type", "episodic")
        threshold = float(params.get("importance_threshold", 0.7))

        if from_type not in self._stores or to_type not in self._stores:
            return "错误的记忆类型"

        to_upgrade = [i for i in self._stores[from_type] if i.importance >= threshold]
        for item in to_upgrade:
            item.memory_type = to_type
            self._stores[to_type].append(item)

        self._stores[from_type] = [i for i in self._stores[from_type] if i.importance < threshold]
        return f"🔄 已整合 {len(to_upgrade)} 条从 {from_type} 到 {to_type}"

    # —— 辅助方法 ——

    def _parse_tags(self, tags_raw) -> list[str]:
        if isinstance(tags_raw, list):
            return tags_raw
        return [t.strip() for t in str(tags_raw).split(",") if t.strip()]

    def _cosine_similarity(self, a, b) -> float:
        dot = sum(x*y for x, y in zip(a, b))
        norm_a = sum(x*x for x in a) ** 0.5
        norm_b = sum(x*x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def _evict_if_needed(self, mem_type: str):
        """超出容量时淘汰低价值记忆"""
        MAX_CAPACITY = {"working": 20, "episodic": 100, "semantic": 200}
        cap = MAX_CAPACITY.get(mem_type, 100)
        store = self._stores[mem_type]
        if len(store) > cap:
            store.sort(key=lambda i: (i.importance, i.last_accessed))
            self._stores[mem_type] = store[-(cap):]

    def _format_search_results(self, results: list, query: str) -> str:
        if not results:
            return f"未找到与 '{query}' 相关的记忆"

        lines = [f"🔍 找到 {len(results)} 条相关记忆:"]
        for i, item in enumerate(results, 1):
            lines.append(
                f"{i}. [{item.memory_type} | 重要性:{item.importance:.2f}]\n"
                f"   {item.content[:150]}\n"
                f"   标签: {', '.join(item.tags) if item.tags else '(无)'}"
            )
        return "\n".join(lines)
```

## 记忆自动触发集成

```python
class MemoryAwareAgent:
    """自动管理记忆的 Agent 包装器"""

    def __init__(self, agent, memory_tool: MemoryTool,
                 auto_remember_threshold: float = 0.5):
        self.agent = agent
        self.memory = memory_tool
        self.auto_threshold = auto_remember_threshold

    def run(self, input_text: str) -> str:
        # 1. 检索相关记忆注入上下文（自动触发）
        memories = self.memory.run({
            "action": "search",
            "query": input_text,
            "limit": 5
        })

        # 2. 增强输入
        enhanced_input = f"[相关记忆]\n{memories}\n\n[当前问题]\n{input_text}"
        result = self.agent.run(enhanced_input)

        # 3. 自动保存重要对话（自动触发）
        importance = self._assess_importance(input_text, result)
        if importance >= self.auto_threshold:
            self.memory.run({
                "action": "add",
                "content": f"Q: {input_text}\nA: {result[:200]}",
                "memory_type": "episodic",
                "importance": importance,
                "tags": self._extract_tags(input_text)
            })

        return result

    def _assess_importance(self, query: str, answer: str) -> float:
        """评估对话的重要性——简单的启发式方法"""
        important_keywords = ["记住", "重要", "偏好", "设置", "配置", "密码", "关键"]
        query_lower = query.lower()
        score = 0.5  # 基础分

        for kw in important_keywords:
            if kw in query_lower:
                score += 0.1

        if len(answer) > 500:  # 长回答通常更重要
            score += 0.1

        return min(1.0, score)

    def _extract_tags(self, text: str) -> list[str]:
        """从文本中提取标签"""
        tech_keywords = ["python", "AI", "agent", "API", "数据库", "前端", "部署"]
        return [kw for kw in tech_keywords if kw.lower() in text.lower()]
```
