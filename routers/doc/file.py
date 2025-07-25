import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Union
from fastapi.responses import JSONResponse
from utils import (
    json_response,
    logger,
    get_current_user,
    get_sorter_sql,
    get_filter_sql,
    PerformanceMonitor,
    AsyncExecutor,
    BaseParamsModel,
    mysql_dbs,
    format_datetime,
    redis_dbs,
)
from utils.schemas import UserOut, ResponseModel
from schemas import FileOut

router = APIRouter()

@router.post("/find", response_model=ResponseModel[List[FileOut]], summary="文件查询")
async def find(
    body: BaseParamsModel[FileOut], user: UserOut = Depends(get_current_user)
):
    print(f"\n")
    logger.info("============= 进入 文件查询 =============")
    logger.info(f"操作人: {user.username}")

    monitor = PerformanceMonitor()
    monitor.start("API")

    try:
        # ========================== 参数解析 ==========================
        logger.info(f"参数: {body}")

        # 排序处理
        order_by = get_sorter_sql(body)

        # ========================== SQL构建 ==========================
        # TODO 后续需要做权限控制
        base_query = """
        SELECT id,name,size,suffix,file_type,url,is_public,create_time,update_time,creator,updater,org_id,org_name
        FROM `file_resource`
        WHERE (is_delete is NULL OR is_delete != 1)
        """

        monitor.start("构建SQL")
        base_query, params = await get_filter_sql(
            base_sql=base_query,
            body=body.body if body.body else {},
            keyword_fields=["name"],
            precise_fields=["id"],
            current_user=user,
        )
        monitor.end("构建SQL")

        count_sql = f"SELECT COUNT(*) FROM ({base_query}) AS total"

        if order_by:
            base_query += f" {order_by}"

        if body.limit != -1:
            base_query += f" LIMIT {body.limit} OFFSET {(body.page-1)*body.limit}"

        # ========================== 创建执行器 ==========================
        system_executor = AsyncExecutor("doc_db", monitor)

        # ========================== 执行查询 ==========================
        monitor.start("并行查询")
        total, data_rows = await asyncio.gather(
            system_executor.fetch_total(count_sql, params),
            system_executor.fetch_all(base_query, params),
        )
        monitor.end("并行查询")

        return JSONResponse(
            content=json_response(code=200, msg="操作成功", data=data_rows, total=total),
            status_code=200,
        )

    except HTTPException as e:
        logger.error(f"业务异常: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"系统异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")
    finally:
        monitor.end("API")
        monitor.log_metrics()

@router.delete("/delete", response_model=ResponseModel[int], summary="删除附件")
async def delete(
    body: Union[List[int], List[str]],
    user: UserOut = Depends(get_current_user),
):
    print(f"\n")
    logger.info("============= 进入 删除附件 =============")
    logger.info(f"操作人: {user.username} 开始删除操作")
    logger.info(f"参数: {body}")
    monitor = PerformanceMonitor()
    monitor.start("API")

    try:
        # ========================== 创建执行器 ==========================
        system_executor = AsyncExecutor("doc_db", monitor)
        
        # ========================== 判断是否为自己的附件 ==========================
        base_query = """
        SELECT id,creator
        FROM `file_resource`
        WHERE (is_delete is NULL OR is_delete != 1)
        AND creator = %s
        AND id IN %s
        """
        params = (user.username, body)
        rows = await system_executor.fetch_all(base_query, params)
        if len(rows) != len(body):
            raise HTTPException(status_code=403, detail="您没有权限删除这些附件")

        # ========================== 执行删除 ==========================
        monitor.start("批量删除")
        affected_rows = await system_executor.delete(
            "file_resource",
            body,
            current_org_id=user.org_id
        )
        monitor.end("批量删除")

        return JSONResponse(
            content=json_response(
                code=200, msg="操作成功", 
                data=affected_rows, total=affected_rows
            ),
            status_code=200,
        )

    except HTTPException as e:
        logger.error(f"业务异常: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"系统异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器错误描述")
    finally:
        monitor.end("API")
        monitor.log_metrics()
