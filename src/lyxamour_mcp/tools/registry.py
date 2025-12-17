"""
工具注册表 - 管理所有已注册的工具
"""

import structlog

from lyxamour_mcp.tools.base import Tool

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """
    工具注册表

    单例模式，管理所有注册的工具
    """

    _instance: "ToolRegistry | None" = None
    _tools: dict[str, Tool] = {}
    _groups: dict[str, list[str]] = {}

    def __new__(cls) -> "ToolRegistry":
        """确保单例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, tool_obj: Tool) -> None:
        """
        注册工具

        Args:
            tool_obj: 工具对象
        """
        if tool_obj.name in self._tools:
            logger.warning("工具已存在，将被覆盖", name=tool_obj.name)

        self._tools[tool_obj.name] = tool_obj

        # 添加到分组
        if tool_obj.group not in self._groups:
            self._groups[tool_obj.group] = []
        if tool_obj.name not in self._groups[tool_obj.group]:
            self._groups[tool_obj.group].append(tool_obj.name)

        logger.info("工具已注册", name=tool_obj.name, group=tool_obj.group)

    def unregister(self, name: str) -> None:
        """
        注销工具

        Args:
            name: 工具名称
        """
        if name in self._tools:
            tool_obj = self._tools[name]
            del self._tools[name]

            # 从分组中移除
            if tool_obj.group in self._groups:
                self._groups[tool_obj.group].remove(name)

            logger.info("工具已注销", name=name)

    def get(self, name: str) -> Tool | None:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            Tool | None: 工具对象，不存在返回 None
        """
        return self._tools.get(name)

    def get_all(self) -> dict[str, Tool]:
        """获取所有工具"""
        return self._tools.copy()

    def get_by_group(self, group: str) -> list[Tool]:
        """
        获取指定分组的所有工具

        Args:
            group: 分组名称

        Returns:
            list[Tool]: 工具列表
        """
        tool_names = self._groups.get(group, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_groups(self) -> list[str]:
        """获取所有分组名称"""
        return list(self._groups.keys())

    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()
        self._groups.clear()
        logger.info("工具注册表已清空")
