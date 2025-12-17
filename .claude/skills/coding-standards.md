---
name: coding-standards
description: MCP 工具项目编码规范和风格指南
auto-activate:
  always: true
---

# MCP 工具编码规范

## Python 版本

- **最低版本**: Python 3.11
- **推荐版本**: Python 3.12+
- **原因**: 需要最新的类型提示特性和性能改进

## 代码风格

### 基础规范

遵循 **PEP 8** 和 **PEP 257**，具体规则：

- 缩进：4 个空格
- 最大行长：88 字符 (Black 默认)
- 引号：双引号用于字符串，单引号用于字典键
- 导入顺序：标准库 → 第三方库 → 本地模块

### 格式化工具

使用 **Black** 进行代码格式化：

```bash
# 格式化所有代码
uv run black src/ tests/

# 检查格式
uv run black --check src/ tests/
```

配置文件 `pyproject.toml`:

```toml
[tool.black]
line-length = 88
target-version = ['py311', 'py312']
include = '\.pyi?$'
```

### Import 排序

使用 **isort** 管理导入：

```bash
uv run isort src/ tests/
```

配置：

```toml
[tool.isort]
profile = "black"
line_length = 88
multi_line_output = 3
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true
```

导入顺序示例：

```python
# 标准库
import asyncio
import logging
from pathlib import Path
from typing import Any, AsyncIterator

# 第三方库
import yaml
from fastapi import FastAPI
from pydantic import BaseModel, Field

# 本地模块
from lyxamour_mcp.core.context import Context
from lyxamour_mcp.core.types import ToolName
```

## 类型提示

### 强制类型提示

**所有**公共函数、方法和类属性必须有类型提示：

```python
# ✅ 正确
async def read_file(
    path: str,
    encoding: str = "utf-8"
) -> str:
    """读取文件内容"""
    ...

# ❌ 错误 - 缺少返回类型
async def read_file(path: str, encoding: str = "utf-8"):
    ...
```

### 现代类型语法

使用 Python 3.10+ 的类型语法：

```python
# ✅ 推荐 - 使用 | 语法
def process(data: str | None) -> dict[str, Any]:
    ...

# ❌ 避免 - 旧式 Union
from typing import Union, Dict, Any
def process(data: Union[str, None]) -> Dict[str, Any]:
    ...
```

### 类型别名

使用 `TypeAlias` 定义复杂类型：

```python
from typing import TypeAlias

ToolName: TypeAlias = str
ConfigDict: TypeAlias = dict[str, Any]
ToolFunction: TypeAlias = Callable[[Context, ...], Awaitable[Any]]
```

### Protocol 定义

使用 `Protocol` 定义接口：

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Transport(Protocol):
    """传输层协议"""
    
    async def send(self, message: dict[str, Any]) -> None:
        ...
    
    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        ...
```

### 泛型使用

适当使用泛型提高类型安全：

```python
from typing import Generic, TypeVar

T = TypeVar('T')

class Registry(Generic[T]):
    """通用注册表"""
    
    def __init__(self) -> None:
        self._items: dict[str, T] = {}
    
    def register(self, name: str, item: T) -> None:
        self._items[name] = item
    
    def get(self, name: str) -> T | None:
        return self._items.get(name)
```

## 命名约定

### 变量和函数

- **变量**: `snake_case`
- **函数**: `snake_case`
- **常量**: `UPPER_SNAKE_CASE`
- **私有**: 前缀 `_`

```python
# 变量
tool_name = "read_file"
max_retries = 3

# 常量
DEFAULT_TIMEOUT = 30
MAX_CONNECTIONS = 100

# 私有变量
_internal_state = {}

# 函数
async def load_config() -> Config:
    ...

# 私有函数
def _validate_path(path: str) -> bool:
    ...
```

### 类和类型

- **类**: `PascalCase`
- **异常**: `PascalCase` + `Error/Exception` 后缀
- **类型别名**: `PascalCase` 或 `snake_case` (简短时)

```python
# 类
class ToolManager:
    ...

class ConfigLoader:
    ...

# 异常
class ToolNotFoundError(Exception):
    ...

class ConfigValidationError(ValueError):
    ...

# 类型别名
ToolName: TypeAlias = str  # 简短
ConfigurationDict: TypeAlias = dict[str, Any]  # 复杂
```

### 模块和包

- **模块**: `snake_case.py`
- **包**: `snake_case/`
- 避免使用与标准库冲突的名称

```python
# ✅ 正确
transport/
├── __init__.py
├── base.py
├── stdio.py
└── http_stream.py

