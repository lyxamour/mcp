---
name: knowledge-system-design
description: MCP 工具知识库系统详细设计
auto-activate:
  always: true
---

# 知识库系统设计

## 概述

知识库系统提供文档存储、检索和管理功能，基于 SQLite 实现，支持：
- 文档存储和元数据管理
- 全文搜索 (FTS5)
- 可选的向量搜索
- 文档分块和索引
- 自动索引更新

## 数据模型

### 数据库 Schema

```python
# knowledge/models.py
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)


class Document(BaseModel):
    """文档模型"""
    
    id: str = Field(..., description="文档唯一标识")
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    source: str | None = Field(default=None, description="文档来源")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="文档元数据"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="更新时间"
    )
    
    model_config = {
        "extra": "forbid",
        "frozen": False,
    }


class Chunk(BaseModel):
    """文档块模型"""
    
    id: str = Field(..., description="块唯一标识")
    document_id: str = Field(..., description="所属文档ID")
    content: str = Field(..., description="块内容")
    chunk_index: int = Field(..., description="块索引")
    start_pos: int = Field(..., description="在原文中的起始位置")
    end_pos: int = Field(..., description="在原文中的结束位置")
    embedding: list[float] | None = Field(
        default=None,
        description="向量嵌入（可选）"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="块元数据"
    )
    
    model_config = {
        "extra": "forbid",
        "frozen": False,
    }


class SearchResult(BaseModel):
    """搜索结果模型"""
    
    document_id: str = Field(..., description="文档ID")
    chunk_id: str | None = Field(default=None, description="块ID（如果是块搜索）")
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="匹配内容")
    score: float = Field(..., description="相关性分数")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="元数据"
    )
    
    model_config = {
        "extra": "forbid",
        "frozen": False,
    }
```

### SQL Schema

```sql
-- knowledge/schema.sql

-- 文档表
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);

-- 文档块表
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_pos INTEGER NOT NULL,
    end_pos INTEGER NOT NULL,
    embedding BLOB,  -- 向量嵌入（可选）
    metadata TEXT,  -- JSON
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON chunks(document_id, chunk_index);

-- 全文搜索表 (FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    document_id UNINDEXED,
    title,
    content,
    tokenize = 'unicode61'
);

-- FTS5 触发器：插入
CREATE TRIGGER IF NOT EXISTS documents_fts_insert AFTER INSERT ON documents
BEGIN
    INSERT INTO documents_fts(document_id, title, content)
    VALUES (new.id, new.title, new.content);
END;

-- FTS5 触发器：更新
CREATE TRIGGER IF NOT EXISTS documents_fts_update AFTER UPDATE ON documents
BEGIN
    UPDATE documents_fts
    SET title = new.title, content = new.content
    WHERE document_id = new.id;
END;

-- FTS5 触发器：删除
CREATE TRIGGER IF NOT EXISTS documents_fts_delete AFTER DELETE ON documents
BEGIN
    DELETE FROM documents_fts WHERE document_id = old.id;
END;

-- 块全文搜索表 (FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    document_id UNINDEXED,
    content,
    tokenize = 'unicode61'
);

-- 块 FTS5 触发器
CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON chunks
BEGIN
    INSERT INTO chunks_fts(chunk_id, document_id, content)
    VALUES (new.id, new.document_id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE ON chunks
BEGIN
    UPDATE chunks_fts
    SET content = new.content
    WHERE chunk_id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON chunks
BEGIN
    DELETE FROM chunks_fts WHERE chunk_id = old.id;
END;
```

## 数据库连接

