# 🏟️ ArenaView — 多视角决策分析平台

> **AI 不做你的决策，AI 帮你理解决策的全貌，你自己选。**

ArenaView 是一个多智能体群聊决策分析平台。用户提出决策困境（买房、跳槽、选专业等），系统生成 4-6 个不同立场的 AI Agent，各自搜索信息、独立论证，然后进行顺序轮次群聊讨论，最后由裁判 Agent 生成「决策地图」。

---

## 演示效果

```
用户提问: "我该不该从大厂跳槽去创业公司？"

  📋 生成 5 个视角...
  ├── 🛡️ 风险厌恶者 — "稳定压倒一切"
  ├── 🚀 机会寻求者 — "富贵险中求"
  ├── ⚖️ 务实权衡者 — "算清楚再决定"
  ├── 🌱 成长导向者 — "能学到什么最重要"
  └── 💰 资产规划师 — "从财务角度分析"

  🔄 第 1 轮 · 开场陈述
  ├── 🛡️ 风险厌恶者: "说实话，大厂给的安全感是真的..."
  ├── 🚀 机会寻求者: "我不同意前面说的！创业公司..."
  ├── ⚖️ 务实权衡者: "大家都有自己的道理，我来算一笔账..."
  ├── 🌱 成长导向者: "你们都在说钱，但成长空间呢？"
  └── 💰 资产规划师: "从资产配置角度看..."

  🔄 第 2 轮 · 交叉回应（每个 Agent 看到上一轮所有人的发言）
  ...

  🧠 裁判生成决策地图 → 共识点 + 分歧点 + 权衡维度 + 风险矩阵
```

---

## 架构

```
用户问题
  → PerspectiveGenerator (信息不对称注入 → 4-6 个视角)
  → 自我介绍 (每个视角发一条入群消息)
  → 顺序轮次群聊讨论 (每轮按固定顺序依次发言，串行 for 循环保证不乱)
  → JudgeAgent (Reflection 模式: 初稿→自审→改进)
  → 决策地图输出 (共识点 + 分歧点 + 权衡维度 + 未知因素 + 风险矩阵)
```

### 四层架构

| 层 | 位置 | 职责 |
|---|------|------|
| **基础设施** | `adapters/` `tools/` `context/` | LLM 适配器、工具注册表、Token 计数、上下文截断 |
| **Agent 基类** | `agents/base.py` | Agent 抽象、推理步骤记录、循环检测 |
| **Agent 实现** | `agents/react_agent.py` `agents/judge_agent.py` | ReAct 研究执行者、Reflection 裁判 |
| **Harness 引擎** | `core/harness_engine.py` | 完整 4 阶段编排 |

### 顺序轮次多智能体群聊（核心特色）

不同于传统辩论的两两配对交叉质询，ArenaView 采用**顺序轮次群聊**模式：

- **固定顺序发言**：每轮内 Agent 按 `p_01→p_02→p_03→p_04→p_05` 固定顺序依次发言
- **独立 LLM 调用**：每个 Agent 是独立的 LLM 调用，保留 multi-agent 项目特色
- **完整对话历史**：每个 Agent 发言前能看到之前所有人的发言，像真人群聊
- **串行保证不乱**：用串行 `for` 循环而非 `asyncio.gather`，发言顺序绝对不会乱

参考：AgentScope `sequential_pipeline` + `MsgHub.observe()` 模式。

### 双层角色建模

6 种人格原型，每种有独立的 `speaking_style`、`catchphrases`、`tone`、`emoji_style`：

| 原型 | 口头禅 | 风格 |
|------|--------|------|
| 🛡️ 风险厌恶者 | "说实话"、"保守一点" | 谨慎务实 |
| 🚀 机会寻求者 | "你想啊"、"搏一搏" | 激情冒险 |
| ⚖️ 务实权衡者 | "算笔账"、"理性看" | 理性分析 |
| 🌱 成长导向者 | "长远来看"、"能力圈" | 发展导向 |
| 💰 资产规划师 | "从财务看"、"资产配置" | 专业量化 |
| 🔍 批判思考者 | "等一下"、"反过来想" | 思辨质疑 |

---

## 项目结构