# ❌ 错误 - 与标准库冲突
types.py  # 使用 core_types.py
json.py   # 使用 json_utils.py
```

## 文档字符串

### 格式

使用 **Google Style** 文档字符串：

```python
def complex_function(
    param1: str,
    param2: int,
    param3: bool = False
) -> dict[str, Any]:
    """执行复杂操作的函数
    
    这里是详细描述，解释函数的用途、行为和注意事项。
    可以多行描述。
    
    Args:
        param1: 第一个参数的描述
        param2: 第二个参数的描述
        param3: 第三个参数的描述，默认为 False
    
    Returns:
        返回值的描述，包含键值说明
    
    Raises:
        ValueError: 当 param2 < 0 时抛出
        FileNotFoundError: 当文件不存在时抛出
    
    Examples:
        >>> result = complex_function("test", 42)
        >>> print(result)
        {'status': 'success', 'data': ...}
    """
    ...
```

### 类文档

```python
class ToolManager:
    """工具管理器
    
    负责工具的注册、发现和调用。支持工具分组和
    动态启用/禁用。
    
    Attributes:
        _tools: 已注册的工具字典
        _groups: 工具组配置
    
    Examples:
        >>> manager = ToolManager()
        >>> manager.register_tool("read_file", read_file_func)
    """
    
    def __init__(self) -> None:
        """初始化工具管理器"""
        self._tools: dict[str, ToolFunction] = {}
        self._groups: dict[str, ToolGroup] = {}
```

### 模块文档

每个模块顶部添加模块级文档：

```python
"""工具系统核心模块

提供工具的注册、发现、调用和管理功能。

主要组件:
    - ToolManager: 工具管理器
    - ToolGroup: 工具分组
    - tool: 工具装饰器

典型用法:
    from lyxamour_mcp.tools import tool, ToolManager
    
    @tool(group="filesystem")
    async def read_file(ctx: Context, path: str) -> str:
        ...
"""

from typing import Any
...
```

## 注释规范

### 何时添加注释

仅在以下情况添加注释：

1. **复杂算法**: 解释算法逻辑和设计理由
2. **性能考虑**: 说明性能相关的决策
3. **临时解决方案**: 标记 TODO、FIXME、HACK
4. **业务逻辑**: 复杂的业务规则

```python
# ✅ 有价值的注释
# 使用二分查找优化性能，时间复杂度 O(log n)
index = binary_search(sorted_list, target)

# TODO(username): 添加缓存机制以提高性能
# FIXME: 边界条件处理不正确，需要修复
# HACK: 临时绕过上游库的 bug，等待官方修复

# ❌ 无价值的注释 - 重复代码
# 设置 x 为 10
x = 10

# 循环遍历列表
for item in items:
    ...
```

### 注释风格

- 使用简体中文
- 句末不加句号（简短注释）
- 多行注释每行 `#` 后空一格

```python
# 单行注释示例

# 多行注释示例
# 第一行说明
# 第二行说明
```

### TODO/FIXME/HACK 标记

```python
# TODO(username): 具体要做的事情
# FIXME: 需要修复的问题描述
# HACK: 临时方案的说明和原因
# NOTE: 重要提示或注意事项
```

## 异步编程

### async/await 使用

- 所有 I/O 操作使用 `async/await`
- 避免在 async 函数中使用阻塞调用
- 使用 `asyncio.run()` 作为入口点

```python
# ✅ 正确
async def read_file(path: str) -> str:
    async with aiofiles.open(path) as f:
        return await f.read()

# ❌ 错误 - 阻塞调用
async def read_file(path: str) -> str:
    with open(path) as f:  # 同步 I/O
        return f.read()
```

### 并发控制

使用信号量限制并发：

```python
from asyncio import Semaphore

# 限制并发数为 10
semaphore = Semaphore(10)

async def process_with_limit(item: Any) -> Any:
    async with semaphore:
        return await process(item)
```

### 异常处理

```python
async def safe_operation() -> Result | None:
    try:
        result = await risky_operation()
        return result
    except SpecificError as e:
        logger.error(f"操作失败: {e}")
        return None
    finally:
        await cleanup()
```

## 错误处理

### 异常层级

```python
# 基础异常
class LyxamourMCPError(Exception):
    """所有项目异常的基类"""
    pass

# 具体异常
class ConfigError(LyxamourMCPError):
    """配置相关错误"""
    pass

class ToolError(LyxamourMCPError):
    """工具相关错误"""
    pass

class ToolNotFoundError(ToolError):
    """工具未找到"""
    pass
```

### 异常处理原则

1. **具体捕获**: 捕获具体异常，避免 `except Exception`
2. **及早失败**: 不要隐藏错误
3. **上下文信息**: 异常消息包含足够的上下文
4. **日志记录**: 记录异常详情

```python
# ✅ 正确
try:
    config = load_config(path)
except FileNotFoundError:
    logger.error(f"配置文件不存在: {path}")
    raise ConfigError(f"无法加载配置: {path}")
except yaml.YAMLError as e:
    logger.error(f"配置文件格式错误: {e}")
    raise ConfigError(f"配置格式无效: {path}")

# ❌ 错误
try:
    config = load_config(path)
except Exception:  # 过于宽泛
    pass  # 吞掉异常
```

