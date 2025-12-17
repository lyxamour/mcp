---
name: web-interface-design
description: MCP 工具 Web 界面详细设计
auto-activate:
  always: true
---

# Web 界面设计

## 概述

Web 界面提供图形化管理界面，基于 FastAPI + 现代 HTML/CSS/JS 实现：

- 工具管理（查看、启用/禁用）
- 配置管理（查看、编辑、验证）
- 知识库管理（上传、搜索、查看）
- 实时监控（日志、性能指标）
- WebSocket 实时更新

## 技术栈

### 后端

- **FastAPI**: ASGI Web 框架
- **Uvicorn**: ASGI 服务器
- **Pydantic**: 数据验证
- **WebSocket**: 实时通信

### 前端

- **原生 HTML/CSS/JS**: 无构建依赖
- **Alpine.js**: 轻量级响应式框架（可选）
- **Tailwind CSS**: 实用样式框架（CDN）
- **Chart.js**: 图表库（监控）

## FastAPI 应用架构

### 主应用

```python
# web/app.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import structlog

from lyxamour_mcp.web.routes import tools, config, knowledge, monitor
from lyxamour_mcp.config.models import WebConfig

logger = structlog.get_logger(__name__)


def create_app(
    web_config: WebConfig,
    **dependencies
) -> FastAPI:
    """创建 FastAPI 应用

    Args:
        web_config: Web 配置
        **dependencies: 依赖注入（如 ToolManager, KnowledgeManager 等）

    Returns:
        FastAPI 应用实例
    """
    app = FastAPI(
        title="LyxAmour MCP 管理界面",
        description="MCP 工具集管理和监控界面",
        version="1.0.0",
        docs_url=f"{web_config.api_prefix}/docs",
        redoc_url=f"{web_config.api_prefix}/redoc"
    )

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=web_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # 静态文件
    static_dir = Path(__file__).parent / web_config.static_dir
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 注册路由
    app.include_router(
        tools.router,
        prefix=f"{web_config.api_prefix}/tools",
        tags=["tools"]
    )
    app.include_router(
        config.router,
        prefix=f"{web_config.api_prefix}/config",
        tags=["config"]
    )
    app.include_router(
        knowledge.router,
        prefix=f"{web_config.api_prefix}/knowledge",
        tags=["knowledge"]
    )
    app.include_router(
        monitor.router,
        prefix=f"{web_config.api_prefix}/monitor",
        tags=["monitor"]
    )

    # 依赖注入
    app.state.dependencies = dependencies

    # 首页
    @app.get("/", response_class=HTMLResponse)
    async def index():
        """返回主页面"""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return index_file.read_text(encoding='utf-8')
        return "<h1>MCP 管理界面</h1>"

    logger.info("FastAPI 应用已创建")
    return app


class WebServer:
    """Web 服务器包装器"""

    def __init__(
        self,
        config: WebConfig,
        **dependencies
    ) -> None:
        self.config = config
        self.app = create_app(config, **dependencies)

    async def start(self) -> None:
        """启动 Web 服务器"""
        import uvicorn

        logger.info(
            "启动 Web 服务器",
            host=self.config.host,
            port=self.config.port
        )

        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        )

        server = uvicorn.Server(config)
        await server.serve()

    def run_sync(self) -> None:
        """同步启动（阻塞）"""
        import uvicorn

        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        )
```

## API 路由设计

### 工具管理路由

