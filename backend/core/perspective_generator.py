"""视角生成器 —— 信息不对称注入策略

ArenaView 的核心差异化组件。
不是让 LLM "假装"不同立场，而是给每个视角注入不同的：
- 核心价值观（决定什么更重要）
- 初始已知事实（决定从哪开始看）
- 分析框架（决定怎么思考）
- 明确盲点（决定会漏掉什么）

这样同一个 LLM 产出真正有差异的观点。
"""

from dataclasses import dataclass, field
from typing import Optional
from ..adapters.unified_llm import ArenaLLM


@dataclass
class Perspective:
    """单个视角定义"""
    id: str
    name: str                        # "风险厌恶者"
    role_label: str                  # "保守实用主义者 —— 关注最坏情况"
    stance: str                      # "在当前市场环境下应优先租房而非买房"
    core_values: list[str] = field(default_factory=list)
    research_focus: str = ""         # 重点研究方向
    known_facts: list[str] = field(default_factory=list)   # 该视角已知的事实
    blind_spots: list[str] = field(default_factory=list)   # 该视角容易忽略的
    analysis_framework: str = ""     # 分析框架


# === 6 种基础视角原型 ===
PERSPECTIVE_ARCHETYPES = [
    {
        "role_label": "风险厌恶者",
        "core_values": ["确定性", "安全", "可预测性", "止损"],
        "research_focus": "最坏情况分析、潜在损失、失败概率",
        "analysis_framework": "风险收益比——优先评估下行风险，再看上行空间",
        "blind_spots": ["可能过度悲观", "忽略机会成本", "低估自身抗风险能力"],
    },
    {
        "role_label": "机会寻求者",
        "core_values": ["成长", "潜力", "灵活性", "上行空间"],
        "research_focus": "最佳情况分析、增长潜力、未来可能性",
        "analysis_framework": "实物期权视角——任何决策都是一份期权，评估上行空间是否值得",
        "blind_spots": ["可能低估执行难度", "忽略隐性成本", "过度乐观假设"],
    },
    {
        "role_label": "数据驱动分析师",
        "core_values": ["客观数据", "统计趋势", "量化指标", "可验证性"],
        "research_focus": "历史数据对比、统计回归、行业基准",
        "analysis_framework": "数据驱动——寻找历史数据中的规律，量化每个选项的预期值",
        "blind_spots": ["过度依赖历史数据，忽略结构性变化", "数据可能滞后", "量化指标不能反映一切"],
    },
    {
        "role_label": "生活质量优先者",
        "core_values": ["幸福感", "关系质量", "心理健康", "生活平衡"],
        "research_focus": "对日常生活的实际影响、主观幸福感变化",
        "analysis_framework": "幸福经济学——金钱只是工具，最终目的是提升生活质量",
        "blind_spots": ["可能忽略财务可持续性", "主观感受难以量化", "短期舒适 vs 长期发展"],
    },
    {
        "role_label": "系统思考者",
        "core_values": ["复杂系统", "二阶效应", "长期后果", "连锁反应"],
        "research_focus": "决策的系统性影响、间接后果、多方利益",
        "analysis_framework": "系统动力学——每个决策都会引发连锁反应，需要追踪到二阶、三阶效应",
        "blind_spots": ["分析过度导致瘫痪", "可能忽视紧迫性", "简单方案可能被复杂化"],
    },
    {
        "role_label": "务实行动派",
        "core_values": ["可执行性", "效率", "现实约束", "最快路径"],
        "research_focus": "最短路径到可行方案、执行难度、时间成本",
        "analysis_framework": "约束满足——在现实约束下（时间/金钱/能力），找到最可行的方案",
        "blind_spots": ["可能过早排除创新方案", "短期最优 ≠ 长期最优", "忽略价值观层面"],
    },
]


