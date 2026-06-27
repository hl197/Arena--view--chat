---
name: agent-builder
description: 在 HarnessAgent 项目中设计和实现 AI Agent 的核心推理范式与编码框架。Use when: (1) 创建新 Agent 或选择推理范式(ReAct/Plan-Solve/Reflection/Hybrid), (2) 设计 Agent 的 Prompt 模板和系统提示词, (3) 编写 Agent 类实现代码, (4) 确定 Agent 架构和开发流程, (5) 编写 Agent 相关代码时参考编码规范和项目结构。
---

# Agent Builder — 核心范式与开发框架

## 概述

本技能覆盖 HarnessAgent 中 Agent 的核心推理范式选择、Prompt 工程、代码实现和项目编码规范。它是构建任何 Agent 的起点——先确定"怎么思考"，再引入工具、记忆、协作等能力。

## 快速决策：选择推理范式

在写任何代码之前，先回答：**这个 Agent 的思考方式是什么样的？**

| 任务特征 | 推荐范式 | 核心循环 | 典型场景 |
|---------|---------|---------|---------|
| 步骤数不确定，需要多步工具调用，每步依赖上一步结果 | **ReAct** | Thought→Action→Observe | 搜索+分析、调试代码、数据查询 |
| 可预先分解为明确的步骤序列，步骤间有清晰依赖 | **Plan-and-Solve** | Plan→Execute(step by step) | 旅行规划、项目分解、报告生成 |
| 需要"先出稿→审查→改进"的迭代打磨 | **Reflection** | Execute→Reflect→Refine | 代码优化、文案润色、方案评审 |
| 复杂任务，需先规划再灵活执行 | **Hybrid(Plan+ReAct)** | Plan→ReAct per step | 多 Agent 编排、长流程自动化 |

### 决策流程图

```
任务分析
├── 可以预判所有步骤？
│   ├── 是 → Plan-and-Solve
│   └── 否 → 需要工具/外部信息？
│       ├── 是 → ReAct
│       └── 否 → 需要迭代改进？
│           ├── 是 → Reflection
│           └── 否 → SimpleAgent（直接对话）
└── 多 Agent 协作？
    └── Hybrid: Plan(分配任务) + ReAct(各Agent执行)
```

## Agent 开发工作流

### Step 1: 确定架构

1. 分析任务特征 → 选择推理范式（参考上方决策表）
2. 列出 Agent 需要的 Tools / Skills
3. 确定是否需要 Memory / RAG / Context
4. 确定是单 Agent 还是多 Agent 编排

### Step 2: 设计 Prompt 模板

Prompt 是 Agent 的"大脑"。每种范式有固定的 Prompt 结构：

**ReAct Prompt 结构：**
```
[系统角色定义]
[可用工具列表：名称 + 描述 + 参数格式]
[输出格式约束：Thought/Action/Observation 格式]
---
当前任务: {question}
执行历史: {history}
```

关键设计要点：
- 工具描述要包含：名称、用途、参数示例、返回值格式
- Action 格式必须明确：`tool_name[input]` 或 `Finish[最终答案]`
- 历史记录追加方式：Observation 后紧跟下一轮 Thought

**Plan-Solve Prompt 结构：**
```
Planner Prompt:
  将问题分解为可执行步骤，输出 Python list: ["步骤1", "步骤2", ...]
  Question: {question}

Executor Prompt:
  原始问题: {question}
  完整计划: {plan}
  已完成步骤及结果: {history}
  当前步骤: {current_step}
  请执行当前步骤并给出结果
```

**Reflection Prompt 三层结构：**
```
INITIAL_PROMPT:  纯任务描述 → 直接输出结果
REFLECT_PROMPT:  原始任务 + 待审查内容 → 找出问题和改进点
REFINE_PROMPT:   原始任务 + 上一轮结果 + 反馈意见 → 改进后输出
```

### Step 3: 实现 Agent 类

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ReasoningStep:
    """HarnessAgent 的核心数据结构"""
    id: str
    thought: str          # 推理过程
    action: str           # 执行的动作
    observation: str      # 观察到的结果
    next_step: str        # 下一步决策
    timestamp: float
    token_usage: int
    metadata: dict

