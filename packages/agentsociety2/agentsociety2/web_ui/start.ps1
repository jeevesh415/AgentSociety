#!/usr/bin/env pwsh
# AgentSociety Chainlit Web UI 启动脚本
# 使用官方 Chainlit 包 (pip install chainlit)

Write-Host "🎭 AgentSociety Chainlit Web UI" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = $PSScriptRoot
Write-Host "📍 当前目录: $ScriptDir" -ForegroundColor Yellow

# 检查 chainlit 是否已安装
try {
    python -c "import chainlit" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Chainlit not found"
    }
    Write-Host "✅ Chainlit 已安装" -ForegroundColor Green
}
catch {
    Write-Host "❌ 错误: 未找到 chainlit 包" -ForegroundColor Red
    Write-Host "   请先运行: pip install chainlit" -ForegroundColor Yellow
    exit 1
}

# 检查是否在正确的目录
if (-not (Test-Path "app.py")) {
    Write-Host "❌ 无法启动: 未在当前目录找到 app.py。" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🚀 启动本地 Chainlit 服务器..." -ForegroundColor Green
Write-Host "   URL: http://localhost:8000" -ForegroundColor Cyan
Write-Host "   按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host ""

# 使用 python -m chainlit 启动，这会使用 PYTHONPATH 中的 chainlit
python -m chainlit run app.py -w --host 0.0.0.0 --port 8000