```python
# web/routes/tools.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any
import structlog

from lyxamour_mcp.tools.manager import ToolManager
from lyxamour_mcp.web.dependencies import get_tool_manager

logger = structlog.get_logger(__name__)

router = APIRouter()


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    group: str
    description: str
    enabled: bool
    parameters: dict[str, Any]


class ToolStatusUpdate(BaseModel):
    """工具状态更新"""
    enabled: bool


class GroupStatusUpdate(BaseModel):
    """工具组状态更新"""
    enabled: bool


@router.get("/", response_model=list[ToolInfo])
async def list_tools(
    group: str | None = None,
    enabled_only: bool = False,
    manager: ToolManager = Depends(get_tool_manager)
):
    """列出所有工具"""
    tools = []

    for metadata in manager.registry.list_tools(group=group, enabled_only=False):
        tools.append(ToolInfo(
            name=metadata.name,
            group=metadata.group,
            description=metadata.description,
            enabled=manager.is_tool_enabled(metadata.name),
            parameters=metadata.parameters
        ))

    if enabled_only:
        tools = [t for t in tools if t.enabled]

    return tools


@router.get("/groups")
async def list_groups(
    manager: ToolManager = Depends(get_tool_manager)
):
    """列出所有工具组"""
    groups = {}

    for group_name in manager.registry.get_all_groups():
        tool_names = manager.registry.get_group_tools(group_name)
        enabled_count = sum(
            1 for name in tool_names
            if manager.is_tool_enabled(name)
        )

        groups[group_name] = {
            "name": group_name,
            "total": len(tool_names),
            "enabled": enabled_count
        }

    return list(groups.values())


@router.get("/{tool_name}", response_model=ToolInfo)
async def get_tool(
    tool_name: str,
    manager: ToolManager = Depends(get_tool_manager)
):
    """获取工具详情"""
    metadata = manager.registry.get_metadata(tool_name)

    if metadata is None:
        raise HTTPException(status_code=404, detail="工具不存在")

    return ToolInfo(
        name=metadata.name,
        group=metadata.group,
        description=metadata.description,
        enabled=manager.is_tool_enabled(metadata.name),
        parameters=metadata.parameters
    )


@router.patch("/{tool_name}/status")
async def update_tool_status(
    tool_name: str,
    update: ToolStatusUpdate,
    manager: ToolManager = Depends(get_tool_manager)
):
    """更新工具启用状态"""
    if manager.registry.get(tool_name) is None:
        raise HTTPException(status_code=404, detail="工具不存在")

    manager.set_tool_enabled(tool_name, update.enabled)

    return {"status": "ok", "enabled": update.enabled}


@router.patch("/groups/{group_name}/status")
async def update_group_status(
    group_name: str,
    update: GroupStatusUpdate,
    manager: ToolManager = Depends(get_tool_manager)
):
    """更新工具组启用状态"""
    if group_name not in manager.registry.get_all_groups():
        raise HTTPException(status_code=404, detail="工具组不存在")

    manager.set_group_enabled(group_name, update.enabled)

    return {"status": "ok", "enabled": update.enabled}
```

### 配置管理路由

```python
# web/routes/config.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any
import structlog

from lyxamour_mcp.config.models import Config
from lyxamour_mcp.config.validator import validate_config
from lyxamour_mcp.web.dependencies import get_config

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/")
async def get_current_config(
    config: Config = Depends(get_config)
):
    """获取当前配置"""
    return config.model_dump()


@router.get("/validate")
async def validate_current_config(
    config: Config = Depends(get_config)
):
    """验证当前配置"""
    try:
        validate_config(config)
        return {"valid": True, "message": "配置有效"}
    except Exception as e:
        return {"valid": False, "message": str(e)}


@router.post("/reload")
async def reload_config():
    """重新加载配置"""
    # TODO: 实现配置重载逻辑
    return {"status": "ok", "message": "配置已重载"}
```

### 知识库管理路由

