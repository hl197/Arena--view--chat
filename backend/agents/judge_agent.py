"""裁判 Agent —— Reflection 模式

裁判不是"判对错"，而是"画决策地图"。
使用 Reflection 模式：初始合成 → 自审 → 改进。
"""

from .base import Agent
from ..core.streaming import StreamEvent, StreamEventType
from ..core.debug_hooks import debug


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
- 像在群里发消息一样，口语化、自然，让人愿意读下去
- 不要用论文格式，不要用 Markdown 标题（## ### 等）
- 说"咱们来看看"、"其实大家的共识是"、"分歧主要在"这样的表达
- 诚实标注不确定的地方，这比假装什么都懂更有价值

你需要完整梳理这场讨论，让用户看清楚"大家聊了什么、怎么聊的、聊出了什么"。包含以下内容：

**📋 讨论全貌**（2-3 段）
- 这场讨论的核心问题是什么
- 一共有几轮讨论，每轮的氛围和重点有什么不同
- 谁提出了什么关键观点

**🤝 共识区**
- 大家在哪些点上达成了一致（哪怕是表面的）
- 这些共识有多牢固？有没有人嘴上同意但理由完全不同？

**⚡ 分歧区**（这是最有价值的部分）
- 核心分歧在哪？不是"A觉得好 B觉得不好"这种表面分歧
- 而是"A看重长期风险 B看重短期机会"这种底层价值观差异
- 列出每位成员的立场演变：从第一轮到最后一轮，谁的观点变了？怎么变的？

**📊 权衡维度**（6-8个）
- 从哪些角度来思考这件事？每个维度的正反两面
- 引用讨论中的具体发言来说明

**❓ 未知因素**
- 我们还不知道什么？（这些可能彻底改变判断）
- 如果知道了哪些信息，结论可能会翻转？

**⚠️ 风险矩阵**
- 各种选择最坏会怎样？概率大吗？

**🪞 我的偏见声明**
- 我作为裁判，在梳理时可能不自觉地偏向/忽略了什么
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
        debug.hook("custom", text="🧠 裁判 开始生成决策地图")
        synthesis_prompt = f"""{self._build_system_prompt()}

请基于以下信息，生成初始决策地图：

{input_text}

按照系统提示词中定义的 所有部分完整输出。每个部分都要充分展开，不能说"略"或一笔带过。"""

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
            debug.hook("reflection", iteration=iteration)
            # 自审
            reflect_prompt = f"""请严格审查你自己生成的决策地图，从以下角度：

原始决策地图：
{current_result}

审查清单：
1. **完整性**：每个部分是否都充分展开？有没有草草收尾的地方？
2. **讨论链**：是否清晰展示了每位成员从第一轮到最后一轮的立场演变？有没有遗漏关键转折？
3. **偏见检查**：你是否不自觉地偏向某个视角？
4. **遗漏检查**：有没有重要的权衡维度或风险被遗漏？
5. **假共识检查**：标记为"共识"的点，是否真正被所有视角同意？
6. **确定性检查**：你对哪些判断过于自信？标记出来。

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
{current_result}

自审反馈：
{feedback}

请输出改进后的完整决策地图（包含全部 7 个部分）。"""
            messages = [{"role": "user", "content": refine_prompt}]
            current_result = (await self.llm.ainvoke(messages)).content

        debug.hook("custom", text=f"✅ 裁判 决策地图完成 ({len(current_result)}字)")
        return current_result
