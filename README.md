# 🏗️ HarnessAgent — 企业级智能 Agent 平台

## 项目愿景

构建一个企业级的在线智能 Agent 平台，融合 Skill、Tool、Memory、Context、RAG、MCP、SubAgent、Multi-Agent、异步流式响应、生命周期轨迹可视化、错误兜底重试机制等前沿技术，打造一个通用、可靠、可观测的 AI Agent 编排引擎。

---

## 一、整体架构（六层模型）

```
┌─────────────────────────────────────────────────┐
│           前端展示层 (Web UI)                      │
│  流式对话 · 轨迹可视化 · 管理后台                    │
├─────────────────────────────────────────────────┤
│           编排层 (Orchestration)                   │
│  Harness Engine · 多步推理 · 生命周期管理           │
├─────────────────────────────────────────────────┤
│           多智能体层 (Multi-Agent)                  │
│  主Agent · SubAgent · Agent池 · 通信协议           │
├─────────────────────────────────────────────────┤
│           能力层 (Capabilities)                    │
│  Skills · Tools(MCP) · RAG · Memory · Context     │
├─────────────────────────────────────────────────┤
│           基础设施层 (Infra)                        │
│  向量数据库 · 消息队列 · 流式管道 · 状态存储         │
├─────────────────────────────────────────────────┤
│           可靠性层 (Reliability)                    │
│  重试机制 · 兜底策略 · 熔断器 · 可观测性             │
└─────────────────────────────────────────────────┘
```

---

## 二、核心模块设计

### 2.1 Harness Engine（编排引擎）— 心脏

Harness Engine 是整个系统的大脑，负责将用户意图转化为可执行的推理步骤，并协调所有能力模块完成目标。

```
Harness 核心循环:

  ┌──────────────────────────────────────────┐
  │                                          │
  │   用户意图输入                             │
  │       ↓                                  │
  │   ┌──────────┐                           │
  │   │  Think   │  分析当前状态，决定下一步     │
  │   └────┬─────┘                           │
  │        ↓                                  │
  │   ┌──────────┐                           │
  │   │  Act     │  调用 Tool / Skill / SubAgent │
  │   └────┬─────┘                           │
  │        ↓                                  │
  │   ┌──────────┐                           │
  │   │ Observe  │  收集行动结果               │
  │   └────┬─────┘                           │
  │        ↓                                  │
  │   ┌──────────┐                           │
  │   │ Reflect  │  评估进展，决定继续或结束     │
  │   └────┬─────┘                           │
  │        ↓                                  │
  │   完成 / 继续循环 ──────────────┘          │
  │                                          │
  └──────────────────────────────────────────┘
```

#### 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 推理模式 | ReAct + Plan-Act 混合 | 简单任务用 ReAct（推理-行动循环），复杂任务先出 Plan 再执行 |
| 任务复杂度评估 | Task Complexity Estimator | 自动评估任务复杂度，决定用单 Agent 还是多 Agent |
| 状态持久化 | 每步骤 checkpoint | 支持断点续跑、状态回放、故障恢复 |
| 上下文管理 | Token 预算机制 | 每个组件分配 token 配额，防止上下文爆炸 |
| 循环检测 | 相似调用检测器 | 3 次以上相似 Tool 调用自动触发干预 |

#### 推理步骤数据结构

每一步产生一个四元组：

```python
@dataclass
class ReasoningStep:
    id: str
    thought: str          # 思考内容 — Agent 在想什么
    action: Action        # 采取的行动 — 调了什么 Tool/Skill/SubAgent
    observation: Any      # 观察结果 — 行动后获取了什么信息
    next_step: str        # 下一步判断 — 继续 / 调整 / 完成
    timestamp: float
    token_usage: int
    metadata: dict        # 扩展元数据
```

---

### 2.2 Skill vs Tool — 能力层核心

#### 边界定义

| 维度 | Tool | Skill |
|------|------|-------|
| **粒度** | 原子操作（搜文件、读URL、查数据库） | 复合能力（写PPT、深度研究、代码审查） |
| **协议** | MCP 标准协议 | 内部 DSL + Prompt 模板 |
| **组合性** | 被 Agent 直接调用 | 可嵌套 Tool + 子 Skill |
| **注册方式** | MCP Server 注册 | Skill Registry 注册 |
| **示例** | `web_search`, `read_file`, `sql_query` | `deep-research`, `code-review`, `ppt-generator` |

