# Agent 推理范式完整实现

## 1. ReAct 范式 (Reasoning + Acting)

### 完整实现

```python
import re
from typing import Optional

class ReActAgent:
    """ReAct 范式 Agent —— Thought→Action→Observation 循环"""

    def __init__(self, name: str, llm, tool_registry=None, max_steps: int = 10):
        self.name = name
        self.llm = llm
        self.tool_registry = tool_registry
        self.max_steps = max_steps
        self.history: list[str] = []

    def run(self, question: str) -> str:
        self.history = []
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1

            # 1. 构建 prompt（含工具描述 + 历史 + 问题）
            prompt = self._build_prompt(question)

            # 2. LLM 推理
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.think(messages)

            # 3. 解析 Thought 和 Action
            thought, action, action_input = self._parse_output(response)

            # 4. 判断是否完成
            if action == "Finish":
                return action_input  # 最终答案

            # 5. 执行工具调用
            try:
                observation = self.tool_registry.execute_tool(action, action_input)
            except Exception as e:
                observation = f"工具执行错误: {e}"

            # 6. 记录历史
            self.history.append(
                f"Step {current_step}: Action: {action}[{action_input}]\n"
                f"Observation: {observation}"
            )

        # 超过最大步数，强制生成最终答案
        messages.append({
            "role": "user",
            "content": "已达到最大步数限制，请基于已有信息直接给出最终答案。"
        })
        return self.llm.invoke(messages)

    def _build_prompt(self, question: str) -> str:
        tools_desc = self.tool_registry.get_tools_description() if self.tool_registry else "无可用工具"
        history_text = "\n".join(self.history) if self.history else "(无)"

        return f"""你是一个智能助手，可以使用工具来解决问题。

## 可用工具
{tools_desc}

## 输出格式
每次回复必须包含：
Thought: [你的思考过程——分析当前状态，决定下一步]
Action: tool_name[input] 或 Finish[最终答案]

## 任务
Question: {question}

## 执行历史
{history_text}

请按照 Thought/Action 格式回复："""

    def _parse_output(self, text: str) -> tuple[str, str, str]:
        """解析 LLM 输出中的 Thought 和 Action"""
        thought = ""
        action = ""
        action_input = ""

        # 提取 Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=\nAction:|\Z)', text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # 提取 Action
        action_match = re.search(r'Action:\s*(.+?)(?:\n|$)', text)
        if action_match:
            action_text = action_match.group(1).strip()

            # 解析 Finish[答案]
            if action_text.startswith("Finish["):
                action = "Finish"
                action_input = action_text[7:-1]  # 去掉 Finish[] 括号
            else:
                # 解析 tool_name[input]
                tool_match = re.match(r'(\w+)\[(.*)\]', action_text)
                if tool_match:
                    action = tool_match.group(1)
                    action_input = tool_match.group(2)

        return thought, action, action_input
```

### Prompt 模板详解

系统提示词的三个关键部分：
1. **工具描述**: 名称 + 功能 + 参数格式 + 返回值格式
2. **输出格式约束**: 明确的 Thought/Action 结构
3. **边界条件**: 何时用 Finish，何时继续

```python
REACT_SYSTEM_PROMPT = """你是 {role}，负责 {responsibility}。

## 可用工具
{tools}
每个工具用 `tool_name[input]` 格式调用。

## 输出格式
每次回复严格按以下格式：
Thought: [分析当前状态，推理下一步该做什么]
Action: tool_name[input] 或 Finish[最终答案]

## 规则
1. 每次只调用一个工具
2. 获得工具结果后，分析是否需要继续调用工具
3. 当有足够信息回答时，用 Finish[答案] 结束
4. 不要重复已经执行过的工具调用
5. 如果工具执行失败，尝试其他方法或说明原因"""
```

### ReAct 适用场景判断

```python
def should_use_react(task: str) -> bool:
    """判断任务是否适合 ReAct 范式"""
    react_indicators = [
        "搜索", "查找", "查询",        # 需要外部信息
        "计算", "分析", "比较",         # 需要工具
        "调试", "排查", "修复",         # 需要多步迭代
        "最新", "当前", "实时",         # 信息不确定
    ]
    task_lower = task.lower()

    # 有工具调用需求 → ReAct
    if any(indicator in task_lower for indicator in react_indicators):
        return True

    # 步骤数不确定 → ReAct
    return False  # 直接对话即可
```

## 2. Plan-and-Solve 范式

### 完整实现

