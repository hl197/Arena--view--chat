# 可观测性参考

## TraceLogger — 双格式追踪记录器

**输出格式**：
- **JSONL**：流式追加，机器可读，支持 `jq` 分析
- **HTML**：增量渲染，人类可读，内置交互式统计面板（Token/工具/错误/时长）

```python
class TraceLogger:
    def __init__(self, output_dir="memory/traces", sanitize=True,
                 html_include_raw_response=False):
        self.session_id = self._generate_session_id()  # s-YYYYMMDD-HHMMSS-xxxx
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 双文件流式写入
        self.jsonl_path = self.output_dir / f"trace-{self.session_id}.jsonl"
        self.html_path = self.output_dir / f"trace-{self.session_id}.html"
        self.jsonl_file = open(self.jsonl_path, 'w', encoding='utf-8')
        self.html_file = open(self.html_path, 'w', encoding='utf-8')

        self._write_html_header()  # 写入 HTML/CSS
        self._events: List[Dict] = []  # 事件缓存（用于统计）

    def log_event(self, event: str, payload: Dict, step: Optional[int] = None):
        """记录事件（流式+增量）"""
        event_obj = {"ts": datetime.now().isoformat(), "session_id": self.session_id,
                     "step": step, "event": event, "payload": payload}
        if self.sanitize:
            event_obj = self._sanitize_event(event_obj)  # API Key/路径脱敏
        self._events.append(event_obj)                    # 缓存
        self.jsonl_file.write(json.dumps(event_obj, ensure_ascii=False) + "\n")
        self.jsonl_file.flush()                           # 立即刷盘
        self._write_html_event(event_obj)                 # 增量 HTML

    def finalize(self):
        """生成最终 HTML 并关闭文件"""
        stats = self._compute_stats()
        self._write_html_footer(stats)  # 统计面板 + 脚本
        self.jsonl_file.close()
        self.html_file.close()
```

## 事件类型

```python
# 会话事件
"session_start"     # Agent 启动（agent_name, agent_type, config）
"session_end"       # Agent 结束（duration, total_steps, final_answer, status）
"message_written"   # 消息写入历史（role, content）

# 模型调用事件
"model_output"      # LLM 输出（content, tool_calls count, usage）

# 工具调用事件
"tool_call"         # 工具调用（tool_name, tool_call_id, args）
"tool_result"       # 工具结果（tool_name, tool_call_id, result）

# 错误事件
"error"             # 错误（error_type, message, stacktrace）
"hook_timeout"      # 钩子超时（event_type, timeout）
"hook_error"        # 钩子异常（event_type, error）
```

## 统计数据自动计算

```python
def _compute_stats(self) -> Dict:
    return {
        "total_steps": max_step,
        "total_tokens": sum(usage.total_tokens),
        "total_cost": sum(usage.cost),
        "tool_calls": {"Read": 5, "Write": 2},  # {tool_name: count}
        "errors": [{"step": 3, "type": "LLM_ERROR", "message": "..."}],
        "duration_seconds": session_end - session_start,
        "model_calls": count
    }
```

## 敏感信息脱敏规则

```python
def _sanitize_value(self, value: Any) -> Any:
    """递归脱敏：字符串/字典/列表"""
    if isinstance(value, str):
        value = re.sub(r'sk-[a-zA-Z0-9]+', 'sk-***', value)     # API Key
        value = re.sub(r'Bearer\s+[a-zA-Z0-9_\-]+', 'Bearer ***', value)  # Token
        value = re.sub(r'(/Users/|/home/|C:\\Users\\)[^/\\]+', r'\1***', value)  # 路径
        return value
    elif isinstance(value, dict):
        return {k: self._sanitize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [self._sanitize_value(item) for item in value]
    return value
```

## HTML Trace 界面

- 深色主题（`#1a1a1a` 背景，`#4af626` 绿色高亮）
- 统计面板：总步数、总 Token、总成本、会话时长、模型调用次数
- 工具调用统计表（按次数降序）
- 错误列表（step + type + message）
- 可折叠事件详情（点击展开/收起 JSON）
- 颜色编码：tool_call(绿色边框)、tool_result(金色)、error(红色)、model_output(蓝色)

## 上下文管理器支持

```python
# 自动 finalize（即使发生异常）
with TraceLogger(output_dir="logs") as logger:
    logger.log_event("session_start", {"agent_name": "test"})
    # ... Agent 执行 ...
    # 异常时自动记录 error 事件 + finalize
```

## Agent 基类中的集成

```python
class Agent:
    def __init__(self, ...):
        self.trace_logger: Optional[TraceLogger] = None
        if self.config.trace_enabled:
            self.trace_logger = TraceLogger(
                output_dir=self.config.trace_dir,
                sanitize=self.config.trace_sanitize,
                html_include_raw_response=self.config.trace_html_include_raw_response)
            self.trace_logger.log_event("session_start", {...})

    # 在各个 Agent 的 run() 方法中
    if self.trace_logger:
        self.trace_logger.log_event("tool_call", {...}, step=current_step)
        self.trace_logger.log_event("tool_result", {...}, step=current_step)
        self.trace_logger.log_event("session_end", {...})
        self.trace_logger.finalize()
```

## 流式输出系统

```python
class StreamEventType(Enum):
    AGENT_START = "agent_start"         # Agent 开始
    AGENT_FINISH = "agent_finish"       # Agent 完成
    STEP_START = "step_start"           # 步骤开始
    STEP_FINISH = "step_finish"         # 步骤完成
    TOOL_CALL_START = "tool_call_start"  # 工具调用开始
    TOOL_CALL_FINISH = "tool_call_finish" # 工具调用完成
    LLM_CHUNK = "llm_chunk"            # LLM 文本块
    THINKING = "thinking"              # 思考过程
    ERROR = "error"                    # 错误

@dataclass
class StreamEvent:
    type: StreamEventType
    timestamp: float
    agent_name: str
    data: Dict[str, Any]

    def to_sse(self) -> str:
        """转为 SSE 格式（event: <type>\ndata: <json>\n\n）"""
```

## 生命周期事件系统

```python
class EventType(Enum):
    AGENT_START, AGENT_FINISH, AGENT_ERROR
    STEP_START, STEP_FINISH
    LLM_START, LLM_CHUNK, LLM_FINISH
    TOOL_CALL, TOOL_RESULT, TOOL_ERROR
    THINKING, REFLECTION, PLAN

@dataclass
class AgentEvent:
    type: EventType
    timestamp: float
    agent_name: str
    data: Dict[str, Any] = {}

LifecycleHook = Optional[Callable[[AgentEvent], Awaitable[None]]]
# 使用：agent.arun("task", on_start=my_hook, on_step=my_hook, on_finish=my_hook)
```
