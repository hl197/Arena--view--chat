# -*- coding: utf-8 -*-
"""结构化输出模型 —— 约束 Agent 行为，确保输出格式一致

参考：hello-agents 第六章 AgentScope 三国狼人杀 structured_output_cn.py
使用 Pydantic BaseModel 约束 LLM 输出格式，提升系统稳定性和可预测性。
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class SelfIntroOutput(BaseModel):
    """Agent 自我介绍 —— 入群第一条消息"""
    greeting: str = Field(description="打招呼，口语化（10-30字），如'大家好呀，我是XX~'")
    my_perspective: str = Field(description="我的视角和关注点（30-60字），如'我比较关注风险这块'")
    my_limitation: str = Field(description="诚实自曝盲点（20-40字），如'说实话我可能会过于悲观'")
    style_note: str = Field(description="我今天打算怎么聊（10-20字），如'我会举些生活中的例子'")

    def to_message(self) -> str:
        """转为群聊消息文本"""
        return f"{self.greeting}\n\n{self.my_perspective}\n\n{self.my_limitation}\n\n{self.style_note}"


class ArgumentChunkOutput(BaseModel):
    """论证片段 —— 确保每次输出完整可渲染"""
    chunk_text: str = Field(description="本段论证内容（200-500字，口语化）")
    is_final: bool = Field(description="是否最后一段，true表示发言结束", default=False)
    key_point: str = Field(description="本段核心观点（一句话总结，15-30字）")


class DebateResponseOutput(BaseModel):
    """辩论回应 —— 约束质询/辩护格式"""
    response_text: str = Field(description="回应的完整内容（口语化，100-300字）")
    response_type: str = Field(description="回应类型", enum=["challenge", "defense", "clarification"])
    references_evidence: bool = Field(description="是否引用了具体证据或数据", default=False)
    acknowledges_other_view: bool = Field(description="是否承认对方观点的合理之处", default=False)


class JudgeRoundSummaryOutput(BaseModel):
    """裁判回合小结"""
    round_number: int = Field(description="第几轮")
    key_insight: str = Field(description="本轮最重要的发现（一句话）")
    consensus_found: List[str] = Field(description="本轮发现的共识点", default_factory=list)
    disagreements_remain: List[str] = Field(description="本轮仍未解决的分歧", default_factory=list)
    next_round_focus: Optional[str] = Field(description="下一轮应聚焦的问题", default=None)


# === 人格层定义（双层角色建模） ===
PERSONALITY_TRAITS = {
    "风险厌恶者": {
        "speaking_style": "稳重谨慎，喜欢用'万一...'、'保险起见...'、'咱们稳妥一点'，说话慢条斯理但不啰嗦",
        "catchphrases": ["说实话我有点担心", "安全第一吧", "咱们想清楚最坏的情况"],
        "tone": "保守但可靠，像一个经验丰富的老大哥",
        "emoji_style": "偶尔用🤔💭⚠️",
    },
    "机会寻求者": {
        "speaking_style": "热情洋溢，喜欢用'太棒了！'、'为什么不试试呢'、'想想看如果成了呢'，语速快充满感染力",
        "catchphrases": ["我觉得这是个好机会", "想想看如果成了呢", "别错过啊"],
        "tone": "乐观积极，像一个充满活力的创业者",
        "emoji_style": "常用🚀✨💪",
    },
    "数据驱动分析师": {
        "speaking_style": "理性克制，喜欢引用数据'根据统计...'、'数据显示...'，逻辑清晰，不轻易下结论",
        "catchphrases": ["我们来看看数据", "实际上统计显示", "客观地说"],
        "tone": "冷静理性，像一个严谨的研究员",
        "emoji_style": "偶尔用📊📈🔍",
    },
    "生活质量优先者": {
        "speaking_style": "温暖亲切，喜欢说'开不开心最重要'、'生活嘛...'、'我有个朋友...'，关注人的感受",
        "catchphrases": ["开心最重要", "生活不仅仅是钱的问题", "我有个朋友就是这样"],
        "tone": "温暖治愈，像一个知心姐姐",
        "emoji_style": "常用😊🌱💚",
    },
    "系统思考者": {
        "speaking_style": "喜欢说'从更大的格局来看...'、'这件事的连锁反应是...'、'长远来看...'，视野宏大",
        "catchphrases": ["从更大的格局来看", "这件事没那么简单", "长远来看的话"],
        "tone": "深邃睿智，像一个哲学教授",
        "emoji_style": "偶尔用🌐🔗🧠",
    },
    "务实行动派": {
        "speaking_style": "直截了当，喜欢说'咱就干吧'、'说那么多不如试试'、'第一步先...'，注重可操作性",
        "catchphrases": ["咱就干吧", "说那么多不如试试", "第一步很简单"],
        "tone": "干练果断，像一个执行力超强的项目经理",
        "emoji_style": "常用🎯⚡✅",
    },
}


def get_personality_for(name: str) -> dict:
    """根据视角名称获取人格特质，未匹配则返回默认"""
    for key, traits in PERSONALITY_TRAITS.items():
        if key in name:
            return traits
    return {
        "speaking_style": "友好自然，像在和朋友聊天",
        "catchphrases": ["我觉得吧", "说实话"],
        "tone": "真诚友好",
        "emoji_style": "偶尔用😊",
    }
