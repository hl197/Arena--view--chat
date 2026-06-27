# Context 工程参考

## ContextBuilder 完整实现

```python
from dataclasses import dataclass, field
import tiktoken

@dataclass
class ContextConfig:
    """上下文构建配置"""
    max_tokens: int = 3000           # 上下文区的 Token 预算
    reserve_ratio: float = 0.2       # 预留 20% 给模型回复
    min_relevance: float = 0.3       # 低于此分数的信息丢弃
    enable_compression: bool = True  # 启用长文本压缩
    max_history_turns: int = 10      # 最多保留最近 N 轮对话
    compression_model: str = "gpt-4o-mini"  # 压缩用的轻量模型

class ContextBuilder:
    """构建 Agent 的上下文——控制注入 LLM 的信息量和质量"""

    def __init__(self, memory_tool=None, rag_tool=None,
                 config: ContextConfig = None):
        self.memory_tool = memory_tool
        self.rag_tool = rag_tool
        self.config = config or ContextConfig()
        self._tokenizer = None

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            try:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._tokenizer = tiktoken.get_encoding("o200k_base")
        return self._tokenizer

    def build(self, user_query: str,
              conversation_history: list = None,
              system_instructions: str = "",
              additional_packets: list = None) -> str:
        """构建最终上下文——这是注入 LLM system message 的内容"""

        packets = []  # (content, relevance, source, priority)

        # 1. 系统指令——最高优先级，不压缩
        if system_instructions:
            packets.append((system_instructions, 1.0, "system", 0))

        # 2. 从记忆检索——高优先级
        if self.memory_tool:
            try:
                memories = self.memory_tool.run({
                    "action": "search", "query": user_query,
                    "limit": 5, "min_importance": self.config.min_relevance
                })
                packets.append((memories, 0.8, "memory", 1))
            except Exception:
                pass

        # 3. 从 RAG 检索——中优先级
        if self.rag_tool:
            try:
                docs = self.rag_tool.run({
                    "action": "search", "query": user_query, "limit": 3
                })
                packets.append((docs, 0.7, "rag", 2))
            except Exception:
                pass

        # 4. 对话历史——滑动窗口
        if conversation_history:
            recent = conversation_history[-self.config.max_history_turns:]
            history_text = "\n".join(
                f"{m.get('role', 'unknown')}: {m.get('content', '')[:200]}"
                for m in recent
            )
            packets.append((history_text, 0.6, "history", 3))

        # 5. 额外上下文包
        if additional_packets:
            for pkt in additional_packets:
                packets.append((
                    pkt.get("content", ""),
                    pkt.get("relevance", 0.5),
                    pkt.get("source", "extra"),
                    pkt.get("priority", 5)
                ))

        # 组装
        return self._assemble(packets)

    def _assemble(self, packets: list) -> str:
        """组装——按优先级排序、相关性过滤、Token 预算控制"""
        # 按 priority 排序（相同 priority 按 relevance 降序）
        packets.sort(key=lambda p: (p[3], -p[1]))

        budget = self.config.max_tokens
        sections = []

        for content, relevance, source, priority in packets:
            # 相关性过滤
            if relevance < self.config.min_relevance and source != "system":
                continue

            # 估算 token 数
            token_count = self._estimate_tokens(content)

            # 压缩长内容
            if (self.config.enable_compression and
                    token_count > budget * 0.3 and
                    source not in ["system"]):
                target = min(int(budget * 0.3), token_count)
                content = self._compress(content, max_tokens=target)
                token_count = self._estimate_tokens(content)

            # Token 预算控制
            if token_count <= budget:
                sections.append(f"## {source.upper()}\n{content}")
                budget -= token_count
            else:
                # 截断
                truncated = self._truncate_to_tokens(content, budget)
                sections.append(f"## {source.upper()}\n{truncated}")
                break

        return "\n\n---\n\n".join(sections)

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数"""
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            # 降级：字符数 / 4（中英文混合粗略估计）
            return len(text) // 2

    def _compress(self, text: str, max_tokens: int = 200) -> str:
        """用 LLM 压缩长文本为简短摘要"""
        prompt = (
            f"请将以下内容压缩为不超过 {max_tokens} tokens 的摘要，"
            f"保留所有关键信息:\n\n{text[:3000]}"  # 只压缩前 3000 字符
        )
        try:
            # 用轻量模型压缩
            import openai
            response = openai.chat.completions.create(
                model=self.config.compression_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0
            )
            return response.choices[0].message.content or text[:max_tokens * 4]
        except Exception:
            return text[:max_tokens * 4]  # 降级：截断

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """截断文本到指定 token 数"""
        try:
            tokens = self.tokenizer.encode(text)
            return self.tokenizer.decode(tokens[:max_tokens])
        except Exception:
            return text[:max_tokens * 4]
```

