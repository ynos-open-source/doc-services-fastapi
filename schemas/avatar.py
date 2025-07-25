from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from utils.utils import snake_to_camel


class AvatarCreate(BaseModel):
    """头像"""

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )

    username: str = Field(..., description="用户名")
    

class AvatarOut(BaseModel):
    """头像"""
    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )
    username: Optional[str] = Field(None, description="用户名")
    file_name: Optional[str] = Field(None, description="文件名")
    url: Optional[str] = Field(None, description="URL")
    size: Optional[int] = Field(None, description="大小")
    suffix: Optional[str] = Field(None, description="附件后缀")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    is_approved: Optional[int] = Field(None, description="是否已审核 0.未审批 1.已审批 2.审批不通过")
    
