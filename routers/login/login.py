import random
from fastapi import APIRouter, Depends, Form, HTTPException, Request, BackgroundTasks
from schemas import LoginResponseModel
from fastapi.responses import JSONResponse
from utils import (
    logger,
    generate_token,
    json_response,
    mysql_dbs,
    AsyncConnectionWrapper,
    load_config,
    redis_dbs,
    PerformanceMonitor,
    get_current_user,
    format_datetime,
    mysql_manager,
)
from utils.schemas import UserOut
from datetime import datetime
import bcrypt
import asyncio

from utils.utils import snake_to_camel

router = APIRouter()


async def _update_login_time(user_id: int, last_login_time):
    """异步更新登录时间"""
    logger.info("⌛️...开始更新登录时间")
    monitor = PerformanceMonitor()
    monitor.start("更新登录时间")
    # 1. 获取数据库连接池
    pool = mysql_manager.mysql_pools["system_db"]
    # 2. 获取连接（使用异步上下文管理器）
    async with pool.acquire() as raw_conn:
        conn = AsyncConnectionWrapper(raw_conn)
        # 4. 获取游标
        async with conn.cursor() as cur:
            sql = """UPDATE users SET last_login_time=%s WHERE id=%s"""
            params = [last_login_time, user_id]
            await cur.execute(sql, params)
            await conn.commit()
            logger.info(f"✅ 用户{user_id}的登录时间已更新")
            monitor.end("更新登录时间")
            monitor.log_metrics()


async def _async_cache_user(user_data):
    """异步缓存用户信息到Redis"""
    try:
        logger.info("⌛️...开始缓存用户信息")
        monitor = PerformanceMonitor()
        monitor.start("缓存用户信息")
        redis_key = f"user:{user_data['orgId']}_{user_data['id']}"
        async with redis_dbs.default.pipeline() as pipe:
            await pipe.hmset(redis_key, user_data)
            config = load_config()
            await pipe.expire(redis_key, config.jwt.expire_minutes)
            await pipe.execute()

        logger.info(f"✅ 用户{user_data['id']}的信息已缓存到Redis")
        monitor.end("缓存用户信息")
        monitor.log_metrics()
    except Exception as e:
        logger.error(f"缓存异常: {str(e)}")


