"""FastAPI backend service for AI Social Scientist VSCode extension"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from pathlib import Path

from agentsociety2.backend.routers import chat, mineru, literature, workspace, modules, prefill_params, experiments, replay, custom

# 加载环境变量
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")


# 配置标准 logging
def _setup_logging():
    """配置应用日志"""
    log_level = os.getenv("BACKEND_LOG_LEVEL", "info")
    # 将 uvicorn 的 "trace" 映射到 Python logging 的 "DEBUG"
    python_log_level = "DEBUG" if log_level.lower() == "trace" else log_level.upper()
    level = getattr(logging, python_log_level, logging.INFO)

    # 配置根 logger（如果还没有配置过）
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            force=True,  # Python 3.8+ 支持，强制重新配置
        )
    else:
        # 如果已经配置过，只更新日志等级
        root_logger.setLevel(level)

    # 设置 agentsociety2 相关模块的日志等级
    agentsociety_logger = logging.getLogger("agentsociety2")
    agentsociety_logger.setLevel(level)

    return agentsociety_logger


_setup_logging()
from agentsociety2.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("AI Social Scientist Backend Service 启动中...")
    logger.info(f"项目根目录: {_project_root}")

    # 初始化工具注册表
    from agentsociety2.backend.tools.registry import get_registry

    registry = get_registry()
    logger.info(f"已注册 {len(registry.get_all_tools())} 个工具")

    yield

    # 关闭时执行
    logger.info("AI Social Scientist Backend Service 关闭中...")


# 创建FastAPI应用
app = FastAPI(
    title="AI Social Scientist Backend API",
    description="Backend API service for AI Social Scientist VSCode extension with function calling support",
    version="2.0.0",
    lifespan=lifespan,
)

# 配置CORS（允许VSCode插件跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router)
app.include_router(mineru.router)
app.include_router(literature.router)
app.include_router(workspace.router)
app.include_router(modules.router)
app.include_router(prefill_params.router)
app.include_router(experiments.router, prefix="/api/v1")
app.include_router(replay.router, prefix="/api/v1")
app.include_router(custom.router)


@app.get("/")
async def root():
    """根路径，返回API信息"""
    from agentsociety2.backend.tools.registry import get_registry

    registry = get_registry()
    tools = list(registry.get_all_tools().keys())

    return {
        "service": "AI Social Scientist Backend API",
        "version": "2.0.0",
        "status": "running",
        "architecture": "function_calling",
        "endpoints": {
            "chat": "/api/v1/chat/completion",
            "tools": "/api/v1/chat/tools",
            "mineru": "/api/v1/mineru/parse",
            "literature": "/api/v1/literature",
            "workspace": "/api/v1/workspace",
            "experiments": "/api/v1/experiments/{hypothesis_id}/{experiment_id}",
            "replay": "/api/v1/replay/{hypothesis_id}/{experiment_id}/*",
        },
        "available_tools": tools,
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "detail": str(exc),
        },
    )


if __name__ == "__main__":
    import uvicorn
    import argparse

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="启动 AI Social Scientist Backend API 服务"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="设置日志等级 (critical, error, warning, info, debug, trace)",
    )
    args = parser.parse_args()

    # 从环境变量读取配置，命令行参数优先
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8001"))
    log_level = args.log_level or os.getenv("BACKEND_LOG_LEVEL", "info")

    # 如果命令行参数设置了日志等级，更新环境变量并重新配置日志
    if args.log_level:
        os.environ["BACKEND_LOG_LEVEL"] = args.log_level
        _setup_logging()

    logger.info(f"启动服务器: http://{host}:{port}")
    logger.info(f"日志等级: {log_level}")
    uvicorn.run(
        "agentsociety2.backend.app:app",
        host=host,
        port=port,
        reload=False,  # 生产环境设为False
        log_level=log_level,
    )
