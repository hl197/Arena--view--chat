# 内置工具参考

## 8 个内置工具概览

| 工具 | 类名 | 文件 | 行数 | 核心特性 |
|------|------|------|------|---------|
| 计算器 | CalculatorTool | calculator.py | 143 | AST 安全解析，支持数学函数 |
| 文件读取 | ReadTool | file_tools.py | 269 | 元数据缓存、目录列表、跨平台 |
| 文件写入 | WriteTool | file_tools.py | 152 | 乐观锁冲突检测、原子写入 |
| 文件编辑 | EditTool | file_tools.py | 183 | 精确替换、备份、冲突检测 |
| 批量编辑 | MultiEditTool | file_tools.py | 159 | 批量替换原子性、全量校验 |
| 子代理 | TaskTool | task_tool.py | 187 | 上下文隔离、工具过滤、多Agent类型 |
| Skills | SkillTool | skill_tool.py | 174 | 渐进式加载、$ARGUMENTS 替换 |
| 进度管理 | TodoWriteTool | todowrite_tool.py | 388 | 单线程强制、声明式、持久化 |
| 开发日志 | DevLogTool | devlog_tool.py | 451 | 结构化日志、过滤查询、摘要生成 |

## CalculatorTool — AST 安全计算器

**安全设计**：用 `ast.parse` 白名单方式解析，只允许安全操作符和函数：

```python
class CalculatorTool(Tool):
    OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub,
                 ast.Mult: operator.mul, ast.Div: operator.truediv, ...}
    FUNCTIONS = {'abs', 'round', 'max', 'min', 'sqrt', 'sin', 'cos', 'tan',
                 'log', 'exp', 'pi', 'e'}

    def run(self, parameters) -> ToolResponse:
        expression = parameters.get("input", "")
        node = ast.parse(expression, mode='eval')  # 安全解析（只允许表达式）
        result = self._eval_node(node.body)         # 递归计算 AST

    def _eval_node(self, node):
        # ast.Constant → value
        # ast.BinOp → operator(left, right)
        # ast.Call → function(*args) — 白名单检查
        # ast.Name → 常量检查（pi, e）
```

## 文件工具 — 乐观锁+原子写入

### ReadTool
- 自动缓存元数据（mtime, size）到 ToolRegistry，供 Write/Edit 做乐观锁检测
- 目录路径自动切换为 `ls` 模式
- 跨平台兼容（Windows/Linux 路径处理）

### WriteTool
- **乐观锁**：如果传了 `file_mtime_ms`，写入前检查文件是否被修改
- **原子写入**：先写 `.tmp` 文件，再 `os.replace()` 原子重命名
- **自动备份**：覆盖前备份原文件到 `.backups/`

### EditTool
- `old_string` 必须唯一匹配（`content.count(old_string) == 1`）
- 同样支持乐观锁冲突检测和自动备份

### MultiEditTool
- 批量替换的原子性保证：先验证所有 `old_string` 都唯一匹配，再一次性执行
- 任一替换失败则全部取消

## TaskTool — 子代理工具

```python
# 参数
{"task": "...", "agent_type": "react|reflection|plan|simple",
 "tool_filter": "readonly|full|none", "max_steps": 15}
```

工具过滤工厂方法：
```python
def _create_tool_filter(self, filter_type) -> Optional[ToolFilter]:
    if filter_type == "readonly": return ReadOnlyFilter()
    elif filter_type == "full":   return FullAccessFilter()
    elif filter_type == "none":   return None
```

## SkillTool — Skills 加载工具

动态生成 description（包含所有可用技能列表），Agent 调用 `Skill(skill="pdf")` 即可加载。

## TodoWriteTool — 任务进度管理

**强制约束**：
1. 声明式覆盖（每次提交完整列表）
2. 单线程强制（最多 1 个 `in_progress`）
3. 自动生成 Recap：`📋 [2/5] 进行中: xxx. 待处理: yyy; zzz.`
4. 持久化到 `memory/todos/todoList-<timestamp>.json`

```python
class TodoWriteTool(Tool):
    def run(self, parameters) -> ToolResponse:
        action = parameters.get("action", "create")
        if action == "clear":
            self.current_todos = TodoList(summary="")
        elif action in ("create", "update"):
            todos_data = parameters.get("todos", [])
            # 验证：最多 1 个 in_progress
            self._validate_todos(todos_data)
            self.current_todos = TodoList(summary=..., todos=[TodoItem(...)])
            recap = self._generate_recap()
            self._persist_todos()  # 原子写入
```

数据结构：
```python
@dataclass
class TodoItem:
    content: str      # 任务内容
    status: str       # "pending"|"in_progress"|"completed"
    created_at: str
    updated_at: str

@dataclass
class TodoList:
    summary: str
    todos: List[TodoItem]
    # 方法: get_in_progress(), get_pending(limit), get_completed(), get_stats()
```

## DevLogTool — 开发日志

**7 种日志类别**：`decision`（架构决策）、`progress`（进展）、`issue`（问题）、`solution`（解决方案）、`refactor`（重构）、`test`（测试）、`performance`（性能）

**4 种操作**：
- `append`: 追加日志（需要 category + content + 可选 metadata{tags}）
- `read`: 读取日志（支持 category/tags/limit 过滤）
- `summary`: 生成摘要（按类别统计+最近3条）
- `clear`: 清空日志

**持久化**：`memory/devlogs/devlog-<session_id>.json`（原子写入）
