---
name: architecture
description: MCP 工具项目架构设计和技术决策说明
auto-activate:
  always: true
---

# MCP 工具项目架构

## 项目结构

```
mcp/
├── pyproject.toml              # 项目配置和依赖管理 (uv)
├── README.md                   # 项目说明
├── .python-version             # Python 版本锁定
├── .gitignore                  # Git 忽略配置
├── src/
│   └── lyxamour_mcp/          # 主包
│       ├── __init__.py
│       ├── __main__.py        # CLI 入口
│       ├── server.py          # MCP 服务器主入口
│       │
│       ├── core/              # 核心模块
│       │   ├── __init__.py
│       │   ├── types.py       # 核心类型定义
│       │   ├── context.py     # 上下文管理
│       │   ├── session.py     # 会话管理
│       │   ├── registry.py    # 工具/资源/提示注册表
│       │   └── lifecycle.py   # 生命周期管理
│       │
│       ├── transport/         # 传输层
│       │   ├── __init__.py
│       │   ├── base.py        # 传输层抽象基类
│       │   ├── stdio.py       # stdio 传输实现
│       │   ├── sse.py         # SSE 传输实现
│       │   ├── http_stream.py # HTTP 流传输实现
│       │   └── factory.py     # 传输层工厂
│       │
│       ├── config/            # 配置系统
│       │   ├── __init__.py
│       │   ├── models.py      # 配置数据模型 (Pydantic)
│       │   ├── loader.py      # 配置加载器
│       │   ├── validator.py   # 配置验证器
│       │   ├── merger.py      # 配置合并逻辑
│       │   └── defaults.py    # 默认配置
│       │
│       ├── tools/             # 工具系统
│       │   ├── __init__.py
│       │   ├── base.py        # 工具基类和装饰器
│       │   ├── manager.py     # 工具管理器
│       │   ├── group.py       # 工具分组
│       │   ├── discovery.py   # 工具发现
│       │   └── builtin/       # 内置工具
│       │       ├── __init__.py
│       │       ├── filesystem.py
│       │       ├── text.py
│       │       └── search.py
│       │
│       ├── resources/         # 资源系统
│       │   ├── __init__.py
│       │   ├── base.py        # 资源基类
│       │   ├── manager.py     # 资源管理器
│       │   └── builtin/       # 内置资源
│       │       ├── __init__.py
│       │       └── config.py
│       │
│       ├── prompts/           # 提示系统
│       │   ├── __init__.py
│       │   ├── base.py        # 提示基类
│       │   ├── manager.py     # 提示管理器
│       │   └── builtin/       # 内置提示
│       │       └── __init__.py
│       │
│       ├── knowledge/         # 知识库系统
│       │   ├── __init__.py
│       │   ├── db.py          # 数据库连接和初始化
│       │   ├── models.py      # 知识库数据模型
│       │   ├── storage.py     # 存储层
│       │   ├── retrieval.py   # 检索层
│       │   ├── embeddings.py  # 向量化 (可选)
│       │   └── migrations/    # 数据库迁移
│       │       └── __init__.py
│       │
│       ├── web/               # Web 界面
│       │   ├── __init__.py
│       │   ├── app.py         # FastAPI 应用
│       │   ├── routes/        # 路由
│       │   │   ├── __init__.py
│       │   │   ├── tools.py   # 工具管理 API
│       │   │   ├── config.py  # 配置管理 API
│       │   │   ├── knowledge.py # 知识库 API
│       │   │   └── monitor.py # 监控 API
│       │   ├── static/        # 静态文件
│       │   │   ├── css/
│       │   │   ├── js/
│       │   │   └── index.html
│       │   └── templates/     # 模板 (如果需要)
│       │
│       ├── utils/             # 工具函数
│       │   ├── __init__.py
│       │   ├── logging.py     # 日志配置
│       │   ├── validation.py  # 验证辅助
│       │   └── files.py       # 文件操作辅助
│       │
│       └── cli/               # 命令行接口
│           ├── __init__.py
│           ├── main.py        # 主命令
│           ├── serve.py       # 启动服务器
│           ├── config.py      # 配置命令
│           └── tools.py       # 工具管理命令
│
├── tests/                     # 测试
│   ├── __init__.py
│   ├── conftest.py           # pytest 配置
│   ├── unit/                 # 单元测试
│   │   ├── test_config.py
│   │   ├── test_transport.py
│   │   ├── test_tools.py
│   │   └── test_knowledge.py
│   ├── integration/          # 集成测试
│   │   ├── test_mcp_server.py
│   │   └── test_web_api.py
│   └── fixtures/             # 测试夹具
│       └── sample_config.yaml
│
├── docs/                      # 文档
│   ├── api/                  # API 文档
│   ├── user-guide/           # 用户指南
│   └── development/          # 开发文档
│
└── examples/                  # 示例
    ├── basic_server.py
    ├── custom_tools.py
    └── config_examples/
        ├── global.yaml
        └── project.yaml
```