class MyAgent:
    """Agent 实现模板"""
    def __init__(self, name: str, llm, tool_registry=None, **kwargs):
        self.name = name
        self.llm = llm
        self.tool_registry = tool_registry
        self._history: List[dict] = []
        self.max_steps = kwargs.get("max_steps", 10)

    def run(self, input_text: str, **kwargs) -> str:
        """核心运行方法——子类必须重写"""
        raise NotImplementedError

    def add_tool(self, tool):
        """动态添加工具"""
        if not self.tool_registry:
            from hello_agents.tools import ToolRegistry
            self.tool_registry = ToolRegistry()
        self.tool_registry.register_tool(tool)

    def get_history(self) -> list:
        """获取对话历史（不含系统提示）"""
        return [{"role": m["role"], "content": m["content"]} for m in self._history]

    def _build_messages(self, input_text: str) -> list:
        """构建发送给 LLM 的消息列表"""
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        messages.extend(self._history)
        messages.append({"role": "user", "content": input_text})
        return messages

    def _build_system_prompt(self) -> str:
        """构建系统提示词——子类重写以定制角色和行为"""
        return "你是一个智能助手。"
```

### Step 4: 编写测试

```python
def test_my_agent():
    """每个 Agent 至少覆盖：基础功能、工具调用、错误处理"""
    from dotenv import load_dotenv
    load_dotenv()

    llm = HelloAgentsLLM()
    agent = MyAgent(name="测试Agent", llm=llm)

    # 基础功能测试
    result = agent.run("简单问题")
    assert result is not None and len(result) > 0

    # 工具调用测试（如有工具）
    if agent.tool_registry:
        result = agent.run("需要用到工具的问题")
        assert "tool" in result.lower() or len(agent.get_history()) > 1

    # 错误处理测试
    result = agent.run("")
    assert result is not None  # 不应崩溃
```

### Step 5: 集成到 Harness Engine

```python
# 在 Harness Engine 中注册
engine.register_agent("my_agent", MyAgent(...))

# 通过统一接口调用
trace = engine.run("用户请求")
# trace.steps 包含完整的 Think→Act→Observe→Reflect 记录
```

## 核心实现模式

### 工具调用解析

Agent 必须能从 LLM 输出中可靠地提取工具调用指令：

```python
import re

def parse_tool_calls(self, text: str) -> list[dict]:
    """解析 LLM 输出中的工具调用标记

    支持两种格式：
    1. ReAct 风格: tool_name[input]
    2. 标记风格:   [TOOL_CALL:name:params]
    """
    calls = []

    # 格式1: tool_name[input]
    for match in re.finditer(r'(\w+)\[(.*?)\]', text):
        calls.append({
            'tool_name': match.group(1),
            'parameters': match.group(2),
            'format': 'react'
        })

    # 格式2: [TOOL_CALL:name:params]
    for match in re.finditer(r'\[TOOL_CALL:([^:]+):([^\]]+)\]', text):
        calls.append({
            'tool_name': match.group(1).strip(),
            'parameters': match.group(2).strip(),
            'format': 'marker'
        })

    return calls
```

### 多轮工具调用循环

```python
def _run_with_tools(self, messages: list, max_iterations: int = 5) -> str:
    """执行多轮工具调用直到 Agent 给出最终答案"""
    for iteration in range(max_iterations):
        response = self.llm.invoke(messages)
        tool_calls = self.parse_tool_calls(response)

        if not tool_calls:
            # 本轮无工具调用 → 判定为最终回答
            return response

        # 执行所有工具调用
        tool_results = []
        for call in tool_calls:
            try:
                result = self.tool_registry.execute_tool(
                    call['tool_name'], call['parameters']
                )
            except Exception as e:
                result = f"工具执行错误: {e}"
            tool_results.append(f"[{call['tool_name']}] {result}")

        # 将工具结果注入对话
        feedback = "\n".join(tool_results)
        messages.append({
            "role": "user",
            "content": f"工具执行结果:\n{feedback}\n\n请继续分析或给出最终答案。"
        })

    # 超过最大轮次，强制要求最终回答
    messages.append({
        "role": "user",
        "content": "已达到最大工具调用次数，请基于已有信息直接给出答案。"
    })
    return self.llm.invoke(messages)
```

### 循环检测与干预

```python
def _detect_loop(self, recent_actions: list[str], threshold: int = 3) -> bool:
    """检测 Agent 是否陷入重复调用循环"""
    if len(recent_actions) < threshold:
        return False
    # 检查最近 N 次调用是否高度相似
    last_n = recent_actions[-threshold:]
    return len(set(last_n)) == 1  # 全部相同 = 死循环
