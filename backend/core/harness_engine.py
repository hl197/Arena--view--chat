"""Harness Engine —— ArenaView 编排核心

完整的辩论生命周期：
0. 视角生成 (1次 LLM)
1. 自我介绍 (各视角入群消息)
2. 研究+顺序发言 (N个 ReAct Agent 并行研究，RoundRobin 顺序发送)
3. 交叉质询 (轮转 Debate)
4. 裁判合成 (Reflection 模式)

所有 SSE 事件通过 stream_callback 实时推送。
参考：hello-agents 第六章 —— AgentScope 消息驱动 + AutoGen RoundRobin + LangGraph 状态图
"""

import asyncio
import time
import json
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, field

from .config import ArenaConfig
from .perspective_generator import PerspectiveGenerator, Perspective
from .debate_scheduler import DebateScheduler, DebateTurn, DebateResult
from .streaming import StreamEvent, StreamEventType

from ..adapters.unified_llm import ArenaLLM
from ..agents.react_agent import ReActAgent
from ..agents.judge_agent import JudgeAgent
from ..agents.factory import create_react_agent, create_judge_agent
from .structured_models import get_personality_for
from ..tools.registry import ToolRegistry
from ..tools.builtin.web_search import WebSearchTool
from ..tools.builtin.web_fetch import WebFetchTool
from ..tools.builtin.finish_tool import FinishTool
from .debug_hooks import debug


@dataclass
class ArenaSession:
    """一次辩论会话"""
    id: str
    question: str
    user_id: str = ""
    user_options: list[str] = field(default_factory=list)
    perspectives: list[Perspective] = field(default_factory=list)
    arguments: dict[str, str] = field(default_factory=dict)   # perspective_id -> argument
    debate_turns: list[DebateTurn] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)  # [{round, speaker, speaker_id, text}, ...]
    decision_map: str = ""
    total_tokens: int = 0
    total_time_ms: int = 0
    status: str = "pending"  # pending | running | completed | error


