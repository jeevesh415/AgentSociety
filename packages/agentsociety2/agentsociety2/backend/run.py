#!/usr/bin/env python
"""启动后端服务的便捷脚本"""

if __name__ == "__main__":
    import uvicorn
    import os
    import argparse
    from dotenv import load_dotenv
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="启动 AI Social Scientist Backend API 服务")
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="设置日志等级 (critical, error, warning, info, debug, trace)",
    )
    args = parser.parse_args()
    
    # 加载环境变量文件
    load_dotenv()
    
    # 从环境变量读取配置，命令行参数优先
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8001"))
    log_level = args.log_level or os.getenv("BACKEND_LOG_LEVEL", "info")
    
    # 如果命令行参数设置了日志等级，更新环境变量以便 app.py 使用
    if args.log_level:
        os.environ["BACKEND_LOG_LEVEL"] = args.log_level
    
    print("启动 AI Social Scientist Backend API 服务...")
    print(f"服务地址: http://{host}:{port}")
    print(f"API文档: http://{host}:{port}/docs")
    print(f"健康检查: http://{host}:{port}/health")
    print(f"日志等级: {log_level}")
    print("-" * 60)
    
    uvicorn.run(
        "agentsociety2.backend.app:app",
        host=host,
        port=port,
        reload=False,
        log_level=log_level,
    )

