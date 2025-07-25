import json
import random
import re
from typing import Dict, List, Literal, Optional, Set, Tuple, Union
from fastapi import HTTPException
from pydantic import BaseModel
from redis.asyncio import RedisError
from .performance_monitor import PerformanceMonitor
from .schemas import BaseParamsModel, UserOut
from .utils import camel_to_snake
from .log import logger
from .redis import redis_dbs
from .database.core import AsyncConnectionWrapper, mysql_manager


def get_sorter_sql(body: BaseParamsModel, valid_columns_with_alias={}):
    """
    多表查询的动态 ORDER BY 生成器
    :param body: 请求参数，包含排序字段
    :param valid_columns_with_alias: 允许排序的字段及表别名映射，格式为 {"字段名": "表别名"}
    :return: 安全的 SQL ORDER BY 子句
    """
    ordering = []
    sorter = body.sorter if body.sorter else {}

    for camel_field, direction in sorter.items():
        snake_field = camel_to_snake(camel_field)
        qualified_field = None

        # 优先从映射表获取带别名的字段
        if snake_field in valid_columns_with_alias:
            table_alias = valid_columns_with_alias[snake_field]
            qualified_field = f"{table_alias}.{snake_field}"
        else:
            qualified_field = snake_field  # 直接使用原字段

        # 处理默认排序冲突（兼容带别名的字段）
        if snake_field == "create_time":
            # 移除所有包含 create_time 的字段（无论是否有别名）
            for field in list(ordering):
                if "create_time" in field:
                    ordering.remove(field)

        # 添加排序标记
        if direction == 1:
            ordering.append(qualified_field)
        elif direction == -1:
            ordering.append(f"-{qualified_field}")

    # 添加默认排序（使用别名，如果存在）
    if not any("create_time" in field for field in ordering):
        if "create_time" in valid_columns_with_alias:
            table_alias = valid_columns_with_alias["create_time"]
            default_field = f"{table_alias}.create_time"
        else:
            default_field = "create_time"
        ordering.append(f"-{default_field}")

    # 转换为 SQL 语法
    order_clauses = []
    for field in ordering:
        if field.startswith("-"):
            column = field[1:]
            order_clauses.append(f"{column} DESC")
        else:
            order_clauses.append(f"{field} ASC")

    return f"ORDER BY {', '.join(order_clauses)}" if order_clauses else ""


def is_valid_time_range(key, value):
    if "Time" in key and isinstance(value, list) and len(value) == 2:
        return True
    return False


async def get_filter_sql(
    base_sql: str,
    body: Union[Dict, BaseModel],
    keyword_fields=[],
    table_alias_map=None,
    precise_fields=[],
    allowed_org_ids: Optional[List[int]] | Literal[False] = None,
    current_user: UserOut = None,
):
    """
    生成完整的 SQL 语句及参数，智能追加 WHERE 条件

    :param base_sql: 基础SQL语句（可能包含WHERE子句）
    :param body: 请求参数字典
    :param keyword_fields: 需要进行关键字模糊查询的字段列表
    :param table_alias_map: 表别名映射字典
    :param precise_fields: 需要精确匹配的字段列表
    :param allowed_org_ids: 允许访问的机构ID列表（None表示不限制，空列表表示无权限）
    :param current_user: 当前用户信息
    :return: (complete_sql, params)
    """
    # 转换 Pydantic 模型为字典
    if isinstance(body, BaseModel):
        body = body.model_dump(exclude_unset=True)

    # 生成 WHERE 子句和参数
    where_clause, params = await _generate_where_clause(
        body,
        keyword_fields,
        table_alias_map,
        precise_fields,
        allowed_org_ids,
        current_user,
    )

    # 构建完整 SQL（关键修改点）
    if where_clause:
        # 检查是否已存在 WHERE 子句
        if re.search(r"\bWHERE\b", base_sql, re.IGNORECASE):
            # 已有 WHERE 子句：追加 AND 条件
            # 处理原始 WHERE 子句末尾可能存在的注释或换行
            base_sql = re.sub(r"(\s*)(--.*?)?$", "", base_sql, flags=re.IGNORECASE)
            complete_sql = f"{base_sql} AND {where_clause}"
        else:
            # 无 WHERE 子句：添加新 WHERE
            complete_sql = f"{base_sql} WHERE {where_clause}"
    else:
        complete_sql = base_sql

    return complete_sql, params


