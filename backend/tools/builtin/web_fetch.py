"""Web 内容抓取工具 —— httpx + BeautifulSoup 版

用 httpx 请求网页，BeautifulSoup 提取正文。
不需要浏览器渲染，速度快、无线程问题。绝大多数信息页面的正文都在 HTML 里。
"""

import re
import httpx
from ..base import Tool, ToolParameter
from ..response import ToolResponse
from ..errors import ToolErrorCode


class WebFetchTool(Tool):
    """Web 内容抓取工具——读取网页正文内容"""

    def __init__(self, timeout: int = 15, max_chars: int = 5000):
        super().__init__(
            name="web_fetch",
            description=(
                "打开一个网页链接，读取里面的文字内容。"
                "当你搜到一个看起来有用的链接，想了解更多细节时使用。"
                "返回页面里的正文文字。"
            )
        )
        self._timeout = timeout
        self._max_chars = max_chars

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="url", type="string",
                          description="要读取的网页链接（完整的 https:// 地址）", required=True),
        ]

    def run(self, parameters: dict) -> ToolResponse:
        url = parameters.get("url", "").strip()

        if not url:
            return ToolResponse.error(ToolErrorCode.MISSING_PARAM, "请提供网页地址")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            resp = httpx.get(
                url,
                timeout=self._timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                }
            )

            if resp.status_code >= 400:
                return ToolResponse.success(
                    text=f"网页 {url} 返回了 {resp.status_code} 状态码，可能无法访问。换个链接试试。",
                    data={"url": url, "status_code": resp.status_code},
                    stats={"char_count": 0}
                )

            title, body_text = self._extract(resp.text)

            if not body_text.strip():
                return ToolResponse.success(
                    text=f"页面 {url} 没有提取到文字内容，可能是动态页面或需要登录。试试其他链接。",
                    data={"url": url, "title": title},
                    stats={"char_count": 0}
                )

            if len(body_text) > self._max_chars:
                body_text = body_text[:self._max_chars] + "\n\n…（内容已截断，打开链接查看全文）"

            display = f"📄 {title}\n🔗 {url}\n\n{body_text}"

            return ToolResponse.success(
                text=display,
                data={"url": url, "title": title, "text_length": len(body_text)},
                stats={"char_count": len(body_text)}
            )

        except httpx.TimeoutException:
            return ToolResponse.success(
                text=f"打开 {url} 超时了。换个链接试试，或者用已有知识继续讨论。",
                data={"url": url},
                stats={"error": "timeout"}
            )
        except Exception as e:
            return ToolResponse.success(
                text=f"打开 {url} 时出错了。你可以换个链接，或者用已有知识继续讨论。",
                data={"url": url, "error": str(e)[:100]},
                stats={"error": str(e)[:100]}
            )

    def _extract(self, html: str) -> tuple[str, str]:
        """从 HTML 提取标题和正文 —— 优先语义标签，回退全文"""
        title = ""
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = self._clean_entities(title_match.group(1)).strip()
            # 去掉常见的站点后缀 " - 知乎" / "| 新浪" 等
            title = re.sub(r'\s*[-|–—]\s*[^-|–—]+$', '', title).strip()

        # 移除干扰元素
        html = re.sub(r'<(script|style|noscript|iframe|svg|canvas|nav|footer|header)[^>]*>.*?</\1>',
                      '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        # 移除常见非内容元素
        html = re.sub(r'<(nav|footer|header|aside|form)[^>]*>.*?</\1>',
                      '', html, flags=re.DOTALL | re.IGNORECASE)

        # 优先提取语义内容区（包含中文常见类名）
        body = ""
        content_patterns = [
            # HTML5 语义
            r'<article[^>]*>(.*?)</article>',
            r'<main[^>]*>(.*?)</main>',
            # 英文常见
            r'<div[^>]*class="[^"]*(?:content|article|post|entry|detail|body|text|main)[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*(?:content|article|post|entry|detail|body|text|main)[^"]*"[^>]*>(.*?)</div>',
            # 中文常见：rich_media_content(微信), article-content, post-body, cnt, main-content 等
            r'<div[^>]*class="[^"]*(?:rich_media|article|post|content|cnt|main|detail|wrapper|bd|con|txt|nr|essay)[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*(?:rich_media|article|post|content|cnt|main|detail|wrapper|bd|con|txt|nr|essay)[^"]*"[^>]*>(.*?)</div>',
            r'<section[^>]*>(.*?)</section>',
        ]
        for pattern in content_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match and len(match.group(1)) > 100:
                body = match.group(1)
                break

        # 回退：全文（去掉 head 部分）
        if not body:
            body = re.sub(r'<head[^>]*>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # 提取段落文本（保留 <p> <li> <h1-h6> 和裸文本，按块分割）
        # 先把块级标签替换成换行
        body = re.sub(r'<br\s*/?>', '\n', body, flags=re.IGNORECASE)
        body = re.sub(r'</?(?:p|li|h\d|tr|div|section|blockquote|pre|td)[^>]*>', '\n', body, flags=re.IGNORECASE)

        # 去除剩余标签
        text = re.sub(r'<[^>]+>', ' ', body)

        # 处理转义
        text = self._clean_entities(text)

        # 按行整理
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            # 跳过太短或明显不是内容的行
            if not stripped:
                continue
            # 保留 >= 5 字符的行（中文5字已有意义）
            if len(stripped) >= 5:
                lines.append(stripped)
            # 短行如果有意义（含中文），合并到上一行
            elif len(stripped) >= 2 and lines and re.search(r'[一-鿿]', stripped):
                lines[-1] = lines[-1] + ' ' + stripped

        # 去重相邻相似行
        deduped = []
        for line in lines:
            if deduped and self._similar(line, deduped[-1]):
                continue
            deduped.append(line)

        return title, "\n".join(deduped)

    def _clean_entities(self, text: str) -> str:
        """清理 HTML 实体和空白"""
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        text = text.replace('&middot;', '·').replace('&mdash;', '—')
        text = text.replace('&ndash;', '–').replace('&hellip;', '…')
        text = re.sub(r'&#?\w+;', ' ', text)  # 其他实体 → 空格
        text = re.sub(r'\s+', ' ', text)
        return text

    def _similar(self, a: str, b: str) -> bool:
        """检查两行是否高度相似（去重用）"""
        if a == b:
            return True
        if len(a) < 20 or len(b) < 20:
            return False
        # 简单 Jaccard（3-gram）
        def ngrams(s):
            return set(s[i:i+3] for i in range(len(s)-2))
        sa, sb = ngrams(a), ngrams(b)
        if not sa or not sb:
            return False
        return len(sa & sb) / min(len(sa), len(sb)) > 0.7