#### Skill 定义格式

```python
class SkillDefinition:
    name: str                    # 技能名称（唯一标识）
    description: str             # 技能描述
    version: str                 # 版本号
    triggers: list[str]          # 触发条件（关键词/正则/上下文模式）
    required_tools: list[str]    # 依赖的 MCP Tool 列表
    required_skills: list[str]   # 依赖的子 Skill 列表
    prompt_template: str         # Skill 的 prompt 模板
    input_schema: dict           # 输入参数的 JSON Schema
    output_schema: dict          # 输出格式的 JSON Schema
    fallback_skill: str | None   # 兜底技能（当前技能失败时）
    timeout_seconds: int         # 超时时间
    max_retries: int             # 最大重试次数
```

#### MCP Tool 集成

Tool 层采用 **MCP（Model Context Protocol）** 标准协议：

```
┌──────────────────────────────────┐
│          Harness Engine           │
│         (MCP Client)              │
└────────────┬─────────────────────┘
             │  MCP Protocol
     ┌───────┼───────┬──────────────┐
     ↓       ↓       ↓              ↓
┌─────────┐ ┌───────┐ ┌───────┐ ┌─────────┐
│ 文件系统  │ │ 数据库 │ │ 网络  │ │ 自定义   │
│ Server  │ │ Server│ │ Server│ │ Server  │
└─────────┘ └───────┘ └───────┘ └─────────┘
```

- **优势**：行业标准协议，生态丰富，工具可插拔
- **实现**：基于 `mcp` Python SDK，支持自定义 MCP Server
- **动态发现**：Agent 启动时自动发现并注册可用的 MCP Tool

---

### 2.3 Memory 三层架构

```
┌──────────────────────────────────────────────────┐
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  Layer 1: Working Memory (工作记忆)          │  │
│  │  当前会话的推理状态、中间结果、活跃上下文       │  │
│  │  实现：内存字典 + 状态机 + LRU 淘汰           │  │
│  │  生命周期：单次会话                           │  │
│  └────────────────────────────────────────────┘  │
│                      ↓ 摘要写入                   │
│  ┌────────────────────────────────────────────┐  │
│  │  Layer 2: Episodic Memory (情节记忆)         │  │
│  │  历史会话摘要、关键决策点、成功/失败经验        │  │
│  │  实现：向量检索 + 时间衰减权重                 │  │
│  │  生命周期：跨会话持久化                        │  │
│  └────────────────────────────────────────────┘  │
│                      ↓ 知识提炼                   │
│  ┌────────────────────────────────────────────┐  │
│  │  Layer 3: Semantic Memory (语义记忆)         │  │
│  │  用户偏好、项目知识、事实性记忆、领域概念       │  │
│  │  实现：知识图谱 + 向量库 + 关系数据库           │  │
│  │  生命周期：永久存储                            │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
└──────────────────────────────────────────────────┘
```

#### Memory 数据结构

借鉴 Claude Code 的 memory 设计，每个记忆一个文件 + frontmatter 元数据 + 索引：

```markdown
---
name: user-prefers-python
description: 用户偏好使用 Python 进行后端开发
metadata:
  type: user
  created: 2026-06-26
  updated: 2026-06-26
---

用户在技术选型时优先选择 Python + FastAPI 方案。
相关记忆: [[tech-stack-preference]], [[fastapi-experience]]
```

#### 记忆操作

| 操作 | 说明 | 触发时机 |
|------|------|---------|
| `remember` | 存储新记忆 | Agent 检测到重要信息时自动触发 |
| `recall` | 检索相关记忆 | 每次用户输入时自动检索 |
| `update` | 更新已有记忆 | 发现冲突或补充信息时 |
| `forget` | 删除过期记忆 | 定期清理 + 手动清理 |
| `consolidate` | 合并相似记忆 | 后台异步任务 |

---

### 2.4 RAG（检索增强生成）

