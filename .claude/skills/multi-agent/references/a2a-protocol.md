# A2A 协议参考

## A2AServer 完整实现模式

```python
from hello_agents.protocols.a2a.implementation import A2AServer

# 创建 Agent Server——将 Agent 暴露为网络服务
server = A2AServer(
    name="code-analyzer",
    description="专业代码分析 Agent，支持安全审查、性能分析和风格检查",
    version="1.0.0",
    capabilities={
        "analysis": ["security", "performance", "style", "complexity"],
        "languages": ["python", "javascript", "typescript", "java", "go"],
        "max_file_size": "1MB"
    }
)

# 注册技能——通过 @server.skill() 装饰器
@server.skill("analyze")
def analyze_code(query: str) -> str:
    """分析代码质量和安全性"""
    params = json.loads(query)
    code = params.get("code", "")
    language = params.get("language", "python")
    focus = params.get("focus", ["security", "performance"])

    # 执行分析...
    return json.dumps({
        "issues": [
            {"file": "main.py", "line": 42, "severity": "high",
             "type": "security", "description": "SQL注入风险"}
        ],
        "score": 75
    })

@server.skill("explain")
def explain_code(query: str) -> str:
    """解释代码逻辑"""
    return "这段代码实现了..."

@server.skill("info")
def get_info(query: str) -> str:
    """返回 Agent 的元信息——用于能力发现"""
    return json.dumps({
        "name": server.name,
        "version": server.version,
        "skills": list(server.skills.keys()),
        "capabilities": server.capabilities
    })
```

## A2AClient 调用模式

```python
from hello_agents.protocols import A2AClient

class AgentConnector:
    """管理与远程 Agent 的连接"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.client = A2AClient(base_url)
        self.timeout = timeout
        self.capabilities = None

    def discover(self) -> dict:
        """发现远程 Agent 的能力"""
        result = self.client.execute_skill("info", "capabilities")
        self.capabilities = json.loads(result)
        return self.capabilities

    def call(self, skill: str, input_data: str | dict) -> str:
        """调用远程技能"""
        if isinstance(input_data, dict):
            input_data = json.dumps(input_data, ensure_ascii=False)
        try:
            return self.client.execute_skill(skill, input_data)
        except TimeoutError:
            return json.dumps({"error": f"调用 {skill} 超时 ({self.timeout}s)"})
        except ConnectionError:
            return json.dumps({"error": "无法连接到远程 Agent"})

    def negotiate(self, task: str, deadline: int, max_rounds: int = 3) -> dict:
        """完整的协商流程"""
        proposal = {"task": task, "deadline": deadline, "round": 1}
        for _ in range(max_rounds):
            response = self.call("evaluate_proposal", proposal)
            decision = json.loads(response)
            if decision.get("status") == "accepted":
                return {"agreed": True, "terms": proposal}
            elif decision.get("status") == "rejected":
                return {"agreed": False, "reason": decision.get("reason")}
            # counter proposal — 继续协商
            proposal = decision.get("counter_proposal", proposal)
        return {"agreed": False, "reason": "超过最大协商轮次"}
```

## MCP vs A2A 边界判断

```python
def select_protocol(target_info: dict) -> str:
    """根据被调用方的特征选择协议"""
    if target_info.get("has_autonomy", False):
        return "A2A"   # 自主 Agent —— 用 A2A
    if target_info.get("is_external_service", False):
        return "MCP"   # 外部服务 —— 用 MCP
    if target_info.get("requires_negotiation", False):
        return "A2A"   # 需要协商 —— 用 A2A
    if target_info.get("stateless", True):
        return "MCP"   # 无状态工具 —— 用 MCP
    return "MCP"       # 默认工具协议
```
