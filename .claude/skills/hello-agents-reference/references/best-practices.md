# 编码规范与最佳实践参考

## 项目文件组织

```
my-agent/
├── .env / .env.example / .gitignore
├── pyproject.toml / setup.py / requirements.txt / README.md
├── hello_agents/
│   ├── core/       # agent, llm, config, message, lifecycle, session_store, streaming
│   ├── agents/     # simple, react, reflection, plan_solve, factory
│   ├── tools/      # base, registry, response, errors, circuit_breaker, tool_filter, builtin/
│   ├── context/    # history, token_counter, truncator, builder
│   ├── observability/  # trace_logger
│   └── skills/     # loader
├── docs/ / examples/ / tests/ / skills/
```

## 错误处理三原则

```python
# 1. 所有外部调用 try-catch，返回错误字符串而非抛异常
try:
    response = self.llm.invoke(messages)
except Exception as e:
    return f"错误: {e}"

# 2. 优雅降级（多级回退）
try:
    result = primary_search(query)
except Exception:
    try: result = fallback_search(query)
    except Exception: result = "搜索不可用"

# 3. 工具返回 ToolResponse，不抛异常
def run(self, parameters) -> ToolResponse:
    if not parameters.get("path"):
        return ToolResponse.error(code=ToolErrorCode.INVALID_PARAM, ...)
    try: return ToolResponse.success(text="完成", data={...})
    except FileNotFoundError: return ToolResponse.error(code=ToolErrorCode.NOT_FOUND, ...)
    except Exception as e: return ToolResponse.error(code=ToolErrorCode.EXECUTION_ERROR, ...)
```

## 日志规范

```python
print(f"✅ Agent 初始化完成")     # 成功
print(f"🔧 工具已注册")          # 工具
print(f"🤖 {name} 处理中...")    # 处理中
print(f"🧠 调用 {model}...")    # LLM
print(f"❌ 失败: {e}")          # 错误
print(f"🎉 任务完成")           # 完成
print(f"📝 统计: {n}条")        # 统计
```

## 工具开发最佳实践

1. **参数验证在前**：`run()` 开头验证所有必需参数
2. **结构化返回**：`ToolResponse.success(text, data={...}, stats={...})`
3. **使用 run_with_timing()**：让框架自动添加时间统计
4. **异步 I/O 实现 arun()**：工具涉及网络/IO 时覆盖异步方法
5. **工具无状态**：不引用 Agent 上下文，通过参数传递

## Agent 开发模式

```python
# 继承模式
class MyAgent(SimpleAgent):
    def __init__(self, name, llm, ...):
        super().__init__(name, llm, ...)

# 工厂函数
agent = create_agent("react", "my_agent", llm, tool_registry=registry)

# 配置驱动
config = Config(trace_enabled=True, session_enabled=True,
    compression_threshold=0.8, min_retain_rounds=10,
    subagent_enabled=True, skills_enabled=True)
```

## 环境变量

```bash
LLM_MODEL_ID=your-model-name
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=your-api-base-url
LLM_TIMEOUT=60
```

## 类型系统

```python
@dataclass
class Message:
    content: str
    role: str       # "user"|"assistant"|"system"|"tool"|"summary"
    timestamp: float
    metadata: Optional[Dict] = None

@dataclass
class ToolParameter:
    name: str
    type: str       # "string"|"integer"|"number"|"boolean"|"array"|"object"
    description: str
    required: bool = True
    default: Any = None
```

## 原子写入模式

```python
# 所有持久化：先写 .tmp 再原子重命名
temp_path = filepath + ".tmp"
with open(temp_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
os.replace(temp_path, filepath)
```

## 缓存友好设计

1. **只追加不编辑**：HistoryManager 只 append
2. **增量 Token 计数**：TokenCounter 缓存+增量
3. **渐进式加载**：SkillLoader 三层机制

## 会话恢复环境检查

恢复时自动检测：LLM 提供商/模型/max_steps 变化、工具 Schema 哈希变化

## pyproject.toml 参考

```toml
[project]
name = "hello-agents"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = [
    "openai>=1.0.0,<2.0.0",
    "pydantic>=2.0.0,<3.0.0",
    "tiktoken>=0.5.0",
    "pyyaml>=6.0.0",
]
[project.optional-dependencies]
gemini = ["google-genai>=1.0.0"]
anthropic = ["anthropic>=0.20.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.black]
line-length = 88
target-version = ['py310']
```
