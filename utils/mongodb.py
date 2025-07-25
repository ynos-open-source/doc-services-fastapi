from fastapi import Depends
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorCollection,
)
from .config import load_config
from .performance_monitor import PerformanceMonitor
from typing import Dict, Literal, overload

# --------------------------
# 数据库连接管理
# --------------------------


class MongodbDatabaseManager:
    def __init__(self):
        self.mongo_clients: Dict[str, AsyncIOMotorDatabase] = {}
        self.config = load_config()
        self._available_dbs = (
            list(self.config.mongodb.keys()) if self.config.mongodb else []
        )

    async def initialize(self):
        """
        初始化所有数据库连接池
        Args:
            mongodb:
                log:
                    host: mongodb-server
                    port: 27017
                    database: log
                    username: log_user
                    password: <PASSWORD>
                    poolsize: 10
        """
        monitor = PerformanceMonitor()

        # 初始化 MongoDB 连接
        if self.config.mongodb:
            for db_name, cfg in self.config.mongodb.items():
                monitor.start(f"创建 mongodb 连接 {db_name}")
                uri = f"mongodb://{cfg.username}:{cfg.password}@{cfg.host}:{cfg.port}"
                self.mongo_clients[db_name] = AsyncIOMotorClient(
                    uri, maxPoolSize=cfg.poolsize
                ).get_database(cfg.database)
                monitor.start(f"创建 mongodb 连接 {db_name}")

        monitor.log_metrics()

    async def shutdown(self):
        # 关闭 MongoDB 连接
        for client in self.mongo_clients.values():
            client.client.close()

    @overload
    def get_collection(
        self, db_name: Literal["ynos_db"], collection_name: str
    ) -> AsyncIOMotorCollection: ...

    def get_collection(
        self, db_name: str, collection_name: str
    ) -> AsyncIOMotorCollection:
        """获取集合对象（带自动补全）"""
        if db_name not in self._available_dbs:
            raise ValueError(f"无效数据库名称，可用数据库：{self._available_dbs}")
        return self.mongo_clients[db_name][collection_name]


# --------------------------
# 依赖注入（带智能提示）
# --------------------------


class CollectionDependency:
    def __init__(self, db_name: str, collection_name: str):
        self.db_name = db_name
        self.collection_name = collection_name

    def __call__(self):
        return mongodb_manager.get_collection(self.db_name, self.collection_name)


class DBCollections:
    """数据库集合快速访问器"""

    @property
    def logs_db(self) -> AsyncIOMotorCollection:
        """日志集合（输入提示会显示这个文档）"""
        return Depends(CollectionDependency("ynos_db", "logs_db"))


# 单例数据库管理器
mongodb_manager = MongodbDatabaseManager()
mongodb_dbs = DBCollections()

# 使用示例
"""
async def example_route(users_collection: AsyncIOMotorCollection = mongodb_dbs.ynos_users):
    # 输入 users_collection. 后会有完整的Motor方法提示
    data = await users_collection.find_one({...})
"""
