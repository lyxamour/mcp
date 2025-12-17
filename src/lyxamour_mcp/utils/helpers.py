"""
辅助函数
"""

import uuid
from typing import Any


def generate_id() -> str:
    """
    生成唯一ID

    Returns:
        str: UUID字符串
    """
    return str(uuid.uuid4())


def merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    深度合并字典

    Args:
        base: 基础字典
        override: 覆盖字典

    Returns:
        dict: 合并后的字典
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dict(result[key], value)
        else:
            result[key] = value

    return result