@router.post("/login", response_model=LoginResponseModel, summary="用户登录")
async def login(
    phone: str = Form(...),
    password: str = Form(...),
    conn=mysql_dbs.system_db,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    用户登录
    """
    print("\n")
    logger.info("============= 用户登录流程 =============")
    # ========================== 1. 参数解析 ==========================
    logger.info(f"请求参数: phone= {phone}, password= {password}")

    monitor = PerformanceMonitor()
    monitor.start("API")

    # ========================== 2. 参数校验 ==========================
    if not phone:
        return JSONResponse(
            json_response(code=400, msg="用户名/邮箱/手机号码不能为空", success=False),
            status_code=400,
        )
    if not password:
        return JSONResponse(
            json_response(code=400, msg="密码不能为空", success=False), status_code=400
        )

    # ========================== 3. 查询用户 ==========================

    async with conn.cursor() as cur:
        # 使用参数化查询防止SQL注入
        select_sql = """
        SELECT id,phone,username,password,name,position,join_time,sex,email,org_id,org_name,last_login_time,create_time,update_time,creator,updater,status,is_delete
        FROM  `users`
        WHERE (is_delete is NULL OR is_delete != 1)
            AND (phone=%s OR email=%s OR username=%s)
        LIMIT 1
        """

        monitor.start("查询用户")
        await cur.execute(select_sql, [phone, phone, phone])
        user_row = await cur.fetchone()
        monitor.end("查询用户")

        # ========================== 4. 用户验证 ==========================
        if not user_row:
            logger.warning(f"用户不存在: {phone}")
            return JSONResponse(
                json_response(code=400, msg="用户不存在", success=False),
                status_code=400,
            )

        # ========================== 5. 密码验证 ==========================
        monitor.start("密码验证")
        is_valid = await asyncio.to_thread(
            bcrypt.checkpw,
            password.encode("utf-8"),
            user_row["password"].encode("utf-8"),
        )
        monitor.end("密码验证")

        if not is_valid:
            logger.warning(f"{phone}: 密码错误: {user_row['id']}")
            monitor.end("API")
            monitor.log_metrics()
            raise HTTPException(400, "密码错误")

        # ========================== 6. 更新登录时间 ==========================
        last_login_time = format_datetime()
        user_row["lastLoginTime"] = last_login_time

        # ========================== 7. 生成Token ==========================
        if user_row["password"]:
            del user_row["password"]
        token = generate_token(user_row)

        # ========================== 8. 缓存用户信息 ==========================
        # 过滤None值并序列化时间
        user_data = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in user_row.items()
            if v is not None
        }

        # ================== 后台任务 ==================
        background_tasks.add_task(_update_login_time, user_row["id"], last_login_time)
        background_tasks.add_task(_async_cache_user, user_data)

        # ========================== 9. 返回结果 ==========================

        logger.info(f"登录成功: {phone}")
        monitor.end("API")
        monitor.log_metrics()

        json_response_obj = JSONResponse(
            content=json_response(
                code=200, msg="登录成功", data=user_data, token=token, success=True
            ),
            status_code=200,
        )

        config = load_config()
        # 设置 Cookie
        json_response_obj.set_cookie(
            key="token",
            value=token,
            httponly=True,
            max_age=config.jwt.expire_minutes,
            path="/",
            secure=False,  # 开发环境设为 False，生产环境应设为 True
            samesite="Lax",
        )

        return json_response_obj


@router.api_route(
    "/isAuth",
    methods=["GET", "POST"],
    response_model=LoginResponseModel,
    summary="检查用户是否已登录",
)
async def is_auth(request: Request, current_user: UserOut = Depends(get_current_user)):
    """
    检查用户是否已登录
    """
    print("\n")
    logger.info("============= 检查用户是否已登录 =============")
    # 尝试从 Cookies 获取 Token
    token = request.cookies.get("token")

    # 如果 Cookie 中没有，尝试从 Header token 获取
    if not token:
        token = request.headers.get("token")

    user = {}
    # 将用户信息转换为字典
    for key, value in current_user.__dict__.items():
        if key != "_state":
            if isinstance(value, datetime):
                value = format_datetime(value)
            key = snake_to_camel(key)
            user[key] = value

    return JSONResponse(
        content=json_response(
            code=200,
            msg="用户已登录",
            data=user,
            success=True,
            token=token,
        ),
        status_code=200,
    )


@router.api_route(
    "/logout",
    methods=["GET", "POST"],
    summary="用户登出",
)
async def logout(request: Request, current_user: UserOut = Depends(get_current_user)):
    """
    用户登出
    """
    print("\n")
    logger.info("============= 用户登出流程 =============")
    logger.info(f"用户={current_user}")
    id = current_user.id
    org_id = current_user.org_id
    try:
        await redis_dbs.default.delete(f"user:{org_id}_{id}")
    except Exception as e:
        logger.error(f"退出登录失败: {e}")

    return JSONResponse(
        content=json_response(code=200, msg="退出登录成功", success=True),
        status_code=200,
    )


@router.post("/code", summary="获取验证码")
async def code(
    phone: str = Form(..., description="手机号码"),
    salt: str = Form("a1b2c3d4", description="安全盐值，用于请求签名"),
):
    """
    获取验证码
    """
    print("\n")
    logger.info("============= 获取验证码 =============")

    r_code = await redis_dbs.default.get(f"code:{phone}-{salt}")
    # 判断redis是否已存在过验证码
    if r_code is not None:
        return JSONResponse(
            content=json_response(code=400, msg="验证码已发送", success=False),
            status_code=400,
        )

    # 生成6位数字的验证码
    code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    # logger.info(f"code = {code}")
    logger.debug(f"code = {code}")

    # 将验证码存储在redis
    await redis_dbs.default.set(f"code:{phone}-{salt}", code, ex=60 * 5)

    return JSONResponse(
        content=json_response(code=200, msg="获取验证码成功", success=True),
        status_code=200,
    )


@router.post("/codeLogin", summary="验证码登录")
async def codeLogin(
    phone: str = Form(..., description="手机号码"),
    code: str = Form(..., min_length=6, max_length=6, description="验证码"),
    salt: str = Form("a1b2c3d4", description="安全盐值，用于请求签名"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    验证码登录
    """
    print("\n")
    logger.info("============= 验证码登录 =============")

    monitor = PerformanceMonitor()
    monitor.start("API")

    # ========================== SQL构建 ==========================
    base_sql = """
    SELECT id,
        phone,
        username,
        name,
        position,
        join_time,
        sex,
        email,
        org_id,
        org_name,
        last_login_time,
        create_time,
        update_time,
        creator,
        updater,
        status,
        is_delete
    FROM users WHERE (is_delete is NULL OR is_delete != 1) AND phone=%s;
    """

    async def _get_user(base_sql, params):
        """异步获取用户信息"""
        logger.info("⌛️...开始获取用户信息")
        monitor = PerformanceMonitor()
        monitor.start("获取用户信息")
        pool = mysql_manager.mysql_pools["system_db"]
        async with pool.acquire() as raw_conn:
            conn = AsyncConnectionWrapper(raw_conn)
            async with conn.cursor() as cur:
                await cur.execute(base_sql, params)
                logger.info(f"✅ 用户信息已获取")
                monitor.end("获取用户信息")
                monitor.log_metrics()
                return await cur.fetchone()

    # ================== 并行阶段1 ==================
    # 同时发起用户查询和验证码获取
    monitor.start("获取用户信息和验证码")
    user_future = _get_user(base_sql=base_sql, params=[phone])
    code_future = redis_dbs.default.get(f"code:{phone}-{salt}")

    # 等待第一阶段结果
    user_row, _code = await asyncio.gather(user_future, code_future)
    monitor.end("获取用户信息和验证码")
    # ================== 用户验证 ==================
    if not user_row:
        monitor.end("API")
        monitor.log_metrics()
        raise HTTPException(status_code=400, detail="手机号不存在")

    # ================== 验证码验证 ==================
    if not _code:
        monitor.end("API")
        monitor.log_metrics()
        raise HTTPException(status_code=400, detail="验证码已过期")

    if _code != code:
        monitor.end("API")
        monitor.log_metrics()
        raise HTTPException(status_code=400, detail="验证码错误")

    # ========================== 6. 更新登录时间 ==========================
    last_login_time = format_datetime()
    user_row["lastLoginTime"] = last_login_time

    # ========================== 生成Token ==========================
    token = generate_token(user_row)

    # ========================== 8. 缓存用户信息 ==========================
    # 过滤None值并序列化时间
    user_data = {
        k: (v.isoformat() if isinstance(v, datetime) else v)
        for k, v in user_row.items()
        if v is not None
    }

    # ================== 后台任务 ==================
    # 更新时间
    background_tasks.add_task(_update_login_time, user_row["id"], last_login_time)
    # 缓存用户信息
    background_tasks.add_task(_async_cache_user, user_data)

    async def _async_delete_code(phone, salt):
        await redis_dbs.default.delete(f"code:{phone}-{salt}")

    # 登录成功删除redis中的验证码
    background_tasks.add_task(_async_delete_code, phone, salt)

    # ========================== 返回结果 ==========================
    monitor.end("API")
    monitor.log_metrics()
    return JSONResponse(
        content=json_response(
            code=200, msg="登录成功", data=user_data, token=token, success=True
        ),
        status_code=200,
    )
