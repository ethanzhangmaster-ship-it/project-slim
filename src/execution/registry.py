"""P2.1 Execution Contract Layer — 执行能力注册表（Capability Registry）。

记录「哪个 ExecutionAction 由哪个 Provider 落地、需要什么权限」。
P2.2 的真实适配器（MAX / Meta / Play）上线时通过 register() 登记能力；
本层（P2.1）只消费这份表做安全校验，不调用任何 Provider。

permission 三档：
- "auto"       ：低风险动作可自动执行（仍需 validator 最终放行）
- "approval"   ：该动作无论风险都必须人工审批
- "blocked"    ：该动作在本案中禁止执行（黑名单）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .models import ExecutionAction


class Permission(str, Enum):
    AUTO = "auto"
    APPROVAL = "approval"
    BLOCKED = "blocked"


@dataclass
class Capability:
    """一个动作的执行能力描述。"""

    action: ExecutionAction
    provider: str
    permission: Permission = Permission.AUTO

    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "provider": self.provider,
            "permission": self.permission.value,
        }


class CapabilityRegistry:
    """动作 → 能力 的注册表（内存态，可序列化为 dict 落盘）。"""

    def __init__(self) -> None:
        self._caps: Dict[ExecutionAction, Capability] = {}
        self._providers: Dict[ExecutionAction, List[str]] = {}

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------
    def register(
        self,
        action: ExecutionAction,
        provider: str,
        permission: Permission = Permission.AUTO,
    ) -> Capability:
        cap = Capability(action=action, provider=provider, permission=permission)
        self._caps[action] = cap
        self._providers.setdefault(action, [])
        if provider not in self._providers[action]:
            self._providers[action].append(provider)
        return cap

    def register_many(self, specs: List[dict]) -> None:
        """批量注册，specs 元素形如
        {"action": ExecutionAction, "provider": str, "permission": Permission}。"""
        for spec in specs:
            self.register(
                spec["action"],
                spec["provider"],
                spec.get("permission", Permission.AUTO),
            )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def is_known(self, action: ExecutionAction) -> bool:
        """该动作是否有任何已注册的 Provider（未知动作必须 BLOCK）。"""
        return action in self._caps

    def get(self, action: ExecutionAction) -> Optional[Capability]:
        return self._caps.get(action)

    def permission_of(self, action: ExecutionAction) -> Optional[Permission]:
        cap = self._caps.get(action)
        return cap.permission if cap else None

    def providers_for(self, action: ExecutionAction) -> List[str]:
        return list(self._providers.get(action, []))

    def requires_approval(self, action: ExecutionAction) -> bool:
        """该动作是否强制需要人工审批（不论风险）。"""
        cap = self._caps.get(action)
        if cap is None:
            return False
        return cap.permission == Permission.APPROVAL

    def is_blocked(self, action: ExecutionAction) -> bool:
        cap = self._caps.get(action)
        if cap is None:
            return False
        return cap.permission == Permission.BLOCKED

    def all(self) -> Dict[str, Dict]:
        return {a.value: c.to_dict() for a, c in self._caps.items()}

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict:
        return {"capabilities": [c.to_dict() for c in self._caps.values()]}

    @classmethod
    def from_dict(cls, d: Dict) -> "CapabilityRegistry":
        reg = cls()
        for item in d.get("capabilities", []):
            reg.register(
                ExecutionAction(item["action"]),
                item["provider"],
                Permission(item.get("permission", "auto")),
            )
        return reg


__all__ = [
    "Permission",
    "Capability",
    "CapabilityRegistry",
]
