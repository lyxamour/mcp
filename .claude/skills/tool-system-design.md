---
name: tool-system-design
description: MCP 工具系统详细设计，包括工具定义、注册、分组和管理
auto-activate:
  always: true
---

# 工具系统设计

## 概述

工具系统是 MCP 服务器的核心功能，负责：
- 工具定义和注册
- 工具自动发现
- 工具分组管理
- 工具启用/禁用控制
- 工具调用执行
- 参数验证和 schema 生成

## 工具定义

### 装饰器方式

```python
# tools/base.py
from typing import Annotated, Any, Callable, TypeVar, ParamSpec
from functools import wraps
import inspect
from docstring_parser import parse as parse_docstring
import structlog

from lyxamour_mcp.core.context import Context
from lyxamour_mcp.core.types import ToolFunction, ToolMetadata

logger = structlog.get_logger(__name__)

P = ParamSpec('P')
R = TypeVar('R')


def tool(
    group: str,
    enabled: bool = True,
    timeout: int = 30,
    description: str | None = None
) -> Callable[[ToolFunction], ToolFunction]:
    """工具装饰器
    
    用于定义 MCP 工具。自动从函数签名和文档字符串
    生成工具 schema。
    
    Args:
        group: 工具所属组
        enabled: 是否默认启用
        timeout: 超时时间（秒）
        description: 工具描述（覆盖文档字符串）
    
    Example:
        @tool(group="filesystem")
        async def read_file(
            ctx: Context,
            path: Annotated[str, "文件路径"],
            encoding: Annotated[str, "编码格式"] = "utf-8"
        ) -> str:
            '''读取文件内容'''
            ...
    """
    def decorator(func: ToolFunction) -> ToolFunction:
        # 解析函数签名
        sig = inspect.signature(func)
        
        # 提取参数 schema
        parameters = _extract_parameters(sig)
        
        # 提取描述
        tool_description = description
        if tool_description is None:
            # 从文档字符串提取
            docstring = parse_docstring(func.__doc__ or "")
            tool_description = docstring.short_description or func.__name__
        
        # 创建工具元数据
        metadata = ToolMetadata(
            name=func.__name__,
            group=group,
            description=tool_description,
            parameters=parameters,
            enabled=enabled,
            timeout=timeout
        )
        
        # 附加元数据到函数
        func.__tool_metadata__ = metadata  # type: ignore
        
        # 包装函数以添加超时控制
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            import asyncio
            
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.error(
                    "工具执行超时",
                    tool=func.__name__,
                    timeout=timeout
                )
                raise ToolTimeoutError(
                    f"工具 {func.__name__} 执行超时 ({timeout}秒)"
                )
        
        wrapper.__tool_metadata__ = metadata  # type: ignore
        
        return wrapper  # type: ignore
    
    return decorator


def _extract_parameters(sig: inspect.Signature) -> dict[str, Any]:
    """从函数签名提取参数 schema
    
    生成符合 JSON Schema 的参数定义。
    """
    properties: dict[str, Any] = {}
    required: list[str] = []
    
    for param_name, param in sig.parameters.items():
        # 跳过 Context 参数
        if param.annotation is Context or param_name == 'ctx':
            continue
        
        # 提取类型和描述
        param_type, param_description = _parse_annotation(param.annotation)
        
        # 生成 schema
        param_schema = _type_to_schema(param_type)
        
        if param_description:
            param_schema["description"] = param_description
        
        properties[param_name] = param_schema
        
        # 检查是否必需（无默认值）
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    
    return {
        "type": "object",
        "properties": properties,
        "required": required
    }


def _parse_annotation(annotation: Any) -> tuple[Any, str | None]:
    """解析类型注解，提取类型和描述
    
    支持 Annotated[type, "description"] 语法。
    """
    # 检查是否是 Annotated
    if hasattr(annotation, '__origin__') and hasattr(annotation, '__metadata__'):
        # Annotated[type, metadata...]
        actual_type = annotation.__args__[0]
        metadata = annotation.__metadata__
        
        # 查找字符串描述
        description = None
        for item in metadata:
            if isinstance(item, str):
                description = item
                break
        
        return actual_type, description
    
    return annotation, None


def _type_to_schema(type_hint: Any) -> dict[str, Any]:
    """将 Python 类型转换为 JSON Schema
    
    支持基本类型、容器类型、Union 等。
    """
    import typing
    
    # 处理 None
    if type_hint is type(None):
        return {"type": "null"}
    
    # 基本类型映射
    basic_types = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
    }
    
    if type_hint in basic_types:
        return basic_types[type_hint]
    
    # 获取 origin (如 list, dict, Union)
    origin = typing.get_origin(type_hint)
    args = typing.get_args(type_hint)
    
    # list[T]
    if origin is list:
        item_type = args[0] if args else Any
        return {
            "type": "array",
            "items": _type_to_schema(item_type)
        }
    
    # dict[K, V]
    if origin is dict:
        value_type = args[1] if len(args) > 1 else Any
        return {
            "type": "object",
            "additionalProperties": _type_to_schema(value_type)
        }
    
    # Union[T1, T2] 或 T | None
    if origin is typing.Union:
        # 检查是否是 Optional (Union[T, None])
        non_none_types = [arg for arg in args if arg is not type(None)]
        
        if len(non_none_types) == 1 and type(None) in args:
            # Optional[T]
            schema = _type_to_schema(non_none_types[0])
            schema["nullable"] = True
            return schema
        else:
            # Union[T1, T2, ...]
            return {
                "oneOf": [_type_to_schema(arg) for arg in args]
            }
    
    # Any
    if type_hint is Any:
        return {}
    
    # 默认为 string
    return {"type": "string"}


class ToolTimeoutError(Exception):
    """工具执行超时"""
    pass
```