```python
# knowledge/db.py
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator
import structlog

from lyxamour_mcp.config.models import KnowledgeConfig

logger = structlog.get_logger(__name__)


class Database:
    """知识库数据库管理"""
    
    def __init__(self, config: KnowledgeConfig) -> None:
        self.config = config
        self.db_path = Path(config.db_path).expanduser()
        self._connection: aiosqlite.Connection | None = None
    
    async def initialize(self) -> None:
        """初始化数据库"""
        logger.info("初始化知识库数据库", path=str(self.db_path))
        
        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 连接数据库
        self._connection = await aiosqlite.connect(str(self.db_path))
        
        # 启用外键约束
        await self._connection.execute("PRAGMA foreign_keys = ON")
        
        # 执行 schema
        await self._execute_schema()
        
        logger.info("知识库数据库初始化完成")
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("知识库数据库已关闭")
    
    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """获取数据库连接（上下文管理器）"""
        if self._connection is None:
            await self.initialize()
        
        assert self._connection is not None
        yield self._connection
    
    async def _execute_schema(self) -> None:
        """执行数据库 schema"""
        assert self._connection is not None
        
        # 读取 schema 文件
        schema_path = Path(__file__).parent / "schema.sql"
        
        if schema_path.exists():
            async with aiosqlite.connect(str(self.db_path)) as conn:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = f.read()
                await conn.executescript(schema)
                await conn.commit()
        else:
            # 内联 schema（如果文件不存在）
            await self._create_inline_schema()
    
    async def _create_inline_schema(self) -> None:
        """创建内联 schema"""
        assert self._connection is not None
        
        # 文档表
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 文档块表
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_pos INTEGER NOT NULL,
                end_pos INTEGER NOT NULL,
                embedding BLOB,
                metadata TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)
        
        # 全文搜索表
        if self.config.enable_fts:
            await self._connection.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    document_id UNINDEXED,
                    title,
                    content,
                    tokenize = 'unicode61'
                )
            """)
            
            await self._connection.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    content,
                    tokenize = 'unicode61'
                )
            """)
        
        await self._connection.commit()
        
        logger.info("数据库 schema 创建完成")
```

## 存储层

```python
# knowledge/storage.py
import json
import uuid
from typing import Any
from datetime import datetime
import structlog

from lyxamour_mcp.knowledge.db import Database
from lyxamour_mcp.knowledge.models import Document, Chunk

logger = structlog.get_logger(__name__)


class DocumentStorage:
    """文档存储层"""
    
    def __init__(self, db: Database) -> None:
        self.db = db
    
    async def create_document(self, document: Document) -> str:
        """创建文档
        
        Returns:
            文档ID
        """
        async with self.db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO documents (id, title, content, source, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.title,
                    document.content,
                    document.source,
                    json.dumps(document.metadata, ensure_ascii=False),
                    document.created_at,
                    document.updated_at
                )
            )
            await conn.commit()
        
        logger.info("文档已创建", document_id=document.id)
        return document.id
    
    async def get_document(self, document_id: str) -> Document | None:
        """获取文档"""
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT * FROM documents WHERE id = ?",
                (document_id,)
            ) as cursor:
                row = await cursor.fetchone()
        
        if row is None:
            return None
        
        return self._row_to_document(row)
    
    async def update_document(self, document: Document) -> None:
        """更新文档"""
        document.updated_at = datetime.now()
        
        async with self.db.connection() as conn:
            await conn.execute(
                """
                UPDATE documents
                SET title = ?, content = ?, source = ?, metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    document.title,
                    document.content,
                    document.source,
                    json.dumps(document.metadata, ensure_ascii=False),
                    document.updated_at,
                    document.id
                )
            )
            await conn.commit()
        
        logger.info("文档已更新", document_id=document.id)
    
    async def delete_document(self, document_id: str) -> None:
        """删除文档（级联删除块）"""
        async with self.db.connection() as conn:
            await conn.execute(
                "DELETE FROM documents WHERE id = ?",
                (document_id,)
            )
            await conn.commit()
        
        logger.info("文档已删除", document_id=document_id)
    
    async def list_documents(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> list[Document]:
        """列出文档"""
        async with self.db.connection() as conn:
            async with conn.execute(
                """
                SELECT * FROM documents
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
        
        return [self._row_to_document(row) for row in rows]
    
    @staticmethod
    def _row_to_document(row: tuple) -> Document:
        """将数据库行转换为文档对象"""
        return Document(
            id=row[0],
            title=row[1],
            content=row[2],
            source=row[3],
            metadata=json.loads(row[4]) if row[4] else {},
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6])
        )


class ChunkStorage:
    """文档块存储层"""
    
    def __init__(self, db: Database) -> None:
        self.db = db
    
    async def create_chunks(self, chunks: list[Chunk]) -> None:
        """批量创建文档块"""
        async with self.db.connection() as conn:
            await conn.executemany(
                """
                INSERT INTO chunks (id, document_id, content, chunk_index, start_pos, end_pos, embedding, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.content,
                        chunk.chunk_index,
                        chunk.start_pos,
                        chunk.end_pos,
                        self._serialize_embedding(chunk.embedding),
                        json.dumps(chunk.metadata, ensure_ascii=False)
                    )
                    for chunk in chunks
                ]
            )
            await conn.commit()
        
        logger.info("文档块已创建", count=len(chunks))
    
    async def get_chunks(self, document_id: str) -> list[Chunk]:
        """获取文档的所有块"""
        async with self.db.connection() as conn:
            async with conn.execute(
                """
                SELECT * FROM chunks
                WHERE document_id = ?
                ORDER BY chunk_index
                """,
                (document_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        
        return [self._row_to_chunk(row) for row in rows]
    
    async def delete_chunks(self, document_id: str) -> None:
        """删除文档的所有块"""
        async with self.db.connection() as conn:
            await conn.execute(
                "DELETE FROM chunks WHERE document_id = ?",
                (document_id,)
            )
            await conn.commit()
        
        logger.info("文档块已删除", document_id=document_id)
    
    @staticmethod
    def _row_to_chunk(row: tuple) -> Chunk:
        """将数据库行转换为块对象"""
        return Chunk(
            id=row[0],
            document_id=row[1],
            content=row[2],
            chunk_index=row[3],
            start_pos=row[4],
            end_pos=row[5],
            embedding=ChunkStorage._deserialize_embedding(row[6]),
            metadata=json.loads(row[7]) if row[7] else {}
        )
    
    @staticmethod
    def _serialize_embedding(embedding: list[float] | None) -> bytes | None:
        """序列化向量嵌入"""
        if embedding is None:
            return None
        
        import struct
        return struct.pack(f'{len(embedding)}f', *embedding)
    
    @staticmethod
    def _deserialize_embedding(data: bytes | None) -> list[float] | None:
        """反序列化向量嵌入"""
        if data is None:
            return None
        
        import struct
        count = len(data) // 4
        return list(struct.unpack(f'{count}f', data))
```

