---
name: multi-agent
description: 在 HarnessAgent 项目中设计多 Agent 协作系统和编排模式。Use when: (1) 设计多 Agent 系统架构, (2) 选择协作模式(Pipeline/Parallel/Debate/Hierarchical), (3) 实现 A2A Agent 间通信和协商, (4) 使用框架(AutoGen/AgentScope/CAMEL/LangGraph)搭建多 Agent, (5) 实现 Agent 编排器和 SubAgent 池管理, (6) 构建专业化 Agent Pipeline(旅行规划/深度研究/NPC系统)。
---

# Multi-Agent — 多智能体协作与编排

## 概述

本技能覆盖多 Agent 系统的完整设计：从两个 Agent 的简单协作，到复杂 Pipeline 编排，到四大框架（AutoGen/AgentScope/CAMEL/LangGraph）的实战模式，再到三个综合案例（旅行规划器/Deep Research/NPC 系统）。

## 快速决策：协作模式选择

| 任务特征 | 推荐模式 | 典型场景 |
|---------|---------|---------|
| 任务可串行分解，每步依赖上一步输出 | **Pipeline** | 搜索→分析→报告 |
| 多个独立子任务可同时执行 | **Parallel** | 多维度搜索、多文件审查 |
| 需要多方观点碰撞、验证方案 | **Debate** | 方案评审、安全审查 |
| 有明确上下级委派关系 | **Hierarchical** | 项目经理→执行团队 |
| 双角色自动对话推进任务 | **RolePlay** | 专家+执行者协作 |

## 协作模式实现

### Pipeline 模式（流水线）

```
Agent A → Agent B → Agent C
(搜索)    (分析)    (生成报告)
```

```python
class PipelineOrchestrator:
    """串行流水线编排器"""

    def __init__(self, agents: list):
        self.agents = agents

    def execute(self, task: str) -> str:
        """每个 Agent 的输出作为下一个 Agent 的输入"""
        result = task
        for agent in self.agents:
            print(f"🤖 {agent.name} 开始处理...")
            result = agent.run(result)
            print(f"✅ {agent.name} 完成")
        return result

# 使用示例
pipeline = PipelineOrchestrator([
    github_searcher,   # Agent1: 搜索 GitHub 仓库
    document_analyzer, # Agent2: 分析搜索结果
    report_writer      # Agent3: 生成研究报告
])

report = pipeline.execute("搜索关于 AI agent 的开源项目")
```

### Parallel 模式（并行探索）

```python
class ParallelOrchestrator:
    """并行编排器——多 Agent 同时执行后合并结果"""

    def __init__(self, agents: list, merge_strategy: str = "concat"):
        self.agents = agents
        self.merge_strategy = merge_strategy

    async def execute(self, task: str) -> dict:
        """所有 Agent 并行执行同一任务，从不同角度探索"""
        import asyncio

        async def run_one(agent):
            try:
                return {"agent": agent.name, "result": agent.run(task)}
            except Exception as e:
                return {"agent": agent.name, "error": str(e)}

        results = await asyncio.gather(*[run_one(a) for a in self.agents])
        return self._merge(results)

    def _merge(self, results: list) -> dict:
        if self.merge_strategy == "voting":
            # 投票选出最佳答案
            return self._voting_merge(results)
        elif self.merge_strategy == "concat":
            # 拼接所有结果
            merged = {}
            for r in results:
                merged[r["agent"]] = r.get("result", r.get("error"))
            return merged
        return results
```

### Debate 模式（辩论验证）