## 核心架构设计

### 1. 传输层抽象

**设计原则**：统一接口，多种实现

```python
# transport/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any

class Transport(ABC):
    """传输层抽象基类"""
    
    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """发送消息到客户端"""
        pass
    
    @abstractmethod
    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """从客户端接收消息流"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭传输连接"""
        pass
```

**实现策略**：

- **stdio**: 使用 asyncio.StreamReader/Writer
- **SSE**: 基于 Starlette EventSourceResponse
- **HTTP Stream**: 使用 Streamable HTTP 协议

### 2. 配置系统

**配置层级**：

1. **内置默认配置** (`config/defaults.py`)
2. **全局用户配置** (`~/.lyxamour/mcp/config.yaml`)
3. **项目配置** (`.lyxamour/mcp/config.yaml`)
4. **环境变量覆盖** (`LYXAMOUR_MCP_*`)
5. **命令行参数覆盖**

**合并策略**：

- 深度合并字典
- 列表追加（工具组）
- 后加载的配置覆盖先加载的

**配置模型示例**：

```python
# config/models.py
from pydantic import BaseModel, Field
from typing import Literal

class TransportConfig(BaseModel):
    """传输配置"""
    type: Literal["stdio", "sse", "http_stream"]
    host: str = "127.0.0.1"
    port: int = 8000

class ToolGroupConfig(BaseModel):
    """工具组配置"""
    name: str
    enabled: bool = True
    tools: dict[str, bool] = Field(default_factory=dict)

class KnowledgeConfig(BaseModel):
    """知识库配置"""
    enabled: bool = True
    db_path: str = "~/.lyxamour/mcp/knowledge.db"
    auto_index: bool = True

class WebConfig(BaseModel):
    """Web 界面配置"""
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8080

class Config(BaseModel):
    """主配置模型"""
    transport: TransportConfig
    tool_groups: list[ToolGroupConfig] = Field(default_factory=list)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    log_level: str = "INFO"
```

### 3. 工具系统

**工具定义**：使用装饰器和类型提示

```python
# tools/base.py
from typing import Annotated
from lyxamour_mcp.core.context import Context

@tool(group="filesystem")
async def read_file(
    ctx: Context,
    path: Annotated[str, "文件路径"],
    encoding: Annotated[str, "编码格式"] = "utf-8"
) -> str:
    """读取文件内容"""
    # 实现
    pass
```

**工具分组**：

- 每个工具属于一个组
- 组可以整体启用/禁用
- 工具可以单独启用/禁用
- 支持动态加载和卸载

**工具发现**：

- 扫描 `tools/builtin/` 目录
- 扫描配置中指定的插件目录
- 自动注册装饰的工具函数

### 4. 知识库系统

**架构**：

```
Knowledge Base
├── Storage Layer (SQLite)
│   ├── Documents Table
│   ├── Chunks Table
│   └── Metadata Table
├── Retrieval Layer
│   ├── Full-text Search (FTS5)
│   └── Vector Search (Optional)
└── API Layer
    ├── Store Document
    ├── Search
    └── Retrieve
```

**数据模型**：

```python
# knowledge/models.py
from datetime import datetime
from pydantic import BaseModel

class Document(BaseModel):
    """文档模型"""
    id: str
    title: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

class Chunk(BaseModel):
    """文档块模型"""
    id: str
    document_id: str
    content: str
    chunk_index: int
    embedding: list[float] | None = None
```

### 5. Web 界面

**技术栈**：

- 后端：FastAPI + Uvicorn
- 前端：现代 HTML/CSS/JS (无构建依赖)
- 通信：REST API + WebSocket (实时更新)

**主要功能**：

1. **工具管理**：查看、启用/禁用工具和组
2. **配置管理**：编辑和验证配置
3. **知识库管理**：上传、搜索、管理文档
4. **监控面板**：日志查看、性能指标

### 6. 类型系统

**类型策略**：

- 全局使用类型提示
- Pydantic 模型用于数据验证
- TypedDict 用于字典结构
- 运行 mypy 严格模式

**示例**：

```python
from typing import Protocol, TypeAlias
from pydantic import BaseModel

# 协议定义
class ToolFunction(Protocol):
    async def __call__(self, ctx: Context, **kwargs: Any) -> Any: ...

# 类型别名
ToolName: TypeAlias = str
GroupName: TypeAlias = str

# Pydantic 模型
class ToolMetadata(BaseModel):
    name: ToolName
    group: GroupName
    description: str
    parameters: dict[str, Any]
```

