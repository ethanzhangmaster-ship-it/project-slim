"""Executor Registry - 自动发现执行器"""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type

from .base_executor import BaseExecutor


def discover_executors() -> Dict[str, Type[BaseExecutor]]:
    """自动扫描 executors 目录下的所有 *_executor.py 文件"""
    executors = {}
    executors_dir = Path(__file__).resolve().parent

    for _, module_name, _ in pkgutil.iter_modules([str(executors_dir)]):
        if module_name.endswith("_executor") and module_name != "base_executor":
            try:
                module = importlib.import_module(f"{__package__}.{module_name}")
                for name in dir(module):
                    obj = getattr(module, name)
                    if (isinstance(obj, type) and
                        issubclass(obj, BaseExecutor) and
                        obj != BaseExecutor and
                        hasattr(obj, "platform_name") and
                        obj.platform_name):
                        executors[obj.platform_name] = obj
            except ImportError:
                continue

    return executors


class ExecutorRegistry:
    _instance = None
    _executors: Dict[str, Type[BaseExecutor]] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._auto_discover()
        return cls._instance

    def _auto_discover(self):
        self._executors = discover_executors()

    def register(self, executor_class: Type[BaseExecutor]):
        if hasattr(executor_class, "platform_name") and executor_class.platform_name:
            self._executors[executor_class.platform_name] = executor_class

    def get(self, platform_name: str) -> Type[BaseExecutor]:
        return self._executors.get(platform_name)

    def create(self, platform_name: str, **kwargs) -> BaseExecutor:
        executor_class = self.get(platform_name)
        if executor_class:
            return executor_class(**kwargs)
        raise ValueError(f"No executor found for platform: {platform_name}")

    def list_platforms(self) -> list:
        return list(self._executors.keys())


executor_registry = ExecutorRegistry()
