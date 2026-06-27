# 编码规范与项目结构

## 项目文件组织

```
project/
├── .env                    # API密钥等敏感配置（不提交git）
├── .env.example            # 环境变量模板（可提交）
├── my_llm.py               # 自定义 LLM 客户端
├── my_agent.py             # 自定义 Agent 实现
├── my_tool.py              # 自定义 Tool 实现
├── test_agent.py           # Agent 测试
├── config.json             # 配置文件
└── README.md
```

**命名约定**: 自定义实现用 `my_` 前缀，测试文件用 `test_` 前缀。

## LLM 客户端

### 标准实现

```python
from openai import OpenAI
import os

class HelloAgentsLLM:
    """统一的 LLM 客户端——支持任何 OpenAI 兼容接口"""

    def __init__(self, model=None, apiKey=None, baseUrl=None):
        self.model = model or os.getenv("LLM_MODEL_ID")
        apiKey = apiKey or os.getenv("LLM_API_KEY")
        baseUrl = baseUrl or os.getenv("LLM_BASE_URL")
        if not all([self.model, apiKey, baseUrl]):
            raise ValueError("模型参数缺失，检查 .env 文件")
        self.client = OpenAI(api_key=apiKey, base_url=baseUrl)

    def think(self, messages, temperature=0) -> str:
        """流式调用——适合实时展示"""
        response = self.client.chat.completions.create(
            model=self.model, messages=messages,
            temperature=temperature, stream=True
        )
        return "".join(
            chunk.choices[0].delta.content or ""
            for chunk in response
        )

    def invoke(self, messages, **kwargs) -> str:
        """非流式调用——适合批处理"""
        response = self.client.chat.completions.create(
            model=self.model, messages=messages, **kwargs
        )
        return response.choices[0].message.content
```

### 多 Provider 扩展

```python
class MyLLM(HelloAgentsLLM):
    """支持多模型提供商"""
    PROVIDERS = {
        "modelscope": {
            "base_url": "https://api-inference.modelscope.cn/v1/",
            "env_key": "MODELSCOPE_API_KEY"
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "env_key": "DEEPSEEK_API_KEY"
        }
    }

    def __init__(self, provider="auto", **kwargs):
        if provider in self.PROVIDERS:
            cfg = self.PROVIDERS[provider]
            kwargs.setdefault("baseUrl", cfg["base_url"])
            kwargs.setdefault("apiKey", os.getenv(cfg["env_key"]))
        super().__init__(**kwargs)
```

## Agent 类层次

```
Agent (基类)
├── SimpleAgent      → 简单对话 + 可选工具
├── ReActAgent       → Thought-Action-Observation 循环
├── FunctionCallAgent → 函数调用驱动
└── 自定义 Agent      → 继承基类，重写 run()
```

### 继承模式

```python
class MySimpleAgent(SimpleAgent):
    def __init__(self, name, llm, system_prompt=None, tool_registry=None, **kwargs):
        super().__init__(name, llm, system_prompt)
        self.tool_registry = tool_registry
        self.enable_tool_calling = tool_registry is not None

    def run(self, input_text: str, **kwargs) -> str:
        messages = self._build_messages(input_text)
        response = self.llm.invoke(messages, **kwargs)
        self._update_history(input_text, response)
        return response

    def stream_run(self, input_text: str, **kwargs):
        for chunk in self.llm.think(messages, **kwargs):
            yield chunk
```

## 环境变量 (.env)

```bash
LLM_MODEL_ID=claude-sonnet-4-6
LLM_API_KEY=your-api-key
LLM_BASE_URL=your-base-url
TAVILY_API_KEY=your-tavily-key
LLM_TIMEOUT=60
```

```python
from dotenv import load_dotenv
load_dotenv()  # 自动从 .env 加载
```

## 测试模式

```python
def test_agent():
    load_dotenv()
    llm = HelloAgentsLLM()
    agent = MyAgent(name="测试", llm=llm)
    # 基础功能
    assert agent.run("hello") is not None
    # 工具调用
    assert len(agent.run("计算 1+1")) > 0
    # 错误处理
    assert agent.run("") is not None
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

## 错误处理

```python
# 原则: 所有外部调用 try-catch，返回错误字符串不抛异常
try:
    response = self.llm.invoke(messages)
except Exception as e:
    return f"错误: {e}"

# 优雅降级
try:
    result = primary_search(query)
except Exception:
    try:
        result = fallback_search(query)
    except Exception:
        result = "搜索不可用，请稍后重试"
```

## 类型系统

```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class Message:
    content: str
    role: str
    timestamp: float

@dataclass
class ReasoningStep:
    id: str
    thought: str
    action: str
    observation: Any
    next_step: str
    timestamp: float
    token_usage: int
    metadata: dict
```

## HarnessAgent 目录结构

```
harness_agent/
├── core/              # 核心引擎 (harness.py, state.py)
├── agents/            # Agent 实现 (base.py, react.py, plan_solve.py)
├── tools/             # 工具 (registry.py, mcp_client.py, builtin/)
├── memory/            # 记忆 (working.py, episodic.py, semantic.py)
├── rag/               # RAG (ingestion.py, retrieval.py)
├── multi_agent/       # 多Agent (orchestrator.py, pool.py)
├── protocols/         # 协议 (mcp/, a2a/)
├── reliability/       # 可靠性 (retry.py, circuit_breaker.py)
├── streaming/         # 流式 (events.py)
├── training/          # 训练 (sft.py, grpo.py, reward_functions.py)
├── evaluation/        # 评估 (bfcl.py, gaia.py, llm_judge.py)
├── tracing/           # 追踪 (trace.py)
└── tests/             # 测试 (test_*.py)
```
