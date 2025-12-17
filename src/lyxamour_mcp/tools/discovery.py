"""
工具发现 - 自动发现可用工具
"""

import importlib
import inspect
from pathlib import Path

import structlog

from lyxamour_mcp.tools.base import Tool

logger = structlog.get_logger(__name__)


class ToolDiscovery:
    """
    工具发现器

    自动发现内置工具和插件工具
    """

    def discover_builtin_tools(self) -> list[Tool]:
        """
        发现内置工具

        Returns:
            list[Tool]: 工具列表
        """
        tools: list[Tool] = []

        # 导入内置工具模块
        builtin_modules = ["filesystem", "text"]

        for module_name in builtin_modules:
            try:
                module = importlib.import_module(f"lyxamour_mcp.tools.builtin.{module_name}")
                tools.extend(self._extract_tools_from_module(module))
                logger.debug("发现内置工具模块", module=module_name)
            except ImportError as e:
                logger.warning("导入内置工具模块失败", module=module_name, error=str(e))

        return tools

    def discover_plugin_tools(self, plugin_dirs: list[Path]) -> list[Tool]:
        """
        发现插件工具

        Args:
            plugin_dirs: 插件目录列表

        Returns:
            list[Tool]: 工具列表
        """
        tools: list[Tool] = []

        for plugin_dir in plugin_dirs:
            if not plugin_dir.exists():
                logger.warning("插件目录不存在", path=str(plugin_dir))
                continue

            # TODO: 实现插件发现逻辑
            logger.debug("扫描插件目录", path=str(plugin_dir))

        return tools

    def _extract_tools_from_module(self, module: object) -> list[Tool]:
        """
        从模块中提取工具

        Args:
            module: Python 模块

        Returns:
            list[Tool]: 工具列表
        """
        tools: list[Tool] = []

        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and hasattr(obj, "__tool_metadata__"):
                tool_obj: Tool = obj.__tool_metadata__
                tools.append(tool_obj)
                logger.debug("发现工具", name=tool_obj.name, group=tool_obj.group)

        return tools
