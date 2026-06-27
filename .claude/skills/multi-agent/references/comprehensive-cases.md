# 综合案例参考

基于 Hello Agent 第十三~十五章的综合案例。

## 1. 多 Agent 旅行规划器 (Ch13)

```python
class MultiAgentTripPlanner:
    """多 Agent 旅行规划——4 个专业 Agent 共享 MCP 地图工具"""

    def __init__(self):
        # 共享工具——只创建一次，多 Agent 共用
        self.amap_tool = MCPTool(name="amap", server_command=["uvx", "amap-mcp-server"])

        # 4 个专业化 Agent——各有不同的 system_prompt
        self.attraction_agent = SimpleAgent(
            name="景点搜索专家",
            llm=HelloAgentsLLM(),
            system_prompt=(
                "你是景点搜索专家。**必须使用 amap 工具搜索，不要自己编造！**\n"
                "工具格式: [TOOL_CALL:amap_maps_text_search:keywords=景点,keywords=城市]\n"
                "输出格式: JSON，包含 name, address, rating, description"
            )
        )
        self.attraction_agent.add_tool(self.amap_tool)

        self.weather_agent = SimpleAgent(
            name="天气查询专家",
            llm=HelloAgentsLLM(),
            system_prompt=(
                "你是天气查询专家。工具: [TOOL_CALL:amap_maps_weather:city=城市名]\n"
                "输出: 日期、天气、温度、风力、建议"
            )
        )
        self.weather_agent.add_tool(self.amap_tool)

        self.hotel_agent = SimpleAgent(
            name="酒店推荐专家",
            llm=HelloAgentsLLM(),
            system_prompt=(
                "你是酒店推荐专家。搜索目标城市酒店。\n"
                "工具: [TOOL_CALL:amap_maps_text_search:keywords=酒店,city=城市]\n"
                "输出: JSON，包含 name, price_range, rating, location, features"
            )
        )
        self.hotel_agent.add_tool(self.amap_tool)

        self.planner_agent = SimpleAgent(
            name="行程规划专家",
            llm=HelloAgentsLLM(),
            system_prompt=(
                "你是行程规划专家。根据景点、天气、酒店信息生成完整的旅行计划。\n"
                "不需要使用工具。以 JSON 格式输出每日行程。"
            )
        )

    def plan_trip(self, request: dict) -> dict:
        destination = request.get("destination", "")
        days = request.get("days", 3)

        try:
            # Step 1-3: 并行收集信息
            attractions = self.attraction_agent.run(f"搜索{destination}的热门景点")
            weather = self.weather_agent.run(f"查询{destination}未来{days}天天气")
            hotels = self.hotel_agent.run(f"搜索{destination}的酒店")

            # Step 4: 汇总生成计划
            planner_query = (
                f"目的地: {destination}\n天数: {days}天\n\n"
                f"景点信息:\n{attractions}\n\n"
                f"天气信息:\n{weather}\n\n"
                f"酒店信息:\n{hotels}\n\n"
                f"请生成完整的 {days} 天旅行计划（JSON 格式）。"
            )
            plan = self.planner_agent.run(planner_query)
            return self._parse_response(plan, request)

        except Exception as e:
            return self._create_fallback_plan(request)

    def _create_fallback_plan(self, request: dict) -> dict:
        """兜底方案——保证系统始终有输出"""
        destination = request.get("destination", "目的地")
        days = request.get("days", 3)
        return {
            "destination": destination,
            "duration": f"{days}天",
            "status": "fallback",
            "plan": [
                {"day": d, "activities": ["自由探索", "品尝当地美食", "休息"]
                 } for d in range(1, days + 1)
            ],
            "note": "无法获取实时数据，以下为通用建议"
        }
```

## 2. Deep Research Agent (Ch14)

