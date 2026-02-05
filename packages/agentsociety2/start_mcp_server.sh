#!/bin/bash
# 启动 MCP Server 的便捷脚本

cd "$(dirname "$0")"

# 激活虚拟环境（如果存在）
if [ -f "../../.venv/bin/activate" ]; then
    source ../../.venv/bin/activate
fi

# 设置 PYTHONPATH
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 运行 MCP server（默认端口 8001，避免与 8000 冲突）
# 可以通过 --port 参数覆盖
if [[ "$*" != *"--port"* ]]; then
    python -m agentsociety2.mcp.server --port 8001 "$@"
else
    python -m agentsociety2.mcp.server "$@"
fi

