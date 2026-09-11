"""
NewsFlow 项目入口模块
创建 FastAPI 应用实例，注册路由，启动服务

使用方式：
1. 开发模式运行：python main.py
2. 命令行运行：uvicorn main:app --host 0.0.0.0 --port 23119 --reload
"""

import sys
import logging

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from collector.services import router as collect_router
from pusher.services import router as pusher_router
from processor.services import router as processor_router
from config import settings

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """将应用日志分流到 stdout/stderr，由启动脚本统一管理文件。"""

    class MaxLevelFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return record.levelno < logging.WARNING

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S%z",
    )
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(MaxLevelFilter())
    stdout_handler.setFormatter(formatter)
    stdout_handler._newsflow_handler = True

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)
    stderr_handler._newsflow_handler = True

    for logger_name in ("collector", "processor", "pusher", "main"):
        app_logger = logging.getLogger(logger_name)
        app_logger.setLevel(logging.INFO)
        app_logger.propagate = False
        if not any(
            getattr(item, "_newsflow_handler", False) for item in app_logger.handlers
        ):
            app_logger.addHandler(stdout_handler)
            app_logger.addHandler(stderr_handler)


configure_logging()


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例

    作用：初始化应用，注册所有路由

    返回：
    FastAPI: 配置完成的 FastAPI 应用实例
    """
    app = FastAPI(
        title="NewsFlow 信息工作流服务",
        description="多源新闻数据采集系统和推送系统",
        version="1.0.0",
    )

    # 注册采集服务路由
    app.include_router(collect_router)
    # 注册推送服务路由
    app.include_router(pusher_router)
    # 注册处理器服务路由
    app.include_router(processor_router)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        logger.error(
            "request stage=validation status=failed method=%s path=%s error=%s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "request stage=handler status=failed method=%s path=%s",
            request.method,
            request.url.path,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # 开发模式启动服务
    # 默认监听地址和端口从配置读取
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # 开发模式开启热重载
        loop="none",
    )
