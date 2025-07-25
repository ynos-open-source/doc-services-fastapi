from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from utils.utils import snake_to_camel


class FileOut(BaseModel):
    """文件输出模型"""

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="allow",
    )

    id: Optional[int] = Field(None, description="主键")
    name: Optional[str] = Field(None, description="文件名称")
    size: Optional[str] = Field(None, description="附件大小")
    suffix: Optional[str] = Field(None, description="附件后缀")
    app_code: Optional[str] = Field(None, description="应用CODE")
    file_type: Optional[str] = Field(None, description="文件类型 jpg,doc,png")
    url: Optional[str] = Field(None, description="文件地址")
    ext_data: Optional[str] = Field(None, description="扩展数据")
    description: Optional[str] = Field(None, description="文件描述")
    is_public: Optional[int] = Field(None, description="是否公开 0.否 1.是")
    dir_id: Optional[int] = Field(None, description="目录ID -1.根目录")
    path: Optional[str] = Field(None, description="文件路径")
    create_time: Optional[datetime] = Field(None, description="创建时间")
    update_time: Optional[datetime] = Field(None, description="更新时间")
    creator: Optional[str] = Field(None, description="创建人")
    updater: Optional[str] = Field(None, description="更新人")
    org_id: Optional[int] = Field(None, description="机构ID")
    is_delete: Optional[int] = Field(None, description="是否删除（1=已删除）")
