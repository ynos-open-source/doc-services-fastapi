from fastapi import HTTPException, Request
from .utils import decode_token
from .redis import redis_dbs
from schemas import UserOut


async def get_current_user(request: Request):
    """
    获取当前用户信息
    """
    # 尝试从 Cookies 获取 Token
    token = request.cookies.get("token")

    # 如果 Cookie 中没有，尝试从 Header token 获取
    if not token:
        token = request.headers.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    user = decode_token(token)

    id = user.get("userId")
    org_id = user.get("orgId")
    keys = [
        "id",
        "createById",
        "updateById",
        "username",
        "joinTime",
        "orgName",
        "orgId",
        "phone",
        "name",
        "email",
        "position",
        "sex",
        "status",
        "createTime",
        "updateTime",
        "lastLoginTime",
    ]
    data = await redis_dbs.default.hmget(f"user:{org_id}_{id}", keys)
    if data[0] is None:
        raise HTTPException(status_code=401, detail="未登录")
    user = {}
    for i in range(len(keys)):
        user[keys[i]] = data[i] if data[i] else None

    return UserOut(**user)
