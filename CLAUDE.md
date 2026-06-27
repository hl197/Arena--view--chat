# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ArenaView — 多视角决策分析平台。用户提出决策困境（买房、跳槽、选专业等），系统生成 4-6 个不同立场的 AI Agent，各自搜索信息、独立论证，然后进行交叉质询（Debate），最后由裁判 Agent 生成"决策地图"。

**产品哲学：** AI 不做你的决策，AI 帮你理解决策的全貌，你自己选。

## Architecture

```
用户问题
  → PerspectiveGenerator (信息不对称注入 → 4-6个视角)
  → Parallel ReActAgents (独立搜索+论证, asyncio.gather)
  → DebateScheduler (轮转交叉质询, 2轮)
  → JudgeAgent (Reflection模式: 初稿→自审→改进)
  → 决策地图输出 (共识点+分歧点+权衡维度+未知因素+风险矩阵)
```

**四层架构：** 基础设施(adapters/tools/context) → Agent基类 → Agent实现(ReAct/Judge) → Harness引擎(core/)

**LLM策略：** 默认 DeepSeek（低成本）→ 用户可自填 API Key 切换到 OpenAI/Gemini/Groq/自定义端点。适配器模式，失败自动降级。

## Commands

```bash
# 后端开发
cd backend && pip install -e ".[dev]"          # 安装依赖
uvicorn backend.main:app --reload --port 8000  # 启动 API (需要先设置 DEEPSEEK_API_KEY)

# 前端开发
cd frontend && npm install && npm run dev      # 启动 Vite dev server (localhost:5173)
                                                # Vite proxy 自动转发 /api → localhost:8000

# 运行测试 (待添加)
pytest tests/ -v
pytest tests/ -v -k test_react_agent           # 单个测试
```

## Environment Variables

```bash
# 推荐：加密存储 API Key（防止明文泄露）
python -m backend.scripts.encrypt_key --key sk-xxx --name DEEPSEEK  # 生成加密值
# 然后将输出的 DEEPSEEK_API_KEY_ENC=... 写入 .env

# 快速测试：明文 Key
DEEPSEEK_API_KEY=your-key  # 获取: https://platform.deepseek.com/api_keys

# 其他可选
ARENA_MASTER_KEY=auto-generated    # 加密主密钥，首次启动自动生成
ARENA_SECRET_KEY=auto-generated    # JWT 签名密钥
DATABASE_URL=sqlite:///arena.db    # 可选，默认 SQLite
```

## Key Modules

| 模块 | 文件 | 职责 |
|------|------|------|
| **LLM适配器** | `adapters/unified_llm.py` | ArenaLLM多模型路由，用户LLM优先→降级默认Gemini |
| **视角生成器** | `core/perspective_generator.py` | 信息不对称注入——6种原型+LLM定制，生成有差异的视角 |
| **辩论调度器** | `core/debate_scheduler.py` | 最大分歧配对+轮转交叉质询 |
| **Harness引擎** | `core/harness_engine.py` | 完整4阶段编排：视角→研究→辩论→合成 |
| **ReActAgent** | `agents/react_agent.py` | 视角研究执行者，FC驱动多步搜索+论证构建 |
| **JudgeAgent** | `agents/judge_agent.py` | Reflection模式：初始合成→自审→改进，输出决策地图 |
| **SSE流式** | `core/streaming.py` | StreamEvent类型系统+SSEManager连接管理 |
| **工具系统** | `tools/` | ToolResponse三态协议+ToolRegistry+CircuitBreaker+WebSearch(免费DuckDuckGo) |
| **上下文工程** | `context/` | HistoryManager(追加+压缩)+TokenCounter(三级降级)+Truncator |

## Coding Patterns

- **工具调用**: Agent 使用 Function Calling (invoke_with_tools)，非文本解析。`Finish` 工具需要在工具 schema 中注册作为终止信号。
- **错误处理**: 所有外部调用 try-catch，返回结构化 `ToolResponse`（SUCCESS/PARTIAL/ERROR），不抛异常。
- **SSE事件**: 前端通过单一 SSE 端点 (`GET /api/debate/{id}/stream`) 接收 typed events，用 `StreamEventType` enum 区分阶段。
- **适配器模式**: `BaseLLMAdapter` ABC → GeminiAdapter / OpenAIAdapter，`create_adapter(provider)` 工厂自动选择。
- **命名约定**: 后端模块用下划线 (`harness_engine.py`)，前端组件 PascalCase (`DebatePage.tsx`)。
- **状态管理**: 前端 Zustand store (`debateStore.ts`)，按 SSE 事件类型分派到 store actions。

## Current State (2026-06-27)

- ✅ 第1-2周完成：后端48文件3696行 + 前端13源文件1077行
- ⏳ 第3周待做：JWT认证、API Key加密存储、SQLite持久化、额度持久化、热门问题缓存
- ⏳ 第4周待做：Docker部署、UI打磨(加载/空态/错误态)、首页Demo预计算、Swagger

## 技能触发规则

开发时根据任务自动调用 `.claude/skills/` 下的 6 个技能：
- **agent-builder**: Agent范式选择、Prompt设计、Agent类实现
- **agent-tools**: 工具接口设计、ToolRegistry、MCP集成、工具安全
- **agent-memory**: 记忆系统、RAG管道、上下文工程
- **multi-agent**: 多Agent协作模式(Pipeline/Parallel/Debate/Hierarchical)
- **agent-training**: RL训练、评估体系
- **hello-agents-reference**: 生产级参考实现(16项能力完整模式)