## 文档分块

```python
# knowledge/chunker.py
import uuid
from typing import Iterator
import structlog

from lyxamour_mcp.knowledge.models import Chunk
from lyxamour_mcp.config.models import KnowledgeConfig

logger = structlog.get_logger(__name__)


class DocumentChunker:
    """文档分块器
    
    将长文档分割成小块，支持重叠。
    """
    
    def __init__(self, config: KnowledgeConfig) -> None:
        self.chunk_size = config.chunk_size
        self.chunk_overlap = config.chunk_overlap
    
    def chunk_document(
        self,
        document_id: str,
        content: str
    ) -> list[Chunk]:
        """分块文档
        
        Args:
            document_id: 文档ID
            content: 文档内容
        
        Returns:
            文档块列表
        """
        chunks = []
        
        for i, (chunk_text, start, end) in enumerate(self._split_text(content)):
            chunk = Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                content=chunk_text,
                chunk_index=i,
                start_pos=start,
                end_pos=end
            )
            chunks.append(chunk)
        
        logger.info(
            "文档分块完成",
            document_id=document_id,
            chunks=len(chunks)
        )
        
        return chunks
    
    def _split_text(self, text: str) -> Iterator[tuple[str, int, int]]:
        """分割文本
        
        Yields:
            (块文本, 起始位置, 结束位置)
        """
        if len(text) <= self.chunk_size:
            # 文本太短，不需要分块
            yield (text, 0, len(text))
            return
        
        start = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # 尝试在句子边界分割
            if end < len(text):
                # 查找最近的句子结束符
                sentence_ends = ['.', '!', '?', '\n', '。', '！', '？']
                best_end = end
                
                for i in range(end - 1, start + self.chunk_size // 2, -1):
                    if text[i] in sentence_ends:
                        best_end = i + 1
                        break
                
                end = best_end
            
            chunk_text = text[start:end]
            yield (chunk_text, start, end)
            
            # 计算下一个块的起始位置（考虑重叠）
            start = end - self.chunk_overlap
            
            # 确保至少前进一个字符
            if start >= end:
                start = end
```

## 检索层

