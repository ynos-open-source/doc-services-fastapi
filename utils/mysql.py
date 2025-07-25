from fastapi import HTTPException
from .database.core import AsyncConnectionWrapper, mysql_manager
from .base_query import get_user_organizations
from .performance_monitor import PerformanceMonitor
from .log import logger
from typing import Optional, Union, List, Any

# --------------------------
# 使用示例
# --------------------------
"""
from aiomysql import Connection

@app.get("/users")
async def read_users(conn: Connection = mysql_dbs.system_db):
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, name FROM users")
        return await cur.fetchall()
"""


class AsyncExecutor:
    def __init__(self, db_name: str = "system_db", monitor: PerformanceMonitor = None):
        """
        异步数据库操作执行器

        :param db_name: 数据库名称（对应mysql_pools的key）
        :param monitor: 性能监控实例
        """
        self.db_name = db_name
        self.monitor = monitor

    async def _execute(
        self,
        sql: str,
        params: tuple = (),
        operation_type: str = "query",
        fetch_method: str = "all",
    ) -> tuple:
        """
        执行SQL的核心方法（修复事务启动问题）
        """
        pool = mysql_manager.mysql_pools.get(self.db_name)
        if not pool:
            raise ValueError(f"数据库连接池 '{self.db_name}' 不存在")

        conn = None
        cursor = None
        try:
            async with pool.acquire() as raw_conn:
                conn = AsyncConnectionWrapper(raw_conn)
                await conn.begin()

                async with conn.cursor() as cursor:
                    logger.debug(
                        f"🚀 执行 {operation_type} 操作\nSQL: {sql}\nParams: {params}"
                    )
                    if self.monitor:
                        self.monitor.start(f"DB_{operation_type.upper()}")

                    await cursor.execute(sql, params)

                    # 处理不同操作类型的结果
                    if operation_type in ("update", "delete", "insert"):
                        result = cursor.rowcount
                        await conn.commit()
                    else:
                        if fetch_method == "one":
                            result = await cursor.fetchone()
                        else:
                            result = await cursor.fetchall()
                        # 查询操作自动提交（根据MySQL的autocommit模式）

                    if self.monitor:
                        self.monitor.end(f"DB_{operation_type.upper()}")
                    logger.info(f"✅ {operation_type} 操作成功")
                    return True, result

        except Exception as e:
            if conn:
                await conn.rollback()
            logger.error(f"❌ 数据库操作失败: {str(e)}", exc_info=True)
            return False, str(e)

    # ------------ 查询操作 ------------
    async def fetch_total(self, count_sql: str, params: tuple = ()) -> int:
        """获取总数统计"""
        success, result = await self._execute(count_sql, params, "query-total", "one")
        return result if success else 0

    async def fetch_one(self, query_sql: str, params: tuple = ()) -> Optional[dict]:
        """获取单条记录"""
        success, result = await self._execute(query_sql, params, "query-one", "one")
        return result if success else None

    async def fetch_all(self, query_sql: str, params: tuple = ()) -> list:
        """获取全部记录"""
        success, result = await self._execute(query_sql, params, "query-list", "all")
        return result if success else []

    # ------------ 写操作 ------------
    async def update(self, update_sql: str, params: tuple = ()) -> int:
        """
        执行更新操作

        :param update_sql: 更新SQL
        :param params: 参数列表
        :return: 影响的行数
        """
        success, result = await self._execute(update_sql, params, "update")
        return result if success else 0

    async def delete(
        self,
        table: str,
        ids: Union[List[int], List[str]],
        current_org_id: Optional[int] = None,
        *,
        physical: bool = False,
        id_field: str = "id",
        org_field: str = "org_id",
        delete_field: str = "is_delete",
        delete_value: Any = 1,
    ) -> int:
        """
        带机构权限校验的批量删除

        :param table: 操作的表名
        :param ids: 要删除的ID列表
        :param current_org_id: 当前用户所属机构ID
        :param physical: 是否物理删除
        :param id_field: 主键字段名（默认id）
        :param org_field: 机构字段名（默认org_id）
        :param delete_field: 逻辑删除字段（默认is_delete）
        :param delete_value: 逻辑删除值（默认1）
        :return: 实际删除行数
        :raises HTTPException: 当权限校验不通过时抛出
        """
        if not ids:
            return 0

        if current_org_id is not None:
            # 获取权限机构集合
            try:
                allowed_orgs = await get_user_organizations(current_org_id)
            except Exception as e:
                logger.error(f"机构权限查询失败: {str(e)}")
                raise HTTPException(status_code=401, detail="机构权限验证失败") from e

            if not allowed_orgs:
                raise HTTPException(status_code=401, detail="无机构访问权限")

        # 构建SQL参数
        id_placeholders = ", ".join(["%s"] * len(ids))

        # 参数顺序：delete_value(如果是逻辑删除) + ids + allowed_orgs
        params = tuple(ids)

        if current_org_id is not None:
            params += tuple(allowed_orgs)
            org_placeholders = ", ".join(["%s"] * len(allowed_orgs))

        if physical:
            sql = f"""
            DELETE FROM {table}
            WHERE {id_field} IN ({id_placeholders})
            """
        else:
            sql = f"""
            UPDATE {table}
            SET {delete_field} = %s
            WHERE {id_field} IN ({id_placeholders})
            """
            params = (delete_value,) + params

        if current_org_id is not None:
            sql += f"""AND {org_field} IN ({org_placeholders})"""

        # 执行SQL
        success, affected_rows = await self._execute(
            sql, params, "delete" if physical else "update"
        )

        if not success:
            raise RuntimeError("删除操作执行失败")

        # 验证实际删除数量
        if affected_rows != len(ids):
            missing_count = len(ids) - affected_rows
            logger.warning(
                f"权限校验未通过: 预期删除{len(ids)}条，"
                f"实际删除{affected_rows}条，"
                f"{missing_count}条数据无权限或不存在"
            )
            raise HTTPException(
                status_code=401, detail=f"无权限删除{missing_count}条数据"
            )

        return affected_rows

    async def insert(self, insert_sql: str, params: tuple = ()) -> int:
        """
        执行插入操作

        :param insert_sql: 插入SQL
        :param params: 参数列表
        :return: 插入的主键ID（需SQL返回LAST_INSERT_ID()）
        """
        success, result = await self._execute(insert_sql, params, "insert")
        return result if success else 0

    # ------------ 批量操作 ------------
    async def batch_operation(
        self, sql: str, params_list: list, operation_type: str
    ) -> int:
        """
        通用批量操作

        :param sql: 带占位符的SQL语句
        :param params_list: 参数列表
        :param operation_type: 操作类型（insert/update/delete）
        :return: 总影响行数
        """
        total = 0
        for params in params_list:
            success, result = await self._execute(sql, params, operation_type)
            if success:
                total += result
        return total

    async def transaction(self, operations: list) -> bool:
        """
        事务执行多个操作

        :param operations: 操作列表 [
            ("update", "UPDATE...", (params)),
            ("insert", "INSERT...", (params)),
            ("delete", "DELETE...", (params))
        ]
        :return: 是否全部成功
        """
        try:
            pool = mysql_manager.mysql_pools[self.db_name]
            async with pool.acquire() as raw_conn:
                conn = AsyncConnectionWrapper(raw_conn)
                await conn.begin()

                for op_type, sql, params in operations:
                    async with conn.cursor() as cur:
                        await cur.execute(sql, params)
                        # 如果是写操作，记录影响行数
                        if op_type in ("update", "delete", "insert"):
                            logger.debug(f"影响行数: {cur.rowcount}")

                await conn.commit()
                return True
        except Exception as e:
            await conn.rollback()
            logger.error(f"事务执行失败: {str(e)}")
            return False
