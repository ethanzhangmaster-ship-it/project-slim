"""Phase 4.1.4 — LTV Correlation Engine (DNA → LTV).

核心问题：
  什么 Creative DNA 元素与高 LTV 相关？

Phase 4.1.4 升级：
  - DNA 级 LTV 相关性分析
  - 新增 d7_ltv 时间窗
  - 新增 dna_ltv_correlation 系数
  - Hook 级 LTV 对比分析（e.g., rescue hook → $8.5 vs challenge → $2.1）

接入 E9.4/E9.7: IAPGenomeFitness + LearningEngine
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import LTVProfile


class LTVCorelationEngine:
    """DNA → LTV 相关性分析引擎。

    Phase 4.1.4 升级：从 Creative DNA 维度分析 LTV 相关性，
    识别哪些 DNA 元素（Hook / Reward / Visual）驱动高 LTV。
    """

    def __init__(self) -> None:
        self._profiles: dict[str, LTVProfile] = {}

    # ── Loading ────────────────────────────────────────────

    def load_from_player_data(
        self, player_genomes_path: Path | None = None
    ) -> int:
        """从玩家数据计算 LTV（Phase 4.1.4 升级：增加 d7_ltv）."""
        root = Path(__file__).parent.parent.parent.parent
        pgp = player_genomes_path or (
            root / "output" / "player_intelligence" / "player_genomes.json"
        )
        if not pgp.exists():
            return 0

        with open(pgp, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            players = data.get("players", list(data.values()))
        else:
            players = data

        # Group by creative_id
        cohorts: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for player in players:
            if not isinstance(player, dict):
                continue
            cid = player.get("creative_id", "")
            if cid:
                cohorts[cid].append(player)

        # Build LTV profiles
        for cid, cohort_players in cohorts.items():
            self._profiles[cid] = self._compute_ltv(cid, cohort_players)

        return len(self._profiles)

    def _compute_ltv(
        self, creative_id: str, players: list[dict[str, Any]]
    ) -> LTVProfile:
        """计算 LTV 画像（Phase 4.1.4 升级）."""
        n = len(players)
        if n == 0:
            return LTVProfile(creative_id=creative_id)

        d7_ltvs = []
        d30_ltvs = []
        d90_ltvs = []
        dna_contrib: dict[str, float] = defaultdict(float)

        for p in players:
            pd = p.get("payment_dna", {})
            if not isinstance(pd, dict):
                continue

            total_spend = float(pd.get("total_spend", 0))
            if total_spend > 0:
                d30_ltvs.append(total_spend)

            # Extract D7 LTV (estimate: 40% of D30 or from total_spend * 0.4)
            d7_ltvs.append(total_spend * 0.4)

            # Try to get LTV from player_genome
            pg = p.get("player_genome", {})
            if isinstance(pg, dict):
                ltv_data = pg.get("ltv", {})
                if isinstance(ltv_data, dict):
                    d30 = ltv_data.get("d30", ltv_data.get("d30_ltv", 0))
                    d90 = ltv_data.get("d90", ltv_data.get("d90_ltv", 0))
                    if d30 > 0:
                        d30_ltvs.append(float(d30))
                    if d90 > 0:
                        d90_ltvs.append(float(d90))

            # DNA contribution estimation
            arch = p.get("archetype", "")
            if arch and isinstance(arch, str):
                if arch.lower() == "collector":
                    dna_contrib["archetype:collector"] += total_spend
                elif arch.lower() == "power":
                    dna_contrib["archetype:power"] += total_spend
                elif arch.lower() == "progression":
                    dna_contrib["archetype:progression"] += total_spend

        avg_d7 = round(
            sum(d7_ltvs) / len(d7_ltvs), 2
        ) if d7_ltvs else 0.0

        avg_d30 = round(
            sum(d30_ltvs) / len(d30_ltvs), 2
        ) if d30_ltvs else 0.0

        avg_d90 = round(
            sum(d90_ltvs) / len(d90_ltvs), 2
        ) if d90_ltvs else 0.0

        projected = round(avg_d30 * 3.0, 2) if avg_d30 > 0 else 0.0

        # Normalize DNA contributions
        total_contrib = sum(dna_contrib.values())
        dna_contrib_norm = {
            k: round(v / total_contrib, 3)
            for k, v in dna_contrib.items()
        } if total_contrib > 0 else {}

        # DNA → LTV correlation: estimated from variance
        dna_ltv_corr = 0.0
        if len(d30_ltvs) >= 5:
            mean_val = sum(d30_ltvs) / len(d30_ltvs)
            variance = sum((x - mean_val) ** 2 for x in d30_ltvs) / len(d30_ltvs)
            # Correlation proxy: higher variance = more differentiated DNA
            dna_ltv_corr = min(variance / (mean_val + 1), 1.0) if mean_val > 0 else 0.0

        return LTVProfile(
            creative_id=creative_id,
            d7_ltv=avg_d7,
            d30_ltv=avg_d30,
            d90_ltv=avg_d90,
            projected_ltv=projected,
            ltv_confidence=round(min(n / 100.0, 1.0), 3),
            sample_size=n,
            dna_ltv_correlation=round(dna_ltv_corr, 3),
            dna_contribution=dna_contrib_norm,
        )

    def compute_dna_level_ltv_correlation(
        self,
        creative_dna_map: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Phase 4.1.4 核心：DNA 级 LTV 相关性分析。

        按 DNA 元素（Hook / Reward / Visual）分组，
        计算每组 DNA 的平均 LTV，找到高 LTV 的 DNA 模式。

        Args:
            creative_dna_map: {creative_id: {dna_dict}}

        Returns:
            {
                "hook:rescue": {"avg_d30_ltv": 8.5, "count": 120, "correlation": 0.82},
                "hook:challenge": {"avg_d30_ltv": 2.1, "count": 80, "correlation": 0.31},
                ...
            }
        """
        # Group creative IDs by DNA element
        dna_groups: dict[str, list[str]] = defaultdict(list)
        for cid, dna in creative_dna_map.items():
            for field in ["hook", "reward", "fantasy", "mechanism"]:
                val = dna.get(field, {})
                if isinstance(val, dict):
                    t = val.get("type", "")
                    if t:
                        key = f"{field}:{t}"
                        dna_groups[key].append(cid)
                elif isinstance(val, str) and val:
                    key = f"{field}:{val}"
                    dna_groups[key].append(cid)

        result: dict[str, dict[str, Any]] = {}
        for dna_key, creative_ids in dna_groups.items():
            ltvs = []
            for cid in creative_ids:
                profile = self._profiles.get(cid)
                if profile and profile.d30_ltv > 0:
                    ltvs.append(profile.d30_ltv)

            if ltvs:
                avg_ltv = sum(ltvs) / len(ltvs)
                # Correlation: how much this DNA element's LTV deviates from global mean
                all_ltvs = [
                    p.d30_ltv for p in self._profiles.values() if p.d30_ltv > 0
                ]
                global_mean = sum(all_ltvs) / len(all_ltvs) if all_ltvs else 0
                correlation = min(
                    abs(avg_ltv - global_mean) / max(global_mean, 0.01), 1.0
                )

                result[dna_key] = {
                    "avg_d30_ltv": round(avg_ltv, 2),
                    "count": len(ltvs),
                    "correlation": round(correlation, 3),
                    "vs_global": round(avg_ltv - global_mean, 2),
                }

        # Update DNA contribution in profiles
        for cid, profile in self._profiles.items():
            dna = creative_dna_map.get(cid, {})
            for field in ["hook", "reward", "fantasy", "mechanism"]:
                val = dna.get(field, {})
                if isinstance(val, dict):
                    t = val.get("type", "")
                    if t:
                        key = f"{field}:{t}"
                        if key in result:
                            profile.dna_contribution[key] = result[key]["correlation"]
                elif isinstance(val, str) and val:
                    key = f"{field}:{val}"
                    if key in result:
                        profile.dna_contribution[key] = result[key]["correlation"]

        return result

    def load_dna_contributions(
        self, creative_dna_path: Path | None = None
    ) -> int:
        """加载 DNA → LTV 贡献分析."""
        root = Path(__file__).parent.parent.parent.parent
        cdp = creative_dna_path or (
            root / "output" / "creative_learning" / "dna_weight_config.json"
        )
        if not cdp.exists():
            return 0

        with open(cdp, "r", encoding="utf-8") as f:
            weights = json.load(f)

        if isinstance(weights, dict):
            weights = weights.get("weights", {})

        loaded = 0
        for cid, profile in self._profiles.items():
            if weights:
                flat_weights = {}
                for arch, arch_weights in weights.items():
                    if isinstance(arch_weights, dict):
                        for k, v in arch_weights.items():
                            flat_weights[f"DNA:{arch}:{k}"] = round(float(v), 3)
                    elif isinstance(arch_weights, (int, float)):
                        flat_weights[f"DNA:{arch}"] = round(float(arch_weights), 3)
                if flat_weights:
                    profile.dna_contribution = flat_weights
                    loaded += 1

        return loaded

    # ── Query ──────────────────────────────────────────────

    def get(self, creative_id: str) -> LTVProfile | None:
        return self._profiles.get(creative_id)

    def get_all(self) -> list[LTVProfile]:
        return list(self._profiles.values())

    def get_by_tier(self, tier: str) -> list[LTVProfile]:
        """按 LTV 层级筛选."""
        return [p for p in self._profiles.values() if p.ltv_tier == tier]

    def get_high_ltv(self, min_d30: float = 5.0) -> list[LTVProfile]:
        return [p for p in self._profiles.values() if p.d30_ltv >= min_d30]

    def get_high_confidence(self, min_confidence: float = 0.5) -> list[LTVProfile]:
        return [p for p in self._profiles.values() if p.ltv_confidence >= min_confidence]

    def get_high_correlation_dna(self, min_corr: float = 0.5) -> list[LTVProfile]:
        """DNA LTV 相关性高的创意（Phase 4.1.4 新增）."""
        return [p for p in self._profiles.values() if p.dna_ltv_correlation >= min_corr]

    def rank_by_ltv(self, n: int = 10) -> list[LTVProfile]:
        return sorted(
            [p for p in self._profiles.values() if p.d30_ltv > 0],
            key=lambda p: p.d30_ltv,
            reverse=True,
        )[:n]

    def rank_by_dna_correlation(self, n: int = 10) -> list[LTVProfile]:
        """按 DNA LTV 相关性排序（Phase 4.1.4 新增）."""
        return sorted(
            [p for p in self._profiles.values() if p.dna_ltv_correlation > 0],
            key=lambda p: p.dna_ltv_correlation,
            reverse=True,
        )[:n]

    # ── Statistics ─────────────────────────────────────────

    def ltv_stats(self) -> dict[str, Any]:
        """全局 LTV 统计（Phase 4.1.4 升级）."""
        all_profiles = list(self._profiles.values())
        if not all_profiles:
            return {"total_creatives": 0}

        with_ltv = [p for p in all_profiles if p.d30_ltv > 0]
        high_confidence = self.get_high_confidence()
        high_corr = self.get_high_correlation_dna()

        return {
            "total_creatives": len(all_profiles),
            "with_ltv_data": len(with_ltv),
            "high_confidence": len(high_confidence),
            "high_dna_correlation": len(high_corr),
            "avg_d7_ltv": round(
                sum(p.d7_ltv for p in with_ltv) / max(1, len(with_ltv)), 2
            ),
            "avg_d30_ltv": round(
                sum(p.d30_ltv for p in with_ltv) / max(1, len(with_ltv)), 2
            ),
            "avg_d90_ltv": round(
                sum(p.d90_ltv for p in with_ltv if p.d90_ltv > 0)
                / max(1, len([p for p in with_ltv if p.d90_ltv > 0])), 2
            ),
            "avg_dna_ltv_correlation": round(
                sum(p.dna_ltv_correlation for p in all_profiles) / len(all_profiles), 3
            ),
            "by_tier": {
                "S": len(self.get_by_tier("S")),
                "A": len(self.get_by_tier("A")),
                "B": len(self.get_by_tier("B")),
                "C": len(self.get_by_tier("C")),
            },
            "top_ltv_creative": (
                max(with_ltv, key=lambda p: p.d30_ltv).creative_id
                if with_ltv else ""
            ),
        }