```

## HarnessAgent 架构对应

本技能覆盖六层模型中的**能力层**核心：

```
Harness Engine (编排层)
    ↓ Think → Act → Observe → Reflect
能力层:
├── Skills (本技能)     → Agent 推理范式 + Prompt 模板
├── Tools/MCP           → 见 agent-tools 技能
├── Memory/RAG/Context  → 见 agent-memory 技能
├── Multi-Agent         → 见 multi-agent 技能
└── Training            → 见 agent-training 技能
```

### HarnessEngine 核心循环

```python
class HarnessEngine:
    def run(self, task: str) -> AgentTrace:
        trace = AgentTrace(root_task=task)
        while not trace.is_complete:
            step = ReasoningStep(id=generate_id(), timestamp=now())

            # Think: 构建上下文 → LLM 推理 → 决定行动
            step.thought, step.action = self._think(task, trace)

            # Act: 执行 Tool / Skill / SubAgent
            step.observation = self._act(step.action)

            # Observe: 解析结果，更新状态
            self._update_state(step)

            # Reflect: 评估进展 → continue / adjust / finish
            step.next_step = self._reflect(step, trace)
            trace.add_step(step)

            if step.next_step == "FINISH":
                trace.is_complete = True
        return trace
```

## 编码规范速查

详见 [coding-conventions.md](references/coding-conventions.md)。核心要点：

### 命名约定
- 自定义实现用 `my_` 前缀，测试用 `test_` 前缀
- 核心模块: `harness_engine.py`, `tool_registry.py`
- Agent 实现: `react_agent.py`, `plan_solve_agent.py`
- HarnessAgent 模块目录: `core/`, `agents/`, `tools/`, `memory/`, `multi_agent/`, `protocols/`, `reliability/`, `streaming/`

### LLM 客户端
- 统一 `OpenAI` 兼容接口，支持 `think()`（流式）和 `invoke()`（非流式）
- 多 Provider 通过继承扩展，环境变量管理密钥

### 错误处理
- 所有外部调用 try-catch
- 返回错误字符串而非抛出异常
- 优雅降级：主方案失败 → 备选方案 → 兜底策略

### 日志
- Emoji 前缀：✅成功 🔧工具 🤖处理中 🧠LLM调用 ❌错误 🎉完成 📝统计

### 类型系统
- 使用 `@dataclass` + 类型提示（`Optional`, `List`, `Dict`）
- 核心数据结构: `Message`, `ReasoningStep`, `AgentTrace`

## Prompt 工程指南

### 系统提示词设计原则

1. **角色明确**: "你是一个[角色]，负责[职责]"
2. **能力边界**: 明确告知 Agent 有什么工具、不能做什么
3. **输出约束**: 指定格式（JSON/Markdown/纯文本）、长度、语言
4. **行为准则**: 步骤优先级、出错时的行为、不确定时的行为

### 示例：完整的 Agent 系统提示词

```
你是 HarnessAgent 平台的代码分析专家，负责审查代码质量和安全性。

## 可用工具
- search_code[query]: 搜索代码库
- read_file[path]: 读取文件内容
- run_tests[module]: 运行测试套件

## 行为准则
1. 先理解代码结构，再深入细节
2. 发现问题时给出具体的行号和修改建议
3. 不确定时明确说明，不要猜测
4. 始终以 JSON 格式输出分析结果

## 输出格式
{
  "summary": "一句话总结",
  "issues": [{"file": "...", "line": 0, "severity": "high|medium|low", "description": "...", "fix": "..."}],
  "score": 0-100
}
```

## 参考资源

| 文件 | 内容 | 何时查阅 |
|------|------|---------|
| [agent-patterns.md](references/agent-patterns.md) | ReAct/Plan-Solve/Reflection/Hybrid 完整实现 | 实现具体推理范式时 |
| [coding-conventions.md](references/coding-conventions.md) | LLM客户端、Agent类层次、项目结构、测试规范 | 编写代码时 |

> 📌 本技能覆盖 Hello Agent 教程 Ch1,4,7 及全章节编码规范。构建 Agent 时，还应参考其他 4 个专精技能：agent-tools（工具系统）、agent-memory（记忆系统）、multi-agent（多智能体）、agent-training（训练评估）。
