"""辩论调度器 —— 轮转交叉质询

协调多个视角 Agent 之间的交叉质询。
策略：
- 第1轮：最大分歧配对（每个视角质疑一个与自己立场最相反的视角）
- 第2轮：Judge 识别 2-3 个核心矛盾，聚焦深挖
- 第3轮（仅按需）：存在可通过额外信息解决的根本分歧
"""

from dataclasses import dataclass, field
from typing import Optional, Callable
from .perspective_generator import Perspective
from ..agents.react_agent import ReActAgent
from ..agents.judge_agent import JudgeAgent
from ..core.streaming import StreamEvent, StreamEventType


@dataclass
class DebateTurn:
    """辩论中的一轮"""
    round: int
    challenger_id: str
    challenger_name: str
    defender_id: str
    defender_name: str
    challenge: str = ""
    defense: str = ""
    judge_note: str = ""
    key_disagreement: str = ""  # 核心分歧点


@dataclass
class DebateResult:
    """辩论结果"""
    turns: list[DebateTurn] = field(default_factory=list)
    total_rounds: int = 0
    unresolved_issues: list[str] = field(default_factory=list)
    resolved_issues: list[str] = field(default_factory=list)


class DebateScheduler:
    """辩论调度器——管理交叉质询流程"""

    def __init__(self, llm, config):
        self.llm = llm
        self.config = config

    def schedule_pairs(self, perspectives: list[Perspective],
                       arguments: dict[str, str],
                       round_num: int = 1,
                       focus_issues: list[str] = None) -> list[tuple[str, str]]:
        """生成辩论配对——每个视角质疑一个对手

        Args:
            perspectives: 所有视角
            arguments: {perspective_id: argument_text}
            round_num: 第几轮
            focus_issues: 第2轮时聚焦的具体议题

        Returns:
            [(challenger_id, defender_id), ...] 配对列表
        """
        if round_num == 1:
            # 第1轮：最大分歧配对
            return self._pair_by_divergence(perspectives)
        else:
            # 第2+轮：聚焦配对
            return self._pair_by_focus(perspectives, focus_issues or [])

    def _pair_by_divergence(self, perspectives: list[Perspective]) -> list[tuple[str, str]]:
        """按最大分歧配对——每个视角挑战价值观最相反的视角"""
        pairs = []
        ids = [p.id for p in perspectives]
        paired = set()

        for i, p1 in enumerate(perspectives):
            if p1.id in paired:
                continue

            # 找价值观重叠最少的视角
            p1_values = set(p1.core_values)
            best_opponent = None
            best_score = float("inf")

            for j, p2 in enumerate(perspectives):
                if i == j or p2.id in paired:
                    continue
                overlap = len(p1_values & set(p2.core_values))
                if overlap < best_score:
                    best_score = overlap
                    best_opponent = p2

            if best_opponent:
                pairs.append((p1.id, best_opponent.id))
                paired.add(p1.id)
                paired.add(best_opponent.id)

        # 如果剩一个（奇数），让它挑战已经配对的第一个
        unpaired = [p for p in perspectives if p.id not in paired]
        if unpaired and pairs:
            pairs.append((unpaired[0].id, pairs[0][0]))

        return pairs

    def _pair_by_focus(self, perspectives: list[Perspective],
                       focus_issues: list[str]) -> list[tuple[str, str]]:
        """聚焦配对——让在焦点议题上立场最对立的视角辩论"""
        # 简化版：正向循环配对
        ids = [p.id for p in perspectives]
        pairs = []
        for i in range(len(ids)):
            pairs.append((ids[i], ids[(i + 1) % len(ids)]))
        return pairs[:len(perspectives)]

    async def run_turn(self, challenger_name: str, defender_name: str,
                       challenger_agent: ReActAgent, defender_agent: ReActAgent,
                       defender_argument: str, round_num: int,
                       stream_callback=None) -> DebateTurn:
        """执行一轮辩论

        挑战方研究防守方论点 → 提出质疑 → 防守方回应
        """
        turn = DebateTurn(
            round=round_num,
            challenger_id=challenger_agent.name,
            challenger_name=challenger_name,
            defender_id=defender_agent.name,
            defender_name=defender_name,
        )

        if stream_callback:
            import asyncio
            asyncio.create_task(stream_callback(StreamEvent(
                type=StreamEventType.DEBATE_TURN_START,
                data={
                    "round": round_num,
                    "challenger_name": challenger_name,
                    "defender_name": defender_name,
                }
            )))

        # Step 1: 挑战方分析防守方论点 → 提出质疑
        challenge_prompt = f"""你是「{challenger_name}」视角的分析师。

请审阅「{defender_name}」视角的论证，找出其逻辑漏洞、证据不足、盲点和假设问题。

对方论证:
{defender_argument[:3000]}

请提出 2-3 个具体的质疑：
1. 聚焦对方论证的薄弱环节
2. 引用具体的数据或逻辑矛盾
3. 质疑不是人身攻击，是有理有据的推敲

输出格式：每个质疑以「质疑N：」开头，包含具体问题和你认为对方可能忽略的方面。"""

        challenge_response = await self.llm.ainvoke([{"role": "user", "content": challenge_prompt}])
        turn.challenge = challenge_response.content

        if stream_callback:
            import asyncio
            asyncio.create_task(stream_callback(StreamEvent(
                type=StreamEventType.DEBATE_CHUNK,
                data={
                    "role": "challenger",
                    "perspective_name": challenger_name,
                    "text": turn.challenge[:300],
                }
            )))

        # Step 2: 防守方回应
        defense_prompt = f"""你是「{defender_name}」视角的分析师。

你的论证被「{challenger_name}」提出了以下质疑：

{challenge_response.content}

请逐条回应：
1. 承认对方质疑中合理的部分（如果有）
2. 对不合理的质疑进行反驳，用数据/逻辑支撑
3. 如果质疑暴露了你论证的真实漏洞，诚实承认并说明如何修正
4. 重申你立场中仍然成立的核心论点"""

        defense_response = await self.llm.ainvoke([{"role": "user", "content": defense_prompt}])
        turn.defense = defense_response.content

        if stream_callback:
            import asyncio
            asyncio.create_task(stream_callback(StreamEvent(
                type=StreamEventType.DEBATE_CHUNK,
                data={
                    "role": "defender",
                    "perspective_name": defender_name,
                    "text": turn.defense[:300],
                }
            )))

        # Step 3: Judge 评议
        judge_note_prompt = f"""你是辩论裁判。以下是一轮交叉质询：

挑战方「{challenger_name}」的质疑：
{challenge_response.content[:500]}

防守方「{defender_name}」的回应：
{defense_response.content[:500]}

请用一句话总结本轮的核心分歧点。格式：
核心分歧：[一句话描述两个视角的根本分歧]
是否达成共识：是/否（如果防守方承认了质疑，则标记为部分共识）"""

        judge_response = await self.llm.ainvoke([{"role": "user", "content": judge_note_prompt}])
        turn.judge_note = judge_response.content[:300]

        if stream_callback:
            import asyncio
            asyncio.create_task(stream_callback(StreamEvent(
                type=StreamEventType.DEBATE_TURN_END,
                data={
                    "round": round_num,
                    "challenger_name": challenger_name,
                    "defender_name": defender_name,
                    "judge_note": turn.judge_note,
                }
            )))

        return turn
