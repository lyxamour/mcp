---
name: project-conventions
description: MCP 工具项目特定的约定和规范
auto-activate:
  always: true
---

# MCP 工具项目约定

## 项目元信息

- **项目名称**: lyxamour-mcp
- **包名称**: lyxamour_mcp
- **Python 版本**: 3.11+
- **包管理器**: uv
- **许可证**: MIT (待确认)

## 目录结构约定

### 源代码组织

```
src/lyxamour_mcp/
├── core/          # 核心功能，被其他模块依赖
├── transport/     # 传输层实现
├── config/        # 配置系统
├── tools/         # 工具系统
├── resources/     # 资源系统
├── prompts/       # 提示系统
├── knowledge/     # 知识库系统
├── web/           # Web 界面
├── utils/         # 通用工具函数
└── cli/           # 命令行接口
```

**依赖规则**：

- `core/` 不依赖其他模块（除 `utils/`）
- 其他模块可以依赖 `core/` 和 `utils/`
- 避免循环依赖
- Web 层可以依赖所有模块

### 测试组织

```
tests/
├── unit/          # 单元测试，对应 src/ 结构
│   ├── test_config.py
│   ├── test_transport.py
│   └── ...
├── integration/   # 集成测试
│   ├── test_mcp_server.py
│   └── test_web_api.py
├── fixtures/      # 测试夹具和数据
│   ├── configs/
│   └── data/
└── conftest.py    # pytest 配置
```

## 文件命名约定

### Python 文件

- **模块**: `snake_case.py`
- **测试**: `test_{module_name}.py`
- **类型存根**: `{module_name}.pyi`

### 配置文件

- **YAML**: `config.yaml`, `{env}.yaml`
- **TOML**: `pyproject.toml`
- **环境变量**: `.env.example` (模板), `.env` (实际，不提交)

### 文档

- **Markdown**: `UPPER_CASE.md` (顶层), `lower-case.md` (子目录)
- **示例**: `README.md`, `CONTRIBUTING.md`, `api-reference.md`

## 导入约定

### 导入顺序

1. 标准库
2. 第三方库
3. 本地模块（绝对导入）

```python
# 标准库
import asyncio
import logging
from pathlib import Path
from typing import Any

# 第三方库
import yaml
from fastapi import FastAPI
from pydantic import BaseModel

# 本地模块
from lyxamour_mcp.core.context import Context
from lyxamour_mcp.core.types import ToolName
from lyxamour_mcp.tools.base import tool
```

### 导入风格

```python
# ✅ 推荐 - 绝对导入
from lyxamour_mcp.core.context import Context
from lyxamour_mcp.tools.manager import ToolManager

# ❌ 避免 - 相对导入（除非同一包内）
from ..core.context import Context
from .manager import ToolManager

# ✅ 同一包内可用相对导入
# 在 lyxamour_mcp/tools/manager.py 中
from .base import tool
from .group import ToolGroup
```

### 循环导入处理

使用 `TYPE_CHECKING` 避免循环导入：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lyxamour_mcp.tools.manager import ToolManager

class Context:
    def __init__(self, manager: "ToolManager") -> None:
        self._manager = manager
```

## 配置约定

### 配置路径

- **全局配置**: `~/.lyxamour/mcp/config.yaml`
- **项目配置**: `.lyxamour/mcp/config.yaml` (项目根目录)
- **数据目录**: `~/.lyxamour/mcp/data/`
- **日志目录**: `~/.lyxamour/mcp/logs/`

### 配置结构

```yaml
# config.yaml 标准结构
transport:
  type: stdio  # stdio | sse | http_stream
  host: 127.0.0.1
  port: 8000

tool_groups:
  - name: filesystem
    enabled: true
    tools:
      read_file: true
      write_file: true
      list_directory: true
  
  - name: text
    enabled: true
    tools:
      search: true
      replace: true

knowledge:
  enabled: true
  db_path: ~/.lyxamour/mcp/knowledge.db
  auto_index: true