```
hahaAgent/
├── backend/                     # Python 后端 (FastAPI + asyncio)
│   ├── main.py                  # FastAPI 应用入口
│   ├── version.py               # 版本号
│   ├── adapters/                # LLM 适配器层
│   │   ├── unified_llm.py       # ArenaLLM 多模型路由（DeepSeek/OpenAI/Gemini）
│   │   ├── openai_adapter.py    # OpenAI 兼容适配器
│   │   ├── gemini_adapter.py    # Gemini 适配器
│   │   ├── base.py              # BaseLLMAdapter ABC
│   │   └── llm_response.py      # LLMResponse 结构化响应
│   ├── agents/                  # Agent 实现
│   │   ├── base.py              # Agent 基类 + ReasoningStep
│   │   ├── react_agent.py       # ReAct Agent（视角研究 + 群聊发言）
│   │   ├── judge_agent.py       # Judge Agent（Reflection 模式裁判合成）
│   │   └── factory.py           # Agent 工厂函数
│   ├── core/                    # 核心引擎
│   │   ├── harness_engine.py    # 编排引擎（4 阶段生命周期）
│   │   ├── perspective_generator.py # 视角生成器（信息不对称注入）
│   │   ├── debate_scheduler.py  # 辩论调度器（保留，向后兼容）
│   │   ├── structured_models.py # 6 种人格原型 + 双层角色建模
│   │   ├── streaming.py         # SSE 事件类型系统 + SSEManager
│   │   ├── debug_hooks.py       # 调试钩子系统（stderr 输出，零开销开关）
│   │   ├── config.py            # ArenaConfig 配置
│   │   └── exceptions.py        # 自定义异常
│   ├── tools/                   # 工具系统
│   │   ├── base.py              # Tool 基类
│   │   ├── registry.py          # ToolRegistry 注册表
│   │   ├── response.py          # ToolResponse 三态协议 (SUCCESS/PARTIAL/ERROR)
│   │   ├── circuit_breaker.py   # 熔断器
│   │   ├── errors.py            # 工具异常
│   │   ├── tool_filter.py       # 工具过滤
│   │   ├── builtin/             # 内置工具
│   │   │   ├── web_search.py    # Bing 搜索 (httpx)
│   │   │   ├── web_fetch.py     # 网页抓取 (httpx + HTML 提取)
│   │   │   └── finish_tool.py   # Finish 终止工具
│   │   └── mcp/                 # MCP 协议集成
│   ├── context/                 # 上下文工程
│   │   ├── history.py           # HistoryManager（追加 + 压缩）
│   │   ├── token_counter.py     # TokenCounter（三级降级策略）
│   │   └── truncator.py         # Truncator（上下文截断）
│   ├── api/                     # API 层
│   │   ├── routes/              # 路由定义
│   │   ├── middleware.py        # 中间件
│   │   └── schemas.py           # Pydantic 请求/响应模型
│   ├── db/                      # 数据库
│   │   └── database.py          # SQLite 数据库（SQLAlchemy）
│   ├── services/                # 服务层
│   │   ├── auth_service.py      # JWT 认证服务
│   │   └── crypto_service.py    # API Key 加密存储
│   ├── memory/                  # 记忆系统
│   │   └── debate_memory.py     # 辩论持久化记忆
│   ├── cache/                   # 缓存模块
│   ├── observability/           # 可观测性
│   │   └── trace_logger.py      # 轨迹日志
│   └── scripts/                 # 工具脚本
│       └── encrypt_key.py       # API Key 加密工具
├── frontend/                    # 前端 (React + TypeScript + Vite)
│   ├── src/
│   │   ├── App.tsx              # 路由配置
│   │   ├── main.tsx             # 入口
│   │   ├── index.css            # 全局样式 + Tailwind
│   │   ├── pages/
│   │   │   ├── HomePage.tsx      # 首页（问题输入）
│   │   │   ├── DebatePage.tsx    # 群聊辩论页（微信风格聊天界面）
│   │   │   └── ResultPage.tsx    # 决策地图结果页
│   │   ├── components/
│   │   │   └── chat/            # 聊天组件
│   │   │       ├── ChatHeader.tsx      # 聊天头部
│   │   │       ├── ChatInput.tsx       # 输入框
│   │   │       ├── MessageBubble.tsx   # 消息气泡
│   │   │       ├── AgentStatusBar.tsx  # Agent 状态栏
│   │   │       ├── TypingIndicator.tsx # 正在输入指示器
│   │   │       └── TimeStamp.tsx       # 时间戳
│   │   ├── store/
│   │   │   └── debateStore.ts   # Zustand 状态管理（消息队列 + Agent 状态）
│   │   ├── hooks/
│   │   │   └── useSSE.ts        # SSE 连接 Hook（自动重连）
│   │   ├── api/
│   │   │   ├── client.ts        # API 客户端
│   │   │   └── types.ts         # TypeScript 类型定义
│   │   └── utils/               # 工具函数
│   ├── public/avatars/          # 预设头像
│   ├── package.json
│   ├── vite.config.ts           # Vite 配置（含 API 代理）
│   ├── tailwind.config.js
│   └── tsconfig.json
├── tests/                       # 测试
│   ├── test_streaming.py        # SSE 事件测试
│   ├── test_tool_registry.py    # 工具注册测试
│   ├── test_circuit_breaker.py  # 熔断器测试
│   ├── test_history.py          # 历史管理测试
│   ├── test_token_counter.py    # Token 计数测试
│   ├── test_perspective_generator.py # 视角生成测试
│   ├── test_config.py           # 配置测试
│   └── ... (共 15 个测试文件)
├── docker/                      # Docker 部署
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── nginx.conf
├── docker-compose.yml
├── pyproject.toml               # Python 项目配置
├── .env.example                 # 环境变量示例
├── CLAUDE.md                    # Claude Code 项目指南
└── README.md
```