```
RAG Pipeline:

┌─────────────────────────────────────────────────────┐
│  文档摄入 (Ingestion)                                  │
│                                                       │
│  文档上传 → 格式解析 → 语义分块 → Embedding → 向量库    │
│            (PDF/HTML/MD/DOCX)      (按段落/章节)       │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  检索 (Retrieval)                                     │
│                                                       │
│  用户查询 → 查询重写 → 混合检索 → 重排序 → 注入上下文   │
│                      (Dense+Sparse)  (Cross-encoder)   │
└─────────────────────────────────────────────────────┘
```

#### 关键技术点

| 技术 | 说明 | 为什么重要 |
|------|------|-----------|
| **语义分块** | 按段落/章节边界切分，非固定 token 数 | 保持语义完整性，避免信息断裂 |
| **查询重写** | LLM 优化用户查询后再检索 | 提高检索命中率，消除口语化表达 |
| **混合检索** | Dense Vector + Sparse BM25 融合 | 向量检索覆盖语义相似，BM25 覆盖关键词精确匹配 |
| **Cross-encoder 重排序** | 对 Top-K 结果用 Cross-encoder 精排 | BERT 类模型的交叉注意力比向量相似度更精确 |
| **HyDE** | 先让 LLM 生成假设答案，用答案向量检索 | 复杂查询时比直接用问题检索效果好 |
| **上下文压缩** | 检索到的长文档先压缩再注入 | 节省 token，聚焦关键信息 |

#### 向量库选型

| 方案 | 适用阶段 | 特点 |
|------|---------|------|
| ChromaDB | 开发/原型 | 轻量，零配置，Python 原生 |
| Qdrant | 中小规模 | 高性能，过滤强大，Rust 实现 |
| Milvus | 生产/大规模 | 分布式，十亿级向量，GPU 加速 |

---

### 2.5 SubAgent 与 Multi-Agent 协作

#### Agent 层级模型

```
                    ┌─────────────┐
                    │  Master Agent │  ← 任务分解、协调、结果聚合
                    │  (Controller) │
                    └──────┬──────┘
                           │ 任务委派
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │SubAgent A│ │SubAgent B│ │SubAgent C│  ← 独立执行
        │  (Worker)│ │ (Worker) │ │ (Worker) │
        └──────────┘ └──────────┘ └──────────┘
              │            │            │
              ↓            ↓            ↓
        结果收集 ────→ 冲突解决 ────→ 最终输出
```

#### 协作模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **Pipeline** (流水线) | A→B→C 串行，每阶段产出流入下一阶段 | 步骤有依赖关系 |
| **Parallel** (并行探索) | A、B、C 同时跑不同维度 | 多维度搜索、审计 |
| **Debate** (辩论模式) | A 和 B 独立论证，相互验证 | 高风险决策 |
| **Hierarchical** (层级委托) | Agent 可以 spawn 子 Agent | 递归分解复杂任务 |
| **Adversarial Verify** (对抗验证) | N 个独立 skeptic 验证每个发现 | 代码审查、安全审计 |

#### SubAgent 定义

```python
@dataclass
class SubAgentSpec:
    role: str                # 角色描述
    goal: str                # 目标任务
    tools: list[str]         # 可用工具列表
    skills: list[str]        # 可用技能列表
    context: dict            # 注入的上下文
    expected_output: dict    # 期望输出格式的 JSON Schema
    timeout_seconds: int     # 超时时间
    isolation: str           # 隔离级别: "shared" | "isolated" | "worktree"
    retry_policy: RetryPolicy # 重试策略
```

#### Agent 池管理

```
Agent Pool:
├── 并发控制 (semaphore, 默认 min(16, cpu-2))
├── 超时控制 (per-agent timeout)
├── 资源隔离 (Bulkhead pattern — 不同 SubAgent 的资源池隔离)
├── 优先级队列 (紧急任务优先调度)
└── 健康检查 (心跳检测, 僵死检测, 自动重启)
```

---

### 2.6 异步流式响应

#### 流式管道架构

```
LLM Provider
    │  token stream
    ↓
Token Buffer (背压控制)
    │
    ├──→ Main Response Stream (SSE)     → 前端文本渲染
    ├──→ Thought Stream (SSE)           → 前端思考过程展示
    ├──→ Tool Call Stream (SSE)         → 前端工具调用展示
    ├──→ SubAgent Status Stream (WS)    → 前端子 Agent 进度
    ├──→ Error/Retry Stream (WS)        → 前端异常通知
    └──→ Trace Stream (WS)             → 前端轨迹图更新
```