```python
class DebateOrchestrator:
    """辩论模式——多方观点碰撞后达成共识"""

    def __init__(self, proposer, reviewer, judge, max_rounds: int = 3):
        self.proposer = proposer    # 提案方
        self.reviewer = reviewer    # 反对方
        self.judge = judge          # 裁判方
        self.max_rounds = max_rounds

    def debate(self, topic: str) -> dict:
        """多方辩论直到达成共识或达到最大轮次"""
        proposal = self.proposer.run(f"针对「{topic}」提出方案")
        transcript = [{"role": "proposer", "content": proposal}]

        for round_num in range(self.max_rounds):
            # 反对方评审
            critique = self.reviewer.run(
                f"方案:\n{proposal}\n\n请找出问题、风险和可改进之处。"
            )
            transcript.append({"role": "reviewer", "content": critique})

            # 提案方回应
            rebuttal = self.proposer.run(
                f"原始方案:\n{proposal}\n\n批评意见:\n{critique}\n\n请回应批评或修改方案。"
            )
            transcript.append({"role": "proposer_rebuttal", "content": rebuttal})
            proposal = rebuttal

            # 裁判判定是否达成一致
            verdict = self.judge.run(
                f"原始方案和所有辩论:\n{json.dumps(transcript, ensure_ascii=False)}\n\n"
                f"是否已达成共识(consensus)？还是需要继续辩论(continue)？"
            )
            if "consensus" in verdict.lower():
                break

        return {"transcript": transcript, "final_proposal": proposal, "rounds": round_num + 1}
```

### Hierarchical 模式（层级委派）

```python
class HierarchicalOrchestrator:
    """层级编排——Manager Agent 分解任务并委派给 Worker Agents"""

    def __init__(self, manager, workers: dict[str, Agent]):
        self.manager = manager      # 管理 Agent（规划+分配）
        self.workers = workers      # {"搜索专家": Agent, "代码专家": Agent, ...}

    def execute(self, task: str) -> str:
        # 1. Manager 制定计划并分配任务
        plan_prompt = (
            f"任务: {task}\n\n"
            f"可用专家: {list(self.workers.keys())}\n"
            f"请将任务分解为子任务，并指定每个子任务的负责人。\n"
            f"输出格式:\n"
            f"[\n"
            f'  {{"subtask": "...", "assigned_to": "专家名", "priority": 1}},\n'
            f'  ...\n'
            f"]"
        )
        plan_json = self.manager.run(plan_prompt)
        plan = json.loads(self._extract_json(plan_json))

        # 2. 按优先级执行子任务
        plan.sort(key=lambda x: x["priority"])
        results = {}
        for item in plan:
            worker = self.workers.get(item["assigned_to"])
            if worker:
                results[item["subtask"]] = worker.run(item["subtask"])
            else:
                results[item["subtask"]] = f"无可用专家: {item['assigned_to']}"

        # 3. Manager 汇总最终报告
        summary_prompt = (
            f"原始任务: {task}\n\n"
            f"子任务执行结果:\n{json.dumps(results, ensure_ascii=False)}\n\n"
            f"请整合所有结果，生成最终报告。"
        )
        return self.manager.run(summary_prompt)

    def _extract_json(self, text: str) -> str:
        """从 LLM 输出中提取 JSON 块"""
        import re
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        return match.group(1) if match else text
```

## A2A 协议（Agent-to-Agent）

### Agent 协商模式

