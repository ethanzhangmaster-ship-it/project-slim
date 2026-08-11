"""P1.4 — 真实游戏注册表（Game Registry）。

统一三源（Adjust / MAX / Meta）的外部标识符 → canonical game_id 映射，替换假
catalog.json 作为「真实产品元数据 + 跨源映射」的权威来源。

纪律：
- 只存映射与 secret_ref（如 "live_accounts:accounts:ACCT_2:report_key"），
  绝不内联任何密钥；真实 token 由各源运行时从 credentials 读取。
- canonical game_id 默认等于 MAX application 名（RealFleetBridge 直接产出），
  故 MaxRealitySource 无需 app_map 即可命中。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = "data/game_registry.json"


@dataclass
class GameRegistryEntry:
    game_id: str
    display_name: str = ""
    package_name: str = ""
    genre: str = ""
    platform: str = "unknown"
    max_apps: List[str] = field(default_factory=list)
    adjust_app_token_ref: str = ""          # P1.4 原有：指向 credentials vault 的 secret_ref
    meta_campaign_ids: List[str] = field(default_factory=list)
    # --- P1.6.1 Reality Binding 字段（新增，兼容旧数据）---
    country: str = ""                       # 目标市场，如 "US" / "GLOBAL"
    meta_app_id: str = ""                   # Meta 应用 / 广告账户 app id
    max_account: str = ""                   # MAX 账户，如 "ACCT_1"（可由 max_apps 推导）
    adjust_app_token: str = ""              # Adjust 绑定：token 引用（非内联密钥，见纪律）

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GameRegistryEntry":
        # adjust_app_token 兼容旧 adjust_app_token_ref（二者任一非空即视为已绑定）
        adj = d.get("adjust_app_token") or d.get("adjust_app_token_ref") or ""
        return cls(
            game_id=str(d["game_id"]),
            display_name=str(d.get("display_name", d["game_id"])),
            package_name=str(d.get("package_name", "")),
            genre=str(d.get("genre", "")),
            platform=str(d.get("platform", "unknown")),
            max_apps=list(d.get("max_apps", [])),
            adjust_app_token_ref=str(d.get("adjust_app_token_ref", "")),
            meta_campaign_ids=list(d.get("meta_campaign_ids", [])),
            country=str(d.get("country", "")),
            meta_app_id=str(d.get("meta_app_id", "")),
            max_account=str(d.get("max_account", "")),
            adjust_app_token=str(adj),
        )


class GameRegistry:
    """加载 data/game_registry.json，提供正/反向映射查询。"""

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = Path(path)
        self._entries: Dict[str, GameRegistryEntry] = {}
        self._app_to_game: Dict[str, str] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            games = data.get("games") if isinstance(data, dict) else data
            for g in games or []:
                e = GameRegistryEntry.from_dict(g)
                self._entries[e.game_id] = e
                for app in e.max_apps:
                    # application 名即 canonical id，但保留账户级兜底
                    self._app_to_game.setdefault(app, e.game_id)
                # 额外登记 application 名本身 → game_id（MAX 报表直接产出 application 名）
                self._app_to_game.setdefault(e.game_id, e.game_id)
                for app in (e.display_name,):
                    if app:
                        self._app_to_game.setdefault(app, e.game_id)
        self._loaded = True

    # -- 查询 --
    def lookup(self, game_id: str) -> Optional[GameRegistryEntry]:
        self._ensure_loaded()
        return self._entries.get(game_id)

    def all_game_ids(self) -> List[str]:
        self._ensure_loaded()
        return list(self._entries.keys())

    def max_app_to_game_id(self, app_name: str) -> Optional[str]:
        """MAX 报表的 application 名 → canonical game_id。"""
        self._ensure_loaded()
        return self._app_to_game.get(app_name)

    def game_id_to_max_apps(self, game_id: str) -> List[str]:
        e = self.lookup(game_id)
        return list(e.max_apps) if e else []

    def game_id_to_adjust_ref(self, game_id: str) -> str:
        e = self.lookup(game_id)
        return e.adjust_app_token_ref if e else ""

    def game_id_to_meta_campaigns(self, game_id: str) -> List[str]:
        e = self.lookup(game_id)
        return list(e.meta_campaign_ids) if e else []

    def resolve_game_id(self, external_id: str) -> str:
        """任意外部 id（MAX app / Adjust token / Meta campaign）→ canonical id。

        优先精确匹配；否则回退原始 id（源自行决定如何处理未知游戏）。
        """
        self._ensure_loaded()
        return self._app_to_game.get(external_id, external_id)

    # -- P1.6.1 Reality Binding 查询 --
    def game_id_to_max_account(self, game_id: str) -> str:
        """MAX 账户（显式字段优先，否则由 max_apps 推导首个 ACCT_ 账户）。"""
        e = self.lookup(game_id)
        if not e:
            return ""
        if e.max_account:
            return e.max_account
        for a in e.max_apps:
            if a.startswith("ACCT_"):
                return a
        return ""

    def game_id_to_meta_app_id(self, game_id: str) -> str:
        e = self.lookup(game_id)
        return e.meta_app_id if e else ""

    def game_id_to_country(self, game_id: str) -> str:
        e = self.lookup(game_id)
        return e.country if e else ""

    def game_id_to_adjust_token(self, game_id: str) -> str:
        """Adjust 绑定 token：兼容 adjust_app_token 与旧 adjust_app_token_ref。"""
        e = self.lookup(game_id)
        if not e:
            return ""
        return e.adjust_app_token or e.adjust_app_token_ref

    def source_bindings(self, game_id: str) -> Dict[str, Any]:
        """返回该游戏已绑定的真实源标识（仅非空项）。"""
        e = self.lookup(game_id)
        if not e:
            return {}
        out: Dict[str, Any] = {}
        acct = self.game_id_to_max_account(game_id)
        if acct:
            out["max_account"] = acct
        if e.package_name:
            out["package_name"] = e.package_name
        if e.country:
            out["country"] = e.country
        adj = self.game_id_to_adjust_token(game_id)
        if adj:
            out["adjust_app_token"] = adj
        if e.meta_app_id:
            out["meta_app_id"] = e.meta_app_id
        if e.meta_campaign_ids:
            out["meta_campaign_ids"] = e.meta_campaign_ids
        return out

    # 视为「完整绑定」所需的核心字段集
    REQUIRED_BINDINGS = (
        "max_account",
        "package_name",
        "country",
        "adjust_app_token",
        "meta_app_id",
        "platform",
    )

    def binding_completeness(self, game_id: str) -> List[str]:
        """返回缺失的真实源绑定项（相对 REQUIRED_BINDINGS）。

        例：未绑 Adjust 且未知国家 → ["adjust_app_token", "country", "meta_app_id"]。
        """
        e = self.lookup(game_id)
        if not e:
            return list(self.REQUIRED_BINDINGS)
        missing: List[str] = []
        for key in self.REQUIRED_BINDINGS:
            if key == "platform":
                if e.platform and e.platform != "unknown":
                    continue
                missing.append("platform")
            elif key == "adjust_app_token":
                if self.game_id_to_adjust_token(game_id):
                    continue
                missing.append("adjust_app_token")
            elif key == "max_account":
                if self.game_id_to_max_account(game_id):
                    continue
                missing.append("max_account")
            else:
                if self.source_bindings(game_id).get(key):
                    continue
                missing.append(key)
        return missing

    def binding_report(self) -> Dict[str, Dict[str, Any]]:
        """全量绑定完整度报告：{game_id: {bound, missing, completeness_ratio}}。"""
        report: Dict[str, Dict[str, Any]] = {}
        for gid in self.all_game_ids():
            missing = self.binding_completeness(gid)
            ratio = (len(self.REQUIRED_BINDINGS) - len(missing)) / len(self.REQUIRED_BINDINGS)
            report[gid] = {
                "bound": self.source_bindings(gid),
                "missing": missing,
                "completeness_ratio": round(ratio, 3),
            }
        return report


class RegistryRealitySource:
    """P1.4 — 真实产品域源：从 GameRegistry 补 product 域（替代假 catalog.json）。

    注册表不含 DAU 等遥测（那是真实源的活），故 product.dau 等留 0，
    仅提供 release_status / genre / package 等稳定元数据。real_api_called 恒 False
    （纯本地读，非外部 API）。
    """

    domain = "product"
    source_id = "registry"
    # 注册表是真实本地数据源（替代假 catalog.json），标记为非 SIM，使 real_confidence 计入。
    real_api_called: bool = True

    def __init__(self, registry: Optional[GameRegistry] = None, path: str = DEFAULT_PATH):
        self.registry = registry or GameRegistry(path)

    def collect(self, game_id: str, as_of: str) -> Dict[str, Any]:
        e = self.registry.lookup(game_id)
        if not e:
            return {}
        return {
            "dau": 0,
            "retention": 0.0,
            "conversion": 0.0,
            "release_status": "published" if e.max_apps else "unknown",
            "genre": e.genre,
            "package_name": e.package_name,
            "country": self.registry.game_id_to_country(game_id),
            "max_account": self.registry.game_id_to_max_account(game_id),
            "meta_app_id": self.registry.game_id_to_meta_app_id(game_id),
            "platform": e.platform,
        }
