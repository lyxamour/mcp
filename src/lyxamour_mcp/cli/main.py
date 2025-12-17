"""
CLI 主入口
"""

import asyncio

import structlog
import typer
from rich.console import Console

from lyxamour_mcp.config.loader import ConfigLoader
from lyxamour_mcp.core.server import MCPServer
from lyxamour_mcp.transport.http_stream import HTTPStreamTransport
from lyxamour_mcp.transport.sse import SSETransport
from lyxamour_mcp.transport.stdio import StdioTransport
from lyxamour_mcp.utils.logger import setup_logger

app = typer.Typer(help="lyxamour-mcp - MCP 工具服务器")
console = Console()
logger = structlog.get_logger(__name__)


@app.command()
def start(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="传输类型: stdio, sse, http_stream",
    ),
    config_file: str = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
    ),
) -> None:
    """启动 MCP 服务器"""
    # 加载配置
    config = ConfigLoader.load()

    # 配置日志
    setup_logger(config.log)

    console.print(f"[green]启动 MCP 服务器[/green]")
    console.print(f"传输类型: {transport}")

    # 创建服务器
    server = MCPServer(config)

    # 创建传输层
    if transport == "stdio":
        transport_instance = StdioTransport()
    elif transport == "sse":
        transport_instance = SSETransport(
            host=config.transport.host,
            port=config.transport.port,
        )
    elif transport == "http_stream":
        transport_instance = HTTPStreamTransport(
            host=config.transport.host,
            port=config.transport.port,
            path=config.transport.path,
        )
    else:
        console.print(f"[red]不支持的传输类型: {transport}[/red]")
        raise typer.Exit(1)

    # 启动服务器
    try:
        asyncio.run(server.start(transport_instance))
    except KeyboardInterrupt:
        console.print("\n[yellow]收到停止信号，正在关闭...[/yellow]")
    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        logger.exception("服务器启动失败")
        raise typer.Exit(1)


@app.command()
def version() -> None:
    """显示版本信息"""
    from lyxamour_mcp import __version__

    console.print(f"lyxamour-mcp version {__version__}")


if __name__ == "__main__":
    app()