async def _generate_where_clause(
    body,
    keyword_fields,
    table_alias_map,
    precise_fields,
    allowed_org_ids,
    current_user: Optional[UserOut],
):
    """生成WHERE子句及参数"""
    conditions = []
    params = []
    table_alias_map = table_alias_map or {}

    # ========================== 1. 关键字查询处理 ==========================
    if "keywords" in body:
        keywords = body.get("keywords", "")
        if keywords and keyword_fields:
            keyword_conds = []
            for field in keyword_fields:
                field_snake = camel_to_snake(field)
                alias = table_alias_map.get(field_snake, "")
                field_name = f"{alias}.{field_snake}" if alias else field_snake
                keyword_conds.append(f"{field_name} LIKE %s")
                params.append(f"%{keywords}%")
            conditions.append(f"({' OR '.join(keyword_conds)})")

    # ========================== 2. 普通条件处理 ==========================
    for key, value in body.items():
        if key == "keywords":
            continue

        if value is None or value == [] or value == "":
            continue

        if is_valid_time_range(key, value):
            start, end = value
            key_snake = camel_to_snake(key)
            alias = table_alias_map.get(key_snake, "")
            field_name = f"{alias}.{key_snake}" if alias else key_snake
            conditions.append(f"{field_name} BETWEEN %s AND %s")
            params.extend([start, end])
        else:
            key_snake = camel_to_snake(key)
            alias = table_alias_map.get(key_snake, "")
            field_name = f"{alias}.{key_snake}" if alias else key_snake
            if key_snake in precise_fields:
                conditions.append(f"{field_name} = %s")
                params.append(value)
            else:
                conditions.append(f"{field_name} LIKE %s")
                params.append(f"%{value}%")

    # ========================== 3. 机构权限过滤 ==========================
    if not allowed_org_ids and allowed_org_ids != False and current_user:
        # 如果是超级管理员，允许访问所有机构
        if current_user.org_id != 0:
            allowed_org_ids = await get_user_organizations(current_user.org_id)

    if allowed_org_ids != False and allowed_org_ids is not None:
        org_id_field = "org_id"
        alias = table_alias_map.get(org_id_field, "")
        field_name = f"{alias}.{org_id_field}" if alias else org_id_field
        placeholders = ", ".join(["%s"] * len(allowed_org_ids))
        conditions.append(f"{field_name} IN ({placeholders})")
        params.extend(allowed_org_ids)

    return " AND ".join(conditions), params


