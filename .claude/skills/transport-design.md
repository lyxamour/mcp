---
name: transport-design
description: MCP 工具传输层详细设计
auto-activate:
  always: true
---

# 传输层设计

## 概述

传输层提供统一的抽象接口，支持三种传输协议：

- **stdio**: 标准输入/输出，用于本地进程通信
- **SSE**: Server-Sent Events，HTTP 单向流（遗留支持）
- **HTTP Stream**: Streamable HTTP，现代双向 HTTP 流（推荐）

## 传输层抽象

### 基础接口

```python
# transport/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any
from contextlib import asynccontextmanager
import structlog

logger = structlog.get_logger(__name__)


class Transport(ABC):
    """传输层抽象基类

    定义了所有传输实现必须遵循的接口。
    """

    def __init__(self) -> None:
        """初始化传输层"""
        self._closed = False

    @abstractmethod
    async def start(self) -> None:
        """启动传输层

        执行必要的初始化工作，如建立连接、启动服务器等。
        """
        pass

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """发送消息到客户端

        Args:
            message: JSON-RPC 消息字典

        Raises:
            TransportError: 发送失败
        """
        pass

    @abstractmethod
    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """接收来自客户端的消息流

        Yields:
            JSON-RPC 消息字典

        Raises:
            TransportError: 接收失败
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭传输连接

        清理资源，关闭连接。
        """
        pass

    @property
    def is_closed(self) -> bool:
        """传输是否已关闭"""
        return self._closed

    @asynccontextmanager
    async def lifecycle(self):
        """传输生命周期管理器

        用法:
            async with transport.lifecycle():
                # 使用传输
                ...
        """
        try:
            await self.start()
            yield self
        finally:
            await self.close()


class TransportError(Exception):
    """传输层错误基类"""
    pass


class ConnectionError(TransportError):
    """连接错误"""
    pass


class MessageError(TransportError):
    """消息处理错误"""
    pass
```

## stdio 传输实现

```python
# transport/stdio.py
import asyncio
import json
import sys
from typing import AsyncIterator, Any
import structlog

from lyxamour_mcp.transport.base import Transport, TransportError, MessageError

logger = structlog.get_logger(__name__)


class StdioTransport(Transport):
    """stdio 传输实现

    使用标准输入/输出进行通信，适用于本地进程。
    每条消息占一行，使用 JSON 格式。
    """

    def __init__(self) -> None:
        super().__init__()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._send_lock = asyncio.Lock()

    async def start(self) -> None:
        """启动 stdio 传输"""
        logger.info("启动 stdio 传输")

        # 创建异步 stdin/stdout 流
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        reader_protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

        transport, writer_protocol = await loop.connect_write_pipe(
            lambda: asyncio.StreamReaderProtocol(asyncio.StreamReader()),
            sys.stdout
        )
        self._writer = asyncio.StreamWriter(
            transport, writer_protocol, None, loop
        )

        logger.info("stdio 传输已启动")

    async def send(self, message: dict[str, Any]) -> None:
        """发送消息到 stdout"""
        if self._closed or self._writer is None:
            raise TransportError("传输已关闭")

        try:
            # JSON 序列化
            json_str = json.dumps(message, ensure_ascii=False)

            # 添加换行符
            line = json_str + "\n"

            # 线程安全发送
            async with self._send_lock:
                self._writer.write(line.encode('utf-8'))
                await self._writer.drain()

            logger.debug("已发送消息", message_id=message.get("id"))

        except Exception as e:
            logger.error("发送消息失败", error=str(e))
            raise MessageError(f"发送失败: {e}") from e

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """从 stdin 接收消息流"""
        if self._reader is None:
            raise TransportError("传输未启动")

        logger.info("开始接收消息")

        while not self._closed:
            try:
                # 读取一行
                line = await self._reader.readline()

                if not line:
                    # EOF，客户端关闭
                    logger.info("客户端关闭连接")
                    break

                # 解析 JSON
                message = json.loads(line.decode('utf-8'))

                logger.debug("收到消息", message_id=message.get("id"))
                yield message

            except json.JSONDecodeError as e:
                logger.error("JSON 解析失败", error=str(e), line=line)
                # 继续接收下一条消息
                continue

            except Exception as e:
                logger.error("接收消息失败", error=str(e))
                raise TransportError(f"接收失败: {e}") from e

    async def close(self) -> None:
        """关闭 stdio 传输"""
        if self._closed:
            return

        logger.info("关闭 stdio 传输")
        self._closed = True

        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

        logger.info("stdio 传输已关闭")
```

## SSE 传输实现