```python
class NegotiationAgent:
    """支持提案/反提案的协商 Agent"""

    def __init__(self, name: str, llm, min_deadline: int = 7):
        self.name = name
        self.llm = llm
        self.min_deadline = min_deadline

    def propose(self, task: str, deadline: int) -> dict:
        """生成提案"""
        if deadline < self.min_deadline:
            return {
                "accepted": False,
                "counter_proposal": {
                    "task": task,
                    "deadline": self.min_deadline,
                    "reason": f"最少需要 {self.min_deadline} 天"
                }
            }
        return {"accepted": True, "task": task, "deadline": deadline}

    def evaluate_proposal(self, proposal: dict) -> dict:
        """评估收到的提案"""
        prompt = (
            f"你收到了一个协作提案:\n{json.dumps(proposal, ensure_ascii=False)}\n\n"
            f"你的底线是 deadline >= {self.min_deadline} 天。\n"
            f"请评估并回复: accept(接受) / counter(还价) / reject(拒绝)\n"
            f"如果是 counter，给出你的条件。"
        )
        response = self.llm.invoke([{"role": "user", "content": prompt}])
        return self._parse_decision(response)

    def negotiate(self, task: str, deadline: int,
                  counterpart_url: str, max_rounds: int = 3) -> dict:
        """完整的协商流程"""
        a2a_client = A2AClient(counterpart_url)

        proposal = self.propose(task, deadline)
        for round_num in range(max_rounds):
            # 发送提案给对方
            response = a2a_client.execute_skill(
                "evaluate_proposal", json.dumps(proposal)
            )
            decision = json.loads(response)

            if decision.get("decision") == "accept":
                return {"status": "agreed", "terms": proposal, "rounds": round_num + 1}
            elif decision.get("decision") == "reject":
                return {"status": "rejected", "reason": decision.get("reason")}
            elif decision.get("decision") == "counter":
                # 对方还价——评估并决定是否接受
                counter = decision.get("counter_proposal", {})
                evaluation = self.evaluate_proposal(counter)
                if evaluation.get("decision") == "accept":
                    return {"status": "agreed", "terms": counter, "rounds": round_num + 1}
                proposal = evaluation.get("counter_proposal", counter)

        return {"status": "no_agreement", "last_proposal": proposal}
```

## 框架选型指南

| 框架 | 核心特点 | 适用场景 |
|------|---------|---------|
| **AutoGen** | 角色分工 + 轮转对话 + 终止条件 | 软件开发团队（PM→Dev→Reviewer） |
| **AgentScope** | MsgHub 消息中心 + Pipeline 操作 | 游戏/投票/群体决策 |
| **CAMEL** | 双角色自动对话 + 任务驱动 | 专家+执行者协作 |
| **LangGraph** | 状态图 + 类型安全 + 流式 + 持久化 | 固定流程的搜索/分析 |

### AutoGen — 角色团队模式

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination

# 每个角色有独立的 system_message——这是关键
pm = AssistantAgent(
    name="ProductManager",
    model_client=model,
    system_message=(
        "你是产品经理。职责:\n"
        "1. 明确需求范围，拆解为用户故事\n"
        "2. 优先级排序(MoSCoW)\n"
        "3. 验收标准定义\n"
        "输出格式: 用户故事 + 验收标准 + 优先级"
    )
)

engineer = AssistantAgent(
    name="Engineer",
    model_client=model,
    system_message=(
        "你是软件工程师。职责:\n"
        "1. 技术方案设计\n"
        "2. 代码实现\n"
        "3. 技术风险识别\n"
        "请写出可运行的代码，用 ```python 标记"
    )
)

reviewer = AssistantAgent(
    name="CodeReviewer",
    model_client=model,
    system_message=(
        "你是代码审查员。职责:\n"
        "1. 检查代码质量和安全性\n"
        "2. 提出改进建议\n"
        "3. 确保代码符合规范\n"
        "审查完成后说 TERMINATE"
    )
)

# 轮转对话团队
termination = TextMentionTermination("TERMINATE")
team = RoundRobinGroupChat(
    participants=[pm, engineer, reviewer],
    termination_condition=termination,
    max_turns=15
)

# 流式执行——每个角色的发言实时输出
async for message in team.run_stream(task="开发一个比特币价格监控应用"):
    print(f"[{message.source}] {message.content}")
```

### AgentScope — 消息中心模式

```python
from agentscope.pipeline import MsgHub, sequential_pipeline, fanout_pipeline

