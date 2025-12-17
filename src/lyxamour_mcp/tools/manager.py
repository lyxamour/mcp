"""
工具管理器 - 协调工具注册、发现和执行
"""

from typing import Any

import structlog
from fastmcp import FastMCP

from lyxamour_mcp.config.models import Config
from lyxamour_mcp.tools.discovery import ToolDiscovery
from lyxamour_mcp.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class ToolManager:
    """
    工具管理器

    负责工具的发现、注册、启用/禁用管理
    """

    def __init__(self, config: Config) -> None:
        """
        初始化工具管理器

        Args:
            config: 配置对象
        """
        self.config = config
        self.registry = ToolRegistry()
        self.discovery = ToolDiscovery()
        self._enabled_tools: set[str] = set()
        self._enabled_groups: set[str] = set()

        # 根据配置初始化启用的工具分组
        for group_config in config.tool_groups:
            if group_config.enabled:
                self._enabled_groups.add(group_config.name)
                self._enabled_tools.update(group_config.tools)

    async def discover_tools(self) -> None:
        """发现并注册所有可用工具"""
        logger.info("开始发现工具")

        # 发现内置工具
        builtin_tools = self.discovery.discover_builtin_tools()
        for tool_obj in builtin_tools:
            self.registry.register(tool_obj)

        # 发现插件工具
        if self.config.plugin.enabled:
            plugin_tools = self.discovery.discover_plugin_tools(self.config.plugin.plugin_dirs)
            for tool_obj in plugin_tools:
                self.registry.register(tool_obj)

        logger.info("工具发现完成", total=len(self.registry.get_all()))

    async def register_tools(self, mcp: FastMCP) -> None:
        """
        将工具注册到 FastMCP 实例

        Args:
            mcp: FastMCP 实例
        """
        await self.discover_tools()

        # 注册启用的工具到 FastMCP
        for tool_name, tool_obj in self.registry.get_all().items():
            if self.is_tool_enabled(tool_name):
                # TODO: 将工具函数注册到 FastMCP
                logger.debug("注册工具到 MCP", name=tool_name)

    def is_tool_enabled(self, tool_name: str) -> bool:
        """
        检查工具是否启用

        Args:
            tool_name: 工具名称

        Returns:
            bool: 是否启用
        """
        tool_obj = self.registry.get(tool_name)
        if not tool_obj:
            return False

        # 检查分组是否启用
        if tool_obj.group not in self._enabled_groups:
            return False

        # 检查工具本身是否在禁用列表中
        return tool_name in self._enabled_tools or not self._enabled_tools

    def enable_tool(self, tool_name: str) -> None:
        """
        启用工具

        Args:
            tool_name: 工具名称
        """
        self._enabled_tools.add(tool_name)
        logger.info("工具已启用", name=tool_name)

    def disable_tool(self, tool_name: str) -> None:
        """
        禁用工具

        Args:
            tool_name: 工具名称
        """
        self._enabled_tools.discard(tool_name)
        logger.info("工具已禁用", name=tool_name)

    def enable_group(self, group_name: str) -> None:
        """
        启用工具分组

        Args:
            group_name: 分组名称
        """
        self._enabled_groups.add(group_name)
        logger.info("工具分组已启用", group=group_name)

    def disable_group(self, group_name: str) -> None:
        """
        禁用工具分组

        Args:
            group_name: 分组名称
        """
        self._enabled_groups.discard(group_name)
        logger.info("工具分组已禁用", group=group_name)

    def get_enabled_tools(self) -> dict[str, Any]:
        """获取所有启用的工具"""
        return {
            name: tool_obj
            for name, tool_obj in self.registry.get_all().items()
            if self.is_tool_enabled(name)
        }
