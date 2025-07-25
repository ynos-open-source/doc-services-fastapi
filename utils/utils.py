from typing import Optional
import uuid
import jwt
from jwt import PyJWTError
from datetime import datetime, timedelta
from .log import logger
from .config import load_config
from fastapi import HTTPException

config = load_config()


def generate_token(user):
    """
    生成token
    """
    payload = {
        "userId": user.get("id"),
        "name": user.get("name"),
        "orgId": user.get("orgId"),
        "exp": datetime.now() + timedelta(seconds=config.jwt.expire_minutes),
    }
    token = jwt.encode(
        payload,
        config.jwt.secret_key,
        algorithm=config.jwt.algorithm,
    )
    return token


def decode_token(token):
    """
    解析token
    """
    try:
        payload = jwt.decode(
            token,
            config.jwt.secret_key,
            algorithms=[config.jwt.algorithm],
        )
        if payload is None:
            raise HTTPException(status_code=401, detail="无效凭证")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="凭证已过期")
    except PyJWTError:
        raise HTTPException(status_code=401, detail="无效凭证")


def new_call_id(replace=""):
    return str(uuid.uuid4()).replace("-", replace)


# 定义json返回内容
# 格式：{"code": 0, "msg": "", "success": true "data": {}}
def json_response(
    code=200,
    msg="",
    success=True,
    data: Optional[dict] = None,
    total: Optional[int] = None,
    **kwargs,
):
    r_d = {}
    r_d["code"] = code
    r_d["msg"] = msg
    r_d["success"] = success

    if data is not None:
        r_d["data"] = data
    if total is not None:
        r_d["total"] = total

    for k, v in kwargs.items():
        r_d[k] = v

    print("\n")
    logger.debug(f"json响应内容: {r_d}")
    if code != 200:
        logger.error(f"json响应状态码: {code}, msg: {msg}, success: {success}")
    else:
        logger.info(f"json响应状态码: {code}, msg: {msg}, success: {success}")
    return r_d


def format_datetime(dt=datetime.now(), fmt="%Y-%m-%d %H:%M:%S"):
    """
    格式化时间
    """
    if isinstance(dt, datetime):
        return dt.strftime(fmt)
    return dt


def camel_to_snake(s):
    """
    将驼峰命名法的字符串转换为下划线命名法

    snake_str = "updateTime"
    camel_str = camel_to_snake(snake_str)
    print(camel_str)  # 输出：update_time
    """
    # 将驼峰命名法的字符串转换为下划线命名法
    return "".join(["_" + c.lower() if c.isupper() else c for c in s]).lstrip("_")


def snake_to_camel(string: str) -> str:
    """
    将下划线命名法的字符串转换为小驼峰命名法

    snake_str = "update_ime"
    camel_str = snake_to_camel(snake_str)
    print(camel_str)  # 输出：updateTime
    """
    # 将下划线命名法的字符串转换为小驼峰命名法
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def is_empty(value):
    """
    判断是否为空
    """
    if value == 0:
        return False
    return (isinstance(value, (int, float)) and value == 0) or not value

