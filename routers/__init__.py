from fastapi import APIRouter
from . import base
from .login import login
from .doc import file, avatar, icon

router = APIRouter()

router.include_router(base.router, prefix="/base", tags=["数据库连接状态"])
router.include_router(login.router, prefix="/login", tags=["用户登录"])
router.include_router(file.router, prefix="/file", tags=["附件信息"])
router.include_router(avatar.router, prefix="/avatar", tags=["头像信息"])
router.include_router(icon.router, prefix="/icon", tags=["图标信息"])
# router.include_router(org.router, prefix="/org", tags=["组织/机构信息"])
# router.include_router(role.router, prefix="/role", tags=["角色信息"])
