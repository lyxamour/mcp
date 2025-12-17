"""
文件系统工具 - 提供文件和目录操作
"""

from pathlib import Path
from typing import Annotated

import aiofiles

from lyxamour_mcp.core.context import Context
from lyxamour_mcp.tools.base import tool


@tool(group="filesystem", description="读取文件内容")
async def read_file(
    ctx: Context,
    path: Annotated[str, "文件路径"],
    encoding: Annotated[str, "编码格式"] = "utf-8",
) -> str:
    """
    读取文件内容

    Args:
        ctx: 执行上下文
        path: 文件路径
        encoding: 编码格式

    Returns:
        str: 文件内容
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    async with aiofiles.open(file_path, encoding=encoding) as f:
        content = await f.read()

    return content


@tool(group="filesystem", description="写入文件内容")
async def write_file(
    ctx: Context,
    path: Annotated[str, "文件路径"],
    content: Annotated[str, "文件内容"],
    encoding: Annotated[str, "编码格式"] = "utf-8",
) -> str:
    """
    写入文件内容

    Args:
        ctx: 执行上下文
        path: 文件路径
        content: 文件内容
        encoding: 编码格式

    Returns:
        str: 成功消息
    """
    file_path = Path(path)

    # 确保父目录存在
    file_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(file_path, "w", encoding=encoding) as f:
        await f.write(content)

    return f"文件已写入: {path}"


@tool(group="filesystem", description="列出目录内容")
async def list_directory(
    ctx: Context,
    path: Annotated[str, "目录路径"] = ".",
) -> list[str]:
    """
    列出目录内容

    Args:
        ctx: 执行上下文
        path: 目录路径

    Returns:
        list[str]: 文件和目录列表
    """
    dir_path = Path(path)

    if not dir_path.exists():
        raise FileNotFoundError(f"目录不存在: {path}")

    if not dir_path.is_dir():
        raise NotADirectoryError(f"不是目录: {path}")

    return [item.name for item in dir_path.iterdir()]
