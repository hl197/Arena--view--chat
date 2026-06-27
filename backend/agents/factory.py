"""Agent 工厂

创建和管理各类 Agent 实例。
"""

from typing import Optional
from .react_agent import ReActAgent
from .judge_agent import JudgeAgent
from ..adapters.unified_llm import ArenaLLM
from ..tools.registry import ToolRegistry
from ..core.config import ArenaConfig


def create_react_agent(
    name: str,
    llm: ArenaLLM,
    perspective_name: str,
    perspective_stance: str,
    tool_registry: Optional[ToolRegistry] = None,
    config: Optional[ArenaConfig] = None,
) -> ReActAgent:
    """创建 ReAct 视角研究 Agent"""
    return ReActAgent(
        name=name,
        llm=llm,
        perspective_name=perspective_name,
        perspective_stance=perspective_stance,
        tool_registry=tool_registry,
        config=config,
    )


def create_judge_agent(
    name: str,
    llm: ArenaLLM,
    config: Optional[ArenaConfig] = None,
) -> JudgeAgent:
    """创建裁判 Agent"""
    return JudgeAgent(
        name=name,
        llm=llm,
        config=config,
    )