### 工具元数据

```python
# core/types.py
from typing import TypeAlias, Protocol, Any, Awaitable
from pydantic import BaseModel, Field

# 类型别名
ToolName: TypeAlias = str
GroupName: TypeAlias = str


class ToolFunction(Protocol):
    """工具函数协议"""
    
    __tool_metadata__: "ToolMetadata"
    
    async def __call__(self, ctx: "Context", **kwargs: Any) -> Any:
        """工具调用"""
        ...


class ToolMetadata(BaseModel):
    """工具元数据"""
    
    name: ToolName = Field(..., description="工具名称")
    group: GroupName = Field(..., description="所属组")
    description: str = Field(..., description="工具描述")
    parameters: dict[str, Any] = Field(..., description="参数 schema")
    enabled: bool = Field(default=True, description="是否启用")
    timeout: int = Field(default=30, description="超时时间（秒）")
    
    model_config = {
        "extra": "forbid",
        "frozen": True,
    }
    
    def to_mcp_schema(self) -> dict[str, Any]:
        """转换为 MCP 工具 schema"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters
        }
```

## 工具注册表

```python
# tools/registry.py
from typing import Any
from collections import defaultdict
import structlog

from lyxamour_mcp.core.types import ToolName, GroupName, ToolFunction, ToolMetadata

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """工具注册表
    
    管理所有已注册的工具，支持按名称和组查询。
    """
    
    def __init__(self) -> None:
        # 工具名称 -> 工具函数
        self._tools: dict[ToolName, ToolFunction] = {}
        
        # 工具名称 -> 元数据
        self._metadata: dict[ToolName, ToolMetadata] = {}
        
        # 组名 -> 工具名称列表
        self._groups: dict[GroupName, list[ToolName]] = defaultdict(list)
    
    def register(self, tool_func: ToolFunction) -> None:
        """注册工具
        
        Args:
            tool_func: 带有 __tool_metadata__ 的工具函数
        
        Raises:
            ValueError: 工具已存在或缺少元数据
        """
        if not hasattr(tool_func, '__tool_metadata__'):
            raise ValueError(f"函数 {tool_func.__name__} 缺少工具元数据")
        
        metadata: ToolMetadata = tool_func.__tool_metadata__
        
        if metadata.name in self._tools:
            logger.warning(
                "工具已存在，将被覆盖",
                tool=metadata.name,
                group=metadata.group
            )
        
        self._tools[metadata.name] = tool_func
        self._metadata[metadata.name] = metadata
        self._groups[metadata.group].append(metadata.name)
        
        logger.info(
            "工具已注册",
            tool=metadata.name,
            group=metadata.group
        )
    
    def unregister(self, tool_name: ToolName) -> None:
        """注销工具"""
        if tool_name not in self._tools:
            raise ValueError(f"工具不存在: {tool_name}")
        
        metadata = self._metadata[tool_name]
        
        # 从组中移除
        if tool_name in self._groups[metadata.group]:
            self._groups[metadata.group].remove(tool_name)
        
        # 删除工具
        del self._tools[tool_name]
        del self._metadata[tool_name]
        
        logger.info("工具已注销", tool=tool_name)
    
    def get(self, tool_name: ToolName) -> ToolFunction | None:
        """获取工具函数"""
        return self._tools.get(tool_name)
    
    def get_metadata(self, tool_name: ToolName) -> ToolMetadata | None:
        """获取工具元数据"""
        return self._metadata.get(tool_name)
    
    def get_group_tools(self, group_name: GroupName) -> list[ToolName]:
        """获取组内所有工具"""
        return self._groups.get(group_name, [])
    
    def get_all_tools(self) -> list[ToolName]:
        """获取所有工具名称"""
        return list(self._tools.keys())
    
    def get_all_groups(self) -> list[GroupName]:
        """获取所有组名"""
        return list(self._groups.keys())
    
    def list_tools(
        self,
        group: GroupName | None = None,
        enabled_only: bool = False
    ) -> list[ToolMetadata]:
        """列出工具
        
        Args:
            group: 按组过滤
            enabled_only: 仅列出启用的工具
        
        Returns:
            工具元数据列表
        """
        tools = []
        
        if group:
            tool_names = self.get_group_tools(group)
        else:
            tool_names = self.get_all_tools()
        
        for tool_name in tool_names:
            metadata = self._metadata[tool_name]
            
            if enabled_only and not metadata.enabled:
                continue
            
            tools.append(metadata)
        
        return tools
```