```python
import ast

class PlanAndSolveAgent:
    """Plan-and-Solve —— 先规划再执行"""

    def __init__(self, llm, tool_registry=None):
        self.llm = llm
        self.tool_registry = tool_registry

    def run(self, question: str) -> str:
        # 阶段1: 生成计划
        plan = self._plan(question)

        # 阶段2: 逐步执行
        return self._execute(question, plan)

    def _plan(self, question: str) -> list[str]:
        """生成步骤列表"""
        prompt = f"""请将以下问题分解为可执行的步骤列表。
只输出 Python list 格式，每项是一个步骤描述。

Question: {question}

输出格式示例: ["步骤1: 确定搜索关键词", "步骤2: 执行搜索", "步骤3: 分析结果"]"""
        response = self.llm.invoke([{"role": "user", "content": prompt}])

        try:
            plan = ast.literal_eval(response)
            if isinstance(plan, list) and all(isinstance(s, str) for s in plan):
                return plan
        except (SyntaxError, ValueError):
            pass

        # 降级：按行解析
        lines = [l.strip().lstrip("0123456789. -") for l in response.split("\n") if l.strip()]
        return [l for l in lines if len(l) > 5]

    def _execute(self, question: str, plan: list[str]) -> str:
        """逐步执行计划"""
        history = []

        for i, step in enumerate(plan, 1):
            history_text = "\n".join(
                f"步骤{j}: {s}\n结果: {r}"
                for j, (s, r) in enumerate(history, 1)
            )

            prompt = f"""原始问题: {question}

完整计划:
{chr(10).join(f"{j}. {s}" for j, s in enumerate(plan, 1))}

已完成步骤:
{history_text if history else "(无)"}

当前步骤 ({i}/{len(plan)}): {step}

请执行当前步骤并给出结果。如果当前步骤需要工具，请使用 tool_name[input] 格式调用。"""

            messages = [{"role": "user", "content": prompt}]
            result = self.llm.invoke(messages)

            # 如果有工具调用
            tool_calls = self._parse_tool_calls(result)
            for call in tool_calls:
                obs = self.tool_registry.execute_tool(call['tool_name'], call['parameters'])
                messages.append({"role": "user", "content": f"工具结果: {obs}"})
                result = self.llm.invoke(messages)

            history.append((step, result))

        # 汇总最终答案
        summary_prompt = f"""原始问题: {question}

所有步骤执行结果:
{chr(10).join(f"步骤{j}: {s}\n结果: {r}" for j, (s, r) in enumerate(history, 1))}

请基于以上所有步骤的结果，给出最终的完整答案。"""
        return self.llm.invoke([{"role": "user", "content": summary_prompt}])

    def _parse_tool_calls(self, text: str) -> list[dict]:
        """解析工具调用"""
        matches = re.findall(r'(\w+)\[(.*?)\]', text)
        return [{'tool_name': m[0], 'parameters': m[1]} for m in matches if m[0] != 'Finish']
```

### Planner Prompt 设计要点

```python
PLANNER_BEST_PRACTICES = """
Planner Prompt 设计原则:
1. 明确输出格式——Python list 最易解析
2. 每步应该是可独立执行的单元
3. 步骤数建议 3-7 个——太少没有意义，太多难以管理
4. 步骤描述要具体——"搜索AI Agent资料" 好过 "做研究"
5. 步骤间依赖关系要清晰——后续步骤可以引用前面步骤的结果
"""
```

## 3. Reflection 范式

### 完整实现