```python
# web/routes/knowledge.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Any
import structlog

from lyxamour_mcp.knowledge.manager import KnowledgeManager
from lyxamour_mcp.web.dependencies import get_knowledge_manager

logger = structlog.get_logger(__name__)

router = APIRouter()


class DocumentCreate(BaseModel):
    """文档创建请求"""
    title: str
    content: str
    source: str | None = None
    metadata: dict[str, Any] = {}


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    limit: int = 10
    search_chunks: bool = True


@router.post("/documents")
async def create_document(
    doc: DocumentCreate,
    manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """创建文档"""
    document_id = await manager.add_document(
        title=doc.title,
        content=doc.content,
        source=doc.source,
        metadata=doc.metadata
    )

    return {"document_id": document_id}


@router.get("/documents")
async def list_documents(
    limit: int = 10,
    offset: int = 0,
    manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """列出文档"""
    documents = await manager.list_documents(limit, offset)

    return [
        {
            "id": doc.id,
            "title": doc.title,
            "source": doc.source,
            "created_at": doc.created_at.isoformat()
        }
        for doc in documents
    ]


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """获取文档详情"""
    document = await manager.get_document(document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "id": document.id,
        "title": document.title,
        "content": document.content,
        "source": document.source,
        "metadata": document.metadata,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat()
    }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """删除文档"""
    await manager.delete_document(document_id)
    return {"status": "ok"}


@router.post("/search")
async def search_knowledge(
    request: SearchRequest,
    manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """搜索知识库"""
    results = await manager.search(
        query=request.query,
        limit=request.limit,
        search_chunks=request.search_chunks
    )

    return [
        {
            "document_id": r.document_id,
            "title": r.title,
            "content": r.content,
            "score": r.score,
            "metadata": r.metadata
        }
        for r in results
    ]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = None,
    manager: KnowledgeManager = Depends(get_knowledge_manager)
):
    """上传文档文件"""
    content = await file.read()
    text_content = content.decode('utf-8')

    document_id = await manager.add_document(
        title=title or file.filename,
        content=text_content,
        source=file.filename
    )

    return {"document_id": document_id}
```

### 监控路由

```python
# web/routes/monitor.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Any
import asyncio
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """接受连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket 连接已建立", count=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """断开连接"""
        self.active_connections.remove(websocket)
        logger.info("WebSocket 连接已断开", count=len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """广播消息"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error("发送消息失败", error=str(e))


manager = ConnectionManager()


@router.get("/stats")
async def get_stats():
    """获取系统统计信息"""
    # TODO: 实现实际统计
    return {
        "tools": {
            "total": 10,
            "enabled": 8
        },
        "documents": {
            "total": 42
        },
        "uptime": 3600
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时更新"""
    await manager.connect(websocket)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()

            # 处理消息
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            # 模拟实时更新
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/logs")
async def get_recent_logs(
    limit: int = 100
):
    """获取最近日志"""
    # TODO: 从日志系统读取
    return []
```

## 依赖注入

```python
# web/dependencies.py
from fastapi import Request
from typing import Any

from lyxamour_mcp.tools.manager import ToolManager
from lyxamour_mcp.config.models import Config
from lyxamour_mcp.knowledge.manager import KnowledgeManager


def get_tool_manager(request: Request) -> ToolManager:
    """获取工具管理器"""
    return request.app.state.dependencies["tool_manager"]


def get_config(request: Request) -> Config:
    """获取配置"""
    return request.app.state.dependencies["config"]


def get_knowledge_manager(request: Request) -> KnowledgeManager:
    """获取知识库管理器"""
    return request.app.state.dependencies["knowledge_manager"]
```

## 前端界面

### HTML 结构

