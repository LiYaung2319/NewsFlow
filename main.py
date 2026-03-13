"""
NewsFlow 项目入口模块
创建 FastAPI 应用实例，注册路由，启动服务

使用方式：
1. 开发模式运行：python main.py
2. 命令行运行：uvicorn main:app --host 0.0.0.0 --port 23119 --reload
"""

import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from collector.services import router as collect_router
from config import settings


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例

    作用：初始化应用，注册所有路由

    返回：
    FastAPI: 配置完成的 FastAPI 应用实例
    """
    app = FastAPI(
        title="NewsFlow 新闻采集服务",
        description="多源新闻数据采集系统，支持新浪、网易、腾讯等新闻源",
        version="1.0.0",
    )

    # 注册采集服务路由
    app.include_router(collect_router)

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # 开发模式启动服务
    # 默认监听地址和端口从配置读取
    uvicorn.run(
        "main:app",
        host=settings.collector_host,
        port=settings.collector_port,
        reload=True,  # 开发模式开启热重载
        loop="none",
    )
