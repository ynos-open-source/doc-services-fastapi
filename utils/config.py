import sys
from pydantic import BaseModel, Field
from typing import Dict, Optional
import yaml
from pathlib import Path
import logging


class MySQLConfig(BaseModel):
    host: str
    port: int = Field(gt=0, le=65535)
    user: str
    password: str
    database: str
    minsize: int = Field(5, gt=0)
    maxsize: int = Field(10, gt=0)


class MongoDBConfig(BaseModel):
    host: str
    port: int = Field(27017, gt=0, le=65535)
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    poolsize: int = Field(10, gt=0)


class RedisConfig(BaseModel):
    host: str
    port: int = Field(6379, gt=0, le=65535)
    db: int = Field(ge=0, le=15)
    password: Optional[str] = None
    minsize: int = Field(5, gt=0)
    maxsize: int = Field(20, gt=0)
    
class MinioConfig(BaseModel):
    host: str
    port: int = Field(19000, gt=0, le=65535)
    access_key: str
    secret_key: str
    secure: bool = False
    buckets: list[str] = []

class JWTConfig(BaseModel):
    secret_key: str = Field(min_length=32)
    algorithm: str = Field("HS256", pattern="^(HS256|HS384|HS512)$")
    expire_minutes: int = Field(30, gt=0)


class LoggingConfig(BaseModel):
    level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")


class APP(BaseModel):
    title: str
    description: str
    version: str = "1.0.0"
    port: int = Field(8080, gt=0, le=65535)
    env: str = Field("dev", pattern="^(dev|prod)$")
    prefix: str = "/"
    host: str = "0.0.0.0"

    def production(self) -> bool:
        return self.env == "prod"


class AppConfig(BaseModel):
    mysql: Dict[str, MySQLConfig] = Field(default_factory=dict)
    mongodb: Dict[str, MongoDBConfig] = Field(default_factory=dict)
    redis: Dict[str, RedisConfig] = Field(default_factory=dict)
    minio: Optional[MinioConfig] = None
    jwt: Optional[JWTConfig] = None
    logging: LoggingConfig = LoggingConfig()
    app: Optional[APP] = Field(default_factory=dict)


_config = None  # 添加全局配置缓存


def load_config() -> AppConfig:
    global _config

    if _config is None:
        try:
            # 解析命令行参数（支持格式：--env=prod 或 prod）
            env = "dev"  # 默认值
            for arg in sys.argv[1:]:
                if arg.startswith("--env="):
                    env = arg.split("=")[1]
                elif arg in ("prod", "test"):
                    env = arg
            filename = f"config.{env}.yaml"
            config_path = Path(__file__).parent.parent / filename
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    raw_config = yaml.safe_load(f)
                    _config = AppConfig(**raw_config)
                    return _config
            except FileNotFoundError:
                logging.error(f"Config file not found: {config_path}")
                raise
            except yaml.YAMLError as e:
                logging.error(f"Invalid YAML format: {str(e)}")
                raise
            except Exception as e:
                logging.error(f"Configuration validation failed: {str(e)}")
                raise
        except Exception as e:
            raise RuntimeError(f"配置文件加载失败: {str(e)}")
    return _config


# 使用示例
if __name__ == "__main__":
    try:
        config = load_config()
        print("Configuration loaded successfully:")
        print(config.json(indent=2))
    except Exception as e:
        print(f"Failed to load config: {str(e)}")