```python
class DeepResearchAgent:
    """TODO 驱动的深度研究 Agent"""

    def __init__(self):
        self.note_tool = NoteTool(workspace="./research_notes")
        self.tracker = ToolCallTracker()

        # 规划专家——制定研究路线
        self.todo_agent = ToolAwareSimpleAgent(
            name="研究规划专家",
            llm=HelloAgentsLLM(),
            system_prompt=(
                "你是研究规划专家。根据研究主题创建 3-5 个研究 TODO。\n"
                "每个 TODO 应该从不同角度、不同层面探索主题。\n"
                "输出格式: JSON list，每项有 title 和 description。"
            )
        )

        # 执行专家——完成单个 TODO
        self.summarizer_agent = ToolAwareSimpleAgent(
            name="研究总结专家",
            llm=HelloAgentsLLM(),
            system_prompt=(
                "你是研究总结专家。针对给定的 TODO，搜索信息并写笔记。\n"
                "1. 先用 web_search 搜索\n"
                "2. 阅读搜索结果\n"
                "3. 用 note_tool 记录关键发现\n"
                "4. 用 note_tool 总结该 TODO"
            )
        )
        self.summarizer_agent.add_tool(WebSearchTool())
        self.summarizer_agent.add_tool(self.note_tool)

        # 报告专家——汇总最终报告
        self.report_agent = ToolAwareSimpleAgent(
            name="报告撰写专家",
            llm=HelloAgentsLLM(),
            system_prompt="你是报告专家。根据所有研究笔记撰写结构化的最终报告。"
        )

    def run(self, topic: str) -> dict:
        # 1. 规划研究路线
        plan = self.todo_agent.run(f"为「{topic}」制定3-5个研究TODO")
        todo_items = self._parse_todo_list(plan)

        # 2. 逐个执行 TODO
        for todo in todo_items:
            self.summarizer_agent.run(
                f"TODO: {todo['title']}\n描述: {todo['description']}\n"
                f"请搜索相关信息并写入笔记。"
            )

        # 3. 生成报告
        notes = self.note_tool.run({"action": "list"})
        report = self.report_agent.run(
            f"研究主题: {topic}\n\n研究笔记:\n{notes}\n\n请撰写最终研究报告。"
        )

        return {
            "topic": topic,
            "todo_items": todo_items,
            "report": report,
            "tool_calls": self.tracker.get_summary()
        }

    def run_stream(self, topic: str):
        """流式版本——实时产出事件"""
        import threading
        from queue import Queue

        event_queue = Queue()

        def plan_phase():
            event_queue.put({"phase": "planning", "status": "started"})
            todo_items = self._parse_todo_list(
                self.todo_agent.run(f"为「{topic}」制定研究TODO")
            )
            event_queue.put({"phase": "planning", "status": "done",
                             "todos": todo_items})
            return todo_items

        def research_phase(todo):
            event_queue.put({"phase": "research", "todo": todo["title"],
                             "status": "started"})
            result = self.summarizer_agent.run(
                f"TODO: {todo['title']}\n{todo['description']}"
            )
            event_queue.put({"phase": "research", "todo": todo["title"],
                             "status": "done", "result": result})

        def report_phase():
            event_queue.put({"phase": "report", "status": "started"})
            notes = self.note_tool.run({"action": "list"})
            return self.report_agent.run(f"研究主题: {topic}\n\n笔记:\n{notes}")

        # 多线程执行
        thread = threading.Thread(target=lambda: (
            todos := plan_phase(),
            [research_phase(t) for t in todos],
            event_queue.put({"phase": "report", "content": report_phase(),
                             "status": "done"})
        ))
        thread.start()

        # 逐事件产出
        while thread.is_alive() or not event_queue.empty():
            try:
                yield event_queue.get(timeout=0.1)
            except:
                continue
```

## 3. AI Town NPC 系统 (Ch15)

