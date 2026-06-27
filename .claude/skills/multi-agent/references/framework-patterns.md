# 多 Agent 框架参考

## 框架选型速查

| 框架 | 核心机制 | 适用场景 | 学习曲线 |
|------|---------|---------|---------|
| AutoGen | 角色分工+轮转对话 | 软件开发团队 | 中 |
| AgentScope | MsgHub消息中心 | 游戏/投票/决策 | 中 |
| CAMEL | 双角色自动对话 | 专家+执行者 | 低 |
| LangGraph | 状态图工作流 | 固定流程搜索/分析 | 中 |

## AutoGen 完整示例

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination

# 核心：每个角色通过 system_message 定义职责和行为
pm = AssistantAgent(
    name="ProductManager",
    model_client=model,
    system_message=(
        "你是产品经理。\n"
        "职责: 需求分析 → 用户故事 → 优先级排序\n"
        "输出: 用户故事 + 验收标准"
    )
)

engineer = AssistantAgent(
    name="Engineer",
    model_client=model,
    system_message=(
        "你是软件工程师。\n"
        "职责: 技术方案 → 代码实现 → 测试\n"
        "输出: 可运行代码（用 ```python 标记）"
    )
)

reviewer = AssistantAgent(
    name="CodeReviewer",
    model_client=model,
    system_message=(
        "你是代码审查员。\n"
        "检查: 安全漏洞、性能问题、代码规范\n"
        "完成后说 TERMINATE"
    )
)

# 轮转对话 + 终止条件
team = RoundRobinGroupChat(
    participants=[pm, engineer, reviewer],
    termination_condition=TextMentionTermination("TERMINATE"),
    max_turns=15
)

# 流式执行
async for msg in team.run_stream(task="开发一个待办事项应用"):
    print(f"[{msg.source}] {msg.content[:100]}...")
```

## AgentScope 完整示例

```python
from agentscope.pipeline import MsgHub, sequential_pipeline, fanout_pipeline

async def voting_session(agents, topic: str):
    async with MsgHub(agents, enable_auto_broadcast=True,
                       announcement=f"讨论主题: {topic}") as hub:
        # 阶段1: 顺序发言
        await sequential_pipeline(agents)

        # 阶段2: 并行投票（关闭广播避免干扰）
        hub.set_auto_broadcast(False)
        votes = await fanout_pipeline(
            agents,
            msg="请投票: A/B/C ——只回复一个字母",
            structured_model=VoteModel,
            enable_gather=False
        )

        # 阶段3: 统计+宣布
        tally = {}
        for v in votes:
            tally[v.content.strip()] = tally.get(v.content.strip(), 0) + 1
        winner = max(tally, key=tally.get)
        hub.broadcast(f"结果: {tally}, 胜出: {winner}")
        return winner
```

## CAMEL 完整示例

```python
from camel.societies import RolePlaying

session = RolePlaying(
    assistant_role_name="数据科学家",
    user_role_name="报告撰写人",
    task_prompt="分析某电商平台用户行为数据，撰写数据报告",
    model=model,
    chat_turn_limit=20
)

input_msg = session.init_chat()
while True:
    scientist_msg, writer_msg = session.step(input_msg)
    print(f"[科学家] {scientist_msg.msg.content[:100]}")
    print(f"[撰写人] {writer_msg.msg.content[:100]}")
    if "CAMEL_TASK_DONE" in str(writer_msg.msg.content):
        break
    input_msg = scientist_msg.msg
```

## LangGraph 完整示例

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class SearchState(TypedDict):
    user_query: str
    search_query: str
    search_results: str
    analysis: str
    final_answer: str

def understand(state: SearchState) -> dict:
    resp = llm.invoke([{"role": "user",
        "content": f"提取搜索关键词: {state['user_query']}"}])
    return {"search_query": resp}

def search(state: SearchState) -> dict:
    results = tavily_client.search(state["search_query"])
    return {"search_results": "\n".join(r['title'] for r in results)}

def analyze(state: SearchState) -> dict:
    resp = llm.invoke([{"role": "user",
        "content": f"分析搜索结果: {state['search_results']}"}])
    return {"analysis": resp}

def answer(state: SearchState) -> dict:
    resp = llm.invoke([{"role": "user",
        "content": f"基于分析回答: {state['user_query']}\n{state['analysis']}"}])
    return {"final_answer": resp}

# 构建图
wf = StateGraph(SearchState)
for node_name, fn in [("understand", understand), ("search", search),
                        ("analyze", analyze), ("answer", answer)]:
    wf.add_node(node_name, fn)

wf.add_edge(START, "understand")
wf.add_edge("understand", "search")
wf.add_edge("search", "analyze")
wf.add_edge("analyze", "answer")
wf.add_edge("answer", END)

app = wf.compile(checkpointer=InMemorySaver())

# 流式执行
async for output in app.astream({"user_query": "量子计算最新进展"},
                                 config={"configurable": {"thread_id": "s1"}}):
    for node_name, node_output in output.items():
        print(f"[{node_name}] 完成")
```

## 框架选择决策

```python
def select_framework(requirements: dict) -> str:
    """根据需求选择最合适的框架"""
    if requirements.get("needs_voting"):
        return "AgentScope"  # 投票/群体决策
    if requirements.get("role_count") == 2:
        return "CAMEL"       # 双角色协作
    if requirements.get("fixed_workflow"):
        return "LangGraph"   # 固定流程
    if requirements.get("team_size", 1) > 2:
        return "AutoGen"     # 多角色团队
    return "AutoGen"         # 默认
```
