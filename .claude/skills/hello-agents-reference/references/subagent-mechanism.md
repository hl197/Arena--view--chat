# 子代理机制参考

## 核心能力

1. **上下文隔离**：子代理使用独立历史，执行后自动恢复主 Agent 状态
2. **工具过滤**：ReadOnlyFilter（只读）/ FullAccessFilter（排除危险）/ CustomFilter（自定义）
3. **摘要返回**：子代理结果以结构化摘要返回，不污染主上下文
4. **成本优化**：子任务可配置轻量模型（节省 60-70%）
5. **零配置**：`Config(subagent_enabled=True)` 自动注册 TaskTool

## Agent.run_as_subagent() — 上下文隔离执行

```python
class Agent:
    def run_as_subagent(self, task, tool_filter=None, return_summary=True,
                        max_steps_override=None) -> Dict[str, Any]:
        """作为子代理运行（上下文隔离模式）"""
        # 1. 保存当前状态
        original_history = self.history_manager.get_history().copy()
        original_tools = None
        original_max_steps = None

        # 2. 创建隔离的新历史
        self.history_manager.clear()

        # 3. 应用工具过滤（如果提供）
        if tool_filter and self.tool_registry:
            original_tools = self._apply_tool_filter(tool_filter)

        # 4. 覆盖最大步数
        if max_steps_override is not None:
            original_max_steps = self.max_steps
            self.max_steps = max_steps_override

        # 5. 执行任务
        try:
            result = self.run(task)
            success = True
        except Exception as e:
            error_msg = str(e)
            success = False
        finally:
            duration = time.time() - start_time

            # 6. 收集元数据
            metadata = {
                "steps": len([m for m in history if m.role == "assistant"]),
                "tokens": sum(len(m.content) for m in history) // 4,
                "duration_seconds": round(duration, 2),
                "tools_used": extract_tools_from_history(history)
            }

            # 7. 生成摘要
            if return_summary:
                summary = f"任务: {task}\n结果: {result[:500]}\n步数: {metadata['steps']}"
            else:
                summary = result

            # 8. 恢复原始状态
            self.history_manager.clear()
            for msg in original_history:
                self.history_manager.append(msg)
            self._restore_tools(original_tools)
            self.max_steps = original_max_steps

        return {"success": success, "summary": summary, "metadata": metadata}
```

## TaskTool — 通过工具调用的子代理

```python
class TaskTool(Tool):
    """参数：
    - task: 子任务描述
    - agent_type: "react"|"reflection"|"plan"|"simple"
    - tool_filter: "readonly"|"full"|"none"
    - max_steps: 最大步数（覆盖默认配置）
    """
    def __init__(self, agent_factory, tool_registry=None, config=None):
        self.agent_factory = agent_factory  # Callable[[str], Agent]

    def run(self, parameters) -> ToolResponse:
        subagent = self.agent_factory(agent_type)  # 工厂创建
        tool_filter = self._create_tool_filter(tool_filter_type)
        result = subagent.run_as_subagent(
            task=task, tool_filter=tool_filter,
            return_summary=True, max_steps_override=max_steps)
        # 返回标准 ToolResponse
```

## Agent 基类自动注册 TaskTool

```python
class Agent:
    def _register_task_tool(self):
        def agent_factory(agent_type: str) -> Agent:
            # 轻量模型（如果启用）或主模型
            llm = self._create_light_llm() if self.config.subagent_use_light_llm else self.llm
            return default_subagent_factory(
                agent_type=agent_type, llm=llm,
                tool_registry=self.tool_registry, config=self.config)
        task_tool = TaskTool(
            agent_factory=agent_factory,
            tool_registry=self.tool_registry, config=self.config)
        self.tool_registry.register_tool(task_tool)
```

## 自定义子代理工厂（成本优化示例）

```python
def my_agent_factory(agent_type: str):
    if agent_type in ["react", "plan"]:
        llm = HelloAgentsLLM(provider="deepseek", model="deepseek-chat")  # 轻量
    else:
        llm = HelloAgentsLLM(provider="openai", model="gpt-4")  # 主模型
    return default_subagent_factory(
        agent_type=agent_type, llm=llm,
        tool_registry=registry, config=Config(subagent_max_steps=10))

# 成本对比：
# 全部 GPT-4: $30/1M tokens
# 30% GPT-4 + 70% DeepSeek: ~$9.7/1M tokens → 节省 68%
```

## 工具过滤的临时应用与恢复

```python
class Agent:
    def _apply_tool_filter(self, tool_filter: 'ToolFilter') -> List[str]:
        """将不允许的工具临时移除"""
        original_tools = self.tool_registry.list_tools()
        filtered = tool_filter.filter(original_tools)
        self._temp_disabled_tools = {}
        for name in original_tools:
            if name not in filtered:
                self._temp_disabled_tools[name] = self.tool_registry.get_tool(name)
                del self.tool_registry._tools[name]
        return original_tools  # 用于恢复

    def _restore_tools(self, original_tools: List[str]):
        """恢复被临时禁用的工具"""
        for name, tool in self._temp_disabled_tools.items():
            self.tool_registry._tools[name] = tool
        self._temp_disabled_tools = {}
```

## 子代理元数据收集

```python
def _get_subagent_metadata(self, duration, error=None) -> Dict:
    return {
        "steps": assistant_message_count,
        "tokens": total_chars // 4,        # 估算
        "duration_seconds": round(duration, 2),
        "tools_used": extract_tools_from_history(history),
        "error": error  # 仅失败时
    }
```

## 使用场景决策

| 场景 | 子代理类型 | 工具过滤 | 说明 |
|------|----------|---------|------|
| 探索代码库 | react | readonly | 快速迭代，只读安全 |
| 深度分析 | reflection | readonly | 需要反思优化 |
| 规划任务 | plan | readonly/full | 生成执行步骤 |
| 代码实现 | simple/react | full | 需要写权限 |