```python
class NPCAgentManager:
    """NPC 系统——角色记忆 + 好感度 + LLM 对话"""

    def __init__(self):
        self.agents: dict[str, SimpleAgent] = {}
        self.memories: dict[str, MemoryTool] = {}
        self.relationships = RelationshipManager()
        self._init_npcs()

    def _init_npcs(self):
        """初始化所有 NPC"""
        for name, role in NPC_ROLES.items():
            system_prompt = self._create_character_prompt(name, role)
            self.agents[name] = SimpleAgent(name=name, llm=HelloAgentsLLM(),
                                             system_prompt=system_prompt)
            self.memories[name] = MemoryTool(
                user_id=f"npc_{name}",
                memory_types=["working", "episodic", "semantic"]
            )

    def chat(self, npc_name: str, message: str, player_id: str = "player") -> dict:
        """与 NPC 对话——完整流程"""

        # 1. 获取好感度
        affinity = self.relationships.get_affinity(npc_name, player_id)
        affinity_context = self._get_affinity_context(affinity)

        # 2. 检索记忆
        memory_tool = self.memories[npc_name]
        memories = memory_tool.run({
            "action": "search",
            "query": message,
            "limit": 3
        })

        # 3. 构建增强 Prompt
        enhanced_message = (
            f"{affinity_context}\n\n"
            f"[对 {player_id} 的记忆]\n{memories}\n\n"
            f"[当前消息] {player_id} 说: {message}"
        )

        # 4. 生成回复
        agent = self.agents[npc_name]
        response = agent.run(enhanced_message)

        # 5. 分析情感 → 更新好感度
        sentiment = self._analyze_sentiment(message, response)
        self.relationships.update_affinity(npc_name, player_id, sentiment)

        # 6. 保存到记忆
        memory_tool.run({
            "action": "add",
            "content": f"{player_id}: {message} → {npc_name}: {response}",
            "memory_type": "episodic",
            "importance": 0.5 + abs(sentiment) * 0.3
        })

        return {
            "npc": npc_name,
            "response": response,
            "affinity": affinity + sentiment,
            "affinity_change": sentiment
        }

    def _create_character_prompt(self, name: str, role: dict) -> str:
        return f"""你是{role['title']}{name}。

【角色设定】
性格: {role['personality']}
专长: {role['expertise']}
说话风格: {role['style']}
爱好: {role['hobbies']}

【行为准则】
1. 始终保持角色一致性——你是{role['title']}，不是 AI
2. 回复自然、有人情味，30-80 字为宜
3. 根据与玩家的好感度调整语气（亲密/疏远/中立）
4. 不主动提及"你是一个 AI"或"作为语言模型"
5. 可以适当拒绝不合理请求，但要符合角色性格

【重要】永远不要破坏角色沉浸感。"""

    def _get_affinity_context(self, affinity: float) -> str:
        """好感度 → 对话风格修饰"""
        if affinity >= 80:
            return "你与这位朋友关系非常亲密，可以开玩笑、分享私事。"
        elif affinity >= 60:
            return "你与这位朋友关系不错，语气可以友好轻松。"
        elif affinity >= 40:
            return "你们关系一般，保持礼貌中带一点热情。"
        elif affinity >= 20:
            return "你们还不太熟，保持礼貌和适当距离。"
        else:
            return "你们之间有些生疏，保持客气和谨慎。"

    def _analyze_sentiment(self, user_msg: str, npc_response: str) -> float:
        """分析对话情感变化——返回 -1.0 到 1.0"""
        # 简化版：关键词分析
        positive = ["谢谢", "喜欢", "好", "棒", "厉害", "有趣", "开心",
                    "thanks", "love", "great", "awesome"]
        negative = ["讨厌", "烦", "滚", "差", "无聊", "恶心",
                    "hate", "bad", "terrible", "annoying"]

        msg_lower = (user_msg + " " + npc_response).lower()
        pos_score = sum(1 for w in positive if w in msg_lower)
        neg_score = sum(1 for w in negative if w in msg_lower)

        if pos_score + neg_score == 0:
            return 0.05  # 中性略正
        return (pos_score - neg_score) * 0.1  # 限制变化幅度
```

### 好感度系统

```python
class RelationshipManager:
    """管理 NPC 与玩家的好感度"""

    AFFINITY_LEVELS = [
        (80, "挚友"),
        (60, "亲密"),
        (40, "友好"),
        (20, "熟悉"),
        (0,  "陌生"),
    ]

    def __init__(self):
        self.affinities: dict[str, dict[str, float]] = {}
        self.change_log: list[dict] = []

    def get_affinity(self, npc_name: str, player_id: str) -> float:
        return self.affinities.get(npc_name, {}).get(player_id, 10.0)

    def get_level(self, npc_name: str, player_id: str) -> str:
        affinity = self.get_affinity(npc_name, player_id)
        for threshold, level in self.AFFINITY_LEVELS:
            if affinity >= threshold:
                return level
        return "陌生"

    def update_affinity(self, npc_name: str, player_id: str,
                         change: float):
        """更新好感度——带上下限"""
        if npc_name not in self.affinities:
            self.affinities[npc_name] = {}

        old = self.affinities[npc_name].get(player_id, 10.0)
        new = max(0.0, min(100.0, old + change))  # 限制 0-100

        self.affinities[npc_name][player_id] = new
        self.change_log.append({
            "npc": npc_name, "player": player_id,
            "old": old, "new": new, "change": change
        })
```

### NPC 角色数据库

```python
NPC_ROLES = {
    "张三": {
        "title": "Python工程师",
        "personality": "技术宅，喜欢讨论算法和框架，偶尔冷幽默",
        "expertise": "多智能体系统、HelloAgents框架、分布式计算",
        "style": "简洁专业，喜欢用技术术语，但不过度",
        "hobbies": "看技术博客、刷LeetCode、参加黑客马拉松"
    },
    "李四": {
        "title": "产品经理",
        "personality": "外向健谈，善于发现需求，话语中总带产品思维",
        "expertise": "用户研究、需求分析、敏捷开发",
        "style": "热情有感染力，喜欢问'你觉得...怎么样？'",
        "hobbies": "体验新产品、写产品分析、参加创业沙龙"
    },
    "王五": {
        "title": "UI设计师",
        "personality": "审美挑剔，注重细节，对不美观的东西零容忍",
        "expertise": "交互设计、视觉设计、Design System",
        "style": "优雅简洁，偶尔吐槽不合理的交互",
        "hobbies": "逛Dribbble、设计挑战、摄影"
    }
}
```
