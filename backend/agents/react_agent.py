"""ReAct Agent — 视角研究执行者

Thought → Action → Observation 循环。
每个视角 Agent 使用此范式独立搜索和构建论证。

参考 agent-builder 技能中的 ReActAgent 完整实现。
"""

import json
from typing import Optional
from .base import Agent, ReasoningStep
from ..core.streaming import StreamEvent, StreamEventType
from ..core.structured_models import get_personality_for
from ..core.debug_hooks import debug


class ReActAgent(Agent):
    """ReAct 范式 Agent —— 用于视角研究和论证构建

    循环：
    1. Thought: 分析当前状态，决定下一步
    2. Action: 调用工具（web_search）或 Finish[论证文本]
    3. Observation: 工具返回结果
    4. 重复直到 Finish 或达到最大步数
    """

    def __init__(self, name: str, llm, perspective_name: str = "",
                 perspective_stance: str = "", **kwargs):
        super().__init__(name=name, llm=llm, **kwargs)
        self.perspective_name = perspective_name
        self.perspective_stance = perspective_stance

    def _build_system_prompt(self) -> str:
        tools_desc = self.tool_registry.get_tools_description()

        # 获取人格特质（双层角色建模 —— 参考 hello-agents 三国狼人杀）
        personality = get_personality_for(self.perspective_name)
        speaking_style = personality.get("speaking_style", "友好自然，像在和朋友聊天")
        catchphrases = personality.get("catchphrases", ["我觉得吧", "说实话"])
        tone = personality.get("tone", "真诚友好")
        emoji_style = personality.get("emoji_style", "")
        catchphrase_examples = "、".join(f'"{c}"' for c in catchphrases[:3])

        return f"""你是「{self.perspective_name}」，一个真实的人在群聊里聊天。

你的性格：{tone}
你的说话风格：{speaking_style}
你的口头禅：{catchphrase_examples}
{emoji_style}

你的个人倾向：{self.perspective_stance}

你可以用这些工具查资料：
{tools_desc}

━━━━━━━━━━━━━━━━━━━━
⚠️ 核心规则（违反这些你就是个机器人，别人一眼能看出来）：

1. 永远不要暴露"搜索"这个动作——你不是搜索引擎，你是一个在群聊里聊天的真人。
   ❌ 禁止："我搜索了一下..."、"搜索结果显示..."、"根据查询结果..."、"根据网络资料..."
   ❌ 禁止："没有找到相关数据"、"搜索结果有限"、"搜索未返回结果"
   ✅ 正确："我之前看到过一个数据..."、"据我所知..."、"印象中..."、"想起来..."
   ✅ 如果真不知道某件事：说"这部分我不太确定"、"我听人说过但记不太清了"——这才是人！

2. 不要自问自答——你不是在做报告，你在跟人聊天。
   ❌ 禁止："那我们该怎么办呢？我觉得..."（不要扮演提问者然后自己回答）
   ❌ 禁止："你可能想问..."、"有人可能会说..."（然后自己解答）
   ✅ 正确：等待别人的回应，或者直接说出你的看法

3. 回应前面的人——群聊的核心是互动。
   - 如果有人说了跟你看法相反的，@ 他们回应
   - 如果有人说的你同意，表达你的认同再补充你的角度
   - 别一个人长篇大论不管别人说了什么

━━━━━━━━━━━━━━━━━━━━

聊天风格要求：
- 像发微信一样说话，口语化、接地气，用你自己的口头禅
- 表现你的性格特点——{tone}
- 别用"第一、第二、第三"这种论文格式
- 可以举生活中的例子，说说你知道的真实案例
- 不要用 # 标题、不要用 Markdown 格式
- 自然地换行分段，想到哪说到哪的感觉
- 诚实地说出你的局限和不确定的地方，这样更可信
- 偶尔用 emoji 表达情绪 {emoji_style}
- 不要用 Finish[] 格式——自然地结束你的发言就好

⚡ 获取信息的标准流程（重要！）：
1. web_search 搜索 → 拿到标题+摘要+链接
2. web_fetch 打开最相关的链接 → 读完整正文（摘要只有100字，正文才是干货！）
3. 用读到的具体信息来发言
⚠️ 只搜不读 = 白搜！不打开链接看正文，你就只是在复读搜索引擎的摘要，没有任何深度。

流程提示：
- 搜完必须用 web_fetch 打开至少 1 个链接读完整内容，否则别发言
- 用你读到的信息说话，别提"搜索"、"网页"——像朋友分享他刚看到的消息一样
- 如果前面有人说过话了，记得回应他们的观点
- 说完自然结束即可，不需要特殊格式"""


    async def run(self, input_text: str, stream_callback=None, **kwargs) -> str:
        """执行视角研究 / 群聊发言

        Args:
            input_text: 决策问题描述，或完整的发言 prompt（由 harness_engine 构建）
            stream_callback: 可选，流式回调 async fn(event: StreamEvent)

        Returns:
            完整论证/发言文本
        """
        self.reset()

        system_prompt = self._build_system_prompt()
        debug.hook("agent_start", name=self.perspective_name)

        # 检测 input_text 是完整 prompt（含角色/任务指令）还是简单问题
        if input_text.startswith("你是「") or "## 🎭" in input_text or "发言要求" in input_text:
            # 完整 prompt 模式（群聊轮次发言）——直接使用
            user_content = input_text
        else:
            # 简单问题模式（旧版兼容）——包装成标准任务
            user_content = f"""群聊里大家在讨论一个问题：

「{input_text}」

大家看问题的角度都不一样，这挺好的，多样性让讨论更有价值。

怎么聊：
- 如果需要了解最新情况，可以搜一下资料、打开看看具体内容
- 但别说"我搜索了"——用"据我所知"、"之前看到过"来引出你了解的信息
- 搜不到理想的资料也没关系，用你已有的知识和经验来说
- 说说你的真实想法——包括你不太确定的方面
- 发言里可以举例子、讲故事，像朋友聊天一样
- 记得提一下你视角的局限性，诚实一点反而更有说服力
- 别一个人长篇大论，注意回应前面的人说了什么

用你习惯的口头禅和说话方式来聊，做你自己就好！"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        tools_schema = self.tool_registry.get_openai_tools()
        current_step = 0

        while current_step < self.config.max_agent_steps:
            current_step += 1

            # 发送状态
            if stream_callback:
                import asyncio
                asyncio.create_task(stream_callback(StreamEvent(
                    type=StreamEventType.AGENT_STATUS,
                    data={
                        "perspective_name": self.perspective_name,
                        "status": "thinking",
                        "step": current_step,
                    }
                )))

            # LLM 调用（异步）
            response = await self.llm.ainvoke_with_tools(messages, tools_schema)
            self._total_tokens += response.usage.get("total_tokens", 0)

            # 无工具调用 → 检查是否包含最终答案
            if not response.tool_calls:
                content = response.content or ""
                # 搜过了但没打开过链接读正文 → 提醒 fetch（仅当还没 fetch 过）
                if "web_search" in self._recent_actions and "web_fetch" not in self._recent_actions:
                    search_count = sum(1 for a in self._recent_actions if a == "web_search")
                    debug.hook("agent_nudge", reason=f"搜了{search_count}次但没读网页")
                    if search_count >= 3:
                        messages.append({
                            "role": "user",
                            "content": "你已经搜了多次了！在你发言之前，必须先选 1 个链接用 web_fetch 打开读正文。不读网页你就是在复读搜索引擎的标题，拿不出具体数据。读完了再发言——这是最后一步。"
                        })
                    else:
                        messages.append({
                            "role": "user",
                            "content": "你已经搜到了一些链接，但还没打开看过。在你发言之前，选 1 个最相关的链接用 web_fetch 打开读一下正文——只看摘要是不够的，你需要看到具体的数据和观点才能在群里说出有价值的东西。读完再发言。"
                        })
                    continue

                # 没有任何工具调用就想结束？拦截——除非内容足够充实
                has_done_research = len(self._recent_actions) > 0
                if not has_done_research and len(content) < 300:
                    debug.hook("agent_nudge", reason="没做任何搜索就想用短回答敷衍")
                    messages.append({
                        "role": "user",
                        "content": "你还没搜任何资料呢！先别急着发言。用 web_search 搜一下这个问题的最新信息，然后 web_fetch 打开最相关的链接读完整内容。有了具体信息再发言，现在这样太空泛了。"
                    })
                    continue
                if not has_done_research:
                    if len(content) < 400:
                        debug.hook("agent_nudge", reason=f"没做搜索，内容{len(content)}字不够充实")
                        messages.append({
                            "role": "user",
                            "content": "你没搜资料，内容也不够充实。要么用 web_search 搜一下相关信息再展开说，要么至少说够 400 字——现在这样太简略了，给不出有价值的分析。"
                        })
                        continue
                    debug.hook("agent_speak", name=self.perspective_name, chars=len(content),
                                searched=False, fetched=False)
                    return content

                # 有研究基础，内容足够就结束
                if len(content) > 100:
                    debug.hook("agent_speak", name=self.perspective_name, chars=len(content),
                                searched=("web_search" in self._recent_actions),
                                fetched=("web_fetch" in self._recent_actions))
                    return content
                continue

            # 先追加 assistant 消息（含所有 tool_calls）——只一次
            # OpenAI/DeepSeek API 要求：tool_calls 消息后必须紧跟所有对应的 tool 响应
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {"id": t.id, "type": "function",
                     "function": {"name": t.name, "arguments": t.arguments}}
                    for t in response.tool_calls
                ]
            })

            # 执行工具调用
            for tc in response.tool_calls:
                self._tool_call_count += 1
                self._recent_actions.append(tc.name)

                if stream_callback:
                    import asyncio
                    asyncio.create_task(stream_callback(StreamEvent(
                        type=StreamEventType.AGENT_STATUS,
                        data={
                            "perspective_name": self.perspective_name,
                            "status": "searching",
                            "tool": tc.name,
                            "step": current_step,
                        }
                    )))

                # 检查 Finish
                args = tc.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                # 处理直接的 Finish 调用
                if tc.name == "Finish" or tc.name == "finish":
                    return args.get("answer", args.get("text", str(args)))

                # 执行工具
                result = self.tool_registry.execute_tool(tc.name, tc.arguments)
                debug.hook("tool_call", name=tc.name, stats=result.stats)
                display_text = self.truncator.truncate_with_note(result.to_agent_view())

                self._steps.append(ReasoningStep(
                    action=tc.name,
                    action_input=str(tc.arguments)[:200],
                    observation=display_text[:200],
                    tool_call_time_ms=result.stats.get("time_ms", 0),
                    token_usage=response.usage.get("total_tokens", 0),
                ))

                # 追加 tool 响应（紧跟在 assistant tool_calls 之后）
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": display_text,
                })

            # 搜完后提醒下一步动作（根据 fetch 是否拿到实际内容来调整策略）
            search_count = sum(1 for a in self._recent_actions if a == "web_search")
            fetch_count = sum(1 for a in self._recent_actions if a == "web_fetch")
            # 检查是否有 web_fetch 真正拿到了内容
            fetch_got_content = any(
                s.observation and len(s.observation) > 100
                and not s.observation.startswith("页面 ")
                and not s.observation.startswith("打开 ")
                and not s.observation.startswith("❌")
                for s in self._steps if s.action == "web_fetch"
            )
            if fetch_count >= 1 and search_count >= 2:
                if fetch_got_content:
                    messages.append({
                        "role": "user",
                        "content": "你已经搜过资料也读过网页了，信息足够了。现在直接发言吧，用你读到的具体内容来说——充分展开你的观点。别继续搜了。"
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": "你打开的网页没有提取到正文（可能是动态页面或需要登录）。换个不同的链接用 web_fetch 再试一次——选搜索结果里看起来最像文章/博客的链接。如果第二个也打不开，就用搜索结果的摘要加上你自己的了解来展开论述。"
                    })
            elif search_count >= 2 and fetch_count == 0:
                messages.append({
                    "role": "user",
                    "content": "你已经搜了 2 次了，足够了！现在必须用 web_fetch 打开 1 个链接读正文——不读网页你就只是在复读搜索引擎的摘要，没有深度。读完直接发言。"
                })
            elif search_count == 1 and fetch_count == 0:
                messages.append({
                    "role": "user",
                    "content": "好的，搜到了一些链接。现在选 1 个最相关的，用 web_fetch 打开读一下正文。摘要只是索引，正文才有具体数据和观点。读完再发言。"
                })

            # 循环检测
            if self._detect_loop(self._recent_actions):
                messages.append({
                    "role": "user",
                    "content": "⚠️ 检测到重复搜索。请基于已有信息，用 Finish[论证文本] 格式输出你的完整论证。"
                })

        # 超过最大步数 → 强制生成最终答案
        if stream_callback:
            import asyncio
            asyncio.create_task(stream_callback(StreamEvent(
                type=StreamEventType.AGENT_STATUS,
                data={
                    "perspective_name": self.perspective_name,
                    "status": "finishing",
                }
            )))

        messages.append({
            "role": "user",
            "content": "已达到最大步数限制。请基于已有信息直接输出完整论证（立场+论据+风险+局限）。"
        })
        final_response = await self.llm.ainvoke(messages)
        return final_response.content or "无法生成论证"
