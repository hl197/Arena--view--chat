# HelloAgents 架构设计参考

## 完整项目目录结构

```
hello-agents/
├── hello_agents/                    # 主包
│   ├── __init__.py                  # 公开 API（HelloAgentsLLM, ReActAgent, ToolRegistry...）
│   ├── version.py                   # __version__, __author__
│   ├── core/                        # 核心组件层
│   │   ├── agent.py                 # Agent 抽象基类（1274行，集成10项能力）
│   │   ├── llm.py                   # HelloAgentsLLM 统一接口
│   │   ├── llm_adapters.py          # BaseLLMAdapter → OpenAI/Anthropic/Gemini (886行)
│   │   ├── llm_response.py          # LLMResponse, LLMToolResponse, ToolCall, StreamStats
│   │   ├── config.py                # Config 配置类（Pydantic, 40+字段）
│   │   ├── message.py               # Message 消息类（Pydantic）
│   │   ├── lifecycle.py             # AgentEvent, EventType, LifecycleHook, ExecutionContext
│   │   ├── session_store.py         # SessionStore 会话持久化(原子写入)
│   │   ├── streaming.py             # StreamEvent, StreamEventType, StreamBuffer, SSE
│   │   └── exceptions.py            # HelloAgentsException 和子类
│   ├── agents/                      # Agent 实现层
│   │   ├── simple_agent.py          # SimpleAgent（对话+可选Function Calling）
│   │   ├── react_agent.py           # ReActAgent（内置Thought/Finish+工具并行）
│   │   ├── reflection_agent.py      # ReflectionAgent（执行→反思→优化循环）
│   │   ├── plan_solve_agent.py      # PlanSolveAgent（Planner+Executor分离）
│   │   └── factory.py               # create_agent(), default_subagent_factory()
│   ├── tools/                       # 工具系统层
│   │   ├── base.py                  # Tool抽象基类, ToolParameter, tool_action装饰器
│   │   ├── registry.py              # ToolRegistry（Tool+Function双模式）
│   │   ├── response.py              # ToolResponse(ToolStatus.SUCCESS/PARTIAL/ERROR)
│   │   ├── errors.py                # ToolErrorCode（15种标准错误码）
│   │   ├── circuit_breaker.py       # CircuitBreaker（关闭→熔断→恢复状态机）
│   │   ├── tool_filter.py           # ToolFilter(ReadOnly/FullAccess/Custom)
│   │   └── builtin/                 # 内置工具
│   │       ├── calculator.py        # CalculatorTool（AST安全计算）
│   │       ├── file_tools.py        # ReadTool/WriteTool/EditTool/MultiEditTool
│   │       ├── task_tool.py         # TaskTool（子代理调用）
│   │       ├── skill_tool.py        # SkillTool（Skills加载）
│   │       ├── todowrite_tool.py    # TodoWriteTool（任务进度管理）
│   │       └── devlog_tool.py       # DevLogTool（开发日志）
│   ├── context/                     # 上下文工程层
│   │   ├── history.py               # HistoryManager（追加+压缩+轮次检测）
│   │   ├── token_counter.py         # TokenCounter（tiktoken+缓存+降级）
│   │   ├── truncator.py             # ObservationTruncator（head/tail/head_tail）
│   │   └── builder.py               # ContextBuilder（GSSC流水线）
│   ├── observability/               # 可观测性层
│   │   └── trace_logger.py          # TraceLogger（JSONL+HTML双格式）
│   └── skills/                      # Skills系统
│       └── loader.py                # SkillLoader（渐进式加载三层机制）
├── docs/                            # 16篇文档指南
├── examples/                        # 17个示例（含6个custom_tools示例）
├── tests/                           # 18个测试文件
├── skills/                          # 16个内置Skills（LLM/pdf/docx/pptx/xlsx/...）
├── pyproject.toml                   # 项目配置（Python 3.10+）
├── .env.example                     # 环境变量模板
└── README.md
```

## 四层分层架构

```
┌─────────────────────────────────┐
│   应用层 (用户代码/示例/Web)      │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│   Agent实现层                    │
│   Simple|ReAct|Reflection|Plan   │  ← 每种范式 ~400-1200行
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│   Agent基类层                    │
│   Agent(ABC) 集成10项能力:       │
│   HistoryManager, TokenCounter,  │  ← 1274行，核心集成点
│   Truncator, TraceLogger,        │
│   SkillLoader, SessionStore,     │
│   CircuitBreaker, TaskTool,      │
│   TodoWrite, DevLog              │
└──────┬───────┬───────┬──────────┘
       │       │       │
┌──────▼──┐ ┌──▼──────┐ ┌▼──────────┐
│工具系统  │ │上下文工程│ │可观测性    │
│ToolBase │ │History  │ │TraceLogger│
│ToolReg  │ │TokenCnt │ │           │
│Circuit  │ │Truncator│ │           │
└────┬────┘ └─────────┘ └───────────┘
     │
     └────────┬──────────┐
              │          │
        ┌─────▼────┐ ┌──▼───────┐
        │ LLM集成  │ │Skills系统│
        │ Adapters │ │Loader    │
        └─────┬────┘ └──────────┘
              │
        ┌─────▼────┐
        │ 底层库   │
        │ OpenAI等 │
        └──────────┘
```

