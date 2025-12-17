"""
监控路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def get_status() -> dict[str, str]:
    """获取服务器状态"""
    # TODO: 实现状态获取逻辑
    return {"status": "running"}


@router.get("/metrics")
async def get_metrics() -> dict[str, int]:
    """获取性能指标"""
    # TODO: 实现指标获取逻辑
    return {"requests": 0, "errors": 0}