## 工具管理器

```python
# tools/manager.py
from typing import Any
import asyncio
import structlog

from lyxamour_mcp.core.context import Context
from lyxamour_mcp.core.types import ToolName, GroupName
from lyxamour_mcp.tools.registry import ToolRegistry
from lyxamour_mcp.config.models import Config

logger = structlog.get_logger(__name__)


class ToolManager:
    """工具管理器
    
    管理工具的启用/禁用、调用执行等。
    """
    
    def __init__(self, config: Config, registry: ToolRegistry) -> None:
        self.config = config
        self.registry = registry
        
        # 运行时启用状态（覆盖配置）
        self._runtime_enabled: dict[ToolName, bool] = {}
    
    def is_tool_enabled(self, tool_name: ToolName) -> bool:
        """检查工具是否启用
        
        优先级：
        1. 运行时设置
        2. 配置文件
        3. 工具默认值
        """
        # 运行时设置
        if tool_name in self._runtime_enabled:
            return self._runtime_enabled[tool_name]
        
        # 获取工具元数据
        metadata = self.registry.get_metadata(tool_name)
        if metadata is None:
            return False
        
        # 检查配置
        return self.config.is_tool_enabled(metadata.group, tool_name)
    
    def set_tool_enabled(self, tool_name: ToolName, enabled: bool) -> None:
        """设置工具启用状态（运行时）"""
        self._runtime_enabled[tool_name] = enabled
        logger.info(
            "工具状态已更新",
            tool=tool_name,
            enabled=enabled
        )
    
    def set_group_enabled(self, group_name: GroupName, enabled: bool) -> None:
        """设置整个组的启用状态"""
        tool_names = self.registry.get_group_tools(group_name)
        
        for tool_name in tool_names:
            self.set_tool_enabled(tool_name, enabled)
        
        logger.info(
            "工具组状态已更新",
            group=group_name,
            enabled=enabled,
            count=len(tool_names)
        )
    
    async def call_tool(
        self,
        ctx: Context,
        tool_name: ToolName,
        arguments: dict[str, Any]
    ) -> Any:
        """调用工具
        
        Args:
            ctx: 上下文
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            工具执行结果
        
        Raises:
            ToolNotFoundError: 工具不存在
            ToolDisabledError: 工具已禁用
            ToolExecutionError: 工具执行失败
        """
        # 检查工具是否存在
        tool_func = self.registry.get(tool_name)
        if tool_func is None:
            raise ToolNotFoundError(f"工具不存在: {tool_name}")
        
        # 检查是否启用
        if not self.is_tool_enabled(tool_name):
            raise ToolDisabledError(f"工具已禁用: {tool_name}")
        
        logger.info("调用工具", tool=tool_name, arguments=arguments)
        
        try:
            # 执行工具
            result = await tool_func(ctx, **arguments)
            
            logger.info("工具执行成功", tool=tool_name)
            return result
        
        except Exception as e:
            logger.error(
                "工具执行失败",
                tool=tool_name,
                error=str(e),
                exc_info=True
            )
            raise ToolExecutionError(
                f"工具 {tool_name} 执行失败: {e}"
            ) from e
    
    def get_available_tools(self) -> list[dict[str, Any]]:
        """获取所有可用工具的 MCP schema
        
        仅包含已启用的工具。
        """
        schemas = []
        
        for metadata in self.registry.list_tools(enabled_only=False):
            # 检查是否启用
            if not self.is_tool_enabled(metadata.name):
                continue
            
            schemas.append(metadata.to_mcp_schema())
        
        logger.debug("可用工具数量", count=len(schemas))
        return schemas


class ToolNotFoundError(Exception):
    """工具不存在"""
    pass


class ToolDisabledError(Exception):
    """工具已禁用"""
    pass


class ToolExecutionError(Exception):
    """工具执行失败"""
    pass
```

