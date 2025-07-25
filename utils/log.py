import logging
import logging.config
import os, time
from .config import load_config

cur_path = os.path.dirname(os.path.realpath(__file__))  # log_path是存放日志的路径
log_path = os.path.join(os.path.dirname(cur_path), "logs")
if not os.path.exists(log_path):
    os.mkdir(log_path)  # 如果不存在这个logs文件夹，就在启动服务时自动创建一个
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        # 日志格式
        "standard": {
            "format": "[%(asctime)s] [%(filename)s:%(lineno)d] [%(module)s:%(funcName)s] "
            "[%(levelname)s]- %(message)s"
        },
        "simple": {"format": "%(levelname)s %(message)s"},  # 简单格式
    },
    # 过滤
    "filters": {},
    # 定义具体处理日志的方式
    "handlers": {
        # 默认记录所有日志
        "default": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(
                log_path, "all-{}.log".format(time.strftime("%Y-%m-%d"))
            ),
            "maxBytes": 1024 * 1024 * 5,  # 文件大小
            "backupCount": 5,  # 备份数
            "formatter": "standard",  # 输出格式
            "encoding": "utf-8",  # 设置默认编码，否则打印出来汉字乱码
        },
        # 输出错误日志
        "error": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(
                log_path, "error-{}.log".format(time.strftime("%Y-%m-%d"))
            ),
            "maxBytes": 1024 * 1024 * 5,  # 文件大小
            "backupCount": 5,  # 备份数
            "formatter": "standard",  # 输出格式
            "encoding": "utf-8",  # 设置默认编码
        },
        # 控制台输出
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        # 输出info日志
        "info": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(
                log_path, "info-{}.log".format(time.strftime("%Y-%m-%d"))
            ),
            "maxBytes": 1024 * 1024 * 5,
            "backupCount": 5,
            "formatter": "standard",
            "encoding": "utf-8",  # 设置默认编码
        },
    },
    # 配置用哪几种 handlers 来处理日志
    "loggers": {
        # 类型 为 django 处理所有类型的日志， 默认调用
        "django": {
            "handlers": ["default", "console"],  # 处理django自己的日志
            "level": "INFO",
            "propagate": False,
        },
        # log 调用时需要当作参数传入
        "log": {
            # 哪里调用，就处理哪里的日志.这里其实是把info、error的日志分别写在了3个文件里，
            # info对应info，error对应error，并且all中也包含了info和error
            "handlers": ["info", "error", "default", "console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}
logging.config.dictConfig(LOGGING)

# 初始化配置
config = load_config()


def _get_logger():
    log = logging.getLogger("log")
    log.setLevel(config.logging.level)
    return log


# 日志句柄
logger = _get_logger()
