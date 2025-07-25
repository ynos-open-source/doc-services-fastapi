from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from utils.utils import snake_to_camel


class DirOut(BaseModel):
    """目录"""

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )

    id: Optional[int] = Field(None, description="主键")
    name: Optional[str] = Field(None, description="目录名称")
    app_code: Optional[str] = Field(None, description="应用CODE")
    pwd: Optional[str] = Field(None, description="密码")
    icon: Optional[str] = Field(None, description="图标")
    is_public: Optional[int] = Field(None, description="是否公开 0.否 1.是")
    is_show: Optional[int] = Field(None, description="是否显示 0.否 1.是")
    dir_id: Optional[int] = Field(None, description="父目录ID -1表示根目录")
    description: Optional[str] = Field(None, description="文件描述")
    create_time: Optional[datetime] = Field(None, description="创建时间")
    update_time: Optional[datetime] = Field(None, description="更新时间")
    creator: Optional[str] = Field(None, description="创建人")
    updater: Optional[str] = Field(None, description="更新人")
    org_id: Optional[int] = Field(None, description="机构ID")
    is_delete: Optional[int] = Field(None, description="是否删除（1=已删除）")
