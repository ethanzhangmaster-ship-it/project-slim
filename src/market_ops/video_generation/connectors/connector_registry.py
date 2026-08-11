"""Connector Registry"""
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type

from .base_connector import BaseConnector


def discover_connectors() -> Dict[str, Type[BaseConnector]]:
    connectors = {}
    connectors_dir = Path(__file__).resolve().parent

    for _, module_name, _ in pkgutil.iter_modules([str(connectors_dir)]):
        if module_name.endswith("_connector") and module_name != "base_connector":
            try:
                module = importlib.import_module(f"{__package__}.{module_name}")
                for name in dir(module):
                    obj = getattr(module, name)
                    if (isinstance(obj, type) and
                        issubclass(obj, BaseConnector) and
                        obj != BaseConnector and
                        hasattr(obj, "platform_name") and
                        obj.platform_name):
                        connectors[obj.platform_name] = obj
            except ImportError:
                continue

    return connectors


class ConnectorRegistry:
    _instance = None
    _connectors: Dict[str, Type[BaseConnector]] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._auto_discover()
        return cls._instance

    def _auto_discover(self):
        self._connectors = discover_connectors()

    def register(self, connector_class: Type[BaseConnector]):
        if hasattr(connector_class, "platform_name") and connector_class.platform_name:
            self._connectors[connector_class.platform_name] = connector_class

    def get(self, platform_name: str) -> Type[BaseConnector]:
        return self._connectors.get(platform_name)

    def create(self, platform_name: str, **kwargs) -> BaseConnector:
        connector_class = self.get(platform_name)
        if connector_class:
            return connector_class(**kwargs)
        raise ValueError(f"No connector found for platform: {platform_name}")

    def list_platforms(self) -> list:
        return list(self._connectors.keys())


connector_registry = ConnectorRegistry()