```python
# knowledge/retrieval.py
from typing import Any
import structlog

from lyxamour_mcp.knowledge.db import Database
from lyxamour_mcp.knowledge.models import SearchResult
from lyxamour_mcp.config.models import KnowledgeConfig

logger = structlog.get_logger(__name__)


class Retriever:
    """知识检索器"""
    
    def __init__(self, db: Database, config: KnowledgeConfig) -> None:
        self.db = db
        self.config = config
    
    async def search_documents(
        self,
        query: str,
        limit: int = 10
    ) -> list[SearchResult]:
        """搜索文档（全文搜索）
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
        
        Returns:
            搜索结果列表
        """
        if not self.config.enable_fts:
            logger.warning("全文搜索未启用")
            return []
        
        logger.info("搜索文档", query=query, limit=limit)
        
        async with self.db.connection() as conn:
            async with conn.execute(
                """
                SELECT
                    d.id,
                    d.title,
                    d.content,
                    d.metadata,
                    fts.rank
                FROM documents_fts fts
                JOIN documents d ON fts.document_id = d.id
                WHERE documents_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        
        results = []
        for row in rows:
            import json
            results.append(SearchResult(
                document_id=row[0],
                title=row[1],
                content=row[2][:500],  # 截取前500字符
                score=-row[4],  # FTS5 rank 是负数
                metadata=json.loads(row[3]) if row[3] else {}
            ))
        
        logger.info("搜索完成", query=query, results=len(results))
        return results
    
    async def search_chunks(
        self,
        query: str,
        limit: int = 10
    ) -> list[SearchResult]:
        """搜索文档块（更精细的搜索）
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
        
        Returns:
            搜索结果列表
        """
        if not self.config.enable_fts:
            logger.warning("全文搜索未启用")
            return []
        
        logger.info("搜索文档块", query=query, limit=limit)
        
        async with self.db.connection() as conn:
            async with conn.execute(
                """
                SELECT
                    c.id,
                    c.document_id,
                    d.title,
                    c.content,
                    c.metadata,
                    fts.rank
                FROM chunks_fts fts
                JOIN chunks c ON fts.chunk_id = c.id
                JOIN documents d ON c.document_id = d.id
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        
        results = []
        for row in rows:
            import json
            results.append(SearchResult(
                document_id=row[1],
                chunk_id=row[0],
                title=row[2],
                content=row[3],
                score=-row[5],
                metadata=json.loads(row[4]) if row[4] else {}
            ))
        
        logger.info("搜索完成", query=query, results=len(results))
        return results
    
    async def vector_search(
        self,
        embedding: list[float],
        limit: int = 10
    ) -> list[SearchResult]:
        """向量搜索（需要启用向量支持）
        
        使用余弦相似度进行向量搜索。
        
        Args:
            embedding: 查询向量
            limit: 结果数量限制
        
        Returns:
            搜索结果列表
        """
        if not self.config.enable_vector:
            logger.warning("向量搜索未启用")
            return []
        
        logger.info("向量搜索", limit=limit)
        
        # TODO: 实现向量搜索
        # 需要额外的向量数据库或扩展
        
        return []
```

## 知识库管理器

```python
# knowledge/manager.py
import uuid
from typing import Any
import structlog

from lyxamour_mcp.knowledge.db import Database
from lyxamour_mcp.knowledge.storage import DocumentStorage, ChunkStorage
from lyxamour_mcp.knowledge.chunker import DocumentChunker
from lyxamour_mcp.knowledge.retrieval import Retriever
from lyxamour_mcp.knowledge.models import Document, SearchResult
from lyxamour_mcp.config.models import KnowledgeConfig

logger = structlog.get_logger(__name__)


class KnowledgeManager:
    """知识库管理器
    
    提供统一的知识库操作接口。
    """
    
    def __init__(self, config: KnowledgeConfig) -> None:
        self.config = config
        self.db = Database(config)
        self.doc_storage = DocumentStorage(self.db)
        self.chunk_storage = ChunkStorage(self.db)
        self.chunker = DocumentChunker(config)
        self.retriever = Retriever(self.db, config)
    
    async def initialize(self) -> None:
        """初始化知识库"""
        await self.db.initialize()
        logger.info("知识库管理器已初始化")
    
    async def close(self) -> None:
        """关闭知识库"""
        await self.db.close()
        logger.info("知识库管理器已关闭")
    
    async def add_document(
        self,
        title: str,
        content: str,
        source: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """添加文档
        
        自动分块和索引。
        
        Args:
            title: 文档标题
            content: 文档内容
            source: 文档来源
            metadata: 文档元数据
        
        Returns:
            文档ID
        """
        # 创建文档
        document = Document(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            source=source,
            metadata=metadata or {}
        )
        
        # 存储文档
        document_id = await self.doc_storage.create_document(document)
        
        # 分块
        if self.config.auto_index:
            chunks = self.chunker.chunk_document(document_id, content)
            await self.chunk_storage.create_chunks(chunks)
        
        logger.info("文档已添加", document_id=document_id)
        return document_id
    
    async def get_document(self, document_id: str) -> Document | None:
        """获取文档"""
        return await self.doc_storage.get_document(document_id)
    
    async def update_document(
        self,
        document_id: str,
        title: str | None = None,
        content: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """更新文档
        
        如果内容变更，重新分块。
        """
        document = await self.doc_storage.get_document(document_id)
        if document is None:
            raise ValueError(f"文档不存在: {document_id}")
        
        # 更新字段
        if title is not None:
            document.title = title
        if content is not None:
            document.content = content
        if source is not None:
            document.source = source
        if metadata is not None:
            document.metadata = metadata
        
        # 保存更新
        await self.doc_storage.update_document(document)
        
        # 如果内容变更，重新分块
        if content is not None and self.config.auto_index:
            await self.chunk_storage.delete_chunks(document_id)
            chunks = self.chunker.chunk_document(document_id, content)
            await self.chunk_storage.create_chunks(chunks)
        
        logger.info("文档已更新", document_id=document_id)
    
    async def delete_document(self, document_id: str) -> None:
        """删除文档"""
        await self.doc_storage.delete_document(document_id)
        logger.info("文档已删除", document_id=document_id)
    
    async def list_documents(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> list[Document]:
        """列出文档"""
        return await self.doc_storage.list_documents(limit, offset)
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        search_chunks: bool = True
    ) -> list[SearchResult]:
        """搜索知识库
        
        Args:
            query: 搜索查询
            limit: 结果数量限制
            search_chunks: 是否搜索块（更精细）
        
        Returns:
            搜索结果列表
        """
        if search_chunks:
            return await self.retriever.search_chunks(query, limit)
        else:
            return await self.retriever.search_documents(query, limit)
```