```html
<!-- web/static/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MCP 管理界面</title>

    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Alpine.js -->
    <script
      defer
      src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"
    ></script>

    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
      [x-cloak] {
        display: none !important;
      }
    </style>
  </head>
  <body class="bg-gray-100">
    <div x-data="app()" x-cloak class="min-h-screen">
      <!-- 导航栏 -->
      <nav class="bg-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4">
          <div class="flex justify-between h-16">
            <div class="flex space-x-8">
              <a
                href="#"
                @click.prevent="currentTab = 'tools'"
                :class="{'border-blue-500 text-gray-900': currentTab === 'tools'}"
                class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
              >
                工具管理
              </a>
              <a
                href="#"
                @click.prevent="currentTab = 'knowledge'"
                :class="{'border-blue-500 text-gray-900': currentTab === 'knowledge'}"
                class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
              >
                知识库
              </a>
              <a
                href="#"
                @click.prevent="currentTab = 'config'"
                :class="{'border-blue-500 text-gray-900': currentTab === 'config'}"
                class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
              >
                配置
              </a>
              <a
                href="#"
                @click.prevent="currentTab = 'monitor'"
                :class="{'border-blue-500 text-gray-900': currentTab === 'monitor'}"
                class="inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
              >
                监控
              </a>
            </div>
          </div>
        </div>
      </nav>

      <!-- 内容区域 -->
      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <!-- 工具管理 -->
        <div x-show="currentTab === 'tools'" class="px-4 py-6 sm:px-0">
          <div class="bg-white shadow rounded-lg p-6">
            <h2 class="text-2xl font-bold mb-4">工具管理</h2>

            <!-- 工具组列表 -->
            <template x-for="group in groups" :key="group.name">
              <div class="mb-4 border rounded p-4">
                <div class="flex justify-between items-center mb-2">
                  <h3 class="text-lg font-semibold" x-text="group.name"></h3>
                  <span class="text-sm text-gray-600">
                    <span x-text="group.enabled"></span> /
                    <span x-text="group.total"></span> 已启用
                  </span>
                </div>

                <!-- 工具列表 -->
                <div class="space-y-2">
                  <template
                    x-for="tool in getGroupTools(group.name)"
                    :key="tool.name"
                  >
                    <div
                      class="flex items-center justify-between p-2 bg-gray-50 rounded"
                    >
                      <div>
                        <span class="font-medium" x-text="tool.name"></span>
                        <p
                          class="text-sm text-gray-600"
                          x-text="tool.description"
                        ></p>
                      </div>
                      <label class="flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          :checked="tool.enabled"
                          @change="toggleTool(tool.name, $event.target.checked)"
                          class="form-checkbox h-5 w-5 text-blue-600"
                        />
                        <span
                          class="ml-2 text-sm"
                          x-text="tool.enabled ? '已启用' : '已禁用'"
                        ></span>
                      </label>
                    </div>
                  </template>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- 知识库 -->
        <div x-show="currentTab === 'knowledge'" class="px-4 py-6 sm:px-0">
          <div class="bg-white shadow rounded-lg p-6">
            <h2 class="text-2xl font-bold mb-4">知识库管理</h2>

            <!-- 搜索 -->
            <div class="mb-6">
              <input
                type="text"
                x-model="searchQuery"
                @keyup.enter="searchKnowledge()"
                placeholder="搜索知识库..."
                class="w-full px-4 py-2 border rounded-lg"
              />
              <button
                @click="searchKnowledge()"
                class="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                搜索
              </button>
            </div>

            <!-- 搜索结果 -->
            <div class="space-y-4" x-show="searchResults.length > 0">
              <template
                x-for="result in searchResults"
                :key="result.document_id"
              >
                <div class="border rounded p-4">
                  <h3 class="font-semibold mb-2" x-text="result.title"></h3>
                  <p
                    class="text-gray-600 text-sm mb-2"
                    x-text="result.content"
                  ></p>
                  <span class="text-xs text-gray-500"
                    >相关性: <span x-text="result.score.toFixed(2)"></span
                  ></span>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- 配置 -->
        <div x-show="currentTab === 'config'" class="px-4 py-6 sm:px-0">
          <div class="bg-white shadow rounded-lg p-6">
            <h2 class="text-2xl font-bold mb-4">配置管理</h2>
            <pre
              class="bg-gray-100 p-4 rounded overflow-auto"
              x-text="JSON.stringify(config, null, 2)"
            ></pre>
          </div>
        </div>

        <!-- 监控 -->
        <div x-show="currentTab === 'monitor'" class="px-4 py-6 sm:px-0">
          <div class="bg-white shadow rounded-lg p-6">
            <h2 class="text-2xl font-bold mb-4">系统监控</h2>

            <!-- 统计卡片 -->
            <div class="grid grid-cols-3 gap-4 mb-6">
              <div class="bg-blue-100 p-4 rounded">
                <div
                  class="text-2xl font-bold"
                  x-text="stats.tools?.total || 0"
                ></div>
                <div class="text-sm text-gray-600">工具总数</div>
              </div>
              <div class="bg-green-100 p-4 rounded">
                <div
                  class="text-2xl font-bold"
                  x-text="stats.tools?.enabled || 0"
                ></div>
                <div class="text-sm text-gray-600">已启用工具</div>
              </div>
              <div class="bg-purple-100 p-4 rounded">
                <div
                  class="text-2xl font-bold"
                  x-text="stats.documents?.total || 0"
                ></div>
                <div class="text-sm text-gray-600">知识库文档</div>
              </div>
            </div>

            <!-- 日志 -->
            <div>
              <h3 class="font-semibold mb-2">实时日志</h3>
              <div
                class="bg-gray-900 text-green-400 p-4 rounded h-64 overflow-y-auto font-mono text-sm"
              >
                <template x-for="log in logs" :key="log.id">
                  <div x-text="log.message"></div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>

    <script src="/static/js/app.js"></script>
  </body>
</html>
```

