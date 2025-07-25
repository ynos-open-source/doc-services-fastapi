from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .utils import json_response


def register_exception_handlers(app):
    # 注册所有异常处理器到app实例

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            msg = f"{request.url.path} 资源不存在"
            if exc.detail != "Not Found":
                msg = exc.detail
            return JSONResponse(
                content=json_response(code=404, msg=msg, success=False),
                status_code=404,
            )

        return JSONResponse(
            content=json_response(code=exc.status_code, msg=exc.detail, success=False),
            status_code=exc.status_code,
        )

    # 处理 400 参数错误
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=json_response(
                code=400,
                msg="请求参数校验失败",
                success=False,
                detail=parse_validation_errors_cn(exc.errors()),
            ),
        )

    # 可选：全局异常捕获
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=json_response(code=500, msg="服务器内部错误", success=False),
        )


def parse_validation_errors_cn(errors):
    """解析验证错误并转换为中文描述"""
    error_mapping = {
        # 常见错误类型映射
        "missing": "缺少必填字段",
        "int_parsing": "需要整数类型",
        "string_type": "需要字符串类型",
        "json_invalid": "无效的JSON格式",
        "value_error": "值不符合要求",
        "greater_than": "数值过小",
        "less_than": "数值过大",
        "pattern_mismatch": "格式不符合要求",
        "uuid_parsing": "需要UUID格式",
        "datetime_parsing": "日期时间格式错误",
    }

    formatted_errors = []

    for error in errors:
        # 转换位置信息为中文路径
        loc = error["loc"]
        cn_loc = []

        # 处理位置信息
        for part in loc:
            cn_loc.append(str(part))

        # 跳过第一个元素后的新列表
        modified_list = cn_loc[1:]
        # 根据新列表长度动态处理
        location = ".".join(modified_list) if modified_list else ""

        # 转换错误类型
        error_type = error_mapping.get(error["type"], "未知错误类型")

        # 转换错误信息
        error_msg = error["msg"]
        if error["type"] == "missing":
            error_msg = f"缺少必填字段：{location.split('.')[-1]}"
        elif "parsing" in error["type"]:
            error_msg = f"字段格式不正确，期望类型：{error_type.split('_')[0]}"

        formatted_errors.append(
            {
                "field": location.split(".")[-1],
                "location": location,
                "type": error_type,
                "message": error_msg,
            }
        )

    return formatted_errors
