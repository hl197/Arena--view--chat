"""裁判 Agent —— Reflection 模式

裁判不是"判对错"，而是"画决策地图"。
使用 Reflection 模式：初始合成 → 自审 → 改进。
"""

from .base import Agent
from ..core.streaming import StreamEvent, StreamEventType


class JudgeAgent(Agent):
    """裁判 Agent —— 使用 Reflection 模式生成决策地图

    两阶段：
    1. INITIAL SYNTHESIS: 审查所有论证+辩论记录 → 草拟决策地图
    2. SELF-REFLECTION: 自审草稿 → 检查偏见/遗漏/假共识
    3. REFINEMENT: 改进 → 输出最终决策地图

    关键约束：裁判不给出推荐，只帮用户理解决策全貌。
    """

    def __init__(self, name: str, llm, **kwargs):
        super().__init__(name=name, llm=llm, **kwargs)
        self.max_iterations = 2  # Reflection 最多 2 轮

    def _build_system_prompt(self) -> str:
        return """你是群聊里的裁判。大家在群里讨论一个决策问题，你需要帮大家梳理讨论内容，但绝不能替人做决定。

说话风格：
- 像在群里发消息一样，口语化、自然
- 不要用论文格式，不要用 Markdown 标题
- 说"咱们来看看"、"其实大家的共识是"、"分歧主要在"这样的表达
- 诚实标注不确定的地方，这比假装什么都懂更有价值

你需要帮大家理清这些：
1. 这个问题的核心是什么（一句话）
2. 大家都同意什么（共识区）
3. 大家分歧在哪（这恰恰是用户需要自己判断的地方）
4. 从哪些角度来权衡这件事（6-8个维度）
5. 我们还不知道什么（这些未知因素可能改变整个判断）
6. 各种选择有什么风险
7. 我有什么可能的偏见需要大家注意
"""

    async def run(self, input_text: str, stream_callback=None, **kwargs) -> str:
        """运行裁判流程——Reflection 循环

        Args:
            input_text: 包含所有论证+辩论记录的完整输入

        Returns:
            完整决策地图文本
        """
        self.reset()

        # Phase 1: 初始合成
        synthesis_prompt = f"""{self._build_system_prompt()}

请基于以下信息，生成初始决策地图：

{input_text}

按照系统提示词中定义的 7 个部分输出。每部分用小标题标注。"""

        messages = [{"role": "user", "content": synthesis_prompt}]
        current_result = (await self.llm.ainvoke(messages)).content

        if stream_callback:
            import asyncio
            asyncio.create_task(stream_callback(StreamEvent(
                type=StreamEventType.SYNTHESIS_START,
                data={"phase": "initial_synthesis"}
            )))

        # Phase 2-3: Reflection → Refinement
        for iteration in range(1, self.max_iterations + 1):
            # 自审
            reflect_prompt = f"""请严格审查你自己生成的决策地图，从以下角度：

原始决策地图：
{current_result[:4000]}

审查清单：
1. **偏见检查**：你是否不自觉地偏向某个视角？在权衡维度上是否给予某些论点更多权重？
2. **遗漏检查**：有没有重要的权衡维度被遗漏？
3. **假共识检查**：标记为"共识"的点，是否真正被所有视角同意？还是只是表面一致但理由不同？
4. **论证强度**：每个视角的论证强度是否被公平评估？有没有某个视角因为表达更好而获得不应有的权重？
5. **确定性检查**：你是否对某些判断过于自信？哪些结论实际上需要更多数据支撑？

如果发现明显问题，请改进决策地图并输出完整的新版本。
如果没有明显问题，回复 "无需改进"。"""

            messages = [{"role": "user", "content": reflect_prompt}]
            feedback = (await self.llm.ainvoke(messages)).content

            if stream_callback:
                import asyncio
                asyncio.create_task(stream_callback(StreamEvent(
                    type=StreamEventType.SELF_REFLECTION,
                    data={"iteration": iteration, "text": feedback[:300]}
                )))

            # 检查停止条件
            if "无需改进" in feedback:
                break

            # 改进
            refine_prompt = f"""请基于以下自审反馈，改进你的决策地图：

原始决策地图：
{current_result[:3000]}

自审反馈：
{feedback[:2000]}

请输出改进后的完整决策地图（包含全部 7 个部分）。"""
            messages = [{"role": "user", "content": refine_prompt}]
            current_result = (await self.llm.ainvoke(messages)).content

        return current_result
