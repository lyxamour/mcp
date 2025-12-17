"""
传输层基类 - 定义所有传输协议的通用接口
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class Transport(ABC):
    """
    传输层抽象基类

    定义 MCP 传输协议的通用接口
    """

    @abstractmethod
    async def start(self) -> None:
        """启动传输层"""
        pass

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """
        发送消息

        Args:
            message: JSON-RPC 2.0 格式的消息
        """
        pass

    @abstractmethod
    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """
        接收消息

        Yields:
            dict: JSON-RPC 2.0 格式的消息
        """
        yield {}

    @abstractmethod
    async def close(self) -> None:
        """关闭传输层"""
        pass
