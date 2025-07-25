from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from ..utils import snake_to_camel


class UserCreate(BaseModel):
    """用户创建"""

    model_config = ConfigDict(
        alias_generator=snake_to_camel,  # Pydantic v2 中的配置方式 :contentReference[oaicite:10]{index=10}
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )

    phone: str = Field(..., description="手机号")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    name: str = Field(..., description="姓名")
    position: Optional[str] = Field(None, description="职位")
    sex: Optional[int] = Field(None, description="性别：0=女，1=男")
    email: Optional[str] = Field(None, description="邮箱")
    org_id: Optional[int] = Field(None, description="机构ID")
    org_name: Optional[str] = Field(None, description="机构名称")
    status: Optional[int] = Field(1, description="状态：0=禁用，1=可用")
    join_time: Optional[datetime] = Field(None, description="入职时间/加入时间")


class UserUpdate(BaseModel):
    """用户更新"""

    model_config = ConfigDict(
        alias_generator=snake_to_camel,  # Pydantic v2 中的配置方式 :contentReference[oaicite:10]{index=10}
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )

    id: int = Field(..., description="主键")
    phone: str = Field(..., description="手机号")
    username: str = Field(..., description="用户名")
    name: str = Field(..., description="姓名")
    position: Optional[str] = Field(None, description="职位")
    sex: Optional[int] = Field(None, description="性别：0=女，1=男")
    email: Optional[str] = Field(None, description="邮箱")
    org_id: Optional[int] = Field(None, description="机构ID")
    org_name: Optional[str] = Field(None, description="机构名称")
    status: Optional[int] = Field(1, description="状态：0=禁用，1=可用")
    join_time: Optional[datetime] = Field(None, description="入职时间/加入时间")


class UserOut(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_camel,  # Pydantic v2 中的配置方式 :contentReference[oaicite:10]{index=10}
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )

    id: Optional[int] = Field(None, description="主键")
    updater: Optional[str] = Field(None, description="更新人")
    username: Optional[str] = Field(None, description="用户名")
    join_time: Optional[datetime] = Field(None, description="入职时间")
    org_id: Optional[int] = Field(None, description="机构ID")
    org_name: Optional[str] = Field(None, description="机构名称")
    status: Optional[int] = Field(None, description="状态：0=禁用，1=可用")
    phone: Optional[str] = Field(None, description="手机号")
    name: Optional[str] = Field(None, description="姓名")
    email: Optional[str] = Field(None, description="邮箱")
    position: Optional[str] = Field(None, description="职位")
    sex: Optional[int] = Field(None, description="性别：0=女，1=男")
    create_time: Optional[datetime] = Field(None, description="创建时间")
    update_time: Optional[datetime] = Field(None, description="更新时间")
    last_login_time: Optional[datetime] = Field(None, description="最后登录时间")


class UserFoName(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_camel,  # Pydantic v2 中的配置方式 :contentReference[oaicite:10]{index=10}
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )
    id: Optional[int] = Field(None, description="主键")
    username: Optional[str] = Field(None, description="用户名")
    name: Optional[str] = Field(None, description="姓名")
    org_id: Optional[int] = Field(None, description="机构ID")
    org_name: Optional[str] = Field(None, description="机构名称")
