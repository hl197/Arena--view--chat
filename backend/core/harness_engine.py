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
from ..tools.registry import ToolRegistry
from ..tools.builtin.web_search import WebSearchTool
from ..tools.builtin.finish_tool import FinishTool


@dataclass
class ArenaSession:
    """一次辩论会话"""
    id: str
    question: str
    user_options: list[str] = field(default_factory=list)
    perspectives: list[Perspective] = field(default_factory=list)
    arguments: dict[str, str] = field(default_factory=dict)   # perspective_id -> argument
    debate_turns: list[DebateTurn] = field(default_factory=list)
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
        user_options: list[str] = None,
        num_perspectives: int = 5,
        debate_rounds: int = 2,
        stream_callback: Callable[[StreamEvent], Awaitable[None]] = None,
    ) -> ArenaSession:
        """执行完整辩论流程

        Args:
            question: 用户决策问题
            session_id: 会话 ID
            user_options: 用户已考虑的选项
            num_perspectives: 视角数量
            debate_rounds: 辩论轮次
            stream_callback: SSE 事件回调

        Returns:
            ArenaSession 包含完整的辩论结果
        """
        session = ArenaSession(
            id=session_id,
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
            await emit(StreamEvent(
                type=StreamEventType.PHASE,
                data={"phase": "discussion", "status": "running"}
            ))

            discussion_rounds = max(1, debate_rounds + 1)  # 至少 1 轮，默认 2-3 轮
            conversation_history = await self._run_conversation_rounds(
                question=question,
                perspectives=perspectives,
                num_rounds=discussion_rounds,
                emit=emit,
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

            # ===== Phase 4: 裁判合成 =====
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

        conversation_history: list[dict] = []  # [{round, speaker, speaker_id, text}, ...]

        round_descriptions = {
            1: "开场陈述 —— 每个人说说自己的初步看法",
            2: "交叉回应 —— 听了大家的发言，你有什么想说的？",
            3: "深入辩论 —— 聚焦核心矛盾，深挖分歧点",
            4: "最后陈述 —— 每个人总结自己的最终立场",
        }

        for round_num in range(1, num_rounds + 1):
            description = round_descriptions.get(round_num, f"第{round_num}轮讨论")

            await emit(StreamEvent(
                type=StreamEventType.ROUND_START,
                data={
                    "round_number": round_num,
                    "total_rounds": num_rounds,
                    "description": description,
                }
            ))

            # 本轮发言顺序
            for i, p in enumerate(perspectives):
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
                agent = create_react_agent(
                    name=f"chat_{p.id}_r{round_num}",
                    llm=self.llm,
                    perspective_name=p.name,
                    perspective_stance=p.stance,
                    tool_registry=self.tool_registry,
                    config=self.config,
                )

                try:
                    argument = await agent.run(input_text=speech_prompt)
                except Exception:
                    # 容错：生成降级回应
                    personality = get_personality_for(p.name)
                    catchphrase = personality.get("catchphrases", ["我觉得吧"])[0]
                    argument = f"{catchphrase}，关于这个问题，从我的角度来看，{p.stance}。不过前面大家聊了这么多，我也在思考。{p.blind_spots[0] if p.blind_spots else '有些方面我可能还没想透'}。"

                # 4. 分块发送到前端
                await emit(StreamEvent(
                    type=StreamEventType.AGENT_STATUS,
                    data={"perspective_name": p.name, "status": "composing"}
                ))

                chunks = self._split_into_chunks(argument, max_chars=350)
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
                        await asyncio.sleep(1.5)

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

                # 下一个人发言前等待 2 秒（模拟真人群聊节奏）
                if i < len(perspectives) - 1:
                    await asyncio.sleep(2)

            # 本轮结束
            await emit(StreamEvent(
                type=StreamEventType.ROUND_END,
                data={"round_number": round_num}
            ))

            # 轮间暂停 3 秒
            if round_num < num_rounds:
                await asyncio.sleep(3)

        return conversation_history

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

你的任务：
1. 先从你的视角分析一下"{question}"
2. 说说你最关注什么、最担心什么
3. 可以搜 1-2 次资料来支撑你的观点
4. 自然地开场，像在群里第一个说话的人

注意：这是开场，不用回应别人（还没人说过话），重点是把你的初步看法说出来。"""
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
1. 看看前面大家的发言，找到你同意和不同意的点
2. 对你不同意的观点，礼貌地提出你的质疑或不同看法
3. 对你同意的观点，可以补充更多论据
4. 如果有人提到了你的盲区或质疑了你的立场，请回应
5. 可以搜 1 次资料来支撑你的反驳"""

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
- 📏 200-500 字就够了，别写太长
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
                    parts.append(f"\n## 第{current_round}轮\n")
                parts.append(f"【{entry['speaker']}】：{entry['text']}\n")
            parts.append("")

        return "\n".join(parts)