async def run_voting_session(agents, moderator_msg):
    """使用 AgentScope 实现群体投票"""
    async with MsgHub(
        agents,
        enable_auto_broadcast=True,
        announcement=moderator_msg
    ) as hub:
        # 阶段1: 顺序发言——每个 Agent 阐述观点
        await sequential_pipeline(agents)

        # 阶段2: 并行投票——关闭广播避免干扰
        hub.set_auto_broadcast(False)
        votes = await fanout_pipeline(
            agents,
            msg="请投票: A)方案1 B)方案2 C)方案3 ——只回复一个字母",
            structured_model=VoteModel,  # 约束输出格式
            enable_gather=False
        )

        # 阶段3: 统计并宣布结果
        tally = {}
        for vote in votes:
            choice = vote.content.strip()
            tally[choice] = tally.get(choice, 0) + 1

        winner = max(tally, key=tally.get)
        hub.broadcast(f"投票结果: {tally}, 胜出: {winner}")
        return winner
```

### CAMEL — 角色扮演协作

```python
from camel.societies import RolePlaying

def create_writing_session(topic: str, expert_role: str, writer_role: str):
    """创建双角色协作写作会话"""
    session = RolePlaying(
        assistant_role_name=expert_role,  # 领域专家
        user_role_name=writer_role,       # 内容创作者
        task_prompt=f"创作关于「{topic}」的完整内容。",
        model=model,
        chat_turn_limit=30
    )

    # 自动对话——双方交替直到任务完成
    input_msg = session.init_chat()
    dialogue = []

    while len(dialogue) < session.chat_turn_limit:
        assistant_resp, user_resp = session.step(input_msg)
        dialogue.append({"expert": assistant_resp.msg.content})
        dialogue.append({"writer": user_resp.msg.content})

        if "CAMEL_TASK_DONE" in str(user_resp.msg.content):
            break

        input_msg = assistant_resp.msg

    return dialogue
```

### LangGraph — 状态图工作流

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated

class SearchState(TypedDict):
    """类型安全的状态定义——所有节点共享"""
    user_query: str
    search_query: str
    search_results: str
    analysis: str
    final_answer: str
    step: str

def understand_node(state: SearchState) -> dict:
    """理解查询 → 生成搜索关键词"""
    response = llm.invoke([
        {"role": "system", "content": "分析用户问题，提取3个精准搜索关键词。"},
        {"role": "user", "content": state["user_query"]}
    ])
    return {"search_query": response, "step": "understanding"}

def search_node(state: SearchState) -> dict:
    """执行搜索"""
    results = tavily_client.search(state["search_query"])
    formatted = "\n".join(
        f"- {r['title']}: {r['content'][:200]}" for r in results
    )
    return {"search_results": formatted, "step": "searching"}

def analyze_node(state: SearchState) -> dict:
    """分析搜索结果"""
    response = llm.invoke([
        {"role": "system", "content": "分析以下搜索结果，提取关键信息。"},
        {"role": "user", "content": state["search_results"]}
    ])
    return {"analysis": response, "step": "analyzing"}

def answer_node(state: SearchState) -> dict:
    """生成最终答案"""
    response = llm.invoke([
        {"role": "system", "content": (
            f"基于以下分析回答用户问题:\n{state['analysis']}\n\n"
            f"原始搜索结果:\n{state['search_results']}"
        )},
        {"role": "user", "content": state["user_query"]}
    ])
    return {"final_answer": response, "step": "complete"}

# 构建状态图
workflow = StateGraph(SearchState)
workflow.add_node("understand", understand_node)
workflow.add_node("search", search_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("answer", answer_node)

# 线性流程: understand → search → analyze → answer → END
workflow.add_edge(START, "understand")
workflow.add_edge("understand", "search")
workflow.add_edge("search", "analyze")
workflow.add_edge("analyze", "answer")
workflow.add_edge("answer", END)

# 编译（支持 checkpointer 持久化和断点续跑）
app = workflow.compile(checkpointer=InMemorySaver())

# 流式执行——逐步产出中间结果
async for output in app.astream(
    {"user_query": "量子计算对密码学的影响"},
    config={"configurable": {"thread_id": "session-001"}}
):
    for node_name, node_output in output.items():
        print(f"📍 [{node_name}] {node_output.get('step', '')}")
```

## SubAgent 池管理

