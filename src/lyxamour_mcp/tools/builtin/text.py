"""
文本处理工具 - 提供文本分析和处理功能
"""

import re
from typing import Annotated

from lyxamour_mcp.core.context import Context
from lyxamour_mcp.tools.base import tool


@tool(group="text", description="搜索文本")
async def search_text(
    ctx: Context,
    text: Annotated[str, "要搜索的文本"],
    pattern: Annotated[str, "搜索模式（正则表达式）"],
    case_sensitive: Annotated[bool, "是否区分大小写"] = True,
) -> list[str]:
    """
    在文本中搜索匹配的内容

    Args:
        ctx: 执行上下文
        text: 要搜索的文本
        pattern: 搜索模式（正则表达式）
        case_sensitive: 是否区分大小写

    Returns:
        list[str]: 匹配结果列表
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    matches = re.findall(pattern, text, flags=flags)
    return matches


@tool(group="text", description="统计文本词数")
async def count_words(
    ctx: Context,
    text: Annotated[str, "要统计的文本"],
) -> dict[str, int]:
    """
    统计文本中的词数和字符数

    Args:
        ctx: 执行上下文
        text: 要统计的文本

    Returns:
        dict[str, int]: 统计结果（词数、字符数、行数）
    """
    words = text.split()
    lines = text.split("\n")

    return {
        "words": len(words),
        "characters": len(text),
        "lines": len(lines),
    }
