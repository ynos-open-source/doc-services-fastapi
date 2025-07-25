from fastapi import FastAPI
from contextlib import asynccontextmanager
from utils import (
    mysql_manager,
    mongodb_manager,
    redis_manager,
    register_exception_handlers,
    load_config,
    logger,
    minio_manager,
)
import sys
from routers import router

# 初始化配置
settings = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # ========== 新增配置加载逻辑 ==========
        load_config()
        logger.info("✅ 配置文件加载成功!")
        # ====================================

        # 开始创建数据库连接
        logger.info("⌛️ 开始创建数据库连接...")
        # 初始化数据库连接池
        await mysql_manager.initialize()
        await mongodb_manager.initialize()
        await redis_manager.initialize()
        minio_manager.initialize()
        logger.info("✅ 数据库连接创建成功!")

    except Exception as e:
        logger.info("\n❌ 应用启动失败!")
        logger.info(f"错误信息: {str(e)}")
        sys.exit(1)  # 退出应用
    yield
    print("\n")
    logger.info("⌛️ 关闭数据库连接...")
    await mysql_manager.shutdown()
    await mongodb_manager.shutdown()
    await redis_manager.shutdown()
    logger.info("✅ 数据库连接关闭成功!")
    logger.info("✅ 应用已正常退出!")
    print("\n")


def configure_app(app: FastAPI):
    """应用配置组装"""
    # 注册路由
    app.include_router(router, prefix=settings.app.prefix)

    # 注册异常处理器
    register_exception_handlers(app)


app = FastAPI(
    lifespan=lifespan,
    title=settings.app.title,
    description=settings.app.description,
    version=settings.app.version,
    docs_url=f"{settings.app.prefix}/docs",
    openapi_url=f"{settings.app.prefix}/openapi.json",  # 规范文件路径
    redoc_url=f"{settings.app.prefix}/redoc",  # ReDoc 路径
)
configure_app(app)


def run_server():
    """运行服务入口"""
    import multiprocessing
    import uvicorn

    # 动态计算工作进程数
    cpu_cores = multiprocessing.cpu_count()
    workers = int(cpu_cores / 2) if settings.app.production() else 1

    # 因为windows不支持uvloop，所以这里使用默认的asyncio事件循环
    LOOP = "asyncio" if sys.platform == "win32" else "uvloop"

    logger.info(f"🏃 启动服务进程 (workers={workers})")
    uvicorn.run(
        app="main:app",  # 应用入口
        host=settings.app.host,
        port=settings.app.port,
        workers=workers,  # 动态进程数
        loop=LOOP,  # 高性能事件循环
        http="httptools",  # 优化HTTP解析器
        timeout_keep_alive=30,  # 连接保活时间（秒）
        limit_concurrency=1000,  # 最大并发连接数
        log_level="info" if settings.app.production() else "debug",
        reload=not settings.app.production(),  # 开发环境热重载
        access_log=not settings.app.production(),  # 生产环境关闭访问日志
    )


if __name__ == "__main__":
    """主程序入口"""
    run_server()