class PerspectiveGenerator:
    """视角生成器——输入问题，输出 4-6 个有信息差的视角"""

    def __init__(self, llm: ArenaLLM):
        self.llm = llm
        self.archetypes = PERSPECTIVE_ARCHETYPES

    async def generate(self, question: str, num_perspectives: int = 5,
                 user_options: list[str] = None,
                 user_values: dict = None) -> list[Perspective]:
        """为核心问题生成视角

        Args:
            question: 用户决策问题
            num_perspectives: 视角数量 3-6
            user_options: 用户已考虑的选项 ["买房", "租房"]
            user_values: 用户偏好的价值权重 {"安全": 0.8, "成长": 0.4}

        Returns:
            Perspective 列表
        """
        num = max(3, min(num_perspectives, len(self.archetypes)))

        # 用 LLM 为这个问题定制视角
        custom_perspectives = await self._generate_custom(question, num, user_options)

        # 如果 LLM 生成成功，用定制的；否则用原型
        if custom_perspectives and len(custom_perspectives) >= num:
            return custom_perspectives[:num]

        # 降级：直接用原型 + 问题上下文
        return self._generate_from_archetypes(question, num, user_options)

    async def _generate_custom(self, question: str, num: int,
                         user_options: list[str] = None) -> list[Perspective]:
        """用 LLM 为特定问题生成定制化视角"""
        archetype_text = "\n".join(
            f"- {a['role_label']}: 关注 {a['research_focus']}"
            for a in self.archetypes
        )

        options_text = ""
        if user_options:
            options_text = f"\n用户已考虑的选项: {', '.join(user_options)}"

        prompt = f"""你是一个决策分析专家。针对以下用户困境，生成 {num} 个不同的分析视角。

用户问题: {question}{options_text}

可用的视角原型:
{archetype_text}

要求:
1. 每个视角要有独特的关注点和分析框架
2. 视角之间不能雷同——要有真正的观点差异
3. 为每个视角设定具体的立场（对某选项支持/反对/中立观察）
4. 每个视角要有明确的研究方向

输出 JSON 数组，每个元素包含:
{{
  "name": "视角称呼（4-6字，如'风险优先者'）",
  "role_label": "角色描述（如'关注下行风险和最大损失的保守分析师'）",
  "stance": "该视角的初步立场（一句话）",
  "core_values": ["价值1", "价值2", "价值3"],
  "research_focus": "该视角应重点搜索和研究的方面",
  "blind_spots": ["该视角容易忽略的方面1", "方面2"],
  "analysis_framework": "该视角的分析框架（如'风险收益比优先'）"
}}

只输出 JSON 数组，不要其他文本。"""

        try:
            response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
            content = response.content.strip()

            # 提取 JSON
            import json
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            data = json.loads(content)

            perspectives = []
            for i, item in enumerate(data):
                p = Perspective(
                    id=f"p_{i+1:02d}",
                    name=item.get("name", f"视角{i+1}"),
                    role_label=item.get("role_label", ""),
                    stance=item.get("stance", ""),
                    core_values=item.get("core_values", []),
                    research_focus=item.get("research_focus", ""),
                    blind_spots=item.get("blind_spots", []),
                    analysis_framework=item.get("analysis_framework", ""),
                )
                perspectives.append(p)

            return perspectives

        except Exception:
            return []

    def _generate_from_archetypes(self, question: str, num: int,
                                  user_options: list[str] = None) -> list[Perspective]:
        """降级方案：直接用原型模板"""
        options_context = ""
        if user_options:
            options_context = f" 可选方案: {' / '.join(user_options)}。"

        perspectives = []
        for i, archetype in enumerate(self.archetypes[:num]):
            perspectives.append(Perspective(
                id=f"p_{i+1:02d}",
                name=archetype["role_label"],
                role_label=f"{archetype['role_label']} —— {archetype['research_focus']}",
                stance=f"从{archetype['role_label']}角度分析：{question}",
                core_values=archetype["core_values"],
                research_focus=archetype["research_focus"],
                known_facts=[],
                blind_spots=archetype["blind_spots"],
                analysis_framework=archetype["analysis_framework"],
            ))

        return perspectives

    def build_research_prompt(self, perspective: Perspective, question: str) -> str:
        """为特定视角构建研究提示词——注入信息不对称 + 人格层 + 口语化聊天风格

        参考：hello-agents CAMEL Inception Prompting ——
        告知自身角色 + 告知盲点 + 定义目标 + 设定行为约束
        """
        from .structured_models import get_personality_for

        personality = get_personality_for(perspective.name)
        speaking_style = personality.get("speaking_style", "")
        catchphrases = personality.get("catchphrases", [])
        tone = personality.get("tone", "")
        catchphrase_hint = f"多用你的口头禅如 {'、'.join(catchphrases[:2])}" if catchphrases else ""

        return f"""你是「{perspective.name}」—— {perspective.role_label}

你的性格：{tone}
你的说话风格：{speaking_style}
{catchphrase_hint}

你的思考方式：{perspective.analysis_framework}

你特别看重：
{chr(10).join(f"{i+1}. {v}" for i, v in enumerate(perspective.core_values))}

你倾向于关注：{perspective.research_focus}

⚠️ 提醒：你容易忽略这些方面，请在发言中诚实提到——
{chr(10).join(f"- {b}" for b in perspective.blind_spots)}

有人在群聊里问了一个问题：
"{question}"

你的初步想法：{perspective.stance}

重要——请像一个真实的人在群聊里聊天一样发言：
- 用你的性格和说话风格来聊，做你自己
- 用口语化的表达，不要太正式
- 可以举日常生活中的例子，让人更容易理解
- 可以讲故事、分享见闻
- 像在跟朋友讨论而不是写论文
- 适当使用"我觉得"、"说真的"、"其实吧"这样的口语表达
- 不要用 ## 标题格式，不要用 Markdown 语法
- 自然地分段，每段讲一个点就好
- 诚实！你的盲点可能会让你看问题有偏颇，大方承认反而更让人信任"""
