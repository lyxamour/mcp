# lyxamour-mcp

完整的 Python MCP (Model Context Protocol) 工具实现。

## 功能特性

- ✅ **多传输协议支持**: stdio、SSE、HTTP Stream
- ✅ **工具分组管理**: 灵活的工具分组和启用/禁用机制
- ✅ **内置知识库**: 基于 SQLite + FTS5 的文档存储和检索
- ✅ **Web 管理界面**: FastAPI + Alpine.js 构建的现代化管理界面
- ✅ **配置系统**: 5层优先级配置系统
- ✅ **插件支持**: 可扩展的插件系统
- ✅ **零外部依赖**: 无需 MySQL、Redis 等外部服务

## 快速开始

### 快速体验（无需安装）

使用 `uvx` 直接从 GitHub 运行，无需克隆仓库或安装：

```bash
# 直接运行（stdio 模式）
uvx --from git+https://github.com/lyxamour/mcp lyxamour-mcp start

# 指定传输协议
uvx --from git+https://github.com/lyxamour/mcp lyxamour-mcp start --transport sse

# 查看版本
uvx --from git+https://github.com/lyxamour/mcp lyxamour-mcp version

# 查看帮助
uvx --from git+https://github.com/lyxamour/mcp lyxamour-mcp --help
```

### 安装

```bash
# 方法 1: 使用 Makefile（推荐）
git clone https://github.com/lyxamour/mcp.git
cd mcp
make install        # 安装到系统
# 或
make install-dev    # 开发模式安装（可编辑）

# 方法 2: 使用 uv 直接安装
uv pip install lyxamour-mcp

# 方法 3: 从源码安装
git clone https://github.com/lyxamour/mcp.git
cd mcp
uv sync --all-extras
```

### 运行

```bash
# 已安装后运行
lyxamour-mcp start                           # stdio 传输（默认）
lyxamour-mcp start --transport sse           # SSE 传输
lyxamour-mcp start --transport http_stream   # HTTP Stream 传输
lyxamour-mcp version                         # 查看版本

# 未安装直接运行（使用 uv run）
uv run lyxamour-mcp start
uv run python main.py start

# 使用 Makefile
make run            # 使用 uv run 运行
make run-main       # 通过 main.py 运行
```

## 配置

配置文件按以下优先级加载（从高到低）：

1. 环境变量
2. 命令行参数
3. 项目配置文件 (`.lyxamour/mcp/config.yaml`)
4. 用户配置文件 (`~/.lyxamour/mcp/config.yaml`)
5. 默认配置

### 配置示例

```yaml
# .lyxamour/mcp/config.yaml

transport:
  type: stdio
  host: 127.0.0.1
  port: 8000

tool_groups:
  - name: filesystem
    enabled: true
    tools:
      - read_file
      - write_file
      - list_directory

  - name: text
    enabled: true
    tools:
      - search_text
      - count_words

knowledge:
  enabled: true
  db_path: ~/.lyxamour/mcp/knowledge.db
  chunk_size: 1000
  chunk_overlap: 200

web:
  enabled: true
  host: 127.0.0.1
  port: 8080

log:
  level: info
  format: json
```

## 开发

### 环境设置

```bash
# 克隆仓库
git clone https://github.com/lyxamour/mcp.git
cd mcp

# 查看所有可用命令
make

# 安装开发依赖
make dev
# 或
uv sync --all-extras
```

### 开发常用命令

```bash
# 使用 Makefile（推荐）
make dev            # 同步开发依赖
make run            # 运行工具
make test           # 运行测试
make format         # 代码格式化
make lint           # 代码检查
make build          # 构建发布包
make clean          # 清理构建产物

# 或直接使用 uv
uv run pytest                  # 运行测试
uv run black src tests         # 格式化
uv run isort src tests         # 导入排序
uv run mypy src                # 类型检查
uv run ruff check src tests    # 代码检查
```

### 项目结构

```text
src/lyxamour_mcp/
├── core/           # 核心服务器实现
├── transport/      # 传输层（stdio, sse, http_stream）
├── config/         # 配置系统
├── tools/          # 工具系统
├── resources/      # 资源管理
├── prompts/        # 提示词管理
├── knowledge/      # 知识库
├── web/            # Web 界面
├── utils/          # 工具函数
└── cli/            # 命令行接口
```

## 技术栈

- **语言**: Python 3.11+
- **MCP 框架**: FastMCP
- **数据验证**: Pydantic v2
- **Web 框架**: FastAPI
- **数据库**: SQLite + FTS5
- **日志**: structlog
- **CLI**: Typer + Rich

## 许可证

MIT License

## 作者

LyxAmour <lyxamour@example.com>
