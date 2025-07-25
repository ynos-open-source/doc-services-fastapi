import asyncio
import json
from datetime import datetime
import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from typing import List, Union
from fastapi.responses import JSONResponse
from minio import S3Error
from ..utils import convert_to_jpg
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
    minio_client,
)
from utils.schemas import UserOut, ResponseModel
from schemas import FileOut, AvatarCreate
from io import BytesIO
from starlette.responses import StreamingResponse

router = APIRouter()


@router.post("/upload", response_model=ResponseModel, summary="头像上传")
async def upload(
    file: UploadFile = File(...),
    user: UserOut = Depends(get_current_user),
    conn=mysql_dbs.system_db,
):
    print(f"\n")
    logger.info("============= 进入 头像上传 =============")
    logger.info(f"操作人: {user.username} 开始创建操作")
    logger.info(f"参数: file:{file}")

    monitor = PerformanceMonitor()
    monitor.start("API")

    try:
        # ===================== 参数预处理 =====================
        allowed_ext = {"png", "jpg", "jpeg", "webp", "gif"}
        file_ext = file.content_type.split("/")[1]
        if file_ext not in allowed_ext:
            raise HTTPException(status_code=400, detail="文件格式必须为图片")

        # ===================== 读取文件流 =====================
        file_stream = BytesIO()
        while chunk := await file.read(1024 * 1024):  # 分块读取（防大文件内存溢出）
            file_stream.write(chunk)
        file_stream.seek(0)

        # ===================== 转换格式并上传MinIO =====================
        jpg_data = convert_to_jpg(file_stream)
        byte_data = jpg_data.getvalue()
        byte_length = len(byte_data)
        object_name = f"{user.username}_{int(datetime.now().timestamp())}.jpg"
        minio_client.avatar.put_object(object_name, jpg_data, byte_length)

        # ===================== 存在性校验 =====================
        async with conn.cursor() as cur:
            await conn.begin()

            query_sql = """
            SELECT file_name
            FROM `user_avatar`
            WHERE username = %s
            """

            monitor.start("重复校验")
            await cur.execute(query_sql, [user.username])
            data_row = await cur.fetchone()
            monitor.end("重复校验")

            old_file_name = data_row["fileName"] if data_row else None
            url = f"/doc/api/avatar/{user.username}"

            if data_row:
                sql = """
                UPDATE `user_avatar` SET 
                    file_name=%s, url=%s, size=%s, suffix=%s, is_approved=%s
                WHERE username=%s
                """
                params = [
                    object_name,
                    url,
                    byte_length,
                    "jpg",
                    0,
                    user.username,
                ]
            else:
                sql = """
                INSERT INTO `user_avatar` (
                    username, file_name, url, size, suffix
                ) VALUES (%s, %s, %s, %s, %s)
                """
                params = [
                    user.username,
                    object_name,
                    url,
                    byte_length,
                    "jpg",
                ]

            monitor.start("执行sql")
            await cur.execute(sql, params)
            if old_file_name:
                minio_client.avatar.remove_object(old_file_name)
            monitor.end("执行sql")

            await conn.commit()

            await redis_dbs.default.set(f"user_avatar:{user.username}", object_name)

            # ===================== 查询新记录 =====================
            query_sql = """
            SELECT username, file_name, url, size, suffix
            FROM `user_avatar`
            WHERE username = %s
            """

            await cur.execute(query_sql, [user.username])
            new_data = await cur.fetchone()

            if not new_data:
                raise HTTPException(status_code=500, detail="查询失败")

            return JSONResponse(
                content=json_response(
                    code=200, msg="上传成功", data=new_data, success=True
                ),
            )

    except S3Error as e:
        raise HTTPException(502, f"MinIO上传失败: {str(e)}")
    except HTTPException as e:
        logger.error(f"业务异常: {str(e)}")
        await conn.rollback()
        raise e
    except Exception as e:
        logger.error(f"系统异常: {str(e)}", exc_info=True)
        await conn.rollback()
        raise HTTPException(status_code=500, detail="服务器错误描述")
    finally:
        monitor.end("API")
        monitor.log_metrics()


@router.get("/{username}", summary="预览头像")
async def detail(username: str):
    try:
        # ========================== 参数解析 ==========================
        logger.info(f"参数: {username}")

        # ========================== 从Redis获取头像信息 ==========================
        avatar_key = f"user_avatar:{username}"
        avatar_info = await redis_dbs.default.get(avatar_key)
        file_name = avatar_info

        if not avatar_info:
            # ========================== SQL构建 ==========================
            base_query = """
            SELECT file_name
            FROM `user_avatar`
            WHERE username = %s
            """
            params = [username]

            # ========================== 创建执行器 ==========================
            system_executor = AsyncExecutor("system_db")

            # ========================== 执行查询 ==========================
            data_row = await system_executor.fetch_one(base_query, params)
            if data_row:
                file_name = data_row["fileName"]
            else:
                logger.error(f"头像不存在: {username}")
                raise HTTPException(status_code=404, detail="头像不存在")

        file = minio_client.avatar.get_object(file_name).read()
        return StreamingResponse(BytesIO(file))

    except HTTPException as e:
        logger.error(f"业务异常: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"系统异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")