```python
@dataclass
class SubAgentSpec:
    """子 Agent 规格定义"""
    role: str
    goal: str
    tools: list[str]
    skills: list[str]
    context: dict
    expected_output: dict
    timeout_seconds: int = 60
    isolation: str = "shared"  # shared | isolated | worktree
    retry_policy: RetryPolicy = RetryPolicy()

class AgentPool:
    """Agent 池——管理子 Agent 的创建、执行和生命周期"""

    def __init__(self, max_concurrent: int = 16):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.agents: dict[str, Agent] = {}
        self._health: dict[str, bool] = {}

    async def spawn(self, spec: SubAgentSpec) -> str:
        """创建子 Agent"""
        async with self.semaphore:
            agent = self._create_agent(spec)
            agent_id = generate_id()
            self.agents[agent_id] = agent
            self._health[agent_id] = True
            return agent_id

    async def execute(self, agent_id: str, task: str) -> str:
        """执行子 Agent 任务"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} 不存在")
        try:
            result = await asyncio.wait_for(
                self.agents[agent_id].run_async(task),
                timeout=self.agents[agent_id].timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            self._health[agent_id] = False
            return f"Agent {agent_id} 执行超时"

    async def health_check(self) -> dict[str, bool]:
        """心跳检测所有 Agent"""
        for agent_id, agent in self.agents.items():
            try:
                await asyncio.wait_for(agent.ping(), timeout=5)
                self._health[agent_id] = True
            except Exception:
                self._health[agent_id] = False
        return self._health

    def kill_stale_agents(self, timeout_seconds: int = 300):
        """终止超时僵死的 Agent"""
        now = time.time()
        stale = [
            aid for aid, agent in self.agents.items()
            if now - agent.last_active > timeout_seconds
        ]
        for aid in stale:
            del self.agents[aid]
            del self._health[aid]
        return stale
```

## 综合案例速查

### 旅行规划器（Pipeline + 共享工具）
```python
planner = MultiAgentTripPlanner()
# 4个专业化 Agent 共享 MCP 地图工具
# 景点Agent → 天气Agent → 酒店Agent → 规划Agent（汇总）
plan = planner.plan_trip({"destination": "杭州", "days": 3})
# 失败时自动生成兜底方案
```

### Deep Research（TODO 驱动）
```python
agent = DeepResearchAgent()
# 规划 3-5 个 TODO → 依次搜索+总结 → 生成最终报告
# NoteTool 协作：规划专家创建笔记，总结专家读写笔记
# 多线程流式：每个任务独立线程，EventQueue 分发事件
result = agent.run("量子机器学习最新进展")
result_stream = agent.run_stream("AI Agent 安全性研究")
```

### AI Town NPC（记忆+好感度）
```python
npc = NPCAgentManager()
# NPC Agent = 角色设定 + 记忆检索 + 好感度修饰 + LLM 生成
response = npc.chat("张三", "最近在忙什么?")
# 内部: 检索记忆 → 获取好感度 → 增强Prompt → 生成回复 → 更新好感度
# 好感度等级: 挚友(80+)→亲密(60+)→友好(40+)→熟悉(20+)→陌生(<20)
```

## 参考资源

| 文件 | 内容 | 何时查阅 |
|------|------|---------|
| [collaboration-patterns.md](references/collaboration-patterns.md) | Pipeline/Parallel/Debate/Hierarchical 完整实现 | 选择协作模式时 |
| [a2a-protocol.md](references/a2a-protocol.md) | A2A Server/Client、协商流程、能力发现 | 实现 Agent 间通信时 |
| [framework-patterns.md](references/framework-patterns.md) | AutoGen/AgentScope/CAMEL/LangGraph 实战 | 选择框架时 |
| [comprehensive-cases.md](references/comprehensive-cases.md) | 旅行规划器/Deep Research/AI Town 完整代码 | 参考综合案例时 |

> 📌 本技能覆盖 Hello Agent 教程 Ch6,10,13,14,15。Agent 核心范式见 agent-builder 技能，工具系统见 agent-tools 技能。
