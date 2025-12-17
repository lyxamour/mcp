---
name: config-design
description: MCP 工具配置系统详细设计
auto-activate:
  always: true
---

# 配置系统设计

## 配置层级和优先级

配置系统采用多层级设计，后加载的配置覆盖先加载的：

```
优先级从低到高：
1. 内置默认配置 (代码中硬编码)
2. 全局用户配置 (~/.lyxamour/mcp/config.yaml)
3. 项目配置 (.lyxamour/mcp/config.yaml)
4. 环境变量 (LYXAMOUR_MCP_*)
5. 命令行参数
```

## 配置模型定义

### 完整配置结构

```python
# config/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Any
from pathlib import Path

class TransportConfig(BaseModel):
    """传输层配置"""

    type: Literal["stdio", "sse", "http_stream"] = Field(
        default="stdio",
        description="传输协议类型"
    )
    host: str = Field(
        default="127.0.0.1",
        description="服务器地址（仅 sse/http_stream）"
    )
    port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="服务器端口（仅 sse/http_stream）"
    )

    @field_validator('host')
    @classmethod
    def validate_host(cls, v: str) -> str:
        """验证主机地址"""
        if v not in ("0.0.0.0", "127.0.0.1", "localhost"):
            # 简单验证 IP 或域名
            parts = v.split('.')
            if len(parts) == 4:
                if not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                    raise ValueError(f"无效的 IP 地址: {v}")
        return v

    model_config = {
        "extra": "forbid",
        "frozen": False,
    }


class ToolConfig(BaseModel):
    """单个工具配置"""

    name: str = Field(..., description="工具名称")
    enabled: bool = Field(default=True, description="是否启用")
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="超时时间（秒）"
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="工具特定配置"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证工具名称"""
        if not v.replace('_', '').isalnum():
            raise ValueError(f"工具名称只能包含字母、数字和下划线: {v}")
        return v


class ToolGroupConfig(BaseModel):
    """工具组配置"""

    name: str = Field(..., description="组名称")
    enabled: bool = Field(default=True, description="是否启用整个组")
    tools: dict[str, bool | ToolConfig] = Field(
        default_factory=dict,
        description="组内工具配置"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证组名称"""
        if not v.replace('_', '').isalnum():
            raise ValueError(f"组名称只能包含字母、数字和下划线: {v}")
        return v

    def is_tool_enabled(self, tool_name: str) -> bool:
        """检查工具是否启用"""
        if not self.enabled:
            return False

        tool_config = self.tools.get(tool_name)
        if tool_config is None:
            return True  # 默认启用

        if isinstance(tool_config, bool):
            return tool_config

        return tool_config.enabled


class KnowledgeConfig(BaseModel):
    """知识库配置"""

    enabled: bool = Field(default=True, description="是否启用知识库")
    db_path: str = Field(
        default="~/.lyxamour/mcp/knowledge.db",
        description="数据库文件路径"
    )
    auto_index: bool = Field(
        default=True,
        description="是否自动索引"
    )
    chunk_size: int = Field(
        default=512,
        ge=128,
        le=2048,
        description="文档分块大小"
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        le=512,
        description="分块重叠大小"
    )
    enable_fts: bool = Field(
        default=True,
        description="启用全文搜索"
    )
    enable_vector: bool = Field(
        default=False,
        description="启用向量搜索（需要额外依赖）"
    )

    @field_validator('db_path')
    @classmethod
    def expand_db_path(cls, v: str) -> str:
        """展开路径中的 ~ """
        return str(Path(v).expanduser())


class WebConfig(BaseModel):
    """Web 界面配置"""

    enabled: bool = Field(default=True, description="是否启用 Web 界面")
    host: str = Field(default="127.0.0.1", description="Web 服务器地址")
    port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Web 服务器端口"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:8080"],
        description="允许的 CORS 来源"
    )
    api_prefix: str = Field(
        default="/api/v1",
        description="API 路径前缀"
    )
    static_dir: str = Field(
        default="static",
        description="静态文件目录"
    )


class LogConfig(BaseModel):
    """日志配置"""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="日志级别"
    )
    format: Literal["json", "console", "text"] = Field(
        default="console",
        description="日志格式"
    )
    file: str | None = Field(
        default=None,
        description="日志文件路径（None 则不写文件）"
    )
    max_file_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        ge=1024 * 1024,
        description="日志文件最大大小（字节）"
    )
    backup_count: int = Field(
        default=5,
        ge=0,
        description="日志文件备份数量"
    )


class PluginConfig(BaseModel):
    """插件配置"""

    enabled: bool = Field(default=True, description="是否启用插件系统")
    directories: list[str] = Field(
        default_factory=lambda: ["~/.lyxamour/mcp/plugins"],
        description="插件搜索目录"
    )
    auto_load: bool = Field(
        default=True,
        description="是否自动加载插件"
    )
    whitelist: list[str] = Field(
        default_factory=list,
        description="插件白名单（空则允许所有）"
    )
    blacklist: list[str] = Field(
        default_factory=list,
        description="插件黑名单"
    )


class Config(BaseModel):
    """主配置模型"""

    transport: TransportConfig = Field(
        default_factory=TransportConfig,
        description="传输层配置"
    )
    tool_groups: list[ToolGroupConfig] = Field(
        default_factory=list,
        description="工具组配置"
    )
    knowledge: KnowledgeConfig = Field(
        default_factory=KnowledgeConfig,
        description="知识库配置"
    )
    web: WebConfig = Field(
        default_factory=WebConfig,
        description="Web 界面配置"
    )
    log: LogConfig = Field(
        default_factory=LogConfig,
        description="日志配置"
    )
    plugin: PluginConfig = Field(
        default_factory=PluginConfig,
        description="插件配置"
    )

    # 其他全局配置
    max_concurrent_tasks: int = Field(
        default=10,
        ge=1,
        le=100,
        description="最大并发任务数"
    )
    task_timeout: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="任务默认超时（秒）"
    )

    model_config = {
        "extra": "forbid",
        "frozen": False,
    }

    def get_tool_group(self, group_name: str) -> ToolGroupConfig | None:
        """获取工具组配置"""
        for group in self.tool_groups:
            if group.name == group_name:
                return group
        return None

    def is_tool_enabled(self, group_name: str, tool_name: str) -> bool:
        """检查工具是否启用"""
        group = self.get_tool_group(group_name)
        if group is None:
            return True  # 组不存在，默认启用
        return group.is_tool_enabled(tool_name)
```

