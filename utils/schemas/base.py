from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field

# 1）定义类型变量
T = TypeVar("T")


# 2）继承 GenericModel 和 Generic[T]
class ResponseModel(BaseModel, Generic[T]):
    """
    响应数据模型基类
    """

    code: int = 0
    msg: str = ""
    success: bool = True
    data: Optional[T] = None
    total: Optional[int] = None

    class Config:
        # 使得 Pydantic 能够在嵌套时正确处理泛型
        arbitrary_types_allowed = True


class BaseParamsModel(BaseModel, Generic[T]):
    """
    请求参数模型基类

    排序参数
    例如：
    sorter = {
        "create_time": -1
    }
    表示按照 create_time 字段倒序排序
    """

    body: Optional[T] = None
    page: Optional[int] = Field(1, ge=-1, description="分页页码")
    limit: Optional[int] = Field(10, ge=-1, description="每页数量")
    sorter: Optional[dict] = Field(default_factory=dict, description="排序条件")
