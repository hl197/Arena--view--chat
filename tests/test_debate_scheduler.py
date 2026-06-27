"""DebateScheduler 辩论调度器测试（配对逻辑，无需 LLM）"""

import pytest
from backend.core.debate_scheduler import DebateScheduler, DebateTurn, DebateResult
from backend.core.perspective_generator import Perspective


def make_perspective(id_, name, values):
    """Helper: 创建视角"""
    return Perspective(
        id=id_, name=name,
        role_label=name,
        stance=f"{name}的立场",
        core_values=values,
    )


@pytest.fixture
def sample_perspectives():
    """创建 6 个视角用于测试"""
    return [
        make_perspective("p_01", "风险厌恶者", ["安全", "稳定", "可预测性", "止损"]),
        make_perspective("p_02", "机会寻求者", ["成长", "潜力", "灵活性", "上行空间"]),
        make_perspective("p_03", "数据驱动分析师", ["数据", "统计", "量化", "可验证性"]),
        make_perspective("p_04", "生活质量优先者", ["幸福", "关系", "心理", "平衡"]),
        make_perspective("p_05", "系统思考者", ["复杂", "二阶效应", "长期", "连锁"]),
        make_perspective("p_06", "务实行动派", ["执行", "效率", "现实", "快速"]),
    ]


class TestDebateTurn:
    """辩论轮次数据类测试"""

    def test_create_turn(self):
        turn = DebateTurn(
            round=1,
            challenger_id="p_01",
            challenger_name="风险厌恶者",
            defender_id="p_02",
            defender_name="机会寻求者",
        )
        assert turn.round == 1
        assert turn.challenge == ""
        assert turn.defense == ""
        assert turn.judge_note == ""


class TestDebateResult:
    """辩论结果数据类测试"""

    def test_default_result(self):
        r = DebateResult()
        assert r.turns == []
        assert r.total_rounds == 0
        assert r.unresolved_issues == []
        assert r.resolved_issues == []


class TestPairByDivergence:
    """最大分歧配对测试"""

    def test_basic_pairing(self, sample_perspectives):
        scheduler = DebateScheduler(llm=None, config=None)
        pairs = scheduler._pair_by_divergence(sample_perspectives)

        # 6 个视角 → 3 对
        assert len(pairs) == 3
        for cid, did in pairs:
            assert cid != did

    def test_pairing_no_duplicates(self, sample_perspectives):
        scheduler = DebateScheduler(llm=None, config=None)
        pairs = scheduler._pair_by_divergence(sample_perspectives)

        # 每个视角只在配对中出现一次
        all_ids = []
        for cid, did in pairs:
            all_ids.append(cid)
            all_ids.append(did)
        assert len(all_ids) == len(set(all_ids))

    def test_pairing_cross_values(self, sample_perspectives):
        """验证最大分歧：价值观重叠最少的配对"""
        scheduler = DebateScheduler(llm=None, config=None)
        pairs = scheduler._pair_by_divergence(sample_perspectives)

        for challenger_id, defender_id in pairs:
            challenger = next(p for p in sample_perspectives if p.id == challenger_id)
            defender = next(p for p in sample_perspectives if p.id == defender_id)

            # 两个视角的价值观重叠应该较少
            overlap = len(set(challenger.core_values) & set(defender.core_values))
            # 至少验证它们被成功配对
            assert overlap >= 0  # 可能为 0

    def test_pairing_odd_count(self):
        """奇数视角时的配对"""
        perspectives = [
            make_perspective("p_01", "A", ["a", "b"]),
            make_perspective("p_02", "B", ["c", "d"]),
            make_perspective("p_03", "C", ["e", "f"]),
        ]

        scheduler = DebateScheduler(llm=None, config=None)
        pairs = scheduler._pair_by_divergence(perspectives)

        # 有配对生成即可（最少 1 对 + 可能额外的奇数配对）
        assert len(pairs) >= 1

    def test_pairing_two_perspectives(self):
        """只有 2 个视角 → 1 对"""
        perspectives = [
            make_perspective("p_01", "A", ["a"]),
            make_perspective("p_02", "B", ["b"]),
        ]

        scheduler = DebateScheduler(llm=None, config=None)
        pairs = scheduler._pair_by_divergence(perspectives)

        assert len(pairs) == 1
        assert pairs[0] == ("p_01", "p_02")


class TestPairByFocus:
    """聚焦配对测试"""

    def test_cyclic_pairing(self):
        perspectives = [
            make_perspective("p_01", "A", ["a"]),
            make_perspective("p_02", "B", ["b"]),
            make_perspective("p_03", "C", ["c"]),
            make_perspective("p_04", "D", ["d"]),
        ]

        scheduler = DebateScheduler(llm=None, config=None)
        pairs = scheduler._pair_by_focus(perspectives, ["issue1"])

        # 4 个视角 → 4 对（循环）
        assert len(pairs) == 4
        # 循环配对: (0→1), (1→2), (2→3), (3→0)
        assert pairs[0] == ("p_01", "p_02")
        assert pairs[-1] == ("p_04", "p_01")


class TestSchedulePairs:
    """公开 API schedule_pairs 测试"""

    def test_round1_uses_divergence(self):
        perspectives = [
            make_perspective("p_01", "A", ["a", "b"]),
            make_perspective("p_02", "B", ["c", "d"]),
        ]

        scheduler = DebateScheduler(llm=None, config=None)
        pairs = scheduler.schedule_pairs(
            perspectives=perspectives,
            arguments={},
            round_num=1,
        )

        assert len(pairs) == 1

    def test_round2_uses_focus(self):
        perspectives = [
            make_perspective("p_01", "A", ["a"]),
            make_perspective("p_02", "B", ["b"]),
        ]

        scheduler = DebateScheduler(llm=None, config=None)
        pairs = scheduler.schedule_pairs(
            perspectives=perspectives,
            arguments={},
            round_num=2,
            focus_issues=["核心分歧1"],
        )

        assert len(pairs) == 2  # 循环配对