## 配置加载器

### 加载流程

```python
# config/loader.py
import yaml
from pathlib import Path
from typing import Any
import os
import logging

from lyxamour_mcp.config.models import Config
from lyxamour_mcp.config.defaults import get_default_config
from lyxamour_mcp.config.merger import merge_configs
from lyxamour_mcp.config.validator import validate_config

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器"""

    # 配置文件路径
    GLOBAL_CONFIG_PATH = Path.home() / ".lyxamour" / "mcp" / "config.yaml"
    PROJECT_CONFIG_NAME = ".lyxamour/mcp/config.yaml"

    @classmethod
    def load(
        cls,
        project_dir: Path | None = None,
        config_file: Path | None = None
    ) -> Config:
        """加载配置

        Args:
            project_dir: 项目目录（搜索项目配置）
            config_file: 明确指定的配置文件

        Returns:
            合并后的配置对象
        """
        # 1. 加载默认配置
        config_dict = get_default_config()
        logger.debug("已加载默认配置")

        # 2. 加载全局配置
        if cls.GLOBAL_CONFIG_PATH.exists():
            global_config = cls._load_yaml(cls.GLOBAL_CONFIG_PATH)
            config_dict = merge_configs(config_dict, global_config)
            logger.info(f"已加载全局配置: {cls.GLOBAL_CONFIG_PATH}")

        # 3. 加载项目配置
        if project_dir:
            project_config_path = project_dir / cls.PROJECT_CONFIG_NAME
            if project_config_path.exists():
                project_config = cls._load_yaml(project_config_path)
                config_dict = merge_configs(config_dict, project_config)
                logger.info(f"已加载项目配置: {project_config_path}")

        # 4. 加载明确指定的配置文件
        if config_file and config_file.exists():
            file_config = cls._load_yaml(config_file)
            config_dict = merge_configs(config_dict, file_config)
            logger.info(f"已加载配置文件: {config_file}")

        # 5. 从环境变量加载
        env_config = cls._load_from_env()
        if env_config:
            config_dict = merge_configs(config_dict, env_config)
            logger.debug("已加载环境变量配置")

        # 6. 验证并构建配置对象
        config = Config(**config_dict)
        validate_config(config)

        logger.info("配置加载完成")
        return config

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """加载 YAML 文件"""
        try:
            with path.open('r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except yaml.YAMLError as e:
            logger.error(f"YAML 解析失败: {path}: {e}")
            raise ConfigError(f"配置文件格式错误: {path}") from e
        except Exception as e:
            logger.error(f"读取配置文件失败: {path}: {e}")
            raise ConfigError(f"无法读取配置文件: {path}") from e

    @staticmethod
    def _load_from_env() -> dict[str, Any]:
        """从环境变量加载配置

        环境变量格式: LYXAMOUR_MCP_<PATH>
        路径使用双下划线分隔，例如:
            LYXAMOUR_MCP_TRANSPORT__TYPE=stdio
            LYXAMOUR_MCP_LOG__LEVEL=DEBUG
        """
        config: dict[str, Any] = {}
        prefix = "LYXAMOUR_MCP_"

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            # 移除前缀并分割路径
            path = key[len(prefix):].lower().split("__")

            # 构建嵌套字典
            current = config
            for part in path[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # 设置值（尝试类型转换）
            current[path[-1]] = _parse_env_value(value)

        return config


def _parse_env_value(value: str) -> Any:
    """解析环境变量值"""
    # 布尔值
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False

    # 数字
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # 字符串
    return value


class ConfigError(Exception):
    """配置错误"""
    pass
```

