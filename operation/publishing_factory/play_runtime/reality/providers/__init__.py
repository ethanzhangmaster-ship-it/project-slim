"""E15.2 Reality Providers — 每个 Provider 只负责一类 Google Play 数据.

统一契约:
- 输入 package_name, 输出对应 dataclass (ReleaseStatus / StabilityMetrics / StoreMetrics)
- API 失败绝不抛出 → 返回 source="fallback" 的空壳结构 (package 级隔离)
"""

from .release import ReleaseProvider
from .stability import StabilityProvider
from .store import StoreProvider

__all__ = ["ReleaseProvider", "StabilityProvider", "StoreProvider"]
