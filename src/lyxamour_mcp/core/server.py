"""
MCP 服务器 - 核心服务器实现
"""

import asyncio
from typing import Any

import structlog
from fastmcp import FastMCP

from lyxamour_mcp.config.loader import ConfigLoader
from lyxamour_mcp.config.models import Config
from lyxamour_mcp.tools.manager import ToolManager
from lyxamour_mcp.transport.base import Transport

logger = structlog.get_logger(__name__)


class MCPServer:
    """
    MCP 服务器主类

    协调各组件工作，处理 MCP 协议通信
    """

    def __init__(self, config: Config | None = None) -> None:
        """
        初始化 MCP 服务器

        Args:
            config: 配置对象，如果为 None 则自动加载
        """
        self.config = config or ConfigLoader.load()
        self.mcp = FastMCP("lyxamour-mcp")
        self.tool_manager = ToolManager(self.config)
        self.transport: Transport | None = None

        logger.info("MCP 服务器已初始化", version=self.config.server.version)

    async def start(self, transport: Transport) -> None:
        """
        启动 MCP 服务器

        Args:
            transport: 传输层实例
        """
        self.transport = transport
        logger.info("启动 MCP 服务器", transport=type(transport).__name__)

        # 注册工具到 FastMCP
        await self.tool_manager.register_tools(self.mcp)

        # 启动传输层
        await transport.start()

        # 处理消息
        try:
            async for message in transport.receive():
                await self._handle_message(message)
        except asyncio.CancelledError:
            logger.info("服务器收到停止信号")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """停止 MCP 服务器"""
        logger.info("停止 MCP 服务器")
        if self.transport:
            await self.transport.close()

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """
        处理接收到的消息

        Args:
            message: JSON-RPC 消息
        """
        # TODO: 实现完整的 JSON-RPC 2.0 消息处理
        logger.debug("收到消息", message=message)