## 配置合并器

```python
# config/merger.py
from typing import Any
from copy import deepcopy


def merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """深度合并配置字典

    Args:
        base: 基础配置
        override: 覆盖配置

    Returns:
        合并后的配置

    规则:
        - 字典递归合并
        - 列表追加（工具组列表）
        - 其他类型直接覆盖
    """
    result = deepcopy(base)

    for key, value in override.items():
        if key not in result:
            result[key] = deepcopy(value)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            # 递归合并字典
            result[key] = merge_configs(result[key], value)
        elif isinstance(result[key], list) and isinstance(value, list):
            # 特殊处理：工具组列表按名称合并
            if key == "tool_groups":
                result[key] = _merge_tool_groups(result[key], value)
            else:
                # 一般列表追加
                result[key] = result[key] + value
        else:
            # 直接覆盖
            result[key] = deepcopy(value)

    return result


def _merge_tool_groups(
    base_groups: list[dict[str, Any]],
    override_groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """合并工具组列表

    按名称合并，同名组递归合并配置
    """
    result = deepcopy(base_groups)
    base_names = {group["name"]: i for i, group in enumerate(result)}

    for override_group in override_groups:
        name = override_group["name"]
        if name in base_names:
            # 同名组，合并配置
            idx = base_names[name]
            result[idx] = merge_configs(result[idx], override_group)
        else:
            # 新组，直接添加
            result.append(deepcopy(override_group))

    return result
```

## 配置验证器