```python
# transport/sse.py
import asyncio
import json
from typing import AsyncIterator, Any
import structlog
from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from starlette.routing import Route
import uvicorn

from lyxamour_mcp.transport.base import Transport, TransportError, MessageError

logger = structlog.get_logger(__name__)


class SSETransport(Transport):
    """SSE (Server-Sent Events) 传输实现

    基于 HTTP 的单向流传输，客户端通过 POST 发送消息，
    服务器通过 SSE 流发送响应。

    注意: SSE 是遗留协议，推荐使用 HTTP Stream。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self._app: Starlette | None = None
        self._server: uvicorn.Server | None = None
        self._client_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._server_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def start(self) -> None:
        """启动 SSE 服务器"""
        logger.info("启动 SSE 传输", host=self.host, port=self.port)

        # 创建 Starlette 应用
        self._app = Starlette(
            routes=[
                Route("/message", self._handle_message, methods=["POST"]),
                Route("/events", self._handle_events, methods=["GET"]),
            ]
        )

        # 启动服务器
        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self._server = uvicorn.Server(config)

        # 在后台运行服务器
        asyncio.create_task(self._server.serve())

        logger.info("SSE 传输已启动", endpoint=f"http://{self.host}:{self.port}")

    async def _handle_message(self, request):
        """处理客户端 POST 的消息"""
        try:
            message = await request.json()
            await self._client_queue.put(message)
            logger.debug("收到客户端消息", message_id=message.get("id"))
            return {"status": "ok"}
        except Exception as e:
            logger.error("处理消息失败", error=str(e))
            return {"status": "error", "message": str(e)}

    async def _handle_events(self, request):
        """处理 SSE 连接"""
        async def event_stream():
            while not self._closed:
                try:
                    # 从队列获取消息
                    message = await asyncio.wait_for(
                        self._server_queue.get(),
                        timeout=30.0  # 30秒心跳
                    )

                    # 格式化为 SSE 事件
                    data = json.dumps(message, ensure_ascii=False)
                    yield f"data: {data}\n\n"

                except asyncio.TimeoutError:
                    # 发送心跳
                    yield ": heartbeat\n\n"

                except Exception as e:
                    logger.error("SSE 流错误", error=str(e))
                    break

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    async def send(self, message: dict[str, Any]) -> None:
        """发送消息到客户端（通过 SSE 流）"""
        if self._closed:
            raise TransportError("传输已关闭")

        try:
            await self._server_queue.put(message)
            logger.debug("已发送消息到 SSE 流", message_id=message.get("id"))
        except Exception as e:
            logger.error("发送消息失败", error=str(e))
            raise MessageError(f"发送失败: {e}") from e

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """接收来自客户端的消息"""
        logger.info("开始接收客户端消息")

        while not self._closed:
            try:
                message = await self._client_queue.get()
                logger.debug("收到消息", message_id=message.get("id"))
                yield message
            except Exception as e:
                logger.error("接收消息失败", error=str(e))
                raise TransportError(f"接收失败: {e}") from e

    async def close(self) -> None:
        """关闭 SSE 服务器"""
        if self._closed:
            return

        logger.info("关闭 SSE 传输")
        self._closed = True

        if self._server:
            await self._server.shutdown()

        logger.info("SSE 传输已关闭")
```

## HTTP Stream 传输实现

