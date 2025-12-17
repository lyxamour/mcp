"""
Web 应用主文件
"""

import asyncio
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


async def run_web_server(config: Config) -> None:
    """
    运行 Web 服务器

    Args:
        config: 配置对象
    """
    if not config.web.enabled:
        logger.info("Web 界面未启用")
        return

    app = create_app(config)

    # 创建 uvicorn 配置
    uvicorn_config = uvicorn.Config(
        app,
        host=config.web.host,
        port=config.web.port,
        log_level="info",
        access_log=False,  # 使用 structlog 而非 uvicorn 的日志
    )

    server = uvicorn.Server(uvicorn_config)

    logger.info(
        "启动 Web 服务器",
        host=config.web.host,
        port=config.web.port,
        url=f"http://{config.web.host}:{config.web.port}",
    )

    # 运行服务器
    await server.serve()
