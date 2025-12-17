"""
上下文管理 - 为工具执行提供运行时上下文
"""

from typing import Any

from pydantic import BaseModel, Field


class Context(BaseModel):
    """
    工具执行上下文

    提供工具执行所需的运行时信息和状态
    """

    # 请求元数据
    request_id: str = Field(description="请求唯一标识符")
    session_id: str | None = Field(default=None, description="会话标识符")

    # 配置信息
    config: dict[str, Any] = Field(default_factory=dict, description="配置信息")

    # 工具特定状态
    state: dict[str, Any] = Field(default_factory=dict, description="工具状态数据")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    class Config:
        """Pydantic 配置"""

        arbitrary_types_allowed = True
