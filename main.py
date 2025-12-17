#!/usr/bin/env python3
"""
lyxamour-mcp 主入口脚本

这个脚本允许直接从项目根目录运行工具，无需安装：
    python main.py start
    python main.py version
"""

import sys
from pathlib import Path

# 将 src 目录添加到 Python 路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 导入并运行 CLI
from lyxamour_mcp.cli.main import app

if __name__ == "__main__":
    app()
