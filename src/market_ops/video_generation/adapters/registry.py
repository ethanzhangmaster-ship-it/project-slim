"""Adapter Registry"""
from typing import Dict, Type
from .base_adapter import BaseAdapter
from .adapter_loader import discover_adapters


class AdapterRegistry:
    _instance = None
    _adapters: Dict[str, Type[BaseAdapter]] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._auto_discover()
        return cls._instance

    def _auto_discover(self):
        self._adapters = discover_adapters()

    def register(self, adapter_class: Type[BaseAdapter]):
        if hasattr(adapter_class, "platform_name") and adapter_class.platform_name:
            self._adapters[adapter_class.platform_name] = adapter_class

    def get(self, platform_name: str) -> Type[BaseAdapter]:
        return self._adapters.get(platform_name)

    def create(self, platform_name: str) -> BaseAdapter:
        adapter_class = self.get(platform_name)
        if adapter_class:
            return adapter_class()
        raise ValueError(f"No adapter found for platform: {platform_name}")

    def list_platforms(self) -> list:
        return list(self._adapters.keys())

    def all(self) -> list:
        return [self.create(p) for p in self.list_platforms()]


registry = AdapterRegistry()