web:
  enabled: true
  host: 127.0.0.1
  port: 8080

log_level: INFO  # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

### 环境变量

前缀: `LYXAMOUR_MCP_`

```bash
# 覆盖配置
LYXAMOUR_MCP_LOG_LEVEL=DEBUG
LYXAMOUR_MCP_TRANSPORT__TYPE=http_stream
LYXAMOUR_MCP_WEB__PORT=9090

# 双下划线表示嵌套
LYXAMOUR_MCP_TRANSPORT__HOST=0.0.0.0
```

## 工具开发约定

### 工具装饰器

```python
from lyxamour_mcp import tool
from lyxamour_mcp.core.context import Context
from typing import Annotated

@tool(
    group="filesystem",        # 必需：所属组
    enabled=True,              # 可选：默认启用状态
    timeout=30,                # 可选：超时时间
    description="读取文件内容"  # 可选：覆盖文档字符串
)
async def read_file(
    ctx: Context,
    path: Annotated[str, "文件路径"],
    encoding: Annotated[str, "编码格式"] = "utf-8"
) -> str:
    """读取文件内容
    
    从指定路径读取文件，返回文件内容。
    
    Args:
        ctx: 上下文对象
        path: 文件路径（相对或绝对）
        encoding: 文件编码，默认 utf-8
    
    Returns:
        文件内容字符串
    
    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无权限读取
    """
    ...
```

### 参数注解

使用 `Annotated` 提供参数描述：

```python
from typing import Annotated

# ✅ 推荐
path: Annotated[str, "文件路径，支持相对和绝对路径"]
max_size: Annotated[int, "最大文件大小（字节）"] = 1024 * 1024

# ❌ 避免 - 无描述
path: str
max_size: int = 1024 * 1024
```

### Context 使用

```python
async def my_tool(ctx: Context, ...) -> ...:
    # 日志
    ctx.logger.info("执行操作", param=value)
    
    # 进度报告
    await ctx.report_progress(0.5, "处理中...")
    
    # 访问配置
    config = ctx.config
    
    # 调用其他工具
    result = await ctx.call_tool("other_tool", param=value)
```

## 错误处理约定

### 异常层级

```
LyxamourMCPError (基类)
├── ConfigError
│   ├── ConfigNotFoundError
│   └── ConfigValidationError
├── TransportError
│   ├── ConnectionError
│   └── MessageError
├── ToolError
│   ├── ToolNotFoundError
│   ├── ToolExecutionError
│   └── ToolTimeoutError
├── ResourceError
└── KnowledgeError
```

### 异常定义位置

- 基础异常：`core/exceptions.py`
- 模块特定异常：各模块的 `exceptions.py` 或主文件

```python
# core/exceptions.py
class LyxamourMCPError(Exception):
    """所有项目异常的基类"""
    pass

# tools/exceptions.py
from lyxamour_mcp.core.exceptions import LyxamourMCPError

class ToolError(LyxamourMCPError):
    """工具相关错误"""
    pass
```

## 日志约定

### 日志器命名

```python
import structlog

# ✅ 使用 __name__
logger = structlog.get_logger(__name__)

# 输出示例: lyxamour_mcp.tools.manager
```

### 日志消息格式

```python
# ✅ 结构化日志
logger.info(
    "工具调用成功",
    tool_name="read_file",
    path=file_path,
    duration=duration,
    size=file_size
)

# ❌ 字符串拼接
logger.info(f"工具 {tool_name} 调用成功，路径: {file_path}")
```

### 日志级别使用

- **DEBUG**: 详细的内部状态，仅开发时使用
- **INFO**: 重要操作（工具调用、配置加载）
- **WARNING**: 可恢复的问题（配置缺失使用默认值）
- **ERROR**: 操作失败但程序可继续
- **CRITICAL**: 严重错误，程序无法继续

## 版本控制约定

### 提交消息

使用 Conventional Commits 格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型**:
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档变更
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具变更