#### 多路流设计

每条流有独立的 `event_type`，前端用事件总线统一分发：

```python
class StreamEvent:
    event_type: str    # "text" | "thought" | "tool_call" | "subagent" | "error" | "trace" | "heartbeat"
    payload: dict      # 事件数据
    timestamp: float   # 时间戳
    parent_id: str     # 父步骤 ID（用于构建轨迹树）
    sequence: int      # 序列号（用于重排序和去重）
```

#### 技术选型

| 通道 | 协议 | 用途 |
|------|------|------|
| 主文本流 | SSE | 单向推送 Agent 回复文本 |
| 思考流 | SSE | 展示 Agent 思考过程 |
| 工具调用流 | SSE | 展示工具调用的开始/结束/结果 |
| 状态推送 | WebSocket | 双向通信，状态同步、进度更新 |
| 轨迹更新 | WebSocket | 实时更新生命周期轨迹图 |

#### 背压处理

```
Producer (LLM)                    Consumer (Browser)
     │                                  │
     ├── token stream ────────────────→ │ (快)
     │                                  │
     │                              [Buffer Full]
     │                                  │
     ├── pause signal ←──────────────── │ (慢)
     │                                  │
     ├── buffer to disk / drop old ────→│
     │                                  │
     ├── resume →─────────────────────→ │ (恢复)
```

---

### 2.7 生命周期轨迹可视化

#### 轨迹数据结构

```python
@dataclass
class AgentTrace:
    trace_id: str                    # 全局唯一 trace ID
    root_task: str                   # 根任务描述
    status: str                      # "running" | "completed" | "failed"
    start_time: float
    end_time: float | None
    total_tokens: int
    steps: list[ReasoningStep]       # 推理步骤列表
    sub_agents: list[SubAgentTrace]  # 子 Agent 轨迹
    errors: list[ErrorRecord]        # 错误记录
    metadata: dict                   # 扩展元数据

@dataclass
class SubAgentTrace:
    agent_id: str
    role: str
    goal: str
    status: str
    start_time: float
    end_time: float | None
    steps: list[ReasoningStep]
    child_agents: list[SubAgentTrace]  # 递归嵌套
    retry_count: int
    errors: list[ErrorRecord]
```

#### 可视化设计

```
前端展示方案（Gantt 图 + 树形结构混合）:

横轴 = 时间线
纵轴 = Agent 层级（树形缩进）

┌──────────────────────────────────────────────────────────┐
│  📋 Task: "分析用户数据并生成报告"      ⏱️ 12.3s   ✅ 完成  │
│  ┌──────────────────────────────────────────────────────┐│
│  │ Step 1  💭 Think  ─────┤                            ││
│  │ Step 2  🔧 Tool   ──────────┤                       ││
│  │           📊 Result → {rows: 150}                    ││
│  │ Step 3  💭 Think  ────┤                             ││
│  │ Step 4  🤖 SubAgent (并行 x3) ─────────────────┤     ││
│  │           ├─ Agent A ────┤ ✅ (2.1s)                 ││
│  │           ├─ Agent B ────┤ ✅ (1.8s)                 ││
│  │           └─ Agent C ────────┤ ⚠️ 重试 → ✅ (4.2s)    ││
│  │ Step 5  ✍️  Output ─────────────────────────┤       ││
│  └──────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

#### 交互功能

| 功能 | 说明 |
|------|------|
| 节点展开/折叠 | 点击节点查看完整的输入/输出/messages |
| 时间线缩放 | 拖拽缩放 Gantt 图时间轴 |
| 错误高亮 | 失败/重试节点红色标记 |
| 历史回放 | 播放完整推理过程的动画回放 |
| 导出 | 导出为 JSON/HTML/PDF 报告 |
| 对比视图 | 并排对比两次不同运行的轨迹 |

#### 前端技术选型

| 库 | 用途 |
|----|------|
| ReactFlow | 节点图 / 树形结构 |
| ECharts / D3.js | Gantt 时间线图 |
| React + TypeScript | 整体 UI 框架 |

---

### 2.8 错误兜底与重试机制

#### 三层错误模型

```
L1: 瞬时错误 → 立即重试
    指数退避: 1s → 2s → 4s → 8s (最多3次)
    ├── 网络超时
    ├── API Rate Limit (429)
    └── 临时服务不可用 (503)

