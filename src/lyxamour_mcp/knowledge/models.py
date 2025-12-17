"""
知识库数据模型
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Document(BaseModel):
    """文档模型"""

    id: str = Field(description="文档唯一标识符")
    title: str = Field(description="文档标题")
    content: str = Field(description="文档内容")
    source: str = Field(description="文档来源")
    metadata: dict[str, str] = Field(default_factory=dict, description="文档元数据")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class Chunk(BaseModel):
    """文档块模型"""

    id: str = Field(description="文档块唯一标识符")
    document_id: str = Field(description="所属文档ID")
    content: str = Field(description="文档块内容")
    position: int = Field(description="在文档中的位置")
    metadata: dict[str, str] = Field(default_factory=dict, description="文档块元数据")