## 工具发现

```python
# tools/discovery.py
import importlib
import pkgutil
from pathlib import Path
from typing import Any
import structlog

from lyxamour_mcp.tools.registry import ToolRegistry
from lyxamour_mcp.core.types import ToolFunction

logger = structlog.get_logger(__name__)


class ToolDiscovery:
    """工具发现
    
    自动发现和加载工具。
    """
    
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
    
    def discover_builtin_tools(self) -> None:
        """发现内置工具
        
        扫描 tools.builtin 包下的所有模块。
        """
        logger.info("开始发现内置工具")
        
        import lyxamour_mcp.tools.builtin as builtin_package
        
        count = self._discover_package(builtin_package)
        
        logger.info("内置工具发现完成", count=count)
    
    def discover_plugin_tools(self, plugin_dirs: list[str | Path]) -> None:
        """发现插件工具
        
        Args:
            plugin_dirs: 插件目录列表
        """
        logger.info("开始发现插件工具", dirs=plugin_dirs)
        
        total_count = 0
        
        for plugin_dir in plugin_dirs:
            plugin_path = Path(plugin_dir).expanduser()
            
            if not plugin_path.exists():
                logger.warning("插件目录不存在", path=plugin_path)
                continue
            
            count = self._discover_directory(plugin_path)
            total_count += count
        
        logger.info("插件工具发现完成", count=total_count)
    
    def _discover_package(self, package: Any) -> int:
        """发现包中的工具"""
        count = 0
        
        # 遍历包中的所有模块
        for importer, modname, ispkg in pkgutil.iter_modules(
            package.__path__,
            package.__name__ + "."
        ):
            try:
                # 导入模块
                module = importlib.import_module(modname)
                
                # 扫描模块中的工具
                count += self._scan_module(module)
            
            except Exception as e:
                logger.error(
                    "导入模块失败",
                    module=modname,
                    error=str(e)
                )
        
        return count
    
    def _discover_directory(self, directory: Path) -> int:
        """发现目录中的工具"""
        count = 0
        
        # 扫描所有 .py 文件
        for py_file in directory.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            try:
                # 动态导入
                module = self._import_file(py_file)
                
                # 扫描工具
                count += self._scan_module(module)
            
            except Exception as e:
                logger.error(
                    "导入文件失败",
                    file=py_file,
                    error=str(e)
                )
        
        return count
    
    def _import_file(self, file_path: Path) -> Any:
        """动态导入 Python 文件"""
        import importlib.util
        
        spec = importlib.util.spec_from_file_location(
            file_path.stem,
            file_path
        )
        
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载模块: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module
    
    def _scan_module(self, module: Any) -> int:
        """扫描模块中的工具函数"""
        count = 0
        
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            
            attr = getattr(module, attr_name)
            
            # 检查是否是工具函数
            if hasattr(attr, '__tool_metadata__'):
                try:
                    self.registry.register(attr)
                    count += 1
                except Exception as e:
                    logger.error(
                        "注册工具失败",
                        tool=attr_name,
                        error=str(e)
                    )
        
        return count
```

## 工具分组