## Agent 基类集成能力详解

`Agent.__init__()` 在初始化时自动组装 10 项能力：

```python
class Agent(ABC):
    def __init__(self, name, llm, system_prompt=None, config=None, tool_registry=None):
        # 1. 基础属性
        self.name, self.llm, self.system_prompt = name, llm, system_prompt
        self.config = config or Config()
        self.tool_registry = tool_registry

        # 2. 上下文工程组件
        self.history_manager = HistoryManager(
            min_retain_rounds=config.min_retain_rounds,
            compression_threshold=config.compression_threshold)
        self.truncator = ObservationTruncator(
            max_lines=config.tool_output_max_lines,
            max_bytes=config.tool_output_max_bytes)
        self.token_counter = TokenCounter(model=llm.model)

        # 3. 可观测性
        if config.trace_enabled:
            self.trace_logger = TraceLogger(output_dir=config.trace_dir)

        # 4. Skills 知识外化
        if config.skills_enabled:
            self.skill_loader = SkillLoader(skills_dir=Path(config.skills_dir))
            if config.skills_auto_register and tool_registry:
                tool_registry.register_tool(SkillTool(skill_loader=self.skill_loader))

        # 5. 会话持久化
        if config.session_enabled:
            self.session_store = SessionStore(session_dir=config.session_dir)

        # 6. 子代理机制（自动注册 TaskTool）
        if config.subagent_enabled and tool_registry:
            self._register_task_tool()

        # 7. TodoWrite 进度管理
        if config.todowrite_enabled and tool_registry:
            self._register_todowrite_tool()

        # 8. DevLog 开发日志
        if config.devlog_enabled and tool_registry:
            self._register_devlog_tool()
```

## 核心数据流

### Agent.run() 主循环

```
用户输入
  → _build_messages() → [system, ...history, user_input]
  → llm.invoke_with_tools(messages, tool_schemas)
  → LLMToolResponse {content, tool_calls: [ToolCall]}
  → 对每个 tool_call:
       → json.loads(tool_call.arguments)
       → _execute_tool_call(name, arguments)
       → ToolResponse {status, text, data, error_info, stats}
       → 添加到 messages 为 tool role
  → 继续循环直到:
       - 没有 tool_calls → 返回 content
       - Finish 工具调用 → 返回 answer
       - 达到 max_steps → 超时返回
  → add_message(user) + add_message(assistant)
  → 返回最终答案
```

### 工具调用执行链

```
Agent._execute_tool_call(name, arguments)
  → ToolRegistry.execute_tool(name, input_text)
     → CircuitBreaker.is_open(name)? → TOOL_CIRCUIT_OPEN
     → Tool.run_with_timing(typed_arguments)
        → Tool.run(parameters) → ToolResponse
        → 自动添加 time_ms 到 stats
     → CircuitBreaker.record_result(name, response)
     → 返回 ToolResponse
  → 根据 ToolStatus 添加前缀:
     SUCCESS → response.text
     PARTIAL → "⚠️ 部分成功: {text}"
     ERROR → "❌ 错误 [{code}]: {message}"
```

### 历史压缩流程

```
add_message(msg)
  → history_manager.append(msg)
  → token_counter.count_message(msg) 增量更新
  → _should_compress()? (O(1) 缓存判断)
     → _compress_history()
        → enable_smart_compression?
           YES → _generate_smart_summary(LLM)
           NO  → _generate_simple_summary(统计)
        → history_manager.compress(summary)
           → find_round_boundaries()
           → 保留最近 min_retain_rounds 轮
           → 旧历史替换为 summary 消息
        → 重新计算 Token 数
  → auto_save_enabled? → _auto_save()
```

## Config 配置项全览

```python
class Config(BaseModel):
    # LLM
    default_model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    # 上下文工程
    context_window: int = 128000
    compression_threshold: float = 0.8    # 80%触发压缩
    min_retain_rounds: int = 10
    enable_smart_compression: bool = False

    # 智能摘要
    summary_llm_provider: str = "deepseek"
    summary_llm_model: str = "deepseek-chat"
    summary_max_tokens: int = 800

    # 工具输出截断
    tool_output_max_lines: int = 2000
    tool_output_max_bytes: int = 51200    # 50KB
    tool_output_truncate_direction: str = "head"

    # 可观测性
    trace_enabled: bool = True
    trace_dir: str = "memory/traces"

    # Skills
    skills_enabled: bool = True
    skills_dir: str = "skills"
    skills_auto_register: bool = True

    # 熔断器
    circuit_enabled: bool = True
    circuit_failure_threshold: int = 3
    circuit_recovery_timeout: int = 300    # 5分钟

    # 会话持久化
    session_enabled: bool = True
    session_dir: str = "memory/sessions"
    auto_save_enabled: bool = False
    auto_save_interval: int = 10

    # 子代理
    subagent_enabled: bool = True
    subagent_max_steps: int = 15
    subagent_use_light_llm: bool = False

    # 异步/流式
    async_enabled: bool = True
    max_concurrent_tools: int = 3
    hook_timeout_seconds: float = 5.0
    stream_enabled: bool = True
```
