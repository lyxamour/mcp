"""
知识库管理路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/documents")
async def add_document() -> dict[str, str]:
    """添加文档"""
    # TODO: 实现文档添加逻辑
    return {"id": ""}


@router.get("/search")
async def search_documents(q: str) -> dict[str, list[dict[str, str]]]:
    """搜索文档"""
    # TODO: 实现文档搜索逻辑
    return {"results": []}