**示例**:

```
feat(tools): 添加文件搜索工具

实现了基于 glob 模式的文件搜索功能，支持递归搜索
和文件类型过滤。

Closes #123
```

### 分支命名

- **功能分支**: `feature/tool-search`
- **修复分支**: `fix/config-validation`
- **发布分支**: `release/v1.0.0`
- **热修复**: `hotfix/critical-bug`

### 版本号

使用语义化版本 (SemVer):

- **主版本**: 不兼容的 API 变更
- **次版本**: 向后兼容的功能新增
- **修订版**: 向后兼容的 bug 修复

示例: `v1.2.3`

## 测试约定

### 测试覆盖率

- **最低要求**: 80%
- **目标**: 90%
- **核心模块**: >95%

### 测试标记

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """测试异步函数"""
    ...

@pytest.mark.slow
def test_slow_operation():
    """标记为慢速测试"""
    ...

@pytest.mark.integration
async def test_full_workflow():
    """集成测试"""
    ...
```

### Mock 使用

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_with_mock():
    """使用 mock 的测试"""
    mock_transport = AsyncMock()
    mock_transport.send.return_value = None
    
    await function_under_test(mock_transport)
    
    mock_transport.send.assert_called_once()
```

## 性能约定

### 性能目标

- **工具调用延迟**: < 10ms (本地, 排除 I/O)
- **配置加载**: < 100ms
- **知识库检索**: < 100ms (前 10 条)
- **Web API 响应**: < 200ms (P95)

### 性能测试

```python
import pytest
import time

@pytest.mark.benchmark
def test_performance(benchmark):
    """性能基准测试"""
    result = benchmark(function_to_test, arg1, arg2)
    assert result is not None
```

## 安全约定

### 敏感数据

- **配置**: 不提交包含密钥的配置文件
- **日志**: 不记录密码、令牌等敏感信息
- **测试**: 使用测试专用的凭证

### 输入验证

所有外部输入必须验证：

```python
from pydantic import BaseModel, Field, field_validator

class FileRequest(BaseModel):
    """文件请求"""
    
    path: str = Field(..., description="文件路径")
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str) -> str:
        """验证路径安全性"""
        # 防止路径遍历
        if '..' in v or v.startswith('/'):
            raise ValueError("非法路径")
        return v
```

## 文档约定

### API 文档

- 所有公共函数/类必须有文档字符串
- 使用 Google Style
- 包含示例代码

### README 结构

```markdown
# 项目名称

简短描述

## 特性

- 特性 1
- 特性 2

## 安装

\`\`\`bash
uv pip install lyxamour-mcp
\`\`\`

## 快速开始

\`\`\`python
示例代码
\`\`\`

## 文档

链接到详细文档

## 贡献

贡献指南

## 许可证

许可证信息
```

## 依赖管理约定

### 使用 uv

```bash
# 添加依赖
uv add package-name

# 添加开发依赖
uv add --dev pytest

# 安装所有依赖
uv sync

# 更新依赖
uv lock --upgrade
```

### 依赖分类

在 `pyproject.toml` 中分组：

```toml
[project]
dependencies = [
    "fastmcp>=1.0.0",
    "pydantic>=2.0.0",
    # 运行时依赖
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",
    # 开发依赖
]
web = [
    "fastapi>=0.100.0",
    # Web 界面依赖
]
```

### 版本约束

- **精确版本**: 关键依赖 `==1.2.3`
- **兼容范围**: 一般依赖 `>=1.0.0,<2.0.0`
- **最低版本**: 可选依赖 `>=1.0.0`

## 代码审查检查项

提交前确认：

- [ ] 符合编码规范（Black + isort + ruff）
- [ ] 通过类型检查（mypy）
- [ ] 测试覆盖率达标
- [ ] 文档字符串完整
- [ ] 无安全隐患
- [ ] 提交消息符合规范
- [ ] 无敏感信息泄露
- [ ] 性能影响可接受
