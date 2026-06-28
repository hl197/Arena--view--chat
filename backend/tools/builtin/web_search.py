"""Web 搜索工具

用 httpx 直接请求 Bing（比浏览器更不容易触发验证码），正则解析结果。
"""

import re
import html as html_mod
import httpx
from ..base import Tool, ToolParameter
from ..response import ToolResponse
from ..errors import ToolErrorCode


class WebSearchTool(Tool):
    """Web 搜索工具——httpx 请求 Bing 搜索"""

    def __init__(self, timeout: int = 8):
        super().__init__(
            name="web_search",
            description="搜索互联网获取最新信息。返回标题、摘要和URL。用于查询事实、新闻、数据。"
        )
        self._timeout = timeout

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="query", type="string",
                          description="搜索查询词", required=True),
            ToolParameter(name="num_results", type="integer",
                          description="返回结果数量（默认5，最多10）", required=False, default=5),
        ]

    def run(self, parameters: dict) -> ToolResponse:
        query = parameters.get("query", "").strip()
        num = max(1, min(int(parameters.get("num_results", 5)), 10))

        if not query:
            return ToolResponse.error(ToolErrorCode.MISSING_PARAM, "搜索词不能为空")

        try:
            results = self._search(query, num)

            if not results:
                return ToolResponse.success(
                    text=f"搜索「{query}」没有找到结果。结合已有知识参与讨论即可。",
                    data={"results": [], "source": "Bing"},
                    stats={"result_count": 0}
                )

            parts = [f"搜索「{query}」的结果：\n"]
            for i, r in enumerate(results, 1):
                parts.append(f"{i}. {r['title']}\n   {r['snippet']}\n   🔗 {r['url']}")

            return ToolResponse.success(
                text="\n\n".join(parts),
                data={"results": results, "source": "Bing"},
                stats={"result_count": len(results)}
            )

        except Exception as e:
            return ToolResponse.success(
                text=f"搜索「{query}」时网络波动，结合已有知识自然参与讨论即可。",
                data={"results": [], "source": "Bing (error)"},
                stats={"result_count": 0, "error": str(e)[:100]}
            )

    def _search(self, query: str, num: int) -> list[dict]:
        resp = httpx.get(
            "https://cn.bing.com/search",
            params={"q": query, "setlang": "zh-cn", "count": min(num + 5, 50)},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            timeout=self._timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return self._parse(resp.text, num)

    def _parse(self, html_text: str, num: int) -> list[dict]:
        results = []
        blocks = re.split(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>', html_text)[1:]

        for block in blocks[:num]:
            title_m = re.search(
                r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                block, re.DOTALL
            )
            if not title_m:
                continue
            url, title = title_m.group(1), self._clean(title_m.group(2))
            if len(title) < 3:
                continue

            snippet = ""
            sm = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
            if not sm:
                sm = re.search(r'<div[^>]*class="[^"]*b_caption[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
            if sm:
                snippet = self._clean(sm.group(1))

            results.append({
                "title": title[:200], "snippet": (snippet or title)[:400],
                "url": url, "type": "organic"
            })
        return results

    @staticmethod
    def _clean(raw: str) -> str:
        text = re.sub(r'<[^>]+>', '', raw)
        text = html_mod.unescape(text)
        text = re.sub(r'&ensp;|&nbsp;|&emsp;|&#0\d+;', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()
