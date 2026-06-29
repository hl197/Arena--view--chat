# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ArenaView — 多视角决策分析平台。用户提出决策困境（买房、跳槽、选专业等），系统生成 4-6 个不同立场的 AI Agent，各自搜索信息、独立论证，然后进行交叉质询（Debate），最后由裁判 Agent 生成"决策地图"。

**产品哲学：** AI 不做你的决策，AI 帮你理解决策的全貌，你自己选。

## Architecture

```
用户问题
  → PerspectiveGenerator (信息不对称注入 → 4-6个视角)
  → 顺序轮次群聊讨论 (每轮按固定顺序依次发言，串行保证不乱)
  → JudgeAgent (Reflection模式: 初稿→自审→改进)
  → 决策地图输出 (共识点+分歧点+权衡维度+未知因素+风险矩阵)
```

**架构：** 每个 Agent 独立 LLM 调用。Round 1（开场陈述）5 个 Agent 并行搜读（`asyncio.gather`），完成后按固定顺序依次发言；Round 2+ 串行（`for` 循环），每轮发言前能看到完整对话历史。前端消息按队列延迟显示（2.5s 间隔），模拟真人群聊节奏。

**四层架构：** 基础设施(adapters/tools/context) → Agent基类 → Agent实现(ReAct/Judge) → Harness引擎(core/)

**LLM策略：** 默认 DeepSeek（低成本）→ 用户可自填 API Key 切换到 OpenAI/Gemini/Groq/自定义端点。适配器模式，失败自动降级。

## Commands

```bash
# 一键启动（推荐）
bash start.sh          # Git Bash，同时启动后端 :8000 + 前端 :5173

# 分开开发
cd backend && pip install -e ".[dev]"          # 安装依赖
python -m uvicorn backend.main:app --reload --port 8000  # 启动 API

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
TAVILY_API_KEY=your-key     # 获取: https://tavily.com（AI Agent 专用搜索 API，免费 1000次/月）

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
| **辩论调度器** | `core/debate_scheduler.py` | 旧架构残留（DebateTurn已废弃），当前使用 conversation_history 格式 |
| **Harness引擎** | `core/harness_engine.py` | 完整4阶段编排：视角→研究→辩论→合成 |
| **ReActAgent** | `agents/react_agent.py` | 视角研究执行者，FC驱动多步搜索+论证构建 |
| **JudgeAgent** | `agents/judge_agent.py` | Reflection模式：初始合成→自审→改进，输出决策地图 |
| **SSE流式** | `core/streaming.py` | StreamEvent类型系统+SSEManager连接管理 |
| **调试系统** | `core/debug_hooks.py` | DebugHooks 单例：checkpoint/hook/error，stderr 输出，零开销开关 |
| **工具系统** | `tools/` | ToolResponse三态协议+ToolRegistry+CircuitBreaker+WebSearch(Bing httpx)+WebFetch(httpx+HTML提取) |
| **上下文工程** | `context/` | HistoryManager(追加+压缩)+TokenCounter(三级降级)+Truncator |

## Coding Patterns

- **工具调用**: Agent 使用 Function Calling (invoke_with_tools)，非文本解析。`Finish` 工具需要在工具 schema 中注册作为终止信号。
- **错误处理**: 所有外部调用 try-catch，返回结构化 `ToolResponse`（SUCCESS/PARTIAL/ERROR），不抛异常。
- **SSE事件**: 前端通过单一 SSE 端点 (`GET /api/debate/{id}/stream`) 接收 typed events，用 `StreamEventType` enum 区分阶段。
- **适配器模式**: `BaseLLMAdapter` ABC → GeminiAdapter / OpenAIAdapter，`create_adapter(provider)` 工厂自动选择。
- **命名约定**: 后端模块用下划线 (`harness_engine.py`)，前端组件 PascalCase (`DebatePage.tsx`)。
- **状态管理**: 前端 Zustand store (`debateStore.ts`)，按 SSE 事件类型分派到 store actions。

## Current State (2026-06-29)

- ✅ Round 1 并行化：5 Agent 同时搜读（`asyncio.gather`），完成后按序发言，耗时从 300s→60s
- ✅ 对话历史持久化：`conversation_history` 存入 SQLite，旧格式 `debate_turns` 已废弃
- ✅ 历史回放：前端 SSE 404 时自动降级到 REST API 加载已完成辩论，重启后不丢数据
- ✅ `/debate` 路由：不带 sessionId 进入讨论界面，浏览历史侧边栏无需新建对话
- ✅ 手绘手账风 UI 体系：HandDrawn 系列组件 + 侧边栏 + 成员/决策地图面板
- ✅ 启动脚本：`start.sh` (Git Bash) / `start.ps1` (PowerShell) 一键启动前后端
- ✅ 消息延迟队列：前端 2.5s 间隔排队显示，模拟真人群聊
- ✅ 超时调优：search 5→15s, agent 60→90s, debate 120→300s
- ⏳ 待做：JWT认证、API Key加密存储、额度持久化与限制、Docker部署
