import logging
import time
import threading
from typing import Dict
from contextlib import contextmanager
from .log import logger
import inspect
import os


class PerformanceMonitor:
    """生产级性能监控类（线程安全）
    Args:
        path: 请求地址

    使用示例：
    monitor = PerformanceMonitor(request.path)
    """

    def __init__(self, path=None):
        """初始化线程本地存储和锁机制"""
        self.local = threading.local()
        self.lock = threading.Lock()
        self._init_thread_local()
        self.path = path
        # 获取调用栈信息
        stack = inspect.stack()
        # 遍历调用栈寻找第一个非本文件的调用者
        for frame_info in stack:
            if frame_info.filename != __file__:
                self.caller_path = os.path.abspath(frame_info.filename)
                self.caller_line = frame_info.lineno
                break
        else:
            self.caller_path = None

    def _init_thread_local(self):
        """初始化线程本地存储结构"""
        if not hasattr(self.local, "initialized"):
            self.local.metrics = {}
            self.local.api_metrics = {}
            self.local.start_times = {}
            self.local.initialized = True

    def start(self, key: str) -> None:
        """启动计时器

        Args:
            key: 指标名称 (如'db_query'或'API')

        特性：
        - 自动区分常规指标和API指标
        - 线程安全存储初始化
        """
        with self.lock:
            storage = self.local.api_metrics if key == "API" else self.local.metrics
            storage.setdefault(key, 0.0)
            self.local.start_times[key] = time.perf_counter()

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"⏳ 启动监控 [{key}]", extra={"metric": key})

    def end(self, key: str) -> None:
        """结束计时器

        Args:
            key: 必须与start()调用时的key一致

        异常处理：
        - 自动忽略未配对的end调用
        - 记录异常耗时
        """
        with self.lock:
            start_time = self.local.start_times.pop(key, None)
            if not start_time:
                return

            elapsed = (time.perf_counter() - start_time) * 1000
            target_store = (
                self.local.api_metrics if key == "API" else self.local.metrics
            )
            target_store[key] += round(elapsed, 2)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"⏱️ 完成监控 [{key}] 耗时: {elapsed:.2f}ms",
                    extra={"metric": key, "duration": elapsed},
                )

    def log_metrics(self) -> Dict[str, float]:
        """生成性能报告并重置计数器

        Returns:
            包含常规指标和API指标的合并字典

        日志格式：
        - INFO级别：结构化文本报告
        - DEBUG级别：彩色终端输出
        """
        with self.lock:
            total = round(sum(self.local.metrics.values()), 2)
            api_total = round(sum(self.local.api_metrics.values()), 2)
            report = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "metrics": self.local.metrics.copy(),
                "api_metrics": self.local.api_metrics.copy(),
                "total": total,
                "api_total": api_total,
            }

            # 结构化日志输出（网页5建议）
            log_msg = [
                f"\n\n{'='*40} 性能报告 {'='*40}",
                f"📅 时间: {report['timestamp']}",
                f"▪ 请求地址: {self.path}" if self.path else "",
                f"▪ 文件路径: {self.caller_path}:{self.caller_line}",
                *[f"▪ {k:<20}: {v:>2.2f}ms" for k, v in report["metrics"].items()],
                f"🏁 业务总耗时: {total:>2.2f}ms",
                f"🏁 总耗时: {api_total:>2.2f}ms",
                f"{'='*90}\n",
            ]
            logger.info("\n".join(log_msg))

            # 重置计数器
            self.local.metrics.clear()
            self.local.api_metrics.clear()
            return {
                **{k: round(v, 2) for k, v in report["metrics"].items()},
                **{k: round(v, 2) for k, v in report["api_metrics"].items()},
            }

    @contextmanager
    def track(self, key: str):
        """上下文管理器自动计时
        使用示例：
        with monitor.track('db_query'):
            execute_query()
        """
        self.start(key)
        try:
            yield
        except Exception as e:
            logger.error(f"⛔ {key} 执行异常", exc_info=True)  # 网页5建议记录异常堆栈
            raise
        finally:
            self.end(key)
