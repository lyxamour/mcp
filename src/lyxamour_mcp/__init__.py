"""
lyxamour-mcp - 完整的 Python MCP (Model Context Protocol) 工具实现

这是一个基于 FastMCP 的 MCP 服务器实现，提供：
- 多种传输协议支持（stdio、SSE、HTTP Stream）
- 灵活的工具分组和管理系统
- 内置知识库功能
- Web 管理界面
- 完整的配置系统
"""

from importlib.metadata import version

__version__ = version("lyxamour-mcp")
__all__ = ["__version__"]
