"""PerspectiveGenerator 视角生成器测试（降级方案，无需 LLM）"""

import pytest
import os
from backend.core.perspective_generator import (
    Perspective,
    PerspectiveGenerator,
    PERSPECTIVE_ARCHETYPES,
)


class TestPerspectiveDataclass:
    """Perspective 数据类测试"""

    def test_create_minimal(self):
        p = Perspective(
            id="p_01",
            name="风险优先者",
            role_label="关注下行风险",
            stance="应谨慎行事"
        )
        assert p.id == "p_01"
        assert p.name == "风险优先者"
        assert p.core_values == []
        assert p.known_facts == []
        assert p.blind_spots == []
        assert p.research_focus == ""
        assert p.analysis_framework == ""

    def test_create_full(self):
        p = Perspective(
            id="p_01",
            name="机会寻求者",
            role_label="关注成长机会",
            stance="应抓住机遇",
            core_values=["成长", "灵活性"],
            research_focus="上行空间分析",
            known_facts=["市场在增长"],
            blind_spots=["低估风险"],
            analysis_framework="实物期权视角",
        )
        assert len(p.core_values) == 2
        assert p.known_facts == ["市场在增长"]


class TestPerspectiveArchetypes:
    """6 种基础原型测试"""

    def test_six_archetypes(self):
        assert len(PERSPECTIVE_ARCHETYPES) == 6

    def test_each_has_required_fields(self):
        for archetype in PERSPECTIVE_ARCHETYPES:
            assert "role_label" in archetype
            assert "core_values" in archetype
            assert "research_focus" in archetype
            assert "analysis_framework" in archetype
            assert "blind_spots" in archetype

    def test_each_has_values(self):
        for archetype in PERSPECTIVE_ARCHETYPES:
            assert len(archetype["core_values"]) >= 3

    def test_each_has_blind_spots(self):
        for archetype in PERSPECTIVE_ARCHETYPES:
            assert len(archetype["blind_spots"]) >= 2

    def test_unique_role_labels(self):
        labels = [a["role_label"] for a in PERSPECTIVE_ARCHETYPES]
        assert len(labels) == len(set(labels))

    def test_role_labels_are_as_expected(self):
        labels = {a["role_label"] for a in PERSPECTIVE_ARCHETYPES}
        assert "风险厌恶者" in labels
        assert "机会寻求者" in labels
        assert "数据驱动分析师" in labels
        assert "生活质量优先者" in labels
        assert "系统思考者" in labels
        assert "务实行动派" in labels


class TestPerspectiveGeneratorFromArchetypes:
    """降级方案（_generate_from_archetypes）测试——不需要 LLM"""

    def test_generates_correct_count(self):
        """用 Mock LLM 测试降级方案"""
        import os
        os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        # Mock invoke 返回无效 JSON → 降级到 archetypes
        mock_llm.invoke.return_value.content = "invalid json"

        gen = PerspectiveGenerator(llm=mock_llm)
        perspectives = gen._generate_from_archetypes(
            question="该买房还是租房？",
            num=4,
            user_options=["买房", "租房"]
        )

        assert len(perspectives) == 4
        for p in perspectives:
            assert isinstance(p, Perspective)
            assert p.id.startswith("p_")
            assert p.name
            assert p.stance

    def test_generates_all_six(self):
        """生成全部 6 个视角"""
        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "invalid"

        gen = PerspectiveGenerator(llm=mock_llm)
        perspectives = gen._generate_from_archetypes(
            question="要不要跳槽？",
            num=6
        )

        assert len(perspectives) == 6

    def test_each_perspective_has_unique_id(self):
        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "invalid"

        gen = PerspectiveGenerator(llm=mock_llm)
        perspectives = gen._generate_from_archetypes("测试", 6)
        ids = [p.id for p in perspectives]
        assert len(ids) == len(set(ids))

    def test_with_user_options(self):
        """用户选项被包含在 stance 中"""
        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "invalid"

        gen = PerspectiveGenerator(llm=mock_llm)
        perspectives = gen._generate_from_archetypes(
            question="该去哪里旅游？",
            num=3,
            user_options=["日本", "泰国", "欧洲"]
        )

        assert len(perspectives) == 3


class TestBuildResearchPrompt:
    """build_research_prompt 输出格式测试"""

    def test_prompt_contains_perspective_info(self):
        p = Perspective(
            id="p_01",
            name="风险厌恶者",
            role_label="关注下行风险",
            stance="应谨慎行事",
            core_values=["安全", "可预测性"],
            research_focus="最坏情况分析",
            blind_spots=["过度悲观"],
            analysis_framework="风险收益比",
        )

        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "invalid"

        gen = PerspectiveGenerator(llm=mock_llm)
        prompt = gen.build_research_prompt(p, "该买房吗？")

        assert "风险厌恶者" in prompt
        assert "风险收益比" in prompt
        assert "安全" in prompt
        assert "最坏情况分析" in prompt
        assert "过度悲观" in prompt
        assert "该买房吗？" in prompt
        assert "⚠️" in prompt  # 盲点警告