### JavaScript 应用逻辑

```javascript
// web/static/js/app.js
function app() {
  return {
    currentTab: "tools",
    tools: [],
    groups: [],
    searchQuery: "",
    searchResults: [],
    config: {},
    stats: {},
    logs: [],
    ws: null,

    async init() {
      await this.loadTools();
      await this.loadGroups();
      await this.loadConfig();
      await this.loadStats();
      this.connectWebSocket();
    },

    async loadTools() {
      const response = await fetch("/api/v1/tools/");
      this.tools = await response.json();
    },

    async loadGroups() {
      const response = await fetch("/api/v1/tools/groups");
      this.groups = await response.json();
    },

    getGroupTools(groupName) {
      return this.tools.filter((t) => t.group === groupName);
    },

    async toggleTool(toolName, enabled) {
      await fetch(`/api/v1/tools/${toolName}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });

      await this.loadTools();
      await this.loadGroups();
    },

    async searchKnowledge() {
      const response = await fetch("/api/v1/knowledge/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: this.searchQuery,
          limit: 10,
        }),
      });

      this.searchResults = await response.json();
    },

    async loadConfig() {
      const response = await fetch("/api/v1/config/");
      this.config = await response.json();
    },

    async loadStats() {
      const response = await fetch("/api/v1/monitor/stats");
      this.stats = await response.json();
    },

    connectWebSocket() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      this.ws = new WebSocket(
        `${protocol}//${window.location.host}/api/v1/monitor/ws`,
      );

      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "log") {
          this.logs.unshift({
            id: Date.now(),
            message: data.message,
          });

          // 限制日志数量
          if (this.logs.length > 100) {
            this.logs.pop();
          }
        }
      };

      // 心跳
      setInterval(() => {
        if (this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 30000);
    },
  };
}
```

## 部署和集成

### 启动 Web 服务器

```python
# 在主服务器中集成
from lyxamour_mcp.web.app import WebServer

# 创建 Web 服务器
web_server = WebServer(
    config=web_config,
    tool_manager=tool_manager,
    knowledge_manager=knowledge_manager,
    config=main_config
)

# 启动（异步）
asyncio.create_task(web_server.start())

# 或同步启动（阻塞）
# web_server.run_sync()
```

## 性能优化

### 缓存

```python
from functools import lru_cache
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend

# 初始化缓存
FastAPICache.init(InMemoryBackend())

# 使用缓存
@router.get("/stats")
@cache(expire=60)  # 缓存60秒
async def get_stats():
    ...
```

### 分页

```python
@router.get("/documents")
async def list_documents(
    page: int = 1,
    page_size: int = 20
):
    offset = (page - 1) * page_size
    ...
```

## 安全考虑

### 认证（可选）

```python
from fastapi import Security
from fastapi.security import HTTPBearer

security = HTTPBearer()

@router.get("/protected")
async def protected_route(
    token: str = Security(security)
):
    # 验证 token
    ...
```

### CSRF 保护

```python
from starlette_csrf import CSRFMiddleware

app.add_middleware(CSRFMiddleware, secret="secret-key")
```

## 测试

```python
from fastapi.testclient import TestClient

client = TestClient(app)

def test_list_tools():
    response = client.get("/api/v1/tools/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```
