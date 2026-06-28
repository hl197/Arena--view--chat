"""Web 搜索工具 —— Tavily Search API

使用 Tavily Search API（专为 AI Agent 设计），httpx POST 请求。
返回结构化结果：标题、URL、内容摘要（远优于搜索引擎爬虫的 100 字 snippet）。
"""

import os
import httpx
from ..base import Tool, ToolParameter
from ..response import ToolResponse
from ..errors import ToolErrorCode


class WebSearchTool(Tool):
    """Web 搜索工具——Tavily Search API（httpx）

    Tavily 专为 AI Agent 设计：
    - 返回详细内容摘要（远不止 100 字 snippet）
    - 支持中文搜索
    - 结构化 JSON 响应，无需 HTML 解析
    - 可选 AI 生成的综合答案
    """

    def __init__(self, timeout: int = 15, api_key: str = ""):
        super().__init__(
            name="web_search",
            description=(
                "搜索互联网获取最新信息。返回标题、详细摘要和 URL。"
                "用于查询事实、新闻、数据、观点等。"
            )
        )
        self._timeout = timeout
        self._api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        self._endpoint = "https://api.tavily.com/search"

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query", type="string",
                description="搜索查询词（支持中文）", required=True
            ),
            ToolParameter(
                name="num_results", type="integer",
                description="返回结果数量（默认5，最多10）", required=False, default=5
            ),
            ToolParameter(
                name="search_depth", type="string",
                description="搜索深度：basic（快速）或 advanced（深入，返回更多内容）",
                required=False, default="basic"
            ),
        ]

    def run(self, parameters: dict) -> ToolResponse:
        query = parameters.get("query", "").strip()
        num = max(1, min(int(parameters.get("num_results", 5)), 10))
        depth = parameters.get("search_depth", "basic")

        if not query:
            return ToolResponse.error(ToolErrorCode.MISSING_PARAM, "搜索词不能为空")

        if not self._api_key:
            return ToolResponse.success(
                text="搜索功能未配置 API Key，结合已有知识参与讨论即可。",
                data={"results": [], "source": "Tavily (未配置)"},
                stats={"result_count": 0}
            )

        try:
            resp = httpx.post(
                self._endpoint,
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "search_depth": depth,
                    "max_results": num,
                    "include_answer": True,       # AI 综合答案
                    "include_raw_content": False,  # 不需要原始 HTML
                },
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )

            if resp.status_code >= 400:
                return ToolResponse.success(
                    text=f"搜索「{query}」暂时不可用（API {resp.status_code}），结合已有知识继续讨论。",
                    data={"results": [], "source": f"Tavily (HTTP {resp.status_code})"},
                    stats={"result_count": 0}
                )

            data = resp.json()
            results = data.get("results", [])

            if not results:
                return ToolResponse.success(
                    text=f"搜索「{query}」没有找到结果。结合已有知识参与讨论即可。",
                    data={"results": [], "source": "Tavily"},
                    stats={"result_count": 0}
                )

            # 格式化输出
            parts = []
            # AI 综合答案（如果有）
            answer = data.get("answer", "")
            if answer:
                parts.append(f"📝 综合摘要：{answer}\n")

            parts.append(f"搜索「{query}」的结果：\n")
            for i, r in enumerate(results, 1):
                title = r.get("title", "无标题")
                url = r.get("url", "")
                content = r.get("content", "")  # Tavily 的内容摘要远超搜索引擎 snippet
                # 截断过长的内容
                if len(content) > 800:
                    content = content[:800] + "…"
                parts.append(f"{i}. {title}\n   {content}\n   🔗 {url}")

            return ToolResponse.success(
                text="\n\n".join(parts),
                data={
                    "results": [
                        {"title": r.get("title", ""), "snippet": r.get("content", ""),
                         "url": r.get("url", ""), "type": "organic"}
                        for r in results
                    ],
                    "answer": answer,
                    "source": "Tavily",
                },
                stats={
                    "result_count": len(results),
                    "has_answer": bool(answer),
                    "response_time_ms": data.get("response_time", 0),
                }
            )

        except httpx.TimeoutException:
            return ToolResponse.success(
                text=f"搜索「{query}」超时了。结合已有知识继续讨论即可。",
                data={"results": [], "source": "Tavily (timeout)"},
                stats={"result_count": 0, "error": "timeout"}
            )
        except Exception as e:
            return ToolResponse.success(
                text=f"搜索「{query}」时网络波动，结合已有知识自然参与讨论即可。",
                data={"results": [], "source": "Tavily (error)"},
                stats={"result_count": 0, "error": str(e)[:100]}
            )
