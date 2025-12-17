"""
Stdio 传输 - 标准输入输出传输实现
"""

import asyncio
import json
import sys
from typing import Any, AsyncIterator

import structlog

from lyxamour_mcp.transport.base import Transport

logger = structlog.get_logger(__name__)


class StdioTransport(Transport):
    """
    Stdio 传输实现

    使用标准输入输出进行 MCP 通信
    """

    def __init__(self) -> None:
        """初始化 Stdio 传输"""
        self._running = False

    async def start(self) -> None:
        """启动 Stdio 传输"""
        self._running = True
        logger.info("Stdio 传输已启动")

    async def send(self, message: dict[str, Any]) -> None:
        """
        发送消息到标准输出

        Args:
            message: JSON-RPC 消息
        """
        try:
            output = json.dumps(message, ensure_ascii=False)
            sys.stdout.write(output + "\n")
            sys.stdout.flush()
            logger.debug("发送消息", message=message)
        except Exception as e:
            logger.error("发送消息失败", error=str(e))
            raise

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """
        从标准输入接收消息

        Yields:
            dict: JSON-RPC 消息
        """
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                # 异步读取标准输入
                line = await loop.run_in_executor(None, sys.stdin.readline)

                if not line:
                    logger.info("标准输入已关闭")
                    break

                message = json.loads(line.strip())
                logger.debug("接收消息", message=message)
                yield message

            except json.JSONDecodeError as e:
                logger.warning("解析 JSON 失败", error=str(e), line=line)
            except Exception as e:
                logger.error("接收消息失败", error=str(e))
                break

    async def close(self) -> None:
        """关闭 Stdio 传输"""
        self._running = False
        logger.info("Stdio 传输已关闭")