```python
# tools/group.py
from typing import Any
from pydantic import BaseModel, Field
import structlog

from lyxamour_mcp.core.types import GroupName, ToolName

logger = structlog.get_logger(__name__)


class ToolGroup(BaseModel):
    """工具组
    
    将相关工具组织在一起，支持整组启用/禁用。
    """
    
    name: GroupName = Field(..., description="组名称")
    description: str = Field(default="", description="组描述")
    enabled: bool = Field(default=True, description="是否启用")
    tools: dict[ToolName, bool] = Field(
        default_factory=dict,
        description="工具启用状态"
    )
    
    model_config = {
        "extra": "forbid",
        "frozen": False,
    }
    
    def is_tool_enabled(self, tool_name: ToolName) -> bool:
        """检查工具是否启用
        
        如果组被禁用，则所有工具都禁用。
        """
        if not self.enabled:
            return False
        
        # 检查工具特定设置
        return self.tools.get(tool_name, True)  # 默认启用
    
    def enable_tool(self, tool_name: ToolName) -> None:
        """启用工具"""
        self.tools[tool_name] = True
    
    def disable_tool(self, tool_name: ToolName) -> None:
        """禁用工具"""
        self.tools[tool_name] = False
    
    def enable_all(self) -> None:
        """启用组和所有工具"""
        self.enabled = True
        for tool_name in self.tools:
            self.tools[tool_name] = True
    
    def disable_all(self) -> None:
        """禁用整个组"""
        self.enabled = False


class GroupManager:
    """工具组管理器"""
    
    def __init__(self) -> None:
        self._groups: dict[GroupName, ToolGroup] = {}
    
    def add_group(self, group: ToolGroup) -> None:
        """添加工具组"""
        self._groups[group.name] = group
        logger.info("工具组已添加", group=group.name)
    
    def get_group(self, name: GroupName) -> ToolGroup | None:
        """获取工具组"""
        return self._groups.get(name)
    
    def list_groups(self) -> list[ToolGroup]:
        """列出所有工具组"""
        return list(self._groups.values())
    
    def is_tool_enabled(
        self,
        group_name: GroupName,
        tool_name: ToolName
    ) -> bool:
        """检查工具是否启用"""
        group = self.get_group(group_name)
        if group is None:
            return True  # 组不存在，默认启用
        
        return group.is_tool_enabled(tool_name)
```

## 内置工具示例

### 文件系统工具

```python
# tools/builtin/filesystem.py
from typing import Annotated
from pathlib import Path
import aiofiles
import structlog

from lyxamour_mcp.tools.base import tool
from lyxamour_mcp.core.context import Context

logger = structlog.get_logger(__name__)


@tool(group="filesystem", description="读取文件内容")
async def read_file(
    ctx: Context,
    path: Annotated[str, "文件路径（相对或绝对）"],
    encoding: Annotated[str, "文件编码"] = "utf-8"
) -> str:
    """读取文件内容
    
    从指定路径读取文件，返回文件内容。
    
    Args:
        ctx: 上下文对象
        path: 文件路径
        encoding: 文件编码，默认 utf-8
    
    Returns:
        文件内容字符串
    
    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无权限读取
    """
    file_path = Path(path).expanduser().resolve()
    
    logger.info("读取文件", path=str(file_path))
    
    async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
        content = await f.read()
    
    logger.info("文件读取成功", path=str(file_path), size=len(content))
    
    return content


@tool(group="filesystem", description="写入文件内容")
async def write_file(
    ctx: Context,
    path: Annotated[str, "文件路径"],
    content: Annotated[str, "要写入的内容"],
    encoding: Annotated[str, "文件编码"] = "utf-8",
    create_dirs: Annotated[bool, "是否创建父目录"] = True
) -> str:
    """写入文件内容
    
    将内容写入指定文件，如果文件存在则覆盖。
    
    Args:
        ctx: 上下文对象
        path: 文件路径
        content: 要写入的内容
        encoding: 文件编码
        create_dirs: 是否自动创建父目录
    
    Returns:
        成功消息
    """
    file_path = Path(path).expanduser().resolve()
    
    # 创建父目录
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info("写入文件", path=str(file_path), size=len(content))
    
    async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
        await f.write(content)
    
    logger.info("文件写入成功", path=str(file_path))
    
    return f"成功写入文件: {file_path}"


@tool(group="filesystem", description="列出目录内容")
async def list_directory(
    ctx: Context,
    path: Annotated[str, "目录路径"] = ".",
    recursive: Annotated[bool, "是否递归列出"] = False
) -> list[str]:
    """列出目录内容
    
    列出指定目录下的所有文件和子目录。
    
    Args:
        ctx: 上下文对象
        path: 目录路径
        recursive: 是否递归列出子目录
    
    Returns:
        文件和目录路径列表
    """
    dir_path = Path(path).expanduser().resolve()
    
    if not dir_path.is_dir():
        raise NotADirectoryError(f"不是目录: {dir_path}")
    
    logger.info("列出目录", path=str(dir_path), recursive=recursive)
    
    items = []
    
    if recursive:
        for item in dir_path.rglob("*"):
            items.append(str(item.relative_to(dir_path)))
    else:
        for item in dir_path.iterdir():
            items.append(item.name)
    
    logger.info("目录列出完成", path=str(dir_path), count=len(items))
    
    return sorted(items)
```