```python
# transport/http_stream.py
import asyncio
import json
from typing import AsyncIterator, Any
import structlog
from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from starlette.routing import Route
from starlette.requests import Request
import uvicorn

from lyxamour_mcp.transport.base import Transport, TransportError, MessageError

logger = structlog.get_logger(__name__)


class HTTPStreamTransport(Transport):
    """HTTP Stream 传输实现

    现代双向 HTTP 流传输，使用 Streamable HTTP 协议。
    客户端和服务器都可以通过 HTTP 流发送和接收消息。

    这是推荐的 HTTP 传输方式。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self._app: Starlette | None = None
        self._server: uvicorn.Server | None = None
        self._message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._response_queues: dict[str, asyncio.Queue] = {}
        self._connection_id = 0

    async def start(self) -> None:
        """启动 HTTP Stream 服务器"""
        logger.info("启动 HTTP Stream 传输", host=self.host, port=self.port)

        # 创建 Starlette 应用
        self._app = Starlette(
            routes=[
                Route("/stream", self._handle_stream, methods=["POST"]),
            ]
        )

        # 启动服务器
        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self._server = uvicorn.Server(config)

        # 在后台运行服务器
        asyncio.create_task(self._server.serve())

        logger.info(
            "HTTP Stream 传输已启动",
            endpoint=f"http://{self.host}:{self.port}/stream"
        )

    async def _handle_stream(self, request: Request):
        """处理双向流连接"""
        connection_id = str(self._connection_id)
        self._connection_id += 1

        logger.info("新的流连接", connection_id=connection_id)

        # 为这个连接创建响应队列
        response_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._response_queues[connection_id] = response_queue

        async def receive_stream():
            """接收客户端消息流"""
            try:
                async for chunk in request.stream():
                    if not chunk:
                        continue

                    # 解析 JSON 消息（每行一个）
                    lines = chunk.decode('utf-8').split('\n')
                    for line in lines:
                        if not line.strip():
                            continue

                        try:
                            message = json.loads(line)
                            await self._message_queue.put(message)
                            logger.debug(
                                "收到消息",
                                connection_id=connection_id,
                                message_id=message.get("id")
                            )
                        except json.JSONDecodeError as e:
                            logger.error("JSON 解析失败", error=str(e))

            except Exception as e:
                logger.error("接收流错误", error=str(e))

        async def send_stream():
            """发送响应流"""
            while not self._closed:
                try:
                    message = await asyncio.wait_for(
                        response_queue.get(),
                        timeout=30.0  # 30秒超时
                    )

                    # 序列化并添加换行符
                    json_str = json.dumps(message, ensure_ascii=False)
                    yield (json_str + "\n").encode('utf-8')

                    logger.debug(
                        "已发送消息",
                        connection_id=connection_id,
                        message_id=message.get("id")
                    )

                except asyncio.TimeoutError:
                    # 发送心跳（空行）
                    yield b"\n"

                except Exception as e:
                    logger.error("发送流错误", error=str(e))
                    break

        # 启动接收任务
        asyncio.create_task(receive_stream())

        # 返回流响应
        try:
            return StreamingResponse(
                send_stream(),
                media_type="application/x-ndjson",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        finally:
            # 清理连接
            if connection_id in self._response_queues:
                del self._response_queues[connection_id]
            logger.info("流连接关闭", connection_id=connection_id)

    async def send(self, message: dict[str, Any]) -> None:
        """发送消息到所有连接的客户端"""
        if self._closed:
            raise TransportError("传输已关闭")

        try:
            # 广播到所有连接
            for queue in self._response_queues.values():
                await queue.put(message)

            logger.debug(
                "已广播消息",
                message_id=message.get("id"),
                connections=len(self._response_queues)
            )

        except Exception as e:
            logger.error("发送消息失败", error=str(e))
            raise MessageError(f"发送失败: {e}") from e

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """接收来自客户端的消息"""
        logger.info("开始接收消息")

        while not self._closed:
            try:
                message = await self._message_queue.get()
                logger.debug("收到消息", message_id=message.get("id"))
                yield message
            except Exception as e:
                logger.error("接收消息失败", error=str(e))
                raise TransportError(f"接收失败: {e}") from e

    async def close(self) -> None:
        """关闭 HTTP Stream 服务器"""
        if self._closed:
            return

        logger.info("关闭 HTTP Stream 传输")
        self._closed = True

        if self._server:
            await self._server.shutdown()

        # 清理所有连接
        self._response_queues.clear()

        logger.info("HTTP Stream 传输已关闭")
```

## 传输层工厂

```python
# transport/factory.py
from typing import Literal
import structlog

from lyxamour_mcp.transport.base import Transport
from lyxamour_mcp.transport.stdio import StdioTransport
from lyxamour_mcp.transport.sse import SSETransport
from lyxamour_mcp.transport.http_stream import HTTPStreamTransport
from lyxamour_mcp.config.models import TransportConfig

logger = structlog.get_logger(__name__)

TransportType = Literal["stdio", "sse", "http_stream"]


class TransportFactory:
    """传输层工厂

    根据配置创建相应的传输实例。
    """

    @staticmethod
    def create(config: TransportConfig) -> Transport:
        """创建传输实例

        Args:
            config: 传输配置

        Returns:
            传输实例

        Raises:
            ValueError: 不支持的传输类型
        """
        transport_type = config.type

        logger.info("创建传输实例", type=transport_type)

        if transport_type == "stdio":
            return StdioTransport()

        elif transport_type == "sse":
            return SSETransport(
                host=config.host,
                port=config.port
            )

        elif transport_type == "http_stream":
            return HTTPStreamTransport(
                host=config.host,
                port=config.port
            )

        else:
            raise ValueError(f"不支持的传输类型: {transport_type}")

    @staticmethod
    def get_available_types() -> list[TransportType]:
        """获取所有可用的传输类型"""
        return ["stdio", "sse", "http_stream"]
```

## 传输层中间件

### 消息验证中间件

