.PHONY: help install install-dev uninstall test lint format clean run build

# 默认目标
help:
	@echo "lyxamour-mcp 开发和安装命令"
	@echo ""
	@echo "安装命令:"
	@echo "  make install        - 安装到系统（使用 uv pip install）"
	@echo "  make install-dev    - 开发模式安装（可编辑模式）"
	@echo "  make uninstall      - 卸载工具"
	@echo ""
	@echo "开发命令:"
	@echo "  make dev            - 同步开发依赖"
	@echo "  make run            - 运行工具（stdio 模式）"
	@echo "  make run-main       - 通过 main.py 运行"
	@echo "  make test           - 运行测试"
	@echo "  make lint           - 代码检查（ruff + mypy）"
	@echo "  make format         - 代码格式化（black + isort）"
	@echo ""
	@echo "构建命令:"
	@echo "  make build          - 构建发布包"
	@echo "  make clean          - 清理构建产物"
	@echo ""
	@echo "直接运行（无需安装）:"
	@echo "  uv run lyxamour-mcp start"

# 安装到系统
install:
	@echo "正在安装 lyxamour-mcp 到系统..."
	uv pip install .
	@echo "✅ 安装完成！使用 'lyxamour-mcp --help' 查看帮助"

# 开发模式安装（可编辑）
install-dev:
	@echo "正在以开发模式安装 lyxamour-mcp..."
	uv pip install -e .
	@echo "✅ 开发模式安装完成！代码修改会立即生效"

# 卸载
uninstall:
	@echo "正在卸载 lyxamour-mcp..."
	uv pip uninstall lyxamour-mcp -y
	@echo "✅ 卸载完成"

# 同步开发依赖
dev:
	@echo "正在同步开发依赖..."
	uv sync --all-extras
	@echo "✅ 依赖同步完成"

# 运行工具（使用 uv run）
run:
	@echo "启动 MCP 服务器（stdio 模式）..."
	uv run lyxamour-mcp start

# 直接运行 main.py
run-main:
	@echo "通过 main.py 启动服务器..."
	uv run python main.py start

# 运行测试
test:
	@echo "运行测试..."
	uv run pytest

# 代码检查
lint:
	@echo "运行代码检查..."
	@echo ">>> Ruff 检查..."
	uv run ruff check src tests
	@echo ">>> MyPy 类型检查..."
	uv run mypy src
	@echo "✅ 代码检查完成"

# 代码格式化
format:
	@echo "格式化代码..."
	@echo ">>> Black 格式化..."
	uv run black src tests
	@echo ">>> isort 导入排序..."
	uv run isort src tests
	@echo "✅ 格式化完成"

# 构建发布包
build:
	@echo "构建发布包..."
	uv build
	@echo "✅ 构建完成，输出在 dist/ 目录"

# 清理
clean:
	@echo "清理构建产物..."
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "✅ 清理完成"
