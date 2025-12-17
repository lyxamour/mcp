"""
工具基类和装饰器
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class Tool:
    """
    工具元数据

    存储工具的基本信息
    """

    name: str
    func: Callable[..., Any]
    group: str = "default"
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def tool(
    group: str = "default",
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    工具装饰器

    用于标记函数为 MCP 工具

    Args:
        group: 工具分组名称
        name: 工具名称（默认使用函数名）
        description: 工具描述（默认使用函数文档字符串）

    Returns:
        装饰后的函数

    Example:
        @tool(group="filesystem", description="读取文件内容")
        async def read_file(ctx: Context, path: str) -> str:
            '''读取指定路径的文件内容'''
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or ""

        # 将工具元数据附加到函数
        func.__tool_metadata__ = Tool(  # type: ignore
            name=tool_name,
            func=func,
            group=group,
            description=tool_description.strip(),
        )

        return func

    return decorator