```python
# config/validator.py
from pathlib import Path
import logging

from lyxamour_mcp.config.models import Config, ConfigError

logger = logging.getLogger(__name__)


def validate_config(config: Config) -> None:
    """验证配置的有效性

    Args:
        config: 配置对象

    Raises:
        ConfigError: 配置无效
    """
    # 1. 验证知识库路径
    if config.knowledge.enabled:
        db_path = Path(config.knowledge.db_path)
        db_dir = db_path.parent
        if not db_dir.exists():
            logger.warning(f"知识库目录不存在，将自动创建: {db_dir}")
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ConfigError(f"无法创建知识库目录: {db_dir}: {e}") from e

    # 2. 验证 Web 配置
    if config.web.enabled:
        if config.web.port == config.transport.port:
            if config.transport.type in ("sse", "http_stream"):
                raise ConfigError(
                    f"Web 端口与传输层端口冲突: {config.web.port}"
                )

    # 3. 验证工具组
    group_names = [group.name for group in config.tool_groups]
    if len(group_names) != len(set(group_names)):
        duplicates = [name for name in group_names if group_names.count(name) > 1]
        raise ConfigError(f"工具组名称重复: {duplicates}")

    # 4. 验证插件目录
    if config.plugin.enabled:
        for plugin_dir in config.plugin.directories:
            path = Path(plugin_dir).expanduser()
            if not path.exists():
                logger.warning(f"插件目录不存在: {path}")

    # 5. 验证日志配置
    if config.log.file:
        log_path = Path(config.log.file).expanduser()
        log_dir = log_path.parent
        if not log_dir.exists():
            logger.warning(f"日志目录不存在，将自动创建: {log_dir}")
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ConfigError(f"无法创建日志目录: {log_dir}: {e}") from e

    logger.info("配置验证通过")
```

## 默认配置

```python
# config/defaults.py
from typing import Any


def get_default_config() -> dict[str, Any]:
    """获取默认配置"""
    return {
        "transport": {
            "type": "stdio",
            "host": "127.0.0.1",
            "port": 8000,
        },
        "tool_groups": [
            {
                "name": "filesystem",
                "enabled": True,
                "tools": {
                    "read_file": True,
                    "write_file": True,
                    "list_directory": True,
                    "search_files": True,
                },
            },
            {
                "name": "text",
                "enabled": True,
                "tools": {
                    "search_text": True,
                    "replace_text": True,
                },
            },
        ],
        "knowledge": {
            "enabled": True,
            "db_path": "~/.lyxamour/mcp/knowledge.db",
            "auto_index": True,
            "chunk_size": 512,
            "chunk_overlap": 50,
            "enable_fts": True,
            "enable_vector": False,
        },
        "web": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8080,
            "cors_origins": ["http://localhost:8080"],
            "api_prefix": "/api/v1",
            "static_dir": "static",
        },
        "log": {
            "level": "INFO",
            "format": "console",
            "file": None,
            "max_file_size": 10 * 1024 * 1024,
            "backup_count": 5,
        },
        "plugin": {
            "enabled": True,
            "directories": ["~/.lyxamour/mcp/plugins"],
            "auto_load": True,
            "whitelist": [],
            "blacklist": [],
        },
        "max_concurrent_tasks": 10,
        "task_timeout": 300,
    }
```

## 配置文件示例

### 全局配置示例

```yaml
# ~/.lyxamour/mcp/config.yaml

# 传输层配置
transport:
  type: stdio # stdio | sse | http_stream
  host: 127.0.0.1
  port: 8000

# 工具组配置
tool_groups:
  - name: filesystem
    enabled: true
    tools:
      read_file: true
      write_file: true
      list_directory: true
      search_files: true

  - name: text
    enabled: true
    tools:
      search_text: true
      replace_text: true

# 知识库配置
knowledge:
  enabled: true
  db_path: ~/.lyxamour/mcp/knowledge.db
  auto_index: true
  chunk_size: 512
  chunk_overlap: 50
  enable_fts: true
  enable_vector: false

# Web 界面配置
web:
  enabled: true
  host: 127.0.0.1
  port: 8080
  cors_origins:
    - http://localhost:8080
  api_prefix: /api/v1
  static_dir: static

# 日志配置
log:
  level: INFO # DEBUG | INFO | WARNING | ERROR | CRITICAL
  format: console # json | console | text
  file: null # 日志文件路径，null 则不写文件
  max_file_size: 10485760 # 10MB
  backup_count: 5

# 插件配置
plugin:
  enabled: true
  directories:
    - ~/.lyxamour/mcp/plugins
  auto_load: true
  whitelist: [] # 空列表表示允许所有
  blacklist: []

# 全局配置
max_concurrent_tasks: 10
task_timeout: 300
```

### 项目配置示例

