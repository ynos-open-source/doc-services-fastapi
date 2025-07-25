import datetime
from fastapi import Depends
from ..utils import format_datetime, snake_to_camel, logger
from contextlib import asynccontextmanager
from aiomysql import (
    Connection as AiomysqlConnection,
    Cursor as AiomysqlCursor,
    create_pool,
    Pool,
)
from typing import Optional, Union, List, Dict, Any, AsyncGenerator
from ..config import load_config
from ..performance_monitor import PerformanceMonitor

# --------------------------
# 数据库连接管理
# --------------------------


class CursorWrapper:
    """封装 aiomysql.Cursor 并提供类型提示"""

    def __init__(self, cursor: AiomysqlCursor):
        self._cursor = cursor

    async def __aenter__(self):
        await self._cursor.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cursor.__aexit__(exc_type, exc_val, exc_tb)

    async def execute(self, query: str, args: Union[tuple, dict, None] = None) -> None:
        await self._cursor.execute(query, args)

    async def executemany(self, query: str, args: List[Union[tuple, dict]]) -> None:
        await self._cursor.executemany(query, args)

    async def fetchone(self) -> Optional[Dict[str, Any]]:
        row = await self._cursor.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in self._cursor.description]
        return dict(zip(columns, row))

    async def fetchmany(self, size: int = None) -> List[Dict[str, Any]]:
        rows = await self._cursor.fetchmany(size)
        columns = [col[0] for col in self._cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def fetchall(self) -> List[Dict[str, Any]]:
        rows = await self._cursor.fetchall()
        columns = [col[0] for col in self._cursor.description]

        select_list = []
        for row in rows:
            # 将行数据与字段名组合成字典
            raw_data = dict(zip(columns, row))
            camel_data = {}
            for key, value in raw_data.items():
                # 日期字段格式化
                if isinstance(value, datetime.datetime):
                    value = format_datetime(value)
                camel_key = snake_to_camel(key)
                camel_data[camel_key] = value
            select_list.append(camel_data)

        return select_list

    async def fetchone(self) -> Dict[str, Any]:
        row = await self._cursor.fetchone()
        if row is None:
            return None
        columns = [col[0] for col in self._cursor.description]

        # 将行数据与字段名组合成字典
        raw_data = dict(zip(columns, row))

        # 直接处理 COUNT(*) 场景
        if "COUNT(*)" in raw_data:
            return raw_data["COUNT(*)"]

        camel_data = {}
        for key, value in raw_data.items():
            # 日期字段格式化
            if isinstance(value, datetime.datetime):
                value = format_datetime(value)
            camel_key = snake_to_camel(key)
            camel_data[camel_key] = value

        return camel_data

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    @property
    def lastrowid(self) -> int:
        """获取最后插入行的自增ID"""
        return self._cursor.lastrowid


class AsyncConnectionWrapper:
    """封装 aiomysql.Connection 并返回包装后的游标"""

    def __init__(self, conn: AiomysqlConnection):
        self._conn = conn

    @asynccontextmanager
    async def cursor(self) -> AsyncGenerator[CursorWrapper, None]:
        async with self._conn.cursor() as raw_cursor:  # 正确进入游标上下文
            yield CursorWrapper(raw_cursor)  # 包装真实游标实例

    async def commit(self):
        await self._conn.commit()

    async def begin(self):
        await self._conn.begin()

    async def rollback(self):
        await self._conn.rollback()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._conn.close()

    def __getattr__(self, name: str):
        """代理其他属性和方法到原始连接"""
        return getattr(self._conn, name)


class MysqlDatabaseManager:
    def __init__(self):
        self.mysql_pools: Dict[str, Pool] = {}
        self.config = load_config()
        self._available_dbs = (
            list(self.config.mysql.keys()) if self.config.mysql else []
        )

    async def initialize(self):
        """
        初始化所有数据库连接池
        Args:
            mysql:
                db1:
                    host: localhost
                    port: 3306
                    user: root
                    password: 123456
                    database: auth_system
                    minsize: 5
                    maxsize: 10
        """
        monitor = PerformanceMonitor()

        # 初始化 MySQL 连接池
        if self.config.mysql:
            for db_name, config in self.config.mysql.items():
                monitor.start(f"创建 mysql 连接池 {db_name}")
                self.mysql_pools[db_name] = await create_pool(
                    host=config.host,
                    port=config.port,
                    user=config.user,
                    password=config.password,
                    db=config.database,
                    minsize=config.maxsize if config.minsize else 5,
                    maxsize=config.maxsize if config.maxsize else 10,
                    autocommit=False,
                    pool_recycle=300,
                )
                monitor.end(f"创建 mysql 连接池 {db_name}")

        monitor.log_metrics()

    async def shutdown(self):
        """关闭所有数据库连接"""
        # 关闭 MySQL 连接池
        for pool in self.mysql_pools.values():
            pool.close()
            await pool.wait_closed()


# --------------------------
# 依赖注入（带智能提示）
# --------------------------


class MysqlConnectionDependency:
    """按名称注入 aiomysql.Connection"""

    def __init__(self, db_name: str):
        if db_name not in mysql_manager._available_dbs:
            logger.warning(f"无效数据库名称：{db_name}")
            # raise ValueError(
            #     f"无效数据库名称，可用数据库：{mysql_manager._available_dbs}"
            # )
        self.db_name = db_name

    async def __call__(self) -> AsyncConnectionWrapper:  # type: ignore
        if self.db_name not in mysql_manager.mysql_pools:
            raise ValueError(f"数据库 {self.db_name} 未初始化")
        async with mysql_manager.mysql_pools[self.db_name].acquire() as conn:
            wrapped_conn = AsyncConnectionWrapper(conn)
            yield wrapped_conn


class DBConnections:
    """数据库连接快速访问器"""

    # 如果你的 config.mysql 中有多个 key（如 "db1", "analytics", "reports"），
    # 请为每个都加一个属性。以下以 "db1" 为示例：

    @property
    def system_db(self) -> AsyncConnectionWrapper:
        """auth_system 数据库连接"""
        return Depends(MysqlConnectionDependency("system_db"))

    @property
    def doc_db(self) -> AsyncConnectionWrapper:
        """doc_db 数据库连接"""
        return Depends(MysqlConnectionDependency("doc_db"))

    @property
    def wiki_db(self) -> AsyncConnectionWrapper:
        """wiki_db 数据库连接"""
        return Depends(MysqlConnectionDependency("wiki_db"))
    
    @property
    def config_db(self) -> AsyncConnectionWrapper:
        """config_db 数据库连接"""
        return Depends(MysqlConnectionDependency("config_db"))
    

# 单例数据库管理器
mysql_manager = MysqlDatabaseManager()

# 单例连接访问器
mysql_dbs = DBConnections()