```python
class ReflectionAgent:
    """Reflection —— Execute→Reflect→Refine 循环"""

    def __init__(self, llm, max_iterations: int = 3):
        self.llm = llm
        self.max_iterations = max_iterations
        self.memory: list[dict] = []

    def run(self, task: str) -> str:
        # 1. 初始执行
        print(f"🔧 初始执行: {task[:50]}...")
        initial_prompt = f"""完成以下任务，直接给出结果:

任务: {task}

请输出你的完整结果。"""
        result = self.llm.invoke([{"role": "user", "content": initial_prompt}])
        self.memory.append({"phase": "execution", "content": result, "iteration": 0})

        # 2. 反思-优化循环
        for iteration in range(1, self.max_iterations + 1):
            # a. 反思——审查上一轮结果
            reflect_prompt = f"""请审查以下内容，找出问题和可改进之处。

原始任务: {task}

待审查内容:
{result}

请从以下角度分析:
1. 是否正确完整地解决了任务？
2. 逻辑是否清晰无矛盾？
3. 输出格式是否合适？
4. 有没有遗漏或过度简化的地方？

如果已经没有明显问题，回复: "无需改进"。
否则，列出具体问题并给出改进建议。"""
            feedback = self.llm.invoke([{"role": "user", "content": reflect_prompt}])
            self.memory.append({"phase": "reflection", "content": feedback, "iteration": iteration})

            # b. 检查停止条件
            if "无需改进" in feedback:
                print(f"✅ 第{iteration}轮反思：无需改进，结束")
                break

            # c. 优化——基于反馈改进
            refine_prompt = f"""请基于反馈改进你的结果。

原始任务: {task}

上一轮结果:
{result}

反馈意见:
{feedback}

请输出改进后的完整结果。"""
            result = self.llm.invoke([{"role": "user", "content": refine_prompt}])
            self.memory.append({"phase": "execution", "content": result, "iteration": iteration})
            print(f"🔄 第{iteration}轮优化完成")

        return result

    def get_improvement_history(self) -> list[dict]:
        """获取改进历程"""
        return [
            {"iteration": m["iteration"], "phase": m["phase"],
             "preview": m["content"][:100] + "..."}
            for m in self.memory
        ]
```

### 三个 Prompt 模板详解

```python
# 模板1: INITIAL — 纯任务执行，不给"审查"提示
# 目的：让 Agent 自由发挥，暴露真实水平
INITIAL_PROMPT = "完成以下任务，直接给出结果:\n\n任务: {task}"

# 模板2: REFLECT — 结构化审查，引导找出具体问题
# 关键：给出审查维度，避免泛泛而谈
REFLECT_PROMPT = """审查以下内容:
原始任务: {task}
待审查内容: {code}

请从正确性、清晰度、完整性、效率四个维度分析。
如果无问题则回复"无需改进"。
有问题则列出具体位置和修改建议。"""

# 模板3: REFINE — 精准改进，不改变正确部分
# 关键：引用原始内容和反馈，避免"另起炉灶"
REFINE_PROMPT = """基于反馈改进:
原始任务: {task}
上一轮: {last_code}
反馈: {feedback}

只修改有问题的地方，保持正确部分不变。
输出完整的改进后内容。"""
```

### Reflection 适用场景

| 场景 | 为什么适合 | 典型迭代次数 |
|------|-----------|------------|
| 代码生成 | 代码有客观质量标准 | 2-3 轮 |
| 文案撰写 | 需要反复润色 | 2-4 轮 |
| 方案设计 | 需要多角度审查 | 1-2 轮 |
| 翻译 | 有忠实度标准 | 1-2 轮 |

## 4. Harness 混合模式

### 复杂度评估

```python
def assess_complexity(task: str) -> str:
    """评估任务复杂度，决定使用哪种范式"""
    # 统计关键词
    multi_step_keywords = ["首先", "然后", "接着", "最后", "步骤", "流程"]
    tool_keywords = ["搜索", "计算", "查询", "调用", "API"]
    multi_agent_keywords = ["多个", "协作", "分配", "团队", "并行"]

    score = 0
    for kw in multi_step_keywords:
        if kw in task:
            score += 1
    for kw in tool_keywords:
        if kw in task:
            score += 2
    for kw in multi_agent_keywords:
        if kw in task:
            score += 3

    if score >= 5:
        return "complex"    # Hybrid: Plan + ReAct
    elif score >= 2:
        return "medium"     # ReAct
    else:
        return "simple"     # 直接对话
```

### 循环检测

```python
def detect_loop(recent_actions: list[str], threshold: int = 3) -> bool:
    """检测 Agent 是否陷入重复调用循环"""
    if len(recent_actions) < threshold:
        return False

    # 检查最近 N 次工具调用是否完全相同
    last_n = recent_actions[-threshold:]
    if len(set(last_n)) == 1:
        print(f"⚠️ 检测到循环调用: {last_n[0]} 重复了 {len(last_n)} 次")
        return True

    # 检查是否在同一类操作上反复
    action_types = [a.split("_")[0] for a in last_n if "_" in a]
    if len(action_types) >= threshold and len(set(action_types)) == 1:
        print(f"⚠️ 检测到同类操作循环: {action_types[0]}")
        return True

    return False

# 干预策略
INTERVENTION_STRATEGIES = {
    "force_finish": "提示 Agent 停止工具调用，直接给出答案",
    "switch_strategy": "建议 Agent 换一种方法或工具",
    "human_escalation": "将问题升级给用户，说明卡住的原因",
}
```
