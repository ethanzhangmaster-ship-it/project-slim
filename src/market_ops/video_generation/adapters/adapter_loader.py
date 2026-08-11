"""Adapter Loader - Auto-discover adapters"""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type

from .base_adapter import BaseAdapter


def discover_adapters() -> Dict[str, Type[BaseAdapter]]:
    """自动扫描 adapters 目录下的所有 *_adapter.py 文件"""
    adapters = {}
    adapters_dir = Path(__file__).resolve().parent

    for _, module_name, _ in pkgutil.iter_modules([str(adapters_dir)]):
        if module_name.endswith("_adapter") and module_name != "base_adapter":
            try:
                module = importlib.import_module(f"{__package__}.{module_name}")
                for name in dir(module):
                    obj = getattr(module, name)
                    if (isinstance(obj, type) and
                        issubclass(obj, BaseAdapter) and
                        obj != BaseAdapter and
                        hasattr(obj, "platform_name") and
                        obj.platform_name):
                        adapters[obj.platform_name] = obj
            except ImportError:
                continue

    return adapters
