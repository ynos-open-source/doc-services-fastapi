from minio import Minio
from minio.error import S3Error
from fastapi import Depends
from typing import Dict, Optional, Iterable
from .config import load_config


class MinioManager:
    def __init__(self):
        self.client: Minio = None
        self.config = load_config()
        self.buckets: Dict[str, str] = (
            {}
        )  # bucket_name -> bucket_name (for compatibility)

    def initialize(self):
        """初始化 MinIO 客户端并确保配置的 buckets 存在"""
        self.client = Minio(
            endpoint=f"{self.config.minio.host}:{self.config.minio.port}",
            access_key=self.config.minio.access_key,
            secret_key=self.config.minio.secret_key,
            secure=self.config.minio.secure,
        )

        for bucket in self.config.minio.buckets:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
            self.buckets[bucket] = bucket  # 登记 bucket 名


class MinioBucketProxy:
    def __init__(self, client: Minio, bucket: str):
        self._client = client
        self._bucket = bucket

    def put_object(
        self,
        object_name: str,
        data,
        length: int,
        content_type: str = "application/octet-stream",
    ):
        """上传对象文件到 MinIO"""
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_name,
            data=data,
            length=length,
            content_type=content_type,
        )
        return self._client.presigned_get_object(self._bucket, object_name)

    def get_object(self, object_name: str):
        """获取对象内容数据流（用于下载或预览）"""
        return self._client.get_object(self._bucket, object_name)

    def remove_object(self, object_name: str):
        """删除指定对象"""
        return self._client.remove_object(self._bucket, object_name)

    def stat_object(self, object_name: str):
        """获取对象元信息（大小、类型等）"""
        return self._client.stat_object(self._bucket, object_name)

    def presigned_get_object(self, object_name: str, expires=3600):
        """生成用于临时下载对象的预签名URL"""
        return self._client.presigned_get_object(
            self._bucket, object_name, expires=expires
        )

    def presigned_put_object(self, object_name: str, expires=3600):
        """生成用于临时上传对象的预签名URL"""
        return self._client.presigned_put_object(
            self._bucket, object_name, expires=expires
        )

    def list_objects(self, prefix: str = "", recursive: bool = False) -> Iterable:
        """列出 bucket 中指定前缀的所有对象"""
        return self._client.list_objects(
            self._bucket, prefix=prefix, recursive=recursive
        )

    def copy_object(self, dest_object_name: str, src_bucket: str, src_object_name: str):
        """从其他 bucket 拷贝对象到当前 bucket 中"""
        from minio.commonconfig import CopySource

        source = CopySource(src_bucket, src_object_name)
        return self._client.copy_object(self._bucket, dest_object_name, source)

    def fput_object(
        self,
        object_name: str,
        file_path: str,
        content_type: str = "application/octet-stream",
    ):
        """通过本地文件路径上传对象（适合大文件）"""
        return self._client.fput_object(
            self._bucket, object_name, file_path, content_type
        )

    def fget_object(self, object_name: str, file_path: str):
        """将对象下载保存到本地文件路径"""
        return self._client.fget_object(self._bucket, object_name, file_path)

    def remove_objects(self, object_names: Iterable[str]):
        """批量删除对象"""
        return self._client.remove_objects(self._bucket, object_names)

    def bucket_exists(self) -> bool:
        """检查当前 bucket 是否存在"""
        return self._client.bucket_exists(self._bucket)

    def make_bucket(self):
        """新建当前 bucket"""
        return self._client.make_bucket(self._bucket)

    def set_bucket_policy(self, policy: str):
        """设置 bucket 的访问策略（如公开读）"""
        return self._client.set_bucket_policy(self._bucket, policy)

    def get_bucket_policy(self) -> str:
        """获取当前 bucket 的访问策略"""
        return self._client.get_bucket_policy(self._bucket)


class MinioClient:
    """根据配置动态生成属性用于访问各个 bucket"""

    @property
    def doc(self):
        return MinioBucketProxy(minio_manager.client, "doc")

    @property
    def avatar(self):
        return MinioBucketProxy(minio_manager.client, "avatar")


# 初始化
minio_manager = MinioManager()
minio_client = MinioClient()

# 使用示例：
"""
async def example_route():
    object_name = "example.txt"
    data = b"Hello MinIO"
    minio_client.doc.put_object(object_name, data, len(data))
"""
