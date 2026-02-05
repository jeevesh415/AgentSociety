#!/usr/bin/env bash

# AgentSociety Web UI 启动脚本 (Linux/macOS)
# 使用官方 Chainlit 包 (pip install chainlit)

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查 Python 版本
check_python() {
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    else
        print_error "未找到 Python！请安装 Python 3.12 或更高版本"
        exit 1
    fi

    # 检查 Python 版本
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    print_info "检测到 Python 版本: $PYTHON_VERSION"
}

# 检查 chainlit
check_chainlit() {
    if ! $PYTHON_CMD -c "import chainlit" 2>/dev/null; then
        print_error "未找到 chainlit 包"
        print_info "请先运行: pip install chainlit"
        exit 1
    fi
    print_success "Chainlit 已安装"
}

# 主逻辑
main() {
    print_info "============================================"
    print_info "  AgentSociety Web UI 启动脚本 (Linux/macOS)"
    print_info "============================================"
    echo

    # 检查 Python
    check_python
    
    # 检查 chainlit
    check_chainlit
    echo

    # 启动服务器
    print_info "正在启动 Chainlit 服务器..."
    print_info "服务地址: http://localhost:8000"
    print_info "按 Ctrl+C 停止服务器"
    echo
    print_info "============================================"
    echo

    # 运行 Chainlit
    $PYTHON_CMD -m chainlit run app.py -w --host 0.0.0.0 --port 8000
}

# 执行主函数
main