## Pydantic 使用

### 模型定义

```python
from pydantic import BaseModel, Field, field_validator

class ToolConfig(BaseModel):
    """工具配置模型"""
    
    name: str = Field(..., description="工具名称")
    group: str = Field(..., description="所属组")
    enabled: bool = Field(default=True, description="是否启用")
    timeout: int = Field(default=30, ge=1, le=300, description="超时时间(秒)")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证工具名称"""
        if not v.isidentifier():
            raise ValueError("工具名称必须是有效的标识符")
        return v
    
    model_config = {
        "frozen": False,  # 是否不可变
        "extra": "forbid",  # 禁止额外字段
    }
```

### 配置类使用

- 使用 `model_config` 配置模型行为
- 使用 `Field` 添加验证和描述
- 使用 `@field_validator` 自定义验证

## 日志

### 日志配置

使用 `structlog` 进行结构化日志：

```python
import structlog

logger = structlog.get_logger(__name__)

# 使用示例
logger.info(
    "工具调用",
    tool_name="read_file",
    path="/path/to/file",
    duration=0.123
)

logger.error(
    "操作失败",
    tool_name="read_file",
    error=str(e),
    exc_info=True
)
```

### 日志级别

- **DEBUG**: 详细的调试信息
- **INFO**: 一般信息，如工具调用
- **WARNING**: 警告信息，如配置缺失
- **ERROR**: 错误信息，如操作失败
- **CRITICAL**: 严重错误，如系统崩溃

### 敏感信息

避免记录敏感信息：

```python
# ✅ 正确
logger.info("用户认证成功", user_id=user.id)

# ❌ 错误
logger.info("用户认证成功", password=user.password)
```

## 测试

### 测试文件组织

```python
# tests/unit/test_config.py
import pytest
from lyxamour_mcp.config import Config

class TestConfig:
    """配置系统测试"""
    
    def test_load_default_config(self):
        """测试加载默认配置"""
        config = Config.load_default()
        assert config.log_level == "INFO"
    
    @pytest.mark.asyncio
    async def test_async_operation(self):
        """测试异步操作"""
        result = await some_async_function()
        assert result is not None
```

### 测试命名

- 测试类: `Test{ClassName}`
- 测试函数: `test_{function_name}_{scenario}`

```python
def test_load_config_success():
    """成功场景"""
    ...

def test_load_config_file_not_found():
    """文件不存在场景"""
    ...

def test_load_config_invalid_format():
    """格式错误场景"""
    ...
```

### Fixture 使用

```python
@pytest.fixture
def temp_config_file(tmp_path):
    """创建临时配置文件"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("transport:\n  type: stdio\n")
    return config_path

def test_with_fixture(temp_config_file):
    """使用 fixture 的测试"""
    config = load_config(temp_config_file)
    assert config.transport.type == "stdio"
```

## 性能优化

### 避免过早优化

```python
# ✅ 先保证正确性
def process_items(items: list[str]) -> list[str]:
    return [item.upper() for item in items]

# ❌ 过早优化
def process_items(items: list[str]) -> list[str]:
    # 复杂的优化逻辑...
    pass
```

### 使用适当的数据结构

```python
# ✅ 使用 set 进行成员检查
allowed_tools = {"read_file", "write_file", "search"}
if tool_name in allowed_tools:
    ...

# ❌ 使用 list
allowed_tools = ["read_file", "write_file", "search"]
if tool_name in allowed_tools:  # O(n)
    ...
```

### 缓存计算结果

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(arg: str) -> str:
    """计算密集型函数"""
    ...
```

## 安全性

### 路径验证

```python
from pathlib import Path

def validate_path(path: str, base_dir: Path) -> Path:
    """验证路径在允许的目录内"""
    resolved = (base_dir / path).resolve()
    if not resolved.is_relative_to(base_dir):
        raise ValueError(f"路径遍历攻击: {path}")
    return resolved
```

### 输入验证

```python
# 使用 Pydantic 自动验证
class FileRequest(BaseModel):
    path: str = Field(..., pattern=r'^[a-zA-Z0-9_/.-]+$')
    encoding: str = Field(default="utf-8", pattern=r'^[a-zA-Z0-9-]+$')
```

## 代码审查检查清单

提交前确保：

- [ ] 代码通过 `black` 格式化
- [ ] 代码通过 `isort` 排序
- [ ] 代码通过 `mypy` 类型检查
- [ ] 代码通过 `ruff` lint 检查
- [ ] 所有测试通过
- [ ] 添加了必要的文档字符串
- [ ] 添加了必要的类型提示
- [ ] 没有遗留 TODO/FIXME（或已记录）
- [ ] 日志不包含敏感信息
- [ ] 异常处理适当
