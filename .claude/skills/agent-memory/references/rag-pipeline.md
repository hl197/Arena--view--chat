# RAG 检索增强生成管道

## 完整 RAG Pipeline 架构

```
┌─────────────────────────────────────────────────────┐
│                    文档摄入                          │
│  文件(.md/.pdf/.txt) → 解析 → 语义分块 → Embedding   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│                    向量存储                          │
│         ChromaDB / FAISS / Milvus                   │
│    ├── Dense Index (向量相似度)                      │
│    └── Sparse Index (BM25 关键词)                   │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│                    在线检索                          │
│  用户查询 → 查询重写 → 混合检索 → RRF融合 → 重排序   │
└─────────────────────────────────────────────────────┘
```

## RAGTool 完整实现

```python
import os
import hashlib
from pathlib import Path

class RAGTool:
    """Agent 的知识库工具——文档管理和智能检索"""

    name = "rag"
    description = (
        "管理和检索知识库。操作: add_text(添加文本), add_file(摄入文件), "
        "search(语义搜索), ask(基于知识库问答), stats(统计)"
    )

    def __init__(self, knowledge_base_path: str, rag_namespace: str = "default",
                 embedding_model_name: str = "text-embedding-3-small"):
        self.kb_path = Path(knowledge_base_path)
        self.kb_path.mkdir(parents=True, exist_ok=True)
        self.namespace = rag_namespace

        # 延迟初始化——避免启动时加载大模型
        self._embedding_model = None
        self._embedding_model_name = embedding_model_name
        self._vector_store = None
        self._bm25_index = None

    @property
    def embedding_model(self):
        if self._embedding_model is None:
            # 加载 embedding 模型
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(
                'BAAI/bge-small-zh-v1.5'  # 中文优化的小模型
            )
        return self._embedding_model

    @property
    def vector_store(self):
        if self._vector_store is None:
            import chromadb
            client = chromadb.PersistentClient(
                path=str(self.kb_path / "chroma_db")
            )
            self._vector_store = client.get_or_create_collection(
                name=self.namespace
            )
        return self._vector_store

    def run(self, params: dict) -> str:
        action = params.get("action", "search")

        if action == "add_text":
            return self._add_text(params)
        elif action == "add_file":
            return self._add_file(params)
        elif action == "search":
            return self._search(params)
        elif action == "ask":
            return self._ask(params)
        elif action == "stats":
            return self._stats()
        else:
            return f"未知操作: {action}"

    # —— 文档摄入 ——

    def _add_text(self, params: dict) -> str:
        text = params.get("text", "")
        doc_id = params.get("document_id") or self._generate_id(text)
        metadata = params.get("metadata", {})

        if not text.strip():
            return "错误: 文本内容为空"

        # 1. 语义分块
        chunks = self._semantic_chunk(text)
        if not chunks:
            return "错误: 无法从文本中提取有效内容"

        # 2. 生成 Embedding
        embeddings = self.embedding_model.encode(chunks).tolist()

        # 3. 存入向量库
        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        self.vector_store.add(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=[{**metadata, "source_doc": doc_id, "chunk_index": i}
                       for i in range(len(chunks))]
        )

        return f"✅ 已摄入文档 {doc_id}: {len(chunks)} 个块, {len(text)} 字符"

    def _add_file(self, params: dict) -> str:
        file_path = params.get("file_path", "")
        if not file_path:
            return "错误: 请提供文件路径"

        path = Path(file_path)
        if not path.exists():
            return f"错误: 文件不存在 {file_path}"

        # 解析文件
        text = self._parse_file(path)
        if not text:
            return f"错误: 无法解析 {path.suffix} 文件"

        return self._add_text({
            "text": text,
            "document_id": path.stem,
            "metadata": {"source_file": str(path.absolute()), "file_type": path.suffix}
        })

    def _parse_file(self, path: Path) -> str:
        """解析不同格式的文件"""
        suffix = path.suffix.lower()
        if suffix in [".md", ".txt", ".py", ".js", ".java", ".go", ".rs"]:
            return path.read_text(encoding="utf-8")
        elif suffix == ".pdf":
            # 需要 PyPDF2 或 pdfplumber
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
        elif suffix == ".html":
            from bs4 import BeautifulSoup
            return BeautifulSoup(path.read_text(), "html.parser").get_text()
        else:
            # 尝试当作文本读取
            try:
                return path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return ""

    # —— 语义分块 ——

    def _semantic_chunk(self, text: str, target_size: int = 512) -> list[str]:
        """按语义边界分块——保持段落完整性"""
        chunks = []
        current_chunk = []
        current_size = 0

        # 先按段落分割
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_words = len(para)

            # 按标题分割（Markdown 标题）
            if para.startswith("#"):
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_size = para_words
                continue

            # 当前块放得下
            if current_size + para_words <= target_size:
                current_chunk.append(para)
                current_size += para_words
            else:
                # 当前块满了，开始新块
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))

                # 长段落的二次分割
                if para_words > target_size:
                    sub_chunks = self._split_long_paragraph(para, target_size)
                    chunks.extend(sub_chunks)
                    current_chunk = []
                    current_size = 0
                else:
                    current_chunk = [para]
                    current_size = para_words

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _split_long_paragraph(self, para: str, target_size: int) -> list[str]:
        """对超长段落按句子边界再分割"""
        import re
        sentences = re.split(r'(?<=[。！？.!?])\s*', para)
        chunks = []
        current = []
        current_size = 0

        for sent in sentences:
            sent_size = len(sent)
            if current_size + sent_size > target_size and current:
                chunks.append("".join(current))
                current = []
                current_size = 0
            current.append(sent)
            current_size += sent_size

        if current:
            chunks.append("".join(current))
        return chunks

    # —— 检索 ——

    def _search(self, params: dict) -> str:
        """混合检索——向量 + BM25"""
        query = params.get("query", "")
        limit = int(params.get("limit", 5))

        if not query:
            return "错误: 请提供搜索关键词"

        # 1. 查询重写
        rewritten = self._rewrite_query(query)

        # 2. Dense 检索（向量）
        query_emb = self.embedding_model.encode([rewritten]).tolist()
        dense_results = self.vector_store.query(
            query_embeddings=query_emb, n_results=limit * 2
        )

        # 3. 重排序——取分数最高的
        results = []
        for i in range(len(dense_results["ids"][0])):
            results.append({
                "id": dense_results["ids"][0][i],
                "content": dense_results["documents"][0][i],
                "score": 1.0 - dense_results["distances"][0][i],
                "metadata": dense_results["metadatas"][0][i],
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return self._format_search_results(results[:limit], query)

    def _ask(self, params: dict) -> str:
        """基于知识库的问答——检索 + LLM 回答"""
        question = params.get("question", "")
        limit = int(params.get("limit", 3))

        # 检索相关文档
        search_result = self._search({"query": question, "limit": limit})

        # 构建 RAG Prompt
        return (
            f"基于以下知识库内容回答问题:\n\n"
            f"---知识库---\n{search_result}\n---\n\n"
            f"问题: {question}\n\n"
            f"要求: 基于知识库内容回答，如果知识库中没有相关信息，请明确说明。"
        )

    # —— 查询优化 ——

    def _rewrite_query(self, query: str) -> str:
        """查询重写——扩展用户简短查询"""
        if len(query) > 50:
            return query  # 已经很详细了

        # 简单的同义词扩展
        expansions = {
            "bug": "bug 错误 缺陷 问题",
            "api": "api 接口 端点 endpoint",
            "部署": "部署 deploy 上线 发布",
            "性能": "性能 performance 优化 速度",
        }

        for key, expansion in expansions.items():
            if key in query.lower():
                return f"{query} {expansion}"

        return query

    def _stats(self, params: dict = None) -> str:
        count = self.vector_store.count()
        return f"📚 知识库 '{self.namespace}': {count} 个文档块"

    def _generate_id(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:12]

    def _format_search_results(self, results: list, query: str) -> str:
        if not results:
            return f"未找到与 '{query}' 相关的文档"

        lines = [f"📚 找到 {len(results)} 条相关内容:"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. [相似度:{r['score']:.2f}]\n{r['content'][:200]}..."
            )
        return "\n\n".join(lines)
```

## 关键技术对比

| 技术 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 向量检索(Dense) | 语义理解好 | 精确匹配差 | 模糊查询、语义搜索 |
| BM25(Sparse) | 精确关键词匹配 | 不理解语义 | 代码搜索、精确查找 |
| 混合检索 | 互补优势 | 实现复杂 | 通用搜索 |
| RRF融合 | 无需调参 | 对分数分布敏感 | 合并多种检索结果 |
| Cross-encoder重排 | 精度高 | 速度慢 | Top-K精排 |
| HyDE | 召回率高 | 多一次LLM调用 | 查全率优先场景 |