## 知识库工具集成

```python
# tools/builtin/knowledge.py
from typing import Annotated
import structlog

from lyxamour_mcp.tools.base import tool
from lyxamour_mcp.core.context import Context

logger = structlog.get_logger(__name__)


@tool(group="knowledge", description="添加文档到知识库")
async def add_knowledge(
    ctx: Context,
    title: Annotated[str, "文档标题"],
    content: Annotated[str, "文档内容"],
    source: Annotated[str | None, "文档来源"] = None
) -> str:
    """添加文档到知识库"""
    knowledge_manager = ctx.knowledge_manager
    
    document_id = await knowledge_manager.add_document(
        title=title,
        content=content,
        source=source
    )
    
    return f"文档已添加，ID: {document_id}"


@tool(group="knowledge", description="搜索知识库")
async def search_knowledge(
    ctx: Context,
    query: Annotated[str, "搜索查询"],
    limit: Annotated[int, "结果数量"] = 10
) -> list[dict]:
    """搜索知识库"""
    knowledge_manager = ctx.knowledge_manager
    
    results = await knowledge_manager.search(query, limit)
    
    return [
        {
            "document_id": r.document_id,
            "title": r.title,
            "content": r.content[:200],  # 前200字符
            "score": r.score
        }
        for r in results
    ]


@tool(group="knowledge", description="获取文档详情")
async def get_knowledge(
    ctx: Context,
    document_id: Annotated[str, "文档ID"]
) -> dict:
    """获取文档详情"""
    knowledge_manager = ctx.knowledge_manager
    
    document = await knowledge_manager.get_document(document_id)
    
    if document is None:
        raise ValueError(f"文档不存在: {document_id}")
    
    return {
        "id": document.id,
        "title": document.title,
        "content": document.content,
        "source": document.source,
        "metadata": document.metadata,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat()
    }
```

## 性能优化

### 批量操作

```python
async def add_documents_batch(self, documents: list[Document]) -> list[str]:
    """批量添加文档"""
    document_ids = []
    
    for document in documents:
        doc_id = await self.doc_storage.create_document(document)
        document_ids.append(doc_id)
        
        if self.config.auto_index:
            chunks = self.chunker.chunk_document(doc_id, document.content)
            await self.chunk_storage.create_chunks(chunks)
    
    return document_ids
```

### 索引优化

```sql
-- 创建复合索引
CREATE INDEX idx_chunks_doc_chunk ON chunks(document_id, chunk_index);

-- 分析统计信息
ANALYZE;
```

## 使用示例

```python
# 初始化知识库
from lyxamour_mcp.knowledge.manager import KnowledgeManager

config = KnowledgeConfig(
    enabled=True,
    db_path="~/.lyxamour/mcp/knowledge.db",
    enable_fts=True,
    chunk_size=512,
    chunk_overlap=50
)

manager = KnowledgeManager(config)
await manager.initialize()

# 添加文档
doc_id = await manager.add_document(
    title="Python 教程",
    content="Python 是一种高级编程语言...",
    source="https://example.com"
)

# 搜索
results = await manager.search("Python 编程", limit=5)
for result in results:
    print(f"{result.title}: {result.content[:100]}")

# 清理
await manager.close()
```
