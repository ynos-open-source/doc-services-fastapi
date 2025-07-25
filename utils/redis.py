from redis.asyncio import Redis, ConnectionPool
from .config import load_config
from fastapi import Depends
from typing import Dict


class RedisManager:
    def __init__(self):
        self.pools: Dict[str, ConnectionPool] = {}
        self.config = load_config().redis
        self._default_pool_name = "default"  # 添加默认连接池名称

    async def initialize(self):
        """初始化所有Redis连接池
        Args:
            redis:
                default:
                    host: redis_server
                    port: 6379
                    db: 0
                    password: redis_pass
        """
        for name, cfg in self.config.items():
            self.pools[name] = ConnectionPool(
                host=cfg.host,
                port=cfg.port,
                db=cfg.db,
                password=cfg.password,
                decode_responses=True,  # 自动解码为字符串
                max_connections=cfg.maxsize,
                socket_connect_timeout=5,  # 连接超时5秒
            )

    async def shutdown(self):
        """关闭所有连接池"""
        for pool in self.pools.values():
            await pool.disconnect()

    def get_redis(self, name: str) -> Redis:
        """获取Redis客户端实例"""
        pool_name = name or self._default_pool_name
        return Redis(connection_pool=self.pools[pool_name])

    async def get_redis_conn(self, name: str = None):
        """获取Redis连接上下文管理器"""
        pool_name = name or self._default_pool_name
        async with self.get_redis(pool_name) as conn:
            yield conn


# --------------------------
# 依赖注入（带智能提示）
# --------------------------


class RedisDependency:
    def __init__(self, db_name: str):
        self.db_name = db_name

    def __call__(self):
        return redis_manager.get_redis(self.db_name)


class RedisClients:
    """数据库集合快速访问器"""

    @property
    def default(self) -> Redis:
        return redis_manager.get_redis("default")

    @property
    def business(self) -> Redis:
        return redis_manager.get_redis("business")


# 初始化管理器
redis_manager = RedisManager()
redis_dbs = RedisClients()

# 使用示例
"""
async def example_route(
    redis_default: Redis = redis_dbs.default,
    redis_business: Redis = redis_dbs.business
):
    await redis_default.set("key", "value")
    await redis_business.expire("temp_key", 60)
"""


def get_redis(name: str) -> Redis:  # type: ignore
    """依赖注入工厂函数
    Args:
        name: 连接池名称
    Returns:
        Redis客户端实例
    """

    async def _get_redis():
        async with redis_manager.get_redis(name) as client:
            yield client

    return Depends(_get_redis)
