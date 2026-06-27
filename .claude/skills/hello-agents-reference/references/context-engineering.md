# 上下文工程参考

## 四大组件协作

```
Agent.add_message()
  → HistoryManager.append()     # 追加消息（缓存友好）
  → TokenCounter.count_message() # 增量计算 Token
  → _should_compress()?          # O(1) 缓存判断
     → HistoryManager.compress()  # 保留最近N轮 + summary
  → Auto-save? → SessionStore.save()
```

工具执行时：
```
Agent._execute_tool_call()
  → ObservationTruncator.truncate()  # 截断长输出
  → 保存完整输出到 tool-output/
```

## HistoryManager — 历史管理

**核心原则：只追加不编辑（KV Cache 友好）**

```python
class HistoryManager:
    def __init__(self, min_retain_rounds=10, compression_threshold=0.8):
        self._history: List[Message] = []
        self.min_retain_rounds = min_retain_rounds

    def append(self, message: Message) -> None:
        """只追加，不编辑 — 保持 KV Cache 有效"""
        self._history.append(message)

    def compress(self, summary: str) -> None:
        """替换旧历史为 summary，保留最近 N 轮"""
        boundaries = self.find_round_boundaries()  # user 消息索引
        if len(boundaries) > self.min_retain_rounds:
            keep_from = boundaries[-self.min_retain_rounds]
            summary_msg = Message(content=summary, role="summary",
                metadata={"compressed_at": datetime.now().isoformat()})
            self._history = [summary_msg] + self._history[keep_from:]

    def find_round_boundaries(self) -> List[int]:
        """查找每轮起始索引（user 消息位置）"""

    def estimate_rounds(self) -> int:
        """预估完整轮次数（一轮 = 1 user + N 条回复）"""

    def to_dict(self) -> Dict: ...   # 序列化
    def load_from_dict(self, data): ...  # 反序列化
```

**压缩效果**：50 轮对话（5 万 tokens）→ summary(500) + 最近 10 轮(1 万) = 1.05 万（节省 79%）

## Agent 基类的两种压缩策略

```python
class Agent:
    def _should_compress(self) -> bool:
        """O(1) 判断：使用缓存的 _history_token_count"""
        threshold = int(self.config.context_window * self.config.compression_threshold)
        return self._history_token_count > threshold

    def _generate_simple_summary(self, history) -> str:
        """简单摘要（免 LLM 调用）：统计轮次/消息数"""
        rounds = self.history_manager.estimate_rounds()
        return f"此会话包含 {rounds} 轮对话：..."

    def _generate_smart_summary(self, history) -> str:
        """智能摘要（调用轻量 LLM）：提取 5 项关键信息"""
        # 1. 任务目标、2. 关键决策、3. 已完成工作
        # 4. 待处理事项、5. 重要发现
        summary_llm = HelloAgentsLLM(provider="deepseek", model="deepseek-chat")
        # 回退：LLM 失败时使用简单摘要
```

## TokenCounter — Token 计数

**三层降级策略**：
1. tiktoken 精确计算（`encoding_for_model`）
2. 通用编码器（`cl100k_base`）
3. 字符估算（`len(text) // 4`）

```python
class TokenCounter:
    def __init__(self, model="gpt-4"):
        self._encoding = self._get_encoding()  # tiktoken 或 None
        self._cache: Dict[str, int] = {}       # 内容→Token数

    def count_message(self, message: Message) -> int:
        """单条消息 Token（含缓存）"""
        cache_key = f"{message.role}:{message.content}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        tokens = self._count_text(message.content) + 4  # +4=角色开销
        self._cache[cache_key] = tokens
        return tokens

    def count_messages(self, messages: List[Message]) -> int:
        """批量计算（逐个带缓存）"""

    def _count_text(self, text: str) -> int:
        if self._encoding:
            try: return len(self._encoding.encode(text))
            except: pass
        return len(text) // 4  # 降级：1 token ≈ 4 字符
```

## ObservationTruncator — 工具输出截断

**三种截断方向**：
- `head`：保留开头（适合日志、错误信息）
- `tail`：保留结尾（适合实时输出）
- `head_tail`：保留头尾（适合长文件）

```python
class ObservationTruncator:
    def __init__(self, max_lines=2000, max_bytes=51200,
                 truncate_direction="head", output_dir="tool-output"):

    def truncate(self, tool_name, output, metadata=None) -> Dict:
        """返回 {truncated, preview, full_output_path, stats}"""
        if len(lines) <= max_lines and bytes_size <= max_bytes:
            return {"truncated": False, "preview": output, ...}
        truncated_lines = self._truncate_lines(lines)
        # 保存完整输出到 tool-output/tool_<timestamp>_<name>.json
        output_path = self._save_full_output(tool_name, output, metadata)
        return {"truncated": True, "preview": preview, "full_output_path": output_path, ...}
```

## ContextBuilder — GSSC 流水线

**Gather → Select → Structure → Compress** 四步：

```python
class ContextBuilder:
    def build(self, user_query, conversation_history=None,
              system_instructions=None, additional_packets=None) -> str:
        packets = self._gather(...)           # 1. 多源收集
        selected = self._select(packets)       # 2. 筛选排序
        structured = self._structure(selected) # 3. 结构化模板
        return self._compress(structured)       # 4. 预算压缩

    def _select(self, packets, user_query):
        """复合打分：0.7×相关性 + 0.3×新近性（指数衰减 τ=3600s）"""
        # 系统指令固定纳入，其余按 Token 预算填充

    def _structure(self, selected_packets, ...):
        """组织成结构化模板：
        [Role & Policies] → [Task] → [State] → [Evidence] → [Context] → [Output]"""
```

ContextPacket 数据结构：
```python
@dataclass
class ContextPacket:
    content: str
    timestamp: datetime
    metadata: Dict       # {"type": "instructions"|"history"|"tool_result"}
    token_count: int     # 自动计算
    relevance_score: float = 0.0
```

## 会话持久化 — SessionStore

**原子写入保证数据完整性**：

```python
class SessionStore:
    def save(self, agent_config, history, tool_schema_hash,
             read_cache, metadata, session_name=None) -> str:
        """保存会话到 JSON 文件（原子写入：tmp + rename）"""
        session_data = {"session_id": ..., "agent_config": ..., "history": [...],
                        "tool_schema_hash": ..., "read_cache": ..., "metadata": ...}
        temp_path = filepath + ".tmp"
        with open(temp_path, 'w') as f: json.dump(session_data, f)
        os.replace(temp_path, filepath)  # 原子重命名

    def load(self, filepath) -> Dict: ...

    def check_config_consistency(self, saved_config, current_config) -> Dict:
        """检查 LLM 提供商/模型/max_steps 是否一致，返回 warnings 列表"""

    def check_tool_schema_consistency(self, saved_hash, current_hash) -> Dict:
        """比较工具 Schema 哈希，给出恢复建议"""
```

Agent 基类的会话方法：
```python
class Agent:
    def save_session(self, session_name: str) -> str:
        """手动保存：包含 agent_config + history + tool_schema_hash + metadata"""
    def load_session(self, filepath, check_consistency=True) -> None:
        """恢复会话：先检查环境一致性，再恢复 history + read_cache"""
    def list_sessions(self) -> List[Dict]: ...
    def _auto_save(self):  # 静默失败不影响主流程
```