## Token 预算分配策略

```python
class TokenBudget:
    """Token 预算管理器"""

    def __init__(self, total_budget: int = 8000):
        self.total = total_budget

    def allocate(self, requirements: dict) -> dict:
        """根据需求分配 Token 预算

        requirements = {
            "system_prompt": 500,    # 固定系统提示
            "tool_descriptions": 0,  # 工具描述(自动计算)
            "context": 0,            # 上下文区(ContextBuilder管理)
            "history": 0,            # 对话历史
            "reserve_for_output": 0, # 模型回复预留
        }
        """
        budget = dict(requirements)

        # 未指定的部分按默认比例分配
        fixed = sum(requirements.values())
        remaining = self.total - fixed

        if "context" not in requirements:
            budget["context"] = int(remaining * 0.50)  # 50%
        if "history" not in requirements:
            budget["history"] = int(remaining * 0.20)  # 20%
        if "reserve_for_output" not in requirements:
            budget["reserve_for_output"] = int(remaining * 0.20)  # 20%
        if "tool_descriptions" not in requirements:
            budget["tool_descriptions"] = remaining - sum(
                v for k, v in budget.items()
                if k not in requirements
            )  # 剩余

        return budget

# 示例分配
budget = TokenBudget(8000).allocate({
    "system_prompt": 500,
    "tool_descriptions": 800,
})
# → {
#     "system_prompt": 500,
#     "tool_descriptions": 800,
#     "context": 3350,
#     "history": 1340,
#     "reserve_for_output": 1340,
# }
```

## 上下文压缩策略对比

| 策略 | Token 节省 | 信息损失 | 延迟 | 最佳场景 |
|------|-----------|---------|------|---------|
| 滑动窗口 | 固定 | 高(旧信息全丢) | 无 | 实时对话 |
| 重要性评分 | 中 | 低 | 低 | 记忆检索 |
| LLM 摘要 | 高 | 中 | 高(1次LLM调用) | 长文档 |
| 相关性过滤 | 中 | 低 | 低 | 检索后过滤 |
| 混合策略 | 高 | 低 | 中 | 通用场景 |

## Agent 集成示例

```python
class ContextAwareAgent:
    """集成 ContextBuilder 的 Agent"""

    def __init__(self, agent, context_builder: ContextBuilder):
        self.agent = agent
        self.context_builder = context_builder

    def run(self, user_input: str) -> str:
        # 构建增强上下文
        enriched_context = self.context_builder.build(
            user_query=user_input,
            conversation_history=self.agent.get_history(),
            system_instructions=self.agent._build_system_prompt(),
            additional_packets=self._collect_extra_context()
        )

        # 用构建好的上下文替换 system message
        messages = [{"role": "system", "content": enriched_context}]
        messages.extend(self.agent.get_history()[-5:])  # 最近5轮
        messages.append({"role": "user", "content": user_input})

        return self.agent.llm.invoke(messages)

    def _collect_extra_context(self) -> list[dict]:
        """收集额外的上下文包——子类可重写"""
        return []
```