```yaml
# .lyxamour/mcp/config.yaml (项目级配置)

# 覆盖传输类型
transport:
  type: http_stream
  port: 9000

# 添加项目特定工具组
tool_groups:
  - name: project_tools
    enabled: true
    tools:
      custom_tool: true

# 项目特定知识库
knowledge:
  db_path: .lyxamour/mcp/project-knowledge.db

# 调试模式
log:
  level: DEBUG
  file: .lyxamour/mcp/logs/debug.log
```

## 配置热重载

```python
# config/watcher.py
import asyncio
from pathlib import Path
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """配置文件监视器，支持热重载"""

    def __init__(
        self,
        config_paths: list[Path],
        on_change: Callable[[Path], None]
    ):
        """
        Args:
            config_paths: 要监视的配置文件路径列表
            on_change: 配置变更时的回调函数
        """
        self.config_paths = config_paths
        self.on_change = on_change
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """开始监视"""
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("配置监视器已启动")

    async def stop(self) -> None:
        """停止监视"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("配置监视器已停止")

    async def _watch_loop(self) -> None:
        """监视循环"""
        last_mtimes = {
            path: path.stat().st_mtime if path.exists() else 0
            for path in self.config_paths
        }

        while self._running:
            await asyncio.sleep(1)  # 每秒检查一次

            for path in self.config_paths:
                if not path.exists():
                    continue

                mtime = path.stat().st_mtime
                if mtime > last_mtimes[path]:
                    logger.info(f"检测到配置变更: {path}")
                    last_mtimes[path] = mtime
                    try:
                        self.on_change(path)
                    except Exception as e:
                        logger.error(f"配置重载失败: {e}")
```

## 命令行参数

```python
# cli/config.py
import typer
from pathlib import Path

app = typer.Typer()


@app.command("show")
def show_config(
    project_dir: Path = typer.Option(
        None,
        "--project",
        "-p",
        help="项目目录"
    )
):
    """显示当前配置"""
    from lyxamour_mcp.config.loader import ConfigLoader

    config = ConfigLoader.load(project_dir=project_dir)
    print(config.model_dump_json(indent=2))


@app.command("validate")
def validate_config_cmd(
    config_file: Path = typer.Argument(..., help="配置文件路径")
):
    """验证配置文件"""
    from lyxamour_mcp.config.loader import ConfigLoader
    from lyxamour_mcp.config.validator import validate_config

    try:
        config = ConfigLoader.load(config_file=config_file)
        validate_config(config)
        print("✓ 配置验证通过")
    except Exception as e:
        print(f"✗ 配置验证失败: {e}")
        raise typer.Exit(code=1)


@app.command("init")
def init_config(
    global_config: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="初始化全局配置"
    ),
    project_dir: Path = typer.Option(
        Path.cwd(),
        "--project",
        "-p",
        help="项目目录"
    )
):
    """初始化配置文件"""
    from lyxamour_mcp.config.defaults import get_default_config
    import yaml

    if global_config:
        config_path = Path.home() / ".lyxamour" / "mcp" / "config.yaml"
    else:
        config_path = project_dir / ".lyxamour" / "mcp" / "config.yaml"

    if config_path.exists():
        overwrite = typer.confirm(f"配置文件已存在: {config_path}。是否覆盖?")
        if not overwrite:
            raise typer.Abort()

    # 创建目录
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入默认配置
    default_config = get_default_config()
    with config_path.open('w', encoding='utf-8') as f:
        yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)

    print(f"✓ 配置文件已创建: {config_path}")
```

## 使用示例

```python
# 基本使用
from lyxamour_mcp.config import ConfigLoader

# 加载配置
config = ConfigLoader.load(project_dir=Path("/path/to/project"))

# 访问配置
print(config.transport.type)
print(config.log.level)

# 检查工具是否启用
if config.is_tool_enabled("filesystem", "read_file"):
    print("read_file 工具已启用")

# 热重载
from lyxamour_mcp.config.watcher import ConfigWatcher

def on_config_change(path: Path):
    new_config = ConfigLoader.load()
    # 更新配置...

watcher = ConfigWatcher(
    config_paths=[ConfigLoader.GLOBAL_CONFIG_PATH],
    on_change=on_config_change
)
await watcher.start()
```