L2: 可恢复错误 → 降级重试
    ├── Token 超限 → 自动压缩上下文后重试
    ├── Tool 调用失败 → 换备用 Tool 再试
    ├── 输出格式错误 → 增加格式约束后重试
    └── LLM 返回异常 → 重写 Prompt 后重试

L3: 硬错误 → 兜底策略
    ├── 模型完全不响应 → 切换到备用模型
    ├── 子 Agent 崩溃 → 主 Agent 接管任务
    ├── RAG 检索失败 → 仅用 LLM 知识回答
    ├── 完全失败 → 返回部分结果 + 明确失败原因
    └── 死循环检测 → 强制终止 + 降级为简单问答
```

#### 可靠性模式

```python
class CircuitBreaker:
    """熔断器 — 连续失败 N 次后，暂停调用该服务一段时间"""
    failure_threshold: int = 5      # 连续失败阈值
    timeout_seconds: int = 30       # 熔断持续时间
    half_open_max: int = 1          # 半开状态最大试探请求数
    state: str                      # "closed" | "open" | "half_open"

class Bulkhead:
    """舱壁隔离 — 不同 SubAgent 的资源池隔离，一个挂了不影响其他"""
    max_concurrent: int = 4
    queue_size: int = 10
    timeout_seconds: int = 30

class GracefulDegradation:
    """优雅降级"""
    fallback_chain: list[str]  # 降级链路: ["gpt5", "claude", "local_model"]
```

#### 重试策略

```python
@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 1.0        # 基础延迟 (秒)
    max_delay: float = 60.0        # 最大延迟
    backoff_multiplier: float = 2.0  # 退避乘数
    jitter: bool = True            # 是否加随机抖动
    retryable_exceptions: list[str]  # 可重试的异常类型
```

---

## 三、技术栈总览

| 层级 | 推荐方案 | 备选 |
|------|---------|------|
| **后端框架** | Python 3.12 + FastAPI + asyncio | Node.js + TypeScript |
| **异步流式** | SSE (主通道) + WebSocket (状态推送) | gRPC Stream |
| **向量数据库** | 开发: ChromaDB / 生产: Milvus / Qdrant | Pinecone |
| **消息队列** | Redis Streams / NATS | RabbitMQ |
| **状态存储** | PostgreSQL + Redis | SQLite (开发阶段) |
| **MCP 集成** | `mcp` Python SDK | 自建 MCP Server |
| **LLM 调用** | 统一 API Gateway（多模型路由） | 直连各 SDK |
| **前端框架** | React 18 + TypeScript + Vite | Next.js (全栈) |
| **可视化库** | ReactFlow + ECharts / D3.js | Recharts |
| **可观测性** | OpenTelemetry + Langfuse | 自建 trace 存储 |
| **容器化** | Docker + Docker Compose | Kubernetes (大规模) |
| **CI/CD** | GitHub Actions | GitLab CI |

### 多模型路由（统一 Gateway）

```
用户请求 → API Gateway → 模型路由
                          ├── Claude (Fable/Opus/Sonnet/Haiku)
                          ├── DeepSeek (Flash/Pro)
                          ├── GPT (5.2/5.3/5.4/5.5)
                          └── 本地模型 (Ollama)
