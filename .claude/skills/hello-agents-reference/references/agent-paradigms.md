# Agent 范式参考

## 四种范式对比

| 维度 | SimpleAgent | ReActAgent | ReflectionAgent | PlanSolveAgent |
|------|------------|------------|-----------------|----------------|
| **文件** | simple_agent.py | react_agent.py | reflection_agent.py | plan_solve_agent.py |
| **行数** | ~437 | ~1242 | ~454 | ~547 |
| **核心循环** | LLM调用→工具执行→返回 | Thought→Action→Observe→循环→Finish | 执行→反思→优化→迭代 | 规划(Planner)→执行(Executor) |
| **工具调用** | OpenAI FC 多轮 | FC + Thought/Finish 内置工具 | FC 辅助 | FC 辅助(每步) |
| **异步支持** | arun_stream(SSE) | arun + arun_stream(完整) | arun_stream(反思可视化) | arun_stream(阶段展示) |
| **适用场景** | 简单对话、单步工具调用 | 需要多步推理+工具的任务 | 代码生成、文案优化 | 复杂数学、多步骤分析 |
| **复杂度** | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

## SimpleAgent — 对话+Function Calling

**设计特点**：
- `enable_tool_calling` 开关自如切换纯对话/工具模式
- 工具调用通过 OpenAI Function Calling，自动多轮（`max_tool_iterations`）
- 同时提供 `stream_run()` 同步流式和 `arun_stream()` 异步流式（SSE事件）

**核心流程**：
```python
def run(self, input_text, **kwargs):
    messages = self._build_messages(input_text)  # [system, ...history, user]
    if not self.enable_tool_calling:
        return self.llm.invoke(messages).content  # 纯对话

    tool_schemas = self._build_tool_schemas()
    for i in range(self.max_tool_iterations):
        response = self.llm.invoke_with_tools(messages, tools=tool_schemas)
        if not response.tool_calls:
            return response.content  # 结束
        # 执行工具 → 添加 tool role 消息 → 继续循环
        for tc in response.tool_calls:
            arguments = json.loads(tc.arguments)
            result = self._execute_tool_call(tc.name, arguments)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return final_response
```

## ReActAgent — 推理-行动循环（核心范式）

**设计亮点**：
1. **用 Function Calling 替代文本解析**：内置 Thought/Finish 工具通过 FC 调用，解析成功率从 ~85% 提升到 99%+
2. **工具分组并行**：内置工具（Thought/Finish）串行执行，用户工具通过 `asyncio.gather` + `Semaphore` 并行执行
3. **完整的异步生命周期**：5 个钩子（on_start/on_step/on_tool_call/on_finish/on_error）
4. **异常保护**：Ctrl+C 和异常时自动保存会话

**内置工具 Schema**：
```python
# Thought 工具 — 显式推理
{"name": "Thought", "parameters": {"reasoning": {"type": "string"}}}

# Finish 工具 — 结束流程
{"name": "Finish", "parameters": {"answer": {"type": "string"}}}
```

**异步工具并行策略**：
```python
async def _execute_tools_async(self, tool_calls, current_step, on_tool_call):
    builtin_calls = [tc for tc in tool_calls if tc.name in self._builtin_tools]
    user_calls = [tc for tc in tool_calls if tc.name not in self._builtin_tools]

    # 1. 串行执行内置工具（Thought/Finish）
    for tc in builtin_calls:
        result = self._handle_builtin_tool(tc.name, json.loads(tc.arguments))
        if tc.name == "Finish" and result.get("finished"):
            return final_answer  # 立即结束

    # 2. 并行执行用户工具（Semaphore 控制并发数）
    semaphore = asyncio.Semaphore(self.config.max_concurrent_tools)
    async def execute_one(tc):
        async with semaphore:
            tool_response = await tool.arun_with_timing(arguments)
            return (tc.name, tc.id, {"content": tool_response.text})
    user_results = await asyncio.gather(*[execute_one(tc) for tc in user_calls])
```

## ReflectionAgent — 自我反思迭代

**核心结构**：Memory 记忆模块 + 三个核心方法

```python
class Memory:
    """短期记忆：记录 execution/reflection 轨迹"""
    def add_record(self, record_type, content): ...
    def get_trajectory(self) -> str: ...       # 格式化完整轨迹
    def get_last_execution(self) -> str: ...    # 最近执行结果

class ReflectionAgent(Agent):
    def run(self, input_text):
        # 1. 初始执行
        initial = self._execute_task(input_text)
        self.memory.add_record("execution", initial)

        # 2. 迭代循环
        for i in range(self.max_iterations):
            # a. 反思
            feedback = self._reflect_on_result(input_text, initial)
            self.memory.add_record("reflection", feedback)

            # b. 检查停止条件
            if "无需改进" in feedback:
                break

            # c. 优化
            refined = self._refine_result(input_text, initial, feedback)
            self.memory.add_record("execution", refined)

        return self.memory.get_last_execution()
```

**三个核心方法的 Prompt 设计**：
- `_execute_task`: "请完成以下任务：{task}"
- `_reflect_on_result`: "请审查回答质量，指出不足，如已很好请回复'无需改进'"
- `_refine_result`: "请根据反馈意见改进你的回答：原始任务/上一轮/反馈"

## PlanSolveAgent — 规划-执行分离

**结构**：Planner 和 Executor 是两个独立类

```python
class Planner:
    """使用 Function Calling 生成计划（JSON Schema 强约束）"""
    def plan(self, question):
        plan_tool = {"name": "generate_plan", "parameters": {
            "steps": {"type": "array", "items": {"type": "string"}}}}
        response = self.llm.invoke_with_tools(messages, tools=[plan_tool],
            tool_choice={"type": "function", "function": {"name": "generate_plan"}})
        return json.loads(response.tool_calls[0].arguments)["steps"]

class Executor:
    """逐步执行，每步有完整上下文"""
    def execute(self, question, plan):
        for i, step in enumerate(plan):
            context = f"""# 原始问题: {question}
# 完整计划: {format_plan(plan)}
# 历史: {format_history(history)}
# 当前步骤: {step}"""
            result = self._execute_step(context)  # 支持工具调用
            history.append({"step": step, "result": result})
        return final_answer
```

## Agent 工厂函数

```python
def create_agent(agent_type, name, llm, tool_registry=None, config=None, system_prompt=None):
    agent_type = agent_type.lower()
    if agent_type == "react":    return ReActAgent(...)
    if agent_type == "reflection": return ReflectionAgent(...)
    if agent_type == "plan":     return PlanSolveAgent(...)
    if agent_type == "simple":   return SimpleAgent(...)

def default_subagent_factory(agent_type, llm, tool_registry=None, config=None):
    """子代理默认工厂 — 用户可自定义替换"""
    name = f"subagent-{agent_type}"
    subagent = create_agent(agent_type, name, llm, tool_registry, config,
                           system_prompt=_get_system_prompt_for_type(agent_type))
    if hasattr(subagent, 'max_steps'):
        subagent.max_steps = config.subagent_max_steps
    return subagent
```

## 范式选择决策

```python
def select_paradigm(task: dict) -> str:
    """根据任务特征选择 Agent 范式"""
    if task.get("steps", 1) == 1 and not task.get("need_reflection"):
        return "simple"      # 单步对话
    if task.get("need_planning") and task.get("steps", 1) > 3:
        return "plan"        # 多步骤需规划
    if task.get("need_iteration") or task.get("quality_critical"):
        return "reflection"  # 需要迭代优化
    return "react"           # 默认：多步推理+工具
```
