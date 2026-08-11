"""DNA Performance Mapper — Video DNA 与真实买量结果关联

核心：把视频 DNA 和真实买量结果关联。

输入：
- Video DNA: {hook, subject, gameplay, reward}
- Performance: {ctr, cpi, roi}

输出：
- creative_performance_library.json
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

import numpy as np

from ..config import OUTPUT_DIR


class DNAPerformanceMapper:
    """DNA 与 Performance 关联器"""

    def __init__(self):
        self.performance_library: List[dict] = []

    def map(self, dna_data: List[dict], performance_data: List[dict]) -> List[dict]:
        """关联 DNA 和 Performance"""
        # 构建索引
        dna_index = {d.get("creative_id", ""): d for d in dna_data}
        perf_index = {p.get("creative_id", ""): p for p in performance_data}

        mapped = []
        for creative_id in set(dna_index.keys()) & set(perf_index.keys()):
            dna = dna_index[creative_id]
            perf = perf_index[creative_id]

            mapped.append({
                "creative_id": creative_id,
                "video_name": dna.get("video_name", ""),
                "platform": dna.get("platform", ""),
                "dna": dna.get("dna", {}),
                "performance": perf.get("performance", {}),
                "raw": {
                    "spend": dna.get("spend", 0),
                    "impressions": dna.get("impressions", 0),
                    "clicks": dna.get("clicks", 0),
                    "installs": dna.get("installs", 0),
                },
            })

        self.performance_library = mapped
        return mapped

    def aggregate_by_dna_pattern(self) -> List[dict]:
        """按 DNA 模式聚合表现"""
        patterns = defaultdict(list)

        for item in self.performance_library:
            dna = item.get("dna", {})
            perf = item.get("performance", {})

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
                "d30_roi": perf.get("d30_roi", 0),
                "efficiency_score": perf.get("efficiency_score", 0),
            })

        aggregated = []
        for (hook, gameplay, reward, subject), items in patterns.items():
            ctrs = [i["ctr"] for i in items]
            cpis = [i["cpi"] for i in items if i["cpi"] < 10]
            d7_rois = [i["d7_roi"] for i in items]
            d30_rois = [i["d30_roi"] for i in items]
            efficiency_scores = [i["efficiency_score"] for i in items]

            aggregated.append({
                "dna_pattern": {
                    "hook": hook,
                    "gameplay": gameplay,
                    "reward": reward,
                    "subject": subject,
                },
                "performance": {
                    "avg_ctr": round(np.mean(ctrs), 2),
                    "median_ctr": round(np.median(ctrs), 2),
                    "avg_cpi": round(np.mean(cpis), 2),
                    "median_cpi": round(np.median(cpis), 2),
                    "avg_d7_roi": round(np.mean(d7_rois), 3),
                    "avg_d30_roi": round(np.mean(d30_rois), 3),
                    "avg_efficiency_score": round(np.mean(efficiency_scores), 1),
                },
                "sample_count": len(items),
                "creatives": [i for i in items],
            })

        # 按效率评分排序
        aggregated.sort(key=lambda x: -x["performance"]["avg_efficiency_score"])
        return aggregated

    def get_top_dna_patterns(self, n: int = 10) -> List[dict]:
        """获取 Top DNA 模式"""
        patterns = self.aggregate_by_dna_pattern()
        return patterns[:n]

    def save_library(self, filename: str = "creative_performance_library.json") -> Path:
        """保存 Performance Library"""
        output_path = OUTPUT_DIR / "v38_1" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        aggregated = self.aggregate_by_dna_pattern()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_creatives": len(self.performance_library),
                "total_patterns": len(aggregated),
                "library": self.performance_library,
                "dna_patterns": aggregated,
                "top_patterns": self.get_top_dna_patterns(10),
            }, f, ensure_ascii=False, indent=2)

        return output_path

    def load_library(self, path: Path) -> bool:
        """加载 Performance Library"""
        if not path.exists():
            return False

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.performance_library = data.get("library", [])
        return True

    def get_dna_pattern_stats(self, hook_type: str = None, gameplay: str = None,
                              subject: str = None) -> Optional[dict]:
        """获取特定 DNA 模式的统计"""
        filtered = []
        for item in self.performance_library:
            dna = item.get("dna", {})
            if hook_type and dna.get("hook") != hook_type:
                continue
            if gameplay and dna.get("gameplay") != gameplay:
                continue
            if subject and dna.get("subject") != subject:
                continue
            filtered.append(item["performance"])

        if not filtered:
            return None

        ctrs = [f["ctr"] for f in filtered]
        cpis = [f["cpi"] for f in filtered if f["cpi"] < 10]
        d7_rois = [f["d7_roi"] for f in filtered]

        return {
            "pattern": {"hook": hook_type, "gameplay": gameplay, "subject": subject},
            "sample_count": len(filtered),
            "avg_ctr": round(np.mean(ctrs), 2),
            "avg_cpi": round(np.mean(cpis), 2),
            "avg_d7_roi": round(np.mean(d7_rois), 3),
            "min_ctr": min(ctrs),
            "max_ctr": max(ctrs),
        }
