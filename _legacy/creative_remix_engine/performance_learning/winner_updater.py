"""Winner Updater — 自动更新 Winner DNA

功能：
- 根据真实 UA 数据自动更新 Winner DNA 权重
- 发现新的 Performance Archetype
- 更新 winner_database.json

例如：
过去100个广告中，发现：
Top ROI: Hook=Transformation, Gameplay=Merge, Reward=Dragon Evolution
自动提升 hook_weight +15%, reward_weight +20%
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

import numpy as np

from ..config import OUTPUT_DIR, MEMORY_DIR
from ..winner_intelligence.winner_database import WinnerDatabase


class WinnerUpdater:
    """Winner DNA 自动更新引擎"""

    def __init__(self, performance_db_path: Optional[Path] = None,
                 winner_db_path: Optional[Path] = None):
        if winner_db_path is None:
            winner_db_path = MEMORY_DIR / "winner_database_v38.json"
        self.winner_db = WinnerDatabase(winner_db_path)
        self.performance_db_path = performance_db_path

    def update_from_performance_data(self, performance_data: List[dict]) -> dict:
        """从表现数据更新 Winner DNA"""
        print("[WinnerUpdater] Analyzing performance data...")

        # 1. 识别 Top DNA 模式
        top_patterns = self._identify_top_dna_patterns(performance_data)
        print(f"  Found {len(top_patterns)} top DNA patterns")

        # 2. 更新权重
        weight_changes = self._calculate_weight_changes(top_patterns)

        # 3. 更新 Winner 数据库
        self._update_winner_database(performance_data, top_patterns)

        # 4. 更新 Archetype
        new_archetypes = self._update_archetypes(top_patterns)

        # 5. 保存更新日志
        self._save_update_log(weight_changes, top_patterns, new_archetypes)

        return {
            "top_patterns": top_patterns,
            "weight_changes": weight_changes,
            "new_archetypes": new_archetypes,
            "updated_winners": len(performance_data),
        }

    def _identify_top_dna_patterns(self, data: List[dict], top_n: int = 10) -> List[dict]:
        """识别 Top DNA 模式"""
        patterns = defaultdict(list)

        for item in data:
            dna = item.get("dna", {})
            perf = item.get("performance", {})

            if not dna or not perf:
                continue

            # 构建模式键
            pattern_key = (
                dna.get("hook", "unknown"),
                dna.get("gameplay", "unknown"),
                dna.get("reward", "unknown"),
                dna.get("subject", "unknown"),
            )

            patterns[pattern_key].append({
                "ctr": perf.get("ctr", 0),
                "cpi": perf.get("cpi", float('inf')),
                "d7_roi": perf.get("d7_roi", 0),
                "efficiency_score": perf.get("efficiency_score", 0),
                "creative_id": item.get("creative_id", ""),
            })

        aggregated = []
        for (hook, gameplay, reward, subject), items in patterns.items():
            ctrs = [i["ctr"] for i in items]
            cpis = [i["cpi"] for i in items if i["cpi"] < 10]
            d7_rois = [i["d7_roi"] for i in items]
            efficiency_scores = [i["efficiency_score"] for i in items]

            if len(items) < 2:
                continue

            aggregated.append({
                "dna_pattern": {
                    "hook": hook,
                    "gameplay": gameplay,
                    "reward": reward,
                    "subject": subject,
                },
                "performance": {
                    "avg_ctr": round(np.mean(ctrs), 2),
                    "avg_cpi": round(np.mean(cpis), 2),
                    "avg_d7_roi": round(np.mean(d7_rois), 3),
                    "avg_efficiency": round(np.mean(efficiency_scores), 1),
                },
                "sample_count": len(items),
                "creatives": [i["creative_id"] for i in items],
            })

        # 按效率评分排序
        aggregated.sort(key=lambda x: -x["performance"]["avg_efficiency"])
        return aggregated[:top_n]

    def _calculate_weight_changes(self, top_patterns: List[dict]) -> dict:
        """计算权重变化"""
        weight_changes = {
            "hook_weights": {},
            "gameplay_weights": {},
            "reward_weights": {},
            "subject_weights": {},
        }

        # 统计每个维度的平均表现
        hook_stats = defaultdict(list)
        gameplay_stats = defaultdict(list)
        reward_stats = defaultdict(list)
        subject_stats = defaultdict(list)

        for pattern in top_patterns:
            dna = pattern["dna_pattern"]
            perf = pattern["performance"]

            hook_stats[dna["hook"]].append(perf["avg_efficiency"])
            gameplay_stats[dna["gameplay"]].append(perf["avg_efficiency"])
            reward_stats[dna["reward"]].append(perf["avg_efficiency"])
            subject_stats[dna["subject"]].append(perf["avg_efficiency"])

        # 计算相对权重
        avg_efficiency = np.mean([p["performance"]["avg_efficiency"] for p in top_patterns])

        for hook, scores in hook_stats.items():
            hook_avg = np.mean(scores)
            diff = hook_avg - avg_efficiency
            pct_change = min(30, max(-15, diff / avg_efficiency * 100))
            weight_changes["hook_weights"][hook] = round(pct_change, 1)

        for gameplay, scores in gameplay_stats.items():
            gp_avg = np.mean(scores)
            diff = gp_avg - avg_efficiency
            pct_change = min(30, max(-15, diff / avg_efficiency * 100))
            weight_changes["gameplay_weights"][gameplay] = round(pct_change, 1)

        for reward, scores in reward_stats.items():
            rw_avg = np.mean(scores)
            diff = rw_avg - avg_efficiency
            pct_change = min(30, max(-15, diff / avg_efficiency * 100))
            weight_changes["reward_weights"][reward] = round(pct_change, 1)

        for subject, scores in subject_stats.items():
            sb_avg = np.mean(scores)
            diff = sb_avg - avg_efficiency
            pct_change = min(30, max(-15, diff / avg_efficiency * 100))
            weight_changes["subject_weights"][subject] = round(pct_change, 1)

        return weight_changes

    def _update_winner_database(self, data: List[dict], top_patterns: List[dict]):
        """更新 Winner 数据库"""
        top_creatives = set()
        for pattern in top_patterns:
            top_creatives.update(pattern["creatives"])

        for item in data:
            creative_id = item.get("creative_id", "")
            dna = item.get("dna", {})
            perf = item.get("performance", {})

            if creative_id in top_creatives or perf.get("quality_flag") == "winner":
                self.winner_db.add_winner(
                    creative_id=creative_id,
                    video_name=item.get("video_name", ""),
                    ctr=perf.get("ctr", 0),
                    cpi=perf.get("cpi", 0),
                    d7_roi=perf.get("d7_roi", 0),
                    d30_roi=perf.get("d30_roi", 0),
                    spend=item.get("spend", 0),
                    impressions=item.get("impressions", 0),
                    dna=dna,
                )

    def _update_archetypes(self, top_patterns: List[dict]) -> List[dict]:
        """更新 Archetype"""
        new_archetypes = []

        for pattern in top_patterns:
            dna = pattern["dna_pattern"]
            perf = pattern["performance"]

            archetype_name = f"Real_{dna['subject']}_{dna['hook']}_{dna['gameplay']}"
            new_archetypes.append({
                "name": archetype_name,
                "dna_pattern": dna,
                "avg_ctr": perf["avg_ctr"],
                "avg_cpi": perf["avg_cpi"],
                "avg_d7_roi": perf["avg_d7_roi"],
                "sample_count": pattern["sample_count"],
            })

        return new_archetypes

    def _save_update_log(self, weight_changes: dict, top_patterns: List[dict],
                         new_archetypes: List[dict]):
        """保存更新日志"""
        output_path = OUTPUT_DIR / "v38_1" / "winner_update_log.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "weight_changes": weight_changes,
                "top_patterns": top_patterns,
                "new_archetypes": new_archetypes,
                "winner_count": len(self.winner_db.winners),
            }, f, ensure_ascii=False, indent=2)

    def get_winner_dna_evolution(self) -> dict:
        """获取 Winner DNA 进化记录"""
        return {
            "total_winners": len(self.winner_db.winners),
            "patterns": self.winner_db.get_winner_dna_patterns(),
        }