```

---

## 四、开发路线图

### Phase 1: 核心 Harness（2-3 周）

**目标**：单 Agent + Tool(MCP) + 基础 ReAct 循环 + 流式响应

- [ ] Harness Engine 核心循环（Think → Act → Observe → Reflect）
- [ ] MCP Client 集成，支持至少 3 个基础 Tool
- [ ] 基础 SSE 流式响应
- [ ] 命令行交互界面（CLI MVP）
- [ ] 简单的任务执行和输出

### Phase 2: 能力扩展（2-3 周）

**目标**：Skills 系统 + Memory 三层 + 基础 RAG

- [ ] Skill Registry 和 Skill 定义 DSL
- [ ] Working Memory + Episodic Memory 实现
- [ ] RAG Pipeline（文档摄入 + 语义检索）
- [ ] 查询重写 + 混合检索
- [ ] 上下文预算管理

### Phase 3: 多 Agent 协作（2-3 周）

**目标**：SubAgent 池 + 多协作模式 + 通信协议

- [ ] SubAgent 池管理（并发控制、超时、隔离）
- [ ] Pipeline / Parallel / Debate 协作模式
- [ ] Agent 间通信协议
- [ ] 任务复杂度评估器
- [ ] SubAgent 轨迹追踪

### Phase 4: 可靠性保障（1-2 周）

**目标**：重试/兜底/熔断 + 上下文管理 + 循环检测

- [ ] 三层错误分级模型
- [ ] 熔断器 + 舱壁隔离 + 优雅降级
- [ ] 循环检测和干预机制
- [ ] Token 预算和强制压缩
- [ ] 多模型 fallback

### Phase 5: 可视化与前端（2-3 周）

**目标**：轨迹追踪 + Web 前端 + 历史回放

- [ ] React 前端框架搭建
- [ ] 流式对话界面
- [ ] 轨迹 Gantt 图 + 树形结构可视化
- [ ] 历史会话管理
- [ ] 轨迹回放功能

### Phase 6: 上线部署（2-3 周）

**目标**：用户系统 + 多租户 + 性能优化 + 在线部署

- [ ] 用户认证和权限管理
- [ ] 多租户隔离
- [ ] 数据库持久化 + 并发优化
- [ ] Docker 部署 + Nginx 反代
- [ ] 监控和告警
- [ ] 文档和 API 文档

---

## 五、架构风险与应对

| # | 风险 | 严重程度 | 应对措施 |
|---|------|---------|---------|
| 1 | **上下文窗口爆炸** — 多步推理 + 多 Agent + RAG 把上下文撑爆 | 🔴 高 | Day 1 设计 Token 预算机制，每个组件有配额；自动压缩和摘要 |
| 2 | **多 Agent 协调开销过大** — Token 消耗一半以上在协调上 | 🔴 高 | 任务复杂度评估器，简单任务走单 Agent；协调消息精简 |
| 3 | **Tool 调用死循环** — Agent 反复调同一个无用的 Tool | 🟡 中 | 循环检测器，3 次以上相似调用触发干预 |
| 4 | **轨迹存储膨胀** — 轨迹数据增长快，存储压力大 | 🟡 中 | 采样策略（关键步骤全量，普通步骤摘要）；过期清理策略 |
| 5 | **LLM 输出不稳定** — 同一输入在不同时间得到不同输出 | 🟡 中 | 结构化输出约束（JSON Schema）；关键步骤加验证 |
| 6 | **SubAgent 雪崩** — 一个 Agent 崩溃触发连锁反应 | 🟡 中 | 舱壁隔离 + 超时控制 + 独立恢复 |
| 7 | **流式连接断开** — 长时间任务 SSE/WS 断连 | 🟢 低 | 心跳保活 + 自动重连 + 断点续传 |

---

## 六、待深入讨论的话题

以下话题需要在后续深入设计：

1. **Harness Engine 的详细状态机设计** — 推理步骤的完整状态流转
2. **Context 管理策略** — 上下文压缩算法、优先级排序、滑动窗口
3. **Memory 召回与冲突解决** — 多条相关记忆如何融合和去重
4. **SubAgent 通信协议细节** — 消息格式、序列化、版本兼容
5. **Skill 的自动发现与组合** — Agent 如何自动发现并组合多个 Skill
6. **多租户安全模型** — 用户隔离、Tool 权限、敏感信息过滤
7. **前端事件总线的详细设计** — 多路流的消费、缓冲、渲染策略
8. **性能基准与优化目标** — 延迟/吞吐量/Token利用率的目标值

---

## 七、参考与灵感

- **Claude Code** — Harness 设计、Workflow 编排、Memory 系统、Skill 机制
- **LangGraph** — Agent 状态机、图式编排
- **CrewAI / AutoGen** — 多 Agent 协作模式
- **MCP (Model Context Protocol)** — 标准化 Tool 协议
- **Langfuse / Phoenix** — LLM 可观测性和轨迹追踪
- **OpenAI Swarm** — 轻量级多 Agent 编排

---

> 📌 **当前状态**：架构设计阶段，正在迭代讨论中。
>
> 📅 **创建日期**：2026-06-26