class HarnessEngine:
    """ArenaView 编排引擎

    协调整个辩论流程：
    ```
    Question
      ↓ PerspectiveGenerator → 4-6 Perspectives
      ↓ Parallel ReActAgents → Arguments
      ↓ DebateScheduler → Cross-Examination
      ↓ JudgeAgent (Reflection) → Decision Map
    ```
    """

    def __init__(self, config: ArenaConfig = None, llm: ArenaLLM = None):
        self.config = config or ArenaConfig()
        self.llm = llm or ArenaLLM()
        self.tool_registry = ToolRegistry()

        # 注册默认工具
        self.tool_registry.register_tool(WebSearchTool(
            timeout=self.config.search_timeout_seconds,
            api_key=self.config.tavily_api_key or "",
        ))
        self.tool_registry.register_tool(WebFetchTool(
            timeout=self.config.search_timeout_seconds
        ))
        self.tool_registry.register_tool(FinishTool())

        # 子组件
        self.perspective_generator = PerspectiveGenerator(self.llm)
        self.debate_scheduler = DebateScheduler(self.llm, self.config)

    async def run(
        self,
        question: str,
        session_id: str,
        user_id: str = "",
        user_options: list[str] = None,
        num_perspectives: int = 5,
        debate_rounds: int = 2,
        stream_callback: Callable[[StreamEvent], Awaitable[None]] = None,
        session: ArenaSession = None,  # 可选：外部预创建的 session（用于实时状态查询）
    ) -> ArenaSession:
        """执行完整辩论流程

        Args:
            question: 用户决策问题
            session_id: 会话 ID
            user_id: 用户 ID（用于所有权校验）
            user_options: 用户已考虑的选项
            num_perspectives: 视角数量
            debate_rounds: 辩论轮次
            stream_callback: SSE 事件回调
            session: 可选，外部预创建的 ArenaSession（辩论过程中可通过引用查询进度）

        Returns:
            ArenaSession 包含完整的辩论结果
        """
        if session is None:
            session = ArenaSession(
                id=session_id,
                user_id=user_id,
                question=question,
                user_options=user_options or [],
            )
        session.status = "running"
        start_time = time.time()

        async def emit(event: StreamEvent):
            if stream_callback:
                await stream_callback(event)

        try:
            # ===== Phase 1: 视角生成 =====
            debug.checkpoint("Phase 1", "视角生成")
            await emit(StreamEvent(
                type=StreamEventType.PHASE,
                data={"phase": "perspectives", "status": "generating"}
            ))

            perspectives = await self.perspective_generator.generate(
                question=question,
                num_perspectives=num_perspectives,
                user_options=user_options,
            )
            session.perspectives = perspectives

            await emit(StreamEvent(
                type=StreamEventType.PHASE,
                data={"phase": "perspectives", "status": "ready",
                      "perspectives": [
                          {"id": p.id, "name": p.name, "stance": p.stance}
                          for p in perspectives
                      ]}
            ))

            for p in perspectives:
                await emit(StreamEvent(
                    type=StreamEventType.PERSPECTIVE_READY,
                    data={"id": p.id, "name": p.name, "role_label": p.role_label,
                          "stance": p.stance}
                ))

            # ===== Phase 1.5: 自我介绍（每个角色发一条入群消息） =====
            debug.checkpoint("Phase 1.5", "自我介绍")
            intro_texts: dict[str, str] = {}  # 收集 intro 文本，后续写入 conversation_history
            for p in perspectives:
                await emit(StreamEvent(
                    type=StreamEventType.AGENT_STATUS,
                    data={"perspective_name": p.name, "status": "thinking"}
                ))

                # 构造个性化的自我介绍
                from .structured_models import get_personality_for
                personality = get_personality_for(p.name)

                intro_text = f"""大家好！我是「{p.name}」~ 👋

{personality['tone']}。我比较关注 {p.research_focus[:60]}。

不过说实话，我也有自己的盲区——{p.blind_spots[0] if p.blind_spots else '可能会忽略一些重要的东西'}，聊天的时候大家可以提醒我哈。

那咱们开始聊吧！"""

                intro_texts[p.id] = intro_text

                await emit(StreamEvent(
                    type=StreamEventType.SELF_INTRO,
                    data={
                        "perspective_name": p.name,
                        "perspective_id": p.id,
                        "text": intro_text,
                    }
                ))
                await emit(StreamEvent(
                    type=StreamEventType.AGENT_STATUS,
                    data={"perspective_name": p.name, "status": "idle"}
                ))

            # ===== Phase 2: 群聊轮次讨论（Multi-Agent Sequential Rounds）=====
            # 替代旧的研究+辩论阶段，采用顺序轮次多智能体群聊模式
            # 参考 AgentScope sequential_pipeline + MsgHub 模式
            debug.checkpoint("Phase 2", f"群聊讨论 ({debate_rounds + 1} 轮)")
            await emit(StreamEvent(
                type=StreamEventType.PHASE,
                data={"phase": "discussion", "status": "running"}
            ))

            discussion_rounds = max(1, debate_rounds)  # 至少 1 轮

            # 提前创建 conversation_history，先写入自我介绍，让 REST API 立即可查
            conversation_history: list[dict] = []
            session.conversation_history = conversation_history
            for p in perspectives:
                conversation_history.append({
                    "round": 0, "speaker": p.name, "speaker_id": p.id,
                    "text": intro_texts.get(p.id, ""),
                })

            conversation_history = await self._run_conversation_rounds(
                question=question,
                perspectives=perspectives,
                num_rounds=discussion_rounds,
                emit=emit,
                conversation_history=conversation_history,  # 复用已有列表
            )

            # 提取 arguments 用于兼容旧接口
            for p in perspectives:
                # 取该视角在所有轮次中的最后一条发言作为 summary
                p_speeches = [h for h in conversation_history if h["speaker_id"] == p.id]
                if p_speeches:
                    session.arguments[p.id] = p_speeches[-1]["text"]

            await emit(StreamEvent(
                type=StreamEventType.PHASE,
                data={"phase": "discussion", "status": "complete",
                      "total_rounds": discussion_rounds,
                      "total_speeches": len(conversation_history)}
            ))

            # ===== Phase 3: 裁判合成 =====
            debug.checkpoint("Phase 3", "裁判合成")
            await emit(StreamEvent(
                type=StreamEventType.PHASE,
                data={"phase": "synthesis", "status": "running"}
            ))

            judge_input = self._build_judge_input(
                question=question,
                perspectives=perspectives,
                arguments=session.arguments,
                conversation_history=conversation_history,
            )

            judge = create_judge_agent(
                name="judge",
                llm=self.llm,
                config=self.config,
            )

            decision_map = await judge.run(
                input_text=judge_input,
                stream_callback=emit,
            )
            session.decision_map = decision_map

            # 发送决策地图分块
            await emit(StreamEvent(
                type=StreamEventType.DECISION_MAP_CHUNK,
                data={"section": "full", "text": decision_map}
            ))

            await emit(StreamEvent(
                type=StreamEventType.PHASE,
                data={"phase": "synthesis", "status": "complete"}
            ))

            session.status = "completed"

        except Exception as e:
            session.status = "error"
            await emit(StreamEvent(
                type=StreamEventType.ERROR,
                data={"code": "ENGINE_ERROR", "message": str(e)}
            ))

        finally:
            session.total_time_ms = int((time.time() - start_time) * 1000)
            await emit(StreamEvent(
                type=StreamEventType.COMPLETE,
                data={
                    "session_id": session_id,
                    "status": session.status,
                    "total_time_ms": session.total_time_ms,
                }
            ))

        return session

    async def _run_conversation_rounds(
        self,
        question: str,
        perspectives: list[Perspective],
        num_rounds: int,
        emit,
        conversation_history: list[dict] = None,  # 外部传入（含自我介绍），复用同一个 list
    ) -> list[dict]:
        """顺序轮次多智能体群聊 —— 每轮内各 Agent 按固定顺序依次发言

        参考 AgentScope sequential_pipeline：每个 Agent 串行执行，前一个输出成为后一个的输入
        参考 AgentScope MsgHub.observe()： 每个 Agent 通过对话历史"听到"所有之前的发言

        核心设计：
        - 每轮内按 perspectives 固定顺序 p_01 → p_02 → ... → p_N 发言
        - 每个 Agent 是独立 LLM 调用（保留 multi-agent 特色）
        - 每个 Agent 看到完整对话历史（本轮前面的发言 + 之前所有轮次）
        - 顺序由串行 for 循环保证，不使用 asyncio.gather
        """
        from .structured_models import get_personality_for

        if conversation_history is None:
            conversation_history = []  # [{round, speaker, speaker_id, text}, ...]

        round_descriptions = {
            1: "开场陈述 —— 每个人说说自己的初步看法",
            2: "交叉回应 —— 听了大家的发言，你有什么想说的？",
            3: "深入辩论 —— 聚焦核心矛盾，深挖分歧点",
            4: "最后陈述 —— 每个人总结自己的最终立场",
        }

        for round_num in range(1, num_rounds + 1):
            description = round_descriptions.get(round_num, f"第{round_num}轮讨论")

            debug.hook("round_start", num=round_num, total=num_rounds)

            await emit(StreamEvent(
                type=StreamEventType.ROUND_START,
                data={
                    "round_number": round_num,
                    "total_rounds": num_rounds,
                    "description": description,
                }
            ))

            # Round 1 全部并行（开场陈述互不依赖），Round 2+ 串行（需回应前面的人）
            if round_num == 1:
                await self._run_round_1_parallel(
                    question=question,
                    perspectives=perspectives,
                    round_num=round_num,
                    total_rounds=num_rounds,
                    conversation_history=conversation_history,
                    emit=emit,
                )
            else:
                # 本轮发言顺序
                for i, p in enumerate(perspectives):
                    debug.hook("agent_turn", name=p.name, round=round_num)
                    # 1. 通知前端"谁在说话"
                    await emit(StreamEvent(
                        type=StreamEventType.AGENT_STATUS,
                        data={"perspective_name": p.name, "status": "thinking"}
                    ))

                    # 2. 构建完整 prompt（含对话历史）
                    history_text = self._build_conversation_history(
                        conversation_history, current_speaker=p.name
                    )
                    speech_prompt = self._build_speech_prompt(
                        question=question,
                        perspective=p,
                        round_num=round_num,
                        total_rounds=num_rounds,
                        conversation_history=history_text,
                    )

                    # 3. Agent 独立调用 LLM（每个 Agent 是独立的 LLM 调用！）
                    #    传入 emit 作为 stream_callback，让前端实时看到搜索/阅读进度
                    agent = create_react_agent(
                        name=f"chat_{p.id}_r{round_num}",
                        llm=self.llm,
                        perspective_name=p.name,
                        perspective_stance=p.stance,
                        tool_registry=self.tool_registry,
                        config=self.config,
                    )

                    try:
                        # 强制超时保护：超时后不会无限等待，降级到 fallback
                        argument = await asyncio.wait_for(
                            agent.run(input_text=speech_prompt, stream_callback=emit),
                            timeout=self.config.agent_timeout_seconds,
                        )
                    except asyncio.TimeoutError:
                        debug.hook("agent_nudge", reason=f"{p.name} 超时 ({self.config.agent_timeout_seconds}s)")
                        argument = self._agent_fallback_speech(p)
                    except Exception as exc:
                        debug.error(f"{p.name} 异常", str(exc)[:100])
                        argument = self._agent_fallback_speech(p)

                    # 4. 分块发送到前端
                    await emit(StreamEvent(
                        type=StreamEventType.AGENT_STATUS,
                        data={"perspective_name": p.name, "status": "composing"}
                    ))

                    chunks = self._split_into_chunks(argument, max_chars=2000)
                    for j, chunk in enumerate(chunks):
                        is_final = (j == len(chunks) - 1)
                        await emit(StreamEvent(
                            type=StreamEventType.SPEECH_CHUNK,
                            data={
                                "perspective_name": p.name,
                                "perspective_id": p.id,
                                "text": chunk,
                                "is_final": is_final,
                                "chunk_index": j,
                                "total_chunks": len(chunks),
                                "round_number": round_num,
                            }
                        ))
                        if not is_final:
                            await asyncio.sleep(0.8)  # 加快分块间隔：1.5s → 0.8s

                    await emit(StreamEvent(
                        type=StreamEventType.SPEECH_END,
                        data={
                            "perspective_name": p.name,
                            "perspective_id": p.id,
                        }
                    ))
                    await emit(StreamEvent(
                        type=StreamEventType.AGENT_STATUS,
                        data={"perspective_name": p.name, "status": "done"}
                    ))

                    # 5. 记录到对话历史
                    conversation_history.append({
                        "round": round_num,
                        "speaker": p.name,
                        "speaker_id": p.id,
                        "text": argument,
                    })

                    # 下一个人发言前等待 1 秒（模拟真人群聊节奏）
                    if i < len(perspectives) - 1:
                        await asyncio.sleep(1.0)

            # 本轮结束
            debug.hook("round_end", num=round_num)
            await emit(StreamEvent(
                type=StreamEventType.ROUND_END,
                data={"round_number": round_num}
            ))

            # 轮间暂停 1.5 秒
            if round_num < num_rounds:
                await asyncio.sleep(1.5)

        return conversation_history

    async def _run_round_1_parallel(
        self,
        question: str,
        perspectives: list[Perspective],
        round_num: int,
        total_rounds: int,
        conversation_history: list[dict],
        emit,
    ) -> None:
        """Round 1 并行执行 —— 5 个 Agent 同时搜+读，然后按顺序依次发言

        开场陈述互不依赖。并行研究把 5×60s=300s 的耗时压缩到 ~60s。

        ⚠️ 并行期间 agent 不接 stream_callback，避免 5 个 agent 的
        AGENT_STATUS 疯狂交叉轰炸前端，导致 typingNames 状态混乱和事件丢失。
        研究完成后按 perspectives 顺序 emit 发言。
        """
        from .structured_models import get_personality_for

        # 通知前端：所有 Agent 开始并行研究
        for p in perspectives:
            await emit(StreamEvent(
                type=StreamEventType.AGENT_STATUS,
                data={"perspective_name": p.name, "status": "searching"}
            ))

        async def run_one(p: Perspective) -> dict:
            """单个 Agent：搜→读→发言，静默运行（不 emit 避免交叉轰炸）"""
            debug.hook("agent_turn", name=p.name, round=round_num, mode="parallel")

            history_text = self._build_conversation_history(
                conversation_history, current_speaker=p.name
            )
            speech_prompt = self._build_speech_prompt(
                question=question,
                perspective=p,
                round_num=round_num,
                total_rounds=total_rounds,
                conversation_history=history_text,
            )

            agent = create_react_agent(
                name=f"chat_{p.id}_r{round_num}",
                llm=self.llm,
                perspective_name=p.name,
                perspective_stance=p.stance,
                tool_registry=self.tool_registry,
                config=self.config,
            )

            try:
                # stream_callback=None：并行期间静默，不往 SSE 发事件
                argument = await asyncio.wait_for(
                    agent.run(input_text=speech_prompt, stream_callback=None),
                    timeout=self.config.agent_timeout_seconds,
                )
            except asyncio.TimeoutError:
                debug.hook("agent_nudge", reason=f"{p.name} 超时 ({self.config.agent_timeout_seconds}s)")
                argument = self._agent_fallback_speech(p)
            except Exception as e:
                debug.error(f"{p.name} 并行异常", str(e)[:100])
                argument = self._agent_fallback_speech(p)

            return {
                "speaker": p.name,
                "speaker_id": p.id,
                "text": argument or self._agent_fallback_speech(p),
                "round": round_num,
            }

        # ═══ 并行执行所有 Agent ═══
        debug.hook("parallel_round_start", count=len(perspectives))
        results = await asyncio.gather(*[run_one(p) for p in perspectives])
        debug.hook("parallel_round_done", count=len([r for r in results if r]))

        # 研究完成，统一重置状态
        for p in perspectives:
            await emit(StreamEvent(
                type=StreamEventType.AGENT_STATUS,
                data={"perspective_name": p.name, "status": "idle"}
            ))

        # 按 perspectives 原始顺序排列
        id_order = [p.id for p in perspectives]
        results.sort(key=lambda r: id_order.index(r["speaker_id"]) if r else 999)

        # 按顺序依次 emit 发言（前端按正确顺序展示，每条间隔充足）
        valid_results = [r for r in results if r]
        for i, result in enumerate(valid_results):
            p = next((pp for pp in perspectives if pp.id == result["speaker_id"]), None)
            if not p:
                continue

            # 通知前端：该 Agent 正在发言
            await emit(StreamEvent(
                type=StreamEventType.AGENT_STATUS,
                data={"perspective_name": p.name, "status": "composing"}
            ))
            # 给前端短暂时间更新 typing 状态
            await asyncio.sleep(0.3)

            chunks = self._split_into_chunks(result["text"], max_chars=2000)
            for j, chunk in enumerate(chunks):
                is_final = (j == len(chunks) - 1)
                await emit(StreamEvent(
                    type=StreamEventType.SPEECH_CHUNK,
                    data={
                        "perspective_name": p.name,
                        "perspective_id": p.id,
                        "text": chunk,
                        "is_final": is_final,
                        "chunk_index": j,
                        "total_chunks": len(chunks),
                        "round_number": round_num,
                    }
                ))
                if not is_final:
                    await asyncio.sleep(0.8)  # Round 1 分块间隔：1.5s → 0.8s

            await emit(StreamEvent(
                type=StreamEventType.SPEECH_END,
                data={"perspective_name": p.name, "perspective_id": p.id}
            ))
            await emit(StreamEvent(
                type=StreamEventType.AGENT_STATUS,
                data={"perspective_name": p.name, "status": "done"}
            ))

            # 记录到对话历史
            conversation_history.append(result)

            # 下一个人发言前等待 1.5 秒（模拟真人群聊节奏）
            if i < len(valid_results) - 1:
                await asyncio.sleep(1.5)

    @staticmethod
    def _agent_fallback_speech(p: 'Perspective') -> str:
        """生成 Agent 的降级发言——当超时或异常时使用，至少 200 字才像真人"""
        try:
            personality = get_personality_for(p.name)
            catchphrase = personality.get("catchphrases", ["我觉得吧"])[0]
            tone = personality.get("tone", "")
        except Exception:
            catchphrase = "我觉得吧"
            tone = ""
        blind = ""
        try:
            blinds = p.blind_spots
            blind = f"当然我也知道，{blinds[0]}" if blinds else ""
        except Exception:
            pass

        return f"""{catchphrase}，关于「{p.stance}」这个角度，我有一些想法想跟大家聊聊。

说实话这个问题挺复杂的，从我的角度来看，核心其实在于怎么平衡各方面的考量。{p.stance}——这不是说其他角度不对，而是我觉得这个方向更值得重视。

{blind and f'{blind}，这是我一直提醒自己的。' or '我也知道自己有些方面可能想得不够全面，欢迎大家帮我补充。'}

其实类似的讨论我之前也关注过，很多人的看法差别挺大的，但这恰恰说明这个问题没有标准答案。每个人的经历和立场不一样，看到的东西自然不同。

{tone and f'我的性格可能比较{tone}，所以看问题会更偏向这个角度。' or ''}不过听大家聊了这么多，我觉得确实有很多我之前没想到的地方。期待听听大家怎么看，特别是跟我看法不一样的——你们的视角可能正好弥补我的盲区。"""

    def _build_conversation_history(
        self,
        history: list[dict],
        current_speaker: str = None,
    ) -> str:
        """将对话历史格式化为文本，供 Agent 理解上下文

        参考 AgentScope MsgHub.observe()：Agent 被动接收所有广播消息
        每个 Agent 在发言前看到完整的对话记录，包括自己之前的发言（标记"你"）
        """
        if not history:
            return "（这是讨论的开始，还没有人发言。作为第一个发言的人，请你先分享你的初步看法。）"

        lines = ["## 📜 之前的讨论记录"]

        current_round = None
        for entry in history:
            if entry["round"] != current_round:
                current_round = entry["round"]
                if current_round == 0:
                    lines.append("\n### 👋 入群介绍")
                else:
                    lines.append(f"\n### 🔄 第{current_round}轮")

            is_self = (entry["speaker"] == current_speaker)
            tag = "（你刚才说的）" if is_self else ""
            lines.append(f"【{entry['speaker']}】{tag}：\n{entry['text']}\n")

        lines.append("\n---")
        lines.append("上面是大家之前的发言。现在轮到你发言了。")
        return "\n".join(lines)

    def _build_speech_prompt(
        self,
        question: str,
        perspective,
        round_num: int,
        total_rounds: int,
        conversation_history: str,
    ) -> str:
        """构建每个 Agent 发言时的完整 prompt

        包含：角色设定 + 讨论主题 + 对话历史 + 本轮任务
        """
        from .structured_models import get_personality_for
        personality = get_personality_for(perspective.name)

        if round_num == 1:
            task = f"""这是第 1 轮讨论（共 {total_rounds} 轮）——开场陈述。

你的任务——按顺序执行，不要跳过任何一步：
1. 🔍 用 web_search 搜 1-2 次，了解"{question}"的最新情况
2. 📖 从搜索结果中选 1-2 个最相关的链接，用 web_fetch 打开阅读完整内容
   ⚠️ 必须读！只看摘要（一两百字）根本不够，一定要打开页面看完整文章
3. 💬 结合读到的具体信息，从你的视角分析，说说你最关注什么
4. 🎤 自然地开场，像在群里第一个说话的人

注意：搜完不读 = 白搜。摘要只是索引，正文才有数据、观点、细节。"""
        elif round_num == total_rounds:
            task = f"""这是最后一轮讨论（第 {round_num}/{total_rounds} 轮）——最后陈述。

你的任务：
1. 回顾前面大家的讨论，总结你的核心观点
2. 回应那些与你立场不同的人——承认他们说得对的地方，但也可以坚持你的判断
3. 说说经过这次讨论，你的想法有没有什么变化
4. 不用再搜资料了，基于讨论内容做总结"""
        else:
            task = f"""这是第 {round_num} 轮讨论（共 {total_rounds} 轮）——交叉回应。

你的任务：
1. 📖 仔细看看前面每个人的发言，找到你同意和不同意的具体观点
2. 💬 对你不同意的观点，礼貌地质疑或提出不同看法——用你自己的知识和之前读到的信息来反驳
3. ✅ 对你同意的观点，补充你的角度或者更深入的论据
4. 🎯 如果有人质疑了你的立场或者提到了你的盲区，认真回应
5. ⚠️ 这一轮重点是讨论和回应，不是收集新资料。除非前面讨论中出现了一个你完全不了解的新话题，否则不要搜索——直接用你已经知道的和第一轮查到的信息来讨论"""


        return f"""你是「{perspective.name}」—— {perspective.role_label}

## 🎭 你的性格
{personality['tone']}
说话风格：{personality['speaking_style']}
口头禅：{'、'.join(f'"{c}"' for c in personality['catchphrases'][:3])}
{personality['emoji_style']}

## 🏷️ 你的立场
{perspective.stance}
重点关注：{perspective.research_focus}
注意你的盲区：{'、'.join(perspective.blind_spots) if perspective.blind_spots else '无特别提示——但保持谦逊总是好的'}

## 💬 讨论主题
{question}

{conversation_history}

---

{task}

**发言要求（很重要！）：**
- 🗣️ 像微信群聊一样自然、口语化，不是写论文
- 🎭 保持你的性格特点和口头禅，做你自己
- 💬 前面有人说过话的话，记得回应他们（赞同/反对/补充都可以）
- 📏 400-1000 字比较合适，充分展开你的观点但别啰嗦
- ❌ 不要用 Markdown 格式、不要用 # 标题、不要列 1234
- ✅ 诚实地说出你的不确定和局限
- 😊 适当用 emoji 表达情绪"""

    def _split_into_chunks(self, text: str, max_chars: int = 350) -> list[str]:
        """将文本按自然段落分割成合适大小的块

        优先在段落边界分割，超长段落按句子边界分割。
        """
        # 先按双换行分段
        paragraphs = text.split('\n\n')
        chunks = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) + 2 <= max_chars:
                current = (current + '\n\n' + para).strip() if current else para
            else:
                if current:
                    chunks.append(current)

                # 如果单个段落仍然太长，按句子分割
                if len(para) > max_chars:
                    sentences = para.replace('。', '。||').replace('！', '！||').replace('？', '？||').split('||')
                    sub = ""
                    for s in sentences:
                        s = s.strip()
                        if not s:
                            continue
                        if len(sub) + len(s) <= max_chars:
                            sub = (sub + s) if sub else s
                        else:
                            if sub:
                                chunks.append(sub)
                            sub = s
                    if sub:
                        current = sub
                    else:
                        current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        return chunks if chunks else [text]

    def _build_judge_input(
        self,
        question: str,
        perspectives: list[Perspective],
        arguments: dict[str, str],
        conversation_history: list[dict] = None,
    ) -> str:
        """构建裁判的输入——汇总群聊讨论的所有信息"""
        parts = [f"# 决策问题\n{question}\n"]

        parts.append("# 各视角立场\n")
        for p in perspectives:
            parts.append(f"## {p.name}（{p.role_label}）")
            parts.append(f"立场: {p.stance}")
            parts.append(f"关注点: {p.research_focus}")
            parts.append(f"盲点: {', '.join(p.blind_spots) if p.blind_spots else '无'}")
            parts.append("")

        if conversation_history:
            parts.append("# 完整群聊讨论记录\n")
            current_round = None
            for entry in conversation_history:
                if entry["round"] != current_round:
                    current_round = entry["round"]
                    label = "## 入群介绍\n" if current_round == 0 else f"\n## 第{current_round}轮\n"
                    parts.append(label)
                parts.append(f"【{entry['speaker']}】：{entry['text']}\n")
            parts.append("")

        return "\n".join(parts)

