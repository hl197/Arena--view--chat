---
name: hello-agents-reference
description: |
  HelloAgents 生产级多 Agent 框架的完整参考实现。当需要设计和实现新 Agent 时，将此项目作为架构参照和代码模板来源。
  触发场景：(1) 创建/设计新的 Agent 类型时 (2) 实现工具系统、上下文工程、子代理机制等基础设施时 (3) 需要参考 ToolResponse 协议、CircuitBreaker、SessionStore 等设计模式时 (4) 了解 Function Calling 架构和 LLM 适配器实现时 (5) 学习从零构建完整 Agent 框架的分步方法论时。
---

# HelloAgents 参考实现指南

## 项目概述

HelloAgents 是一个基于 OpenAI 原生 API 构建的**生产级多 Agent 框架**（pip install hello-agents），集成了 16 项核心能力。本技能将其作为参考实现，用于指导新 Agent 的设计和开发。

### 16 项核心能力

| 分类 | 能力 |
|------|------|
| 基础设施 | ToolResponse 统一响应协议、LLM 多适配器(OpenAI/Anthropic/Gemini) |
| 核心系统 | Agent 抽象基类、4 种 Agent 范式、上下文工程(历史/Token/截断) |
| 高级特性 | 子代理机制(上下文隔离)、Skills 渐进式加载、CircuitBreaker 熔断器 |
| 工程保障 | 会话持久化、可观测性(JSONL+HTML Trace)、乐观锁文件编辑 |
| 辅助工具 | TodoWrite 进度管理、DevLog 开发日志、SSE 流式输出 |

### 分层架构速览

```
应用层 (用户代码/Web服务)
  ↓
Agent 实现层 (Simple/ReAct/Reflection/PlanSolve)
  ↓
Agent 基类层 (集成 10 项横切能力)
  ↓
基础设施层 (工具系统/上下文工程/LLM适配/Skills/可观测性)
```

## 何时使用本技能

本技能是**参考实现**——当开发新 Agent 遇到以下问题时，查阅对应的 reference 文件获取完整实现模式：

| 需求 | 查阅 |
|------|------|
| 选择 Agent 范式 | [agent-paradigms.md](references/agent-paradigms.md) — 4 种范式对比+决策树 |
| 设计工具系统 | [tool-system.md](references/tool-system.md) — ToolResponse 协议+ToolRegistry+CircuitBreaker |
| 管理上下文/Token | [context-engineering.md](references/context-engineering.md) — HistoryManager+TokenCounter+Truncator |
| 集成 LLM 调用 | [llm-integration.md](references/llm-integration.md) — 统一接口+多适配器+Function Calling |
| 实现子代理隔离 | [subagent-mechanism.md](references/subagent-mechanism.md) — 上下文隔离+工具过滤 |
| 知识外化/Skills | [skills-system.md](references/skills-system.md) — 渐进式加载机制 |
| 追踪/调试 Agent | [observability.md](references/observability.md) — 双格式 TraceLogger |
| 查看内置工具 | [builtin-tools.md](references/builtin-tools.md) — 8 个内置工具完整实现 |
| 整体架构设计 | [architecture.md](references/architecture.md) — 分层设计+数据流 |
| 编码规范/模式 | [best-practices.md](references/best-practices.md) — 错误处理+项目结构 |

## 从零构建 Agent 的 6 步方法论

参考 HelloAgents 的开发顺序：

1. **定义核心抽象** → Agent 抽象基类（集成点设计）
2. **实现工具系统** → ToolRegistry + Tool + ToolResponse 协议
3. **实现 LLM 集成** → 统一接口 + 适配器模式支持多种 LLM
4. **实现 Agent 基类** → 集成工具系统 + LLM + 上下文管理
5. **实现具体 Agent** → SimpleAgent → ReActAgent → PlanSolveAgent
6. **添加高级功能** → 会话持久化 + 可观测性 + 子代理机制 + Skills

## 核心设计原则

1. **关注点分离**：LLM 调用 / Agent 逻辑 / 工具管理 / 上下文管理 独立分层
2. **可扩展性**：基于抽象基类，适配器模式切换 LLM，工厂模式创建 Agent
3. **生产就绪**：完整的错误处理(15种错误码)、熔断器、乐观锁、原子写入
4. **向后兼容**：通过 property 代理和默认参数保证 API 稳定
