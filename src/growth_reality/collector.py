"""E17.1 Growth Reality Hub — 采集层。

职责：
- 定义 RealitySource 接入协议（每个部门 reality 的接入点）
- RealityCollector 把多个源按 game_id 汇总成原始 domain dict
- 内置两个源：
    DemoRealitySource  —— SIM 演示源（确定性、real_api_called=False）
    CatalogRealitySource —— 真实目录桥（只读 data/catalog.json，补 product 域）

SIM 纪律：任何源若触发真实 API（Adjust/MAX/Meta/Play），必须显式把
collector.real_api_called 置 True；内置源均为 False。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

VALID_DOMAINS = ("revenue", "acquisition", "aso", "creative", "product")


@runtime_checkable
class RealitySource(Protocol):
    """部门 reality 接入点。domain ∈ {revenue,acquisition,aso,creative,product}。"""

    domain: str
    source_id: str

    def collect(self, game_id: str, as_of: str) -> Dict[str, Any]:
        """返回该 domain 的原始字段 dict；无数据返回 {}。"""
        ...


class RealityCollector:
    def __init__(
        self,
        sources: Optional[List[RealitySource]] = None,
        *,
        mode: str = "sim",
        production_sources: Optional[List[RealitySource]] = None,
    ):
        if sources is not None:
            self.sources: List[RealitySource] = list(sources)
        elif mode == "production" and production_sources:
            # P1.1：生产模式直接吃真实源（Adjust/MAX/...），SIM 默认不动
            self.sources = list(production_sources)
        else:
            self.sources = [DemoRealitySource(), CatalogRealitySource()]
        self.real_api_called: bool = False
        self.mode: str = mode

    def add_source(self, source: RealitySource) -> None:
        self.sources.append(source)

    def collect_game(self, game_id: str, as_of: str) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        src_ids: List[str] = []
        real_domains: List[str] = []
        for s in self.sources:
            try:
                data = s.collect(game_id, as_of)
            except Exception:
                data = {}
            if not data:
                continue
            # 多域打包源：顶层键全是合法 domain → 摊开到各 domain
            bundle = [k for k in data.keys() if k in VALID_DOMAINS]
            if bundle and len(bundle) == len(data):
                for k in bundle:
                    merged.setdefault(k, {}).update(data[k])
            else:
                merged.setdefault(s.domain, {}).update(data)
                bundle = [s.domain] if s.domain in VALID_DOMAINS else []
            src_ids.append(s.source_id)
            # P1.1：源若真打了真实 API，把 flag 汇聚到 collector 层
            if getattr(s, "real_api_called", False):
                self.real_api_called = True
                # P1.4：记录该源贡献的真实域，供 normalizer 算真实置信度/归因
                for k in bundle:
                    if k not in real_domains:
                        real_domains.append(k)
        return {
            "game_id": game_id,
            "as_of": as_of,
            "domains": merged,
            "sources": src_ids,
            "real_domains": real_domains,
        }

    def collect_fleet(self, game_ids: List[str], as_of: str) -> Dict[str, Dict[str, Any]]:
        return {g: self.collect_game(g, as_of) for g in game_ids}


# --------------------------------------------------------------------------- #
# SIM 演示源（确定性，离收入最近的全域假数据）
# --------------------------------------------------------------------------- #
def _pseudo(game_id: str, salt: str) -> float:
    """稳定 float ∈ [0,1)，跨进程一致（seed 无关），满足确定性要求。"""
    h = hashlib.sha256(f"{game_id}:{salt}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class DemoRealitySource:
    """SIM 演示：为任意 game_id 生成五域确定性假数据。

    覆盖全部 5 个 domain，用于验证 Hub 全链路；real_api_called 恒 False。
    """

    domain = "demo"  # 占位，实际一次性产出全部域
    source_id = "demo_sim"

    def collect(self, game_id: str, as_of: str) -> Dict[str, Any]:
        p = _pseudo
        revenue = {
            "daily_revenue": round(p(game_id, "rev") * 2000 + 50, 2),
            "payer_count": int(p(game_id, "pay") * 500 + 5),
            "ltv": round(p(game_id, "ltv") * 30 + 1, 2),
        }
        acquisition = {
            "spend": round(p(game_id, "spend") * 800 + 20, 2),
            "installs": int(p(game_id, "inst") * 3000 + 50),
            "cpi": round(p(game_id, "cpi") * 3 + 0.5, 2),
        }
        aso = {
            "ranking": int(p(game_id, "rank") * 200 + 1),
            "store_cvr": round(p(game_id, "cvr") * 0.08 + 0.01, 4),
            "rating": round(p(game_id, "rating") * 1.5 + 3.0, 2),
            "review_velocity": round(p(game_id, "rv") * 20, 2),
        }
        creative = {
            "ctr": round(p(game_id, "ctr") * 0.04 + 0.005, 4),
            "fatigue_score": round(p(game_id, "fat") * 1.0, 3),
            "creative_score": round(p(game_id, "cs") * 100, 2),
        }
        product = {
            "dau": int(p(game_id, "dau") * 20000 + 200),
            "retention": round(p(game_id, "ret") * 0.4 + 0.1, 3),
            "conversion": round(p(game_id, "conv") * 0.05 + 0.005, 4),
        }
        # demo 源一次性返回所有 5 域，collector 按 domain 名拆放
        return {
            "revenue": revenue,
            "acquisition": acquisition,
            "aso": aso,
            "creative": creative,
            "product": product,
        }


# --------------------------------------------------------------------------- #
# 真实目录桥（只读 data/catalog.json，补 product 域 + release 状态）
# --------------------------------------------------------------------------- #
class CatalogRealitySource:
    """真实桥：读取 data/catalog.json，为已知游戏补 product 域 + release 状态。

    目录无 metrics，仅 status（development/published），故 product.dau 等留 0，
    这正是数据中台要暴露的「覆盖盲区」。real_api_called 恒 False（纯本地读）。
    """

    domain = "product"
    source_id = "catalog"

    def __init__(self, catalog_path: str = "data/catalog.json"):
        self.catalog_path = Path(catalog_path)
        self._index: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.catalog_path.exists():
            try:
                data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            except Exception:
                data = []
            games = data if isinstance(data, list) else data.get("games") or []
            for g in games:
                self._index[g.get("game_id")] = g
        self._loaded = True

    def collect(self, game_id: str, as_of: str) -> Dict[str, Any]:
        self._ensure_loaded()
        g = self._index.get(game_id)
        if not g:
            return {}
        status = g.get("status", "unknown")
        # 仅 published 视为在跑量，development 视为未上线（product 信号弱）
        dau = int(g.get("metrics_dau", 0)) if g.get("metrics_dau") else 0
        return {
            "dau": dau,
            "retention": 0.0,
            "conversion": 0.0,
            "release_status": status,
        }
