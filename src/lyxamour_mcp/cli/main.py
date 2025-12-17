"""
CLI 主入口
"""

import asyncio
import webbrowser

import structlog
import typer
from rich.console import Console

from lyxamour_mcp.config.loader import ConfigLoader
from lyxamour_mcp.core.server import MCPServer
from lyxamour_mcp.transport.http_stream import HTTPStreamTransport
from lyxamour_mcp.transport.sse import SSETransport
from lyxamour_mcp.transport.stdio import StdioTransport
from lyxamour_mcp.utils.logger import setup_logger
from lyxamour_mcp.web.app import run_web_server

app = typer.Typer(help="lyxamour-mcp - MCP 工具服务器")
console = Console()
logger = structlog.get_logger(__name__)


async def _start_services(
    server: MCPServer,
    transport_instance,
    config,
    transport_type: str,
) -> None:
    """
    启动服务（MCP 服务器和 Web 服务器）

    Args:
        server: MCP 服务器实例
        transport_instance: 传输层实例
        config: 配置对象
        transport_type: 传输类型（stdio, sse, http_stream）
    """
    tasks = []

    # 创建 MCP 服务器任务
    mcp_task = asyncio.create_task(server.start(transport_instance))
    tasks.append(mcp_task)

    # 如果启用了 Web 界面，创建 Web 服务器任务
    if config.web.enabled:
        # stdio 模式使用随机端口并自动打开浏览器
        use_random_port = transport_type == "stdio"
        web_port = 0 if use_random_port else None

        # 端口回调函数，用于获取实际端口并打开浏览器
        def on_port_ready(actual_port: int) -> None:
            url = f"http://{config.web.host}:{actual_port}"
            console.print(f"[green]Web 管理界面:[/green] {url}")

            # 仅在 stdio 模式下自动打开浏览器
            if use_random_port:
                try:
                    webbrowser.open(url)
                    logger.info("已自动打开浏览器", url=url)
                except Exception as e:
                    logger.warning("打开浏览器失败", error=str(e))

        web_task = asyncio.create_task(
            run_web_server(config, port=web_port, port_callback=on_port_ready)
        )
        tasks.append(web_task)

    # 等待所有任务完成（或被取消）
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("所有服务已停止")


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

    # 启动服务
    try:
        asyncio.run(_start_services(server, transport_instance, config, transport))
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
