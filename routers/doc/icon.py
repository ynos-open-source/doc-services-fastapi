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


@router.post("/upload", response_model=ResponseModel, summary="图标上传")
async def upload(
    file: UploadFile = File(...),
    name: str = Form(None, description="图标名称"),
    app_code: str = Form(None, description="应用CODE"),
    compress: bool = Form(True, description="是否压缩 默认是"),
    user: UserOut = Depends(get_current_user),
    conn=mysql_dbs.doc_db,
):
    print(f"\n")
    logger.info("============= 进入 图标上传 =============")
    logger.info(f"操作人: {user.username}")
    logger.info(f"参数: file:{file}")

    monitor = PerformanceMonitor()
    monitor.start("API")

    try:
        # ===================== 参数预处理 =====================
        allowed_ext = {"png", "jpg", "jpeg", "webp", "gif"}
        file_ext = file.content_type.split("/")[1]
        if file_ext not in allowed_ext:
            raise HTTPException(status_code=400, detail="文件格式必须为图片")

        o_id = f"{int(datetime.now().timestamp())}"
        suffix = "jpg" if compress else file_ext
        object_name = f"icon/{o_id}.{suffix}"
        url = f"/doc/api/icon/{o_id}.{suffix}"

        # ===================== 读取文件流 =====================
        if compress:
            file_stream = BytesIO()
            while chunk := await file.read(1024 * 1024):  # 分块读取（防大文件内存溢出）
                file_stream.write(chunk)
            file_stream.seek(0)
            jpg_data = convert_to_jpg(file_stream)
            byte_data = jpg_data.getvalue()
            byte_length = len(byte_data)
        else:
            jpg_data = file.file
            byte_length = file.size

        # ===================== 存在性校验 =====================
        async with conn.cursor() as cur:
            await conn.begin()

            sql = """
            INSERT INTO `icon_info` (
                name,url,size,suffix,app_code,creator,org_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = [
                name if name else object_name,
                url,
                byte_length,
                suffix,
                app_code if app_code else None,
                user.username,
                user.org_id,
            ]

            monitor.start("执行sql")
            await cur.execute(sql, params)
            insert_id = cur.lastrowid
            monitor.end("执行sql")

            await conn.commit()

            # ===================== 转换格式并上传MinIO =====================
            minio_client.doc.put_object(object_name, jpg_data, byte_length)

            # ===================== 查询新记录 =====================
            query_sql = """
            SELECT id,name,url,size,suffix,app_code,creator,org_id
            FROM `icon_info`
            WHERE id = %s
            """

            await cur.execute(query_sql, [insert_id])
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


@router.get("/{id}", summary="预览图标")
async def detail(id: str):
    try:
        # ========================== 参数解析 ==========================
        logger.info(f"参数: {id}")
        file_name = f"icon/{id}"
        file = minio_client.doc.get_object(file_name).read()
        return StreamingResponse(BytesIO(file))

    except S3Error as e:
        raise HTTPException(502, f"读取流失败: {str(e)}")
    except HTTPException as e:
        logger.error(f"业务异常: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"系统异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")
