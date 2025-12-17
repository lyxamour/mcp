"""
Web 应用主文件
"""

import asyncio
from collections.abc import Callable
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from lyxamour_mcp.config.models import Config
from lyxamour_mcp.web.routes import config as config_routes
from lyxamour_mcp.web.routes import knowledge, monitor, tools

logger = structlog.get_logger(__name__)


def create_app(config: Config) -> FastAPI:
    """
    创建 FastAPI 应用

    Args:
        config: 配置对象

    Returns:
        FastAPI: 应用实例
    """
    app = FastAPI(
        title="lyxamour-mcp Web 界面",
        description="MCP 工具服务器管理界面",
        version="0.1.0",
    )

    # 注册路由
    app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
    app.include_router(config_routes.router, prefix="/api/config", tags=["config"])
    app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
    app.include_router(monitor.router, prefix="/api/monitor", tags=["monitor"])

    # 挂载静态文件
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    logger.info("Web 应用已创建")

    return app


async def run_web_server(
    config: Config,
    port: int | None = None,
    port_callback: Callable[[int], None] | None = None,
) -> None:
    """
    运行 Web 服务器

    Args:
        config: 配置对象
        port: 端口号，None 则使用配置文件中的端口，0 则使用随机端口
        port_callback: 端口回调函数，在服务器启动后调用，传入实际端口号
    """
    if not config.web.enabled:
        logger.info("Web 界面未启用")
        return

    app = create_app(config)

    # 确定使用的端口
    actual_port = port if port is not None else config.web.port

    # 创建 uvicorn 配置
    uvicorn_config = uvicorn.Config(
        app,
        host=config.web.host,
        port=actual_port,
        log_level="info",
        access_log=False,  # 使用 structlog 而非 uvicorn 的日志
    )

    server = uvicorn.Server(uvicorn_config)

    # 如果使用端口 0，需要特殊处理以获取实际端口
    if actual_port == 0:
        # 创建一个临时 socket 来获取可用端口
        import socket as sock_module

        temp_sock = sock_module.socket(sock_module.AF_INET, sock_module.SOCK_STREAM)
        temp_sock.bind((config.web.host, 0))
        actual_port = temp_sock.getsockname()[1]
        temp_sock.close()

        # 重新创建配置使用获取到的端口
        uvicorn_config = uvicorn.Config(
            app,
            host=config.web.host,
            port=actual_port,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(uvicorn_config)

    logger.info(
        "启动 Web 服务器",
        host=config.web.host,
        port=actual_port,
        url=f"http://{config.web.host}:{actual_port}",
    )

    # 调用端口回调
    if port_callback:
        port_callback(actual_port)

    # 运行服务器
    await server.serve()