async def delete_organizations_cache():
    """
    删除所有机构相关缓存（支持多匹配模式）
    """
    try:
        # 定义需要删除的缓存模式
        cache_patterns = ["auth_org_ids_*", "org_parent:*"]

        all_keys = set()

        # 遍历所有匹配模式收集键
        for pattern in cache_patterns:
            async for key in redis_dbs.default.scan_iter(pattern):
                all_keys.add(key.decode("utf-8"))  # 转换字节为字符串

        # 批量删除所有匹配键
        if all_keys:
            # 使用管道提升删除效率
            async with redis_dbs.default.pipeline(transaction=True) as pipe:
                for key in all_keys:
                    await pipe.delete(key)
                await pipe.execute()

            logger.info(f"已清除机构缓存，数量：{len(all_keys)}")
        else:
            logger.debug("未发现需要清除的机构缓存")

    except Exception as e:
        logger.error(f"清除机构缓存失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="机构缓存清除失败")


async def get_user_organizations(org_id: int) -> Set[int]:
    """
    获取用户所在机构及其所有子机构的ID集合 （所有子级）
    优化点：
    1. 使用SQL递归查询替代Python递归
    2. 改进缓存机制
    3. 防御性编程
    4. 性能优化
    """
    redis_key = f"auth_org_ids:{org_id}"

    # ========================== 1. 尝试从缓存获取 ==========================
    if cached := await redis_dbs.default.smembers(redis_key):
        logger.info(f"[缓存命中] 机构{org_id}子机构列表")
        return {int(org_id_str) for org_id_str in cached}

    logger.info(f"[缓存未命中] 开始查询机构{org_id}层级数据")

    # ========================== 2. 数据库递归查询 ==========================
    org_set = set()

    # 1. 获取数据库连接池
    pool = mysql_manager.mysql_pools["system_db"]
    # 2. 获取连接（使用异步上下文管理器）
    async with pool.acquire() as raw_conn:
        conn = AsyncConnectionWrapper(raw_conn)

        # 4. 获取游标
        async with conn.cursor() as cur:
            recursive_sql = """
            WITH RECURSIVE org_tree AS (
                SELECT id, org_id
                FROM `sys_org`
                WHERE id = %s
                UNION ALL
                SELECT o.id, o.org_id
                FROM `sys_org` o
                INNER JOIN org_tree ot ON o.org_id = ot.id
            )
            SELECT id FROM org_tree
            """
            # 5. 执行查询
            await cur.execute(recursive_sql, [org_id])
            rows = await cur.fetchall()
            org_set = {row["id"] for row in rows}

    # ========================== 3. 缓存处理 ==========================
    if org_set:
        # 转换为字符串列表存储
        org_str_list = [str(org_id) for org_id in org_set]
        try:
            # 设置缓存过期时间(1小时)和随机抖动防止雪崩
            ex_time = 3600 + random.randint(0, 300)
            await redis_dbs.default.sadd(redis_key, *org_str_list)
            await redis_dbs.default.expire(redis_key, ex_time)
        except RedisError as e:
            logger.warning(f"Redis操作失败: {str(e)}")

    return org_set


async def get_org_hierarchy(
    org_id: int, monitor: Optional[PerformanceMonitor] = None
) -> Tuple[List[str], List[str]]:
    """
    使用递归CTE查询机构层级 （所有父级）
    返回：(机构名称路径, 机构ID路径)
    """
    redis_key = f"org_parent:{org_id}"

    # ==================== 缓存检查 ====================
    if monitor:
        monitor.start("缓存检查")
    cached = await redis_dbs.default.get(redis_key)
    if monitor:
        monitor.end("缓存检查")
    if cached:
        data = json.loads(cached)
        return data["names"], data["ids"]

    # ==================== 数据库查询 ====================
    query = """
    WITH RECURSIVE cte AS (
        SELECT id, name, org_id, 1 AS depth
        FROM `sys_org`
        WHERE id = %s
        UNION ALL
        SELECT p.id, p.name, p.org_id, c.depth + 1
        FROM `sys_org` p
        INNER JOIN cte c ON p.id = c.org_id
        WHERE c.org_id != 0 AND depth < 10
    )
    SELECT name, id FROM cte ORDER BY depth DESC;
    """

    pool = mysql_manager.mysql_pools["system_db"]
    names, ids = [], ["0"]

    try:
        async with pool.acquire() as raw_conn:
            conn = AsyncConnectionWrapper(raw_conn)
            if monitor:
                monitor.start("递归查询机构层级")

            async with conn.cursor() as cur:
                await cur.execute(query, [org_id])
                while (row := await cur.fetchone()) is not None:
                    if row["id"] != 0:  # 排除根机构
                        names.append(row["name"])
                    ids.append(str(row["id"]))

            # ==================== 存储到Redis ====================
            cache_data = {"names": names, "ids": ids}
            # 设置缓存带随机过期时间（30分钟±5分钟）
            ex_time = 1800 + random.randint(-300, 300)
            # 设置1小时缓存过期时间
            await redis_dbs.default.setex(redis_key, ex_time, json.dumps(cache_data))

            if monitor:
                monitor.end("递归查询机构层级")
            return names, ids  # 反转结果顺序

    except Exception as e:
        logger.error(f"机构层级查询异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="机构层级查询失败")
