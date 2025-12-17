"""
配置加载器 - 从多个来源加载和合并配置
"""

import os
from pathlib import Path
from typing import Any

import structlog
import yaml

from lyxamour_mcp.config.models import Config

logger = structlog.get_logger(__name__)


class ConfigLoader:
    """
    配置加载器

    按优先级从以下来源加载配置：
    1. 环境变量 (最高优先级)
    2. 命令行参数
    3. 项目配置文件 (.lyxamour/mcp/config.yaml)
    4. 用户配置文件 (~/.lyxamour/mcp/config.yaml)
    5. 默认配置 (最低优先级)
    """

    @staticmethod
    def load(
        project_config: Path | None = None,
        user_config: Path | None = None,
        cli_args: dict[str, Any] | None = None,
    ) -> Config:
        """
        加载配置

        Args:
            project_config: 项目配置文件路径
            user_config: 用户配置文件路径
            cli_args: 命令行参数

        Returns:
            Config: 合并后的配置对象
        """
        # 默认配置
        config_data: dict[str, Any] = {}

        # 1. 加载用户配置
        user_config_path = user_config or Path.home() / ".lyxamour/mcp/config.yaml"
        if user_config_path.exists():
            logger.debug("加载用户配置", path=str(user_config_path))
            config_data = ConfigLoader._merge_config(
                config_data, ConfigLoader._load_yaml(user_config_path)
            )

        # 2. 加载项目配置
        project_config_path = project_config or Path.cwd() / ".lyxamour/mcp/config.yaml"
        if project_config_path.exists():
            logger.debug("加载项目配置", path=str(project_config_path))
            config_data = ConfigLoader._merge_config(
                config_data, ConfigLoader._load_yaml(project_config_path)
            )

        # 3. 合并命令行参数
        if cli_args:
            logger.debug("合并命令行参数")
            config_data = ConfigLoader._merge_config(config_data, cli_args)

        # 4. 合并环境变量
        env_config = ConfigLoader._load_from_env()
        if env_config:
            logger.debug("合并环境变量")
            config_data = ConfigLoader._merge_config(config_data, env_config)

        # 创建配置对象
        return Config(**config_data)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """从 YAML 文件加载配置"""
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("加载配置文件失败", path=str(path), error=str(e))
            return {}

    @staticmethod
    def _load_from_env() -> dict[str, Any]:
        """从环境变量加载配置"""
        config: dict[str, Any] = {}

        # MCP_TRANSPORT_TYPE
        if transport_type := os.getenv("MCP_TRANSPORT_TYPE"):
            config.setdefault("transport", {})["type"] = transport_type

        # MCP_LOG_LEVEL
        if log_level := os.getenv("MCP_LOG_LEVEL"):
            config.setdefault("log", {})["level"] = log_level

        # MCP_WEB_ENABLED
        if web_enabled := os.getenv("MCP_WEB_ENABLED"):
            config.setdefault("web", {})["enabled"] = web_enabled.lower() == "true"

        return config

    @staticmethod
    def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """
        深度合并配置字典

        Args:
            base: 基础配置
            override: 覆盖配置

        Returns:
            dict: 合并后的配置
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._merge_config(result[key], value)
            else:
                result[key] = value

        return result