### 文本处理工具

```python
# tools/builtin/text.py
from typing import Annotated
import re
import structlog

from lyxamour_mcp.tools.base import tool
from lyxamour_mcp.core.context import Context

logger = structlog.get_logger(__name__)


@tool(group="text", description="搜索文本")
async def search_text(
    ctx: Context,
    text: Annotated[str, "要搜索的文本"],
    pattern: Annotated[str, "正则表达式模式"],
    case_sensitive: Annotated[bool, "是否区分大小写"] = True
) -> list[str]:
    """在文本中搜索匹配的内容
    
    使用正则表达式搜索文本，返回所有匹配项。
    
    Args:
        ctx: 上下文对象
        text: 要搜索的文本
        pattern: 正则表达式模式
        case_sensitive: 是否区分大小写
    
    Returns:
        匹配项列表
    """
    logger.info("搜索文本", pattern=pattern, case_sensitive=case_sensitive)
    
    flags = 0 if case_sensitive else re.IGNORECASE
    
    matches = re.findall(pattern, text, flags)
    
    logger.info("搜索完成", pattern=pattern, matches=len(matches))
    
    return matches


@tool(group="text", description="替换文本")
async def replace_text(
    ctx: Context,
    text: Annotated[str, "原始文本"],
    pattern: Annotated[str, "正则表达式模式"],
    replacement: Annotated[str, "替换文本"],
    case_sensitive: Annotated[bool, "是否区分大小写"] = True
) -> str:
    """替换文本中的匹配内容
    
    使用正则表达式查找并替换文本。
    
    Args:
        ctx: 上下文对象
        text: 原始文本
        pattern: 正则表达式模式
        replacement: 替换文本
        case_sensitive: 是否区分大小写
    
    Returns:
        替换后的文本
    """
    logger.info("替换文本", pattern=pattern)
    
    flags = 0 if case_sensitive else re.IGNORECASE
    
    result = re.sub(pattern, replacement, text, flags=flags)
    
    logger.info("替换完成", pattern=pattern)
    
    return result
```

## 使用示例

```python
# 注册工具
from lyxamour_mcp.tools.registry import ToolRegistry
from lyxamour_mcp.tools.discovery import ToolDiscovery

registry = ToolRegistry()
discovery = ToolDiscovery(registry)

# 发现内置工具
discovery.discover_builtin_tools()

# 发现插件工具
discovery.discover_plugin_tools(["~/.lyxamour/mcp/plugins"])

# 创建工具管理器
from lyxamour_mcp.tools.manager import ToolManager

manager = ToolManager(config, registry)

# 调用工具
from lyxamour_mcp.core.context import Context

ctx = Context(config=config, manager=manager)
result = await manager.call_tool(
    ctx,
    "read_file",
    {"path": "test.txt"}
)

# 管理工具状态
manager.set_tool_enabled("write_file", False)
manager.set_group_enabled("text", True)

# 获取可用工具
tools = manager.get_available_tools()
```

## 性能优化

### 工具缓存

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_tool_schema(tool_name: str) -> dict:
    """缓存工具 schema"""
    ...
```

### 并发限制

```python
from asyncio import Semaphore

class ToolManager:
    def __init__(self, config: Config, registry: ToolRegistry):
        ...
        self._semaphore = Semaphore(config.max_concurrent_tasks)
    
    async def call_tool(self, ctx, tool_name, arguments):
        async with self._semaphore:
            # 执行工具
            ...
```

## 测试策略

### 工具装饰器测试

```python
@pytest.mark.asyncio
async def test_tool_decorator():
    """测试工具装饰器"""
    
    @tool(group="test")
    async def test_tool(
        ctx: Context,
        arg: Annotated[str, "测试参数"]
    ) -> str:
        return f"Result: {arg}"
    
    assert hasattr(test_tool, '__tool_metadata__')
    metadata = test_tool.__tool_metadata__
    assert metadata.name == "test_tool"
    assert metadata.group == "test"
```

### 工具调用测试

```python
@pytest.mark.asyncio
async def test_tool_execution():
    """测试工具执行"""
    registry = ToolRegistry()
    manager = ToolManager(config, registry)
    
    # 注册测试工具
    registry.register(test_tool)
    
    # 调用工具
    ctx = Context(config=config, manager=manager)
    result = await manager.call_tool(ctx, "test_tool", {"arg": "test"})
    
    assert result == "Result: test"
```
