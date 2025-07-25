from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from utils.utils import snake_to_camel


class IconOut(BaseModel):
    """图标"""

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )
    id: Optional[int] = Field(None, description="ID")
    name: Optional[str] = Field(None, description="文件名")
    url: Optional[str] = Field(None, description="URL")
    size: Optional[int] = Field(None, description="大小")
    suffix: Optional[str] = Field(None, description="附件后缀")
    is_approved: Optional[int] = Field(
        None, description="是否已审核 0.未审批 1.已审批 2.审批不通过"
    )
    app_code: Optional[str] = Field(None, description="应用CODE")
    description: Optional[str] = Field(None, description="描述")
    create_time: Optional[datetime] = Field(None, description="创建时间")
    creator: Optional[str] = Field(None, description="创建人")
    org_id: Optional[int] = Field(None, description="机构ID")
    is_delete: Optional[int] = Field(None, description="是否删除（1=已删除）")
