"""
配置模型 - Pydantic 配置模型定义
"""

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TransportType(str, Enum):
    """传输类型枚举"""

    STDIO = "stdio"
    SSE = "sse"
    HTTP_STREAM = "http_stream"


class LogLevel(str, Enum):
    """日志级别枚举"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TransportConfig(BaseModel):
    """传输层配置"""

    type: TransportType = Field(default=TransportType.STDIO, description="传输类型")
    host: str = Field(default="127.0.0.1", description="服务器主机地址")
    port: int = Field(default=8000, description="服务器端口")
    path: str = Field(default="/mcp", description="HTTP 路径")


class ToolGroupConfig(BaseModel):
    """工具分组配置"""

    name: str = Field(description="分组名称")
    enabled: bool = Field(default=True, description="是否启用")
    tools: list[str] = Field(default_factory=list, description="工具列表")


class KnowledgeConfig(BaseModel):
    """知识库配置"""

    enabled: bool = Field(default=True, description="是否启用知识库")
    db_path: Path = Field(
        default=Path("~/.lyxamour/mcp/knowledge.db").expanduser(),
        description="数据库路径",
    )
    chunk_size: int = Field(default=1000, description="文档分块大小")
    chunk_overlap: int = Field(default=200, description="分块重叠大小")


class WebConfig(BaseModel):
    """Web 界面配置"""

    enabled: bool = Field(default=True, description="是否启用 Web 界面")
    host: str = Field(default="127.0.0.1", description="Web 服务器主机")
    port: int = Field(default=8080, description="Web 服务器端口")


class LogConfig(BaseModel):
    """日志配置"""

    level: LogLevel = Field(default=LogLevel.INFO, description="日志级别")
    format: str = Field(default="json", description="日志格式")
    file: Path | None = Field(default=None, description="日志文件路径")


class PluginConfig(BaseModel):
    """插件配置"""

    enabled: bool = Field(default=False, description="是否启用插件系统")
    plugin_dirs: list[Path] = Field(default_factory=list, description="插件目录列表")


class ServerConfig(BaseModel):
    """服务器配置"""

    name: str = Field(default="lyxamour-mcp", description="服务器名称")
    version: str = Field(default="0.1.0", description="服务器版本")


class Config(BaseModel):
    """主配置模型"""

    server: ServerConfig = Field(default_factory=ServerConfig, description="服务器配置")
    transport: TransportConfig = Field(default_factory=TransportConfig, description="传输层配置")
    tool_groups: list[ToolGroupConfig] = Field(default_factory=list, description="工具分组配置")
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig, description="知识库配置")
    web: WebConfig = Field(default_factory=WebConfig, description="Web 界面配置")
    log: LogConfig = Field(default_factory=LogConfig, description="日志配置")
    plugin: PluginConfig = Field(default_factory=PluginConfig, description="插件配置")
    max_concurrent_tasks: int = Field(default=10, description="最大并发任务数")
    task_timeout: int = Field(default=300, description="任务超时时间(秒)")

    @field_validator("knowledge", mode="before")
    @classmethod
    def expand_db_path(cls, v: Any) -> Any:
        """展开知识库数据库路径"""
        if isinstance(v, dict) and "db_path" in v:
            v["db_path"] = Path(v["db_path"]).expanduser()
        return v
