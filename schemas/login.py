from typing import Optional
from pydantic import BaseModel
from utils.schemas.sys_users import UserOut


class LoginResponseModel(BaseModel):
    code: int = 0
    msg: str = ""
    success: bool = True
    token: Optional[str] = None
    data: Optional[UserOut] = None

    class Config:
        # 使得 Pydantic 能够在嵌套时正确处理泛型
        arbitrary_types_allowed = True
