"""Web 搜索工具

免费方案：DuckDuckGo Instant Answer API（无需 Key）
高级方案：用户配置 SerpAPI / Google Custom Search

搜索策略：
1. DuckDuckGo（免费，无速率限制问题）
2. 降级：纯文本返回（告知用户配置 Key 可解锁更好搜索）
"""

import re
from urllib.parse import quote
from ..base import Tool, ToolParameter
from ..response import ToolResponse
from ..errors import ToolErrorCode


class WebSearchTool(Tool):
    """Web 搜索工具——免费 DuckDuckGo + 可选 SerpAPI"""

    def __init__(self, user_serpapi_key: str = None, timeout: int = 5):
        super().__init__(
            name="web_search",
            description="搜索互联网获取最新信息。返回标题、摘要和URL。用于查询事实、新闻、数据。"
        )
        self._serpapi_key = user_serpapi_key
        self._timeout = timeout

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="query", type="string",
                          description="搜索查询词", required=True),
            ToolParameter(name="num_results", type="integer",
                          description="返回结果数量（默认5）", required=False, default=5),
        ]

    def run(self, parameters: dict) -> ToolResponse:
        query = parameters.get("query", "")
        num_results = int(parameters.get("num_results", 5))

        # 安全检查
        if not query.strip():
            return ToolResponse.error(
                code=ToolErrorCode.MISSING_PARAM,
                message="搜索查询词不能为空"
            )
        if len(query) > 500:
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_PARAM,
                message=f"查询词过长（{len(query)}字符），最大 500 字符"
            )
        num_results = max(1, min(num_results, 10))  # 限制 1-10

        # 优先 SerpAPI（如有 Key）
        if self._serpapi_key:
            return self._search_serpapi(query, num_results)

        # 默认 DuckDuckGo
        return self._search_duckduckgo(query, num_results)

    def _search_duckduckgo(self, query: str, num: int) -> ToolResponse:
        """DuckDuckGo Instant Answer API（免费）"""
        import urllib.request
        import json

        try:
            url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1"
            req = urllib.request.Request(url, headers={"User-Agent": "ArenaView/1.0"})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = []

            # 1. Instant Answer（如有）
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("AbstractSource", "DuckDuckGo"),
                    "snippet": data["AbstractText"],
                    "url": data.get("AbstractURL", ""),
                    "type": "instant_answer"
                })

            # 2. Related Topics
            for topic in data.get("RelatedTopics", [])[:num]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                        "snippet": topic["Text"],
                        "url": topic.get("FirstURL", ""),
                        "type": "related"
                    })

            if not results:
                # 返回原始信息
                heading = data.get("Heading", "")
                results.append({
                    "title": heading or query,
                    "snippet": f"关于 '{query}' 的搜索结果有限。请尝试更具体的查询词，或配置 SerpAPI Key 获取更丰富的搜索结果。",
                    "url": f"https://duckduckgo.com/?q={quote(query)}",
                    "type": "fallback"
                })

            # 格式化输出
            text_parts = []
            for i, r in enumerate(results[:num], 1):
                text_parts.append(f"{i}. **{r['title']}**\n   {r['snippet'][:300]}\n   来源: {r['url']}")

            return ToolResponse.success(
                text="\n\n".join(text_parts),
                data={"results": results[:num], "source": "DuckDuckGo (免费)"},
                stats={"result_count": len(results[:num])}
            )

        except Exception as e:
            return ToolResponse.error(
                code=ToolErrorCode.NETWORK_ERROR,
                message=f"搜索请求失败: {e}",
                text=f"搜索 '{query}' 时网络错误，请稍后重试。"
            )

    def _search_serpapi(self, query: str, num: int) -> ToolResponse:
        """SerpAPI 搜索（高级）"""
        import urllib.request
        import json

        try:
            url = (
                f"https://serpapi.com/search?"
                f"q={quote(query)}&num={num}&api_key={self._serpapi_key}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "ArenaView/1.0"})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = []
            for r in data.get("organic_results", [])[:num]:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": r.get("link", ""),
                    "type": "organic"
                })

            text_parts = []
            for i, r in enumerate(results, 1):
                text_parts.append(f"{i}. **{r['title']}**\n   {r['snippet'][:300]}\n   来源: {r['url']}")

            return ToolResponse.success(
                text="\n\n".join(text_parts),
                data={"results": results, "source": "SerpAPI"},
                stats={"result_count": len(results)}
            )

        except Exception as e:
            # SerpAPI 失败 → 降级 DuckDuckGo
            return self._search_duckduckgo(query, num)