---

## 快速开始

### 前置条件

- Python 3.11+
- Node.js 18+
- DeepSeek API Key（[获取](https://platform.deepseek.com/api_keys)）

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxx
```

### 2. 启动后端

```bash
cd backend
pip install -e ".[dev]"
uvicorn backend.main:app --reload --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev        # → http://localhost:5173
```

Vite 自动将 `/api` 请求代理到 `localhost:8000`。

### 4. 体验

浏览器打开 `http://localhost:5173`，输入一个决策问题，观看多智能体群聊讨论：

- 试试："**我该不该从北京搬到成都？**"
- 试试："**30 岁要不要转行学 AI？**"
- 试试："**买房还是租房更划算？**"

---

## SSE 事件类型

ArenaView 通过单一 SSE 端点 (`GET /api/debate/{id}/stream`) 推送全流程事件：

| 事件 | 说明 |
|------|------|
| `phase` | 阶段切换 (perspectives / discussion / synthesis) |
| `perspective_ready` | 视角生成完成 |
| `self_intro` | Agent 自我介绍 |
| `round_start` | 新一轮讨论开始 |
| `speech_chunk` | Agent 发言片段（支持流式合并） |
| `speech_end` | Agent 发言结束 |
| `round_end` | 本轮讨论结束 |
| `agent_status` | Agent 状态变更 (thinking/searching/composing/done) |
| `tradeoff_update` | 权衡维度更新 |
| `decision_map_chunk` | 决策地图分块推送 |
| `self_reflection` | 裁判自我审查 |
| `complete` | 全流程结束 |
| `error` | 异常通知 |

---

## LLM 策略

默认使用 **DeepSeek**（低成本），用户可自填 API Key 切换到 OpenAI/Gemini/Groq/自定义端点。

适配器模式自动路由：
```
ArenaLLM → 用户配置的 provider → 失败降级到 DeepSeek
```

支持的环境变量：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `OPENAI_API_KEY` | OpenAI API Key（可选） |
| `GEMINI_API_KEY` | Google Gemini API Key（可选） |
| `GROQ_API_KEY` | Groq API Key（可选） |

---

## 技术栈

| 层 | 技术 |
|---|------|
| **网页抓取** | httpx + HTML 正则提取（替代 Playwright，无线程冲突） |
| **后端框架** | Python 3.12 + FastAPI + asyncio |
| **LLM 调用** | 适配器模式多模型路由（DeepSeek / OpenAI / Gemini） |
| **流式推送** | SSE（Server-Sent Events） |
| **前端框架** | React 18 + TypeScript + Vite |
| **样式** | Tailwind CSS |
| **状态管理** | Zustand |
| **数据库** | SQLite（开发阶段，可切换 PostgreSQL） |
| **容器化** | Docker + Docker Compose |
| **测试** | pytest |

---

## 开发状态

- ✅ 第 1-2 周：后端 48 文件 ~3700 行 + 前端 16 源文件 ~1200 行
- ✅ 顺序轮次多智能体群聊架构
- ✅ 6 种人格原型 + 双层角色建模
- ✅ SSE 全流程流式推送
- ✅ 微信风格聊天界面
- ⏳ JWT 认证、API Key 加密存储
- ⏳ SQLite 持久化、热门问题缓存
- ⏳ Docker 部署、UI 打磨

---

## 参考

- **AgentScope** — `sequential_pipeline` + `MsgHub` 多智能体消息传递
- **AutoGen** — RoundRobin 群聊模式
- **LangGraph** — Agent 状态机设计
- **hello-agents** — 三国狼人杀生产级多智能体参考实现

---

> 📌 **产品哲学**：AI 不做你的决策，AI 帮你理解决策的全貌，你自己选。
>
> 📅 **创建日期**：2026-06-26