```python
# transport/middleware.py
from typing import AsyncIterator, Any
import structlog

from lyxamour_mcp.transport.base import Transport, MessageError

logger = structlog.get_logger(__name__)


class ValidationMiddleware(Transport):
    """消息验证中间件

    在发送和接收消息时进行 JSON-RPC 格式验证。
    """

    def __init__(self, transport: Transport) -> None:
        super().__init__()
        self._transport = transport

    async def start(self) -> None:
        await self._transport.start()

    async def send(self, message: dict[str, Any]) -> None:
        """发送前验证消息格式"""
        self._validate_message(message, direction="outgoing")
        await self._transport.send(message)

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        """接收后验证消息格式"""
        async for message in self._transport.receive():
            self._validate_message(message, direction="incoming")
            yield message

    async def close(self) -> None:
        await self._transport.close()

    @staticmethod
    def _validate_message(message: dict[str, Any], direction: str) -> None:
        """验证 JSON-RPC 消息格式"""
        # JSON-RPC 2.0 必须包含 jsonrpc 字段
        if "jsonrpc" not in message:
            raise MessageError(f"{direction} 消息缺少 jsonrpc 字段")

        if message["jsonrpc"] != "2.0":
            raise MessageError(
                f"{direction} 消息 jsonrpc 版本错误: {message['jsonrpc']}"
            )

        # 请求必须包含 method
        if "method" in message:
            if not isinstance(message["method"], str):
                raise MessageError(f"{direction} 消息 method 必须是字符串")

        # 响应必须包含 result 或 error
        elif "result" not in message and "error" not in message:
            if "id" in message:  # 响应消息
                raise MessageError(
                    f"{direction} 响应消息必须包含 result 或 error"
                )


class LoggingMiddleware(Transport):
    """日志中间件

    记录所有传输的消息。
    """

    def __init__(self, transport: Transport) -> None:
        super().__init__()
        self._transport = transport

    async def start(self) -> None:
        await self._transport.start()

    async def send(self, message: dict[str, Any]) -> None:
        logger.debug(
            "发送消息",
            method=message.get("method"),
            id=message.get("id"),
            message=message
        )
        await self._transport.send(message)

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        async for message in self._transport.receive():
            logger.debug(
                "接收消息",
                method=message.get("method"),
                id=message.get("id"),
                message=message
            )
            yield message

    async def close(self) -> None:
        await self._transport.close()
```

## 使用示例

```python
# 基本使用
from lyxamour_mcp.transport.factory import TransportFactory
from lyxamour_mcp.config.models import TransportConfig

# 创建配置
config = TransportConfig(type="stdio")

# 创建传输
transport = TransportFactory.create(config)

# 使用生命周期管理器
async with transport.lifecycle():
    # 发送消息
    await transport.send({
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "read_file", "arguments": {"path": "test.txt"}},
        "id": 1
    })

    # 接收消息
    async for message in transport.receive():
        print(f"收到消息: {message}")

        # 处理消息...

        # 发送响应
        await transport.send({
            "jsonrpc": "2.0",
            "result": {"content": "文件内容"},
            "id": message["id"]
        })


# 使用中间件
from lyxamour_mcp.transport.middleware import ValidationMiddleware, LoggingMiddleware

# 包装传输
transport = TransportFactory.create(config)
transport = ValidationMiddleware(transport)
transport = LoggingMiddleware(transport)

async with transport.lifecycle():
    # 所有消息都会被验证和记录
    await transport.send(message)
```

## 性能考虑

### 消息批处理

对于高吞吐场景，支持消息批处理：

```python
async def send_batch(transport: Transport, messages: list[dict]) -> None:
    """批量发送消息"""
    for message in messages:
        await transport.send(message)
        # 或使用 asyncio.gather 并发发送
```

### 背压控制

使用有界队列防止内存溢出：

```python
# 在传输实现中
self._queue = asyncio.Queue(maxsize=1000)  # 限制队列大小
```

### 连接池

对于 HTTP 传输，复用连接：

```python
# 使用 httpx 的异步客户端
import httpx

async with httpx.AsyncClient() as client:
    # 复用连接
    ...
```

## 测试策略

### 单元测试

```python
import pytest
from lyxamour_mcp.transport.stdio import StdioTransport

@pytest.mark.asyncio
async def test_stdio_send_receive():
    """测试 stdio 发送和接收"""
    transport = StdioTransport()

    async with transport.lifecycle():
        # 发送消息
        await transport.send({"jsonrpc": "2.0", "method": "test", "id": 1})

        # 验证...
```

### 集成测试

测试完整的消息流：

```python
@pytest.mark.asyncio
async def test_full_message_flow():
    """测试完整消息流"""
    # 创建传输
    # 模拟客户端
    # 发送请求
    # 验证响应
    ...
```
