"""
Web 应用主文件
"""

from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from lyxamour_mcp.config.models import Config
from lyxamour_mcp.web.routes import config, knowledge, monitor, tools

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
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
    app.include_router(monitor.router, prefix="/api/monitor", tags=["monitor"])

    # 挂载静态文件
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    logger.info("Web 应用已创建")

    return app