## 技术决策记录

### TD-001: 使用 FastMCP vs 原生 MCP SDK

**决策**: 使用 FastMCP 作为主框架

**理由**:
- 提供装饰器语法，简化工具定义
- 自动 schema 生成
- 内置类型验证
- 社区推荐

**替代方案**: 直接使用 modelcontextprotocol/python-sdk
**权衡**: FastMCP 抽象层可能限制某些底层控制

### TD-002: 配置格式

**决策**: 使用 YAML 格式

**理由**:
- 人类可读性强
- 支持注释
- 层级结构清晰
- Python 生态系统成熟

**替代方案**: TOML, JSON
**权衡**: YAML 解析略慢，但对配置文件影响可忽略

### TD-003: 内嵌数据库

**决策**: 使用 SQLite + FTS5

**理由**:
- 零配置、零依赖
- 内置全文搜索 (FTS5)
- 成熟稳定
- Python 标准库支持

**替代方案**: 纯文件、其他嵌入式数据库
**权衡**: 大规模数据性能有限，但对工具场景足够

### TD-004: 异步 vs 同步

**决策**: 全异步架构

**理由**:
- MCP 协议本质是异步的
- 支持高并发连接
- 现代 Python 最佳实践
- FastAPI/FastMCP 都是异步的

**替代方案**: 同步 + 线程池
**权衡**: 异步代码复杂度略高

### TD-005: Web 框架

**决策**: FastAPI

**理由**:
- 类型安全
- 自动 OpenAPI 文档
- 高性能 (ASGI)
- 与 FastMCP 技术栈一致

**替代方案**: Flask, Django
**权衡**: FastAPI 相对年轻，但生态已足够成熟

## 模块依赖关系

```
CLI ─────────┐
             ├──→ Server ←──→ Transport Layer
Web UI ──────┘       │
                     ├──→ Config System
                     ├──→ Tool Manager ←──→ Tool Groups
                     ├──→ Resource Manager
                     ├──→ Prompt Manager
                     └──→ Knowledge Base ←──→ SQLite
```

## 扩展性设计

### 插件系统

**插件加载机制**：

1. 扫描配置中的插件目录
2. 动态导入 Python 模块
3. 发现并注册工具/资源/提示
4. 验证插件兼容性

**插件接口**：

```python
# plugins/base.py
from typing import Protocol

class Plugin(Protocol):
    """插件接口"""
    name: str
    version: str
    
    async def initialize(self, ctx: Context) -> None:
        """初始化插件"""
        pass
    
    async def shutdown(self) -> None:
        """关闭插件"""
        pass
```

### 自定义工具开发

**开发者体验**：

1. 创建 Python 文件
2. 使用 `@tool` 装饰器
3. 添加类型提示和文档字符串
4. 配置中启用工具

**示例**：

```python
from lyxamour_mcp import tool, Context

@tool(group="custom")
async def my_tool(
    ctx: Context,
    param: str
) -> str:
    """我的自定义工具"""
    return f"Processed: {param}"
```

## 性能考虑

### 关键路径优化

1. **工具调用延迟**: < 10ms (本地)
2. **配置加载**: 启动时一次性加载，支持热重载
3. **知识库检索**: 使用索引，< 100ms
4. **传输层**: 异步非阻塞 I/O

### 内存管理

- 工具懒加载
- 知识库分页查询
- 连接池复用
- 大文件流式处理

### 并发控制

- 异步信号量限制并发数
- 超时控制
- 优雅降级

## 安全考虑

### 输入验证

- Pydantic 自动验证
- 路径遍历防护
- 参数类型检查

### 权限控制

- 文件系统访问限制
- 工具权限级别
- 配置敏感字段保护

### 日志脱敏

- 自动检测敏感信息
- 可配置的脱敏规则

## 测试策略

### 单元测试

- 每个模块 >80% 覆盖率
- 使用 pytest + pytest-asyncio
- Mock 外部依赖

### 集成测试

- 端到端 MCP 协议测试
- 多传输协议测试
- Web API 测试

### 性能测试

- 基准测试
- 压力测试
- 内存泄漏检测

## 部署和分发

### 包分发

- PyPI 发布
- uv 安装: `uv pip install lyxamour-mcp`
- 独立可执行文件 (PyInstaller)

### 配置管理

- 首次运行自动初始化
- 配置向导
- 配置验证和诊断

### 升级策略

- 语义化版本
- 配置迁移工具
- 平滑升级路径
