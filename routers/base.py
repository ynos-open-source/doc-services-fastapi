from fastapi import APIRouter
from utils import mysql_manager, mongodb_manager, redis_manager

router = APIRouter()


@router.get("/database-status", summary="数据库状态")
async def db_status():
    return {
        "mysql": {
            name: {"size": pool.size, "used": pool.size - pool.freesize}
            for name, pool in mysql_manager.mysql_pools.items()
        },
        "mongodb": list(mongodb_manager.mongo_clients.keys()),
    }


@router.get("/redis-status", summary="Redis状态")
async def redis_status():
    return {
        name: {
            "available": pool._available_connections,
            "in_use": pool._in_use_connections,
        }
        for name, pool in redis_manager.pools.items()
    }


@router.get("/health-redis", summary="Redis健康检查")
async def redis_health_check():
    try:
        for name in redis_manager.pools:
            client = redis_manager.get_redis(name)
            await client.ping()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
