"""Export Module — 机器可读数据导出

导出:
- creative_dna.json: 所有 winner 的 DNA 数据
- generation_constraints.json: 生成约束 (供 prompt builder 使用)
- performance_report.json: 汇总统计
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ..config import OUTPUT_DIR, REPORTS_DIR, ensure_dirs


class DataExporter:
    """数据导出器"""

    def export_all(self, pools_data: Optional[Dict] = None,
                   dna_data: Optional[Dict] = None) -> Dict[str, Path]:
        """导出所有机器可读数据

        Args:
            pools_data: Winner pools 数据
            dna_data: DNA 数据

        Returns:
            {"creative_dna": Path, "constraints": Path, "report": Path}
        """
        ensure_dirs()

        if pools_data is None:
            pools_data = self._load_pools()
        if dna_data is None:
            dna_data = self._load_dna()

        paths = {}
        paths["creative_dna"] = self.export_creative_dna(dna_data)
        paths["constraints"] = self.export_generation_constraints(dna_data)
        paths["report"] = self.export_performance_report(pools_data, dna_data)

        return paths

    def export_creative_dna(self, dna_data: Optional[Dict] = None) -> Path:
        """导出 creative_dna.json — 所有 winner DNA

        格式:
        {
            "version": "2.1.8",
            "exported_at": "...",
            "winners": [{asset_id, dna, performance}, ...]
        }
        """
        if dna_data is None:
            dna_data = self._load_dna()

        output = {
            "version": "2.1.8",
            "exported_at": datetime.now().isoformat(),
            "total": dna_data.get("total", 0),
            "winners": dna_data.get("winners", []),
        }

        path = OUTPUT_DIR / "creative_dna.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"[Export] creative_dna.json: {output['total']} winners")
        return path

    def export_generation_constraints(self, dna_data: Optional[Dict] = None) -> Path:
        """导出 generation_constraints.json — 生成硬约束

        从 Top Winner DNA 中提取共性，生成硬约束:
        - gameplay_ratio 范围
        - 必须包含的元素类型
        - 风格约束
        """
        if dna_data is None:
            dna_data = self._load_dna()

        winners = dna_data.get("winners", [])

        # 统计 DNA 共性
        gameplay_ratios = []
        gameplay_types = {}
        reward_types = {}
        color_palettes = {}
        render_styles = {}

        for w in winners:
            dna = w.get("dna", {})
            comp = dna.get("composition", {})
            gp_ratio = comp.get("gameplay_area", {}).get("ratio", 0)
            if gp_ratio > 0:
                gameplay_ratios.append(gp_ratio)

            gp_type = dna.get("gameplay", {}).get("type", "")
            if gp_type:
                gameplay_types[gp_type] = gameplay_types.get(gp_type, 0) + 1

            rw_type = dna.get("reward", {}).get("type", "")
            if rw_type:
                reward_types[rw_type] = reward_types.get(rw_type, 0) + 1

            style = dna.get("style", {})
            cp = style.get("color_palette", "")
            if cp:
                color_palettes[cp] = color_palettes.get(cp, 0) + 1
            rs = style.get("render_style", "")
            if rs:
                render_styles[rs] = render_styles.get(rs, 0) + 1

        # 构建约束
        constraints = {
            "version": "2.1.8",
            "exported_at": datetime.now().isoformat(),
            "based_on_winners": len(winners),
            "composition": {
                "gameplay_ratio": {
                    "min": round(min(gameplay_ratios) - 0.10, 2) if gameplay_ratios else 0.30,
                    "max": round(max(gameplay_ratios) + 0.10, 2) if gameplay_ratios else 0.70,
                    "avg": round(sum(gameplay_ratios) / len(gameplay_ratios), 2) if gameplay_ratios else 0.50,
                },
            },
            "gameplay": {
                "preferred_types": sorted(gameplay_types, key=gameplay_types.get, reverse=True)[:3],
                "distribution": gameplay_types,
            },
            "reward": {
                "preferred_types": sorted(reward_types, key=reward_types.get, reverse=True)[:3],
                "distribution": reward_types,
            },
            "style": {
                "preferred_palettes": sorted(color_palettes, key=color_palettes.get, reverse=True)[:3],
                "preferred_render": sorted(render_styles, key=render_styles.get, reverse=True)[:2],
                "palette_distribution": color_palettes,
                "render_distribution": render_styles,
            },
            "hard_constraints": {
                "min_gameplay_ratio": 0.30,
                "required_render_style": sorted(render_styles, key=render_styles.get, reverse=True)[0] if render_styles else "3d_cartoon",
                "banned_elements": ["text_heavy", "screenshot", "phone_frame"],
            },
        }

        path = OUTPUT_DIR / "generation_constraints.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(constraints, f, ensure_ascii=False, indent=2)

        print(f"[Export] generation_constraints.json")
        return path

    def export_performance_report(self, pools_data: Optional[Dict] = None,
                                  dna_data: Optional[Dict] = None) -> Path:
        """导出 performance_report.json — 汇总统计"""
        if pools_data is None:
            pools_data = self._load_pools()
        if dna_data is None:
            dna_data = self._load_dna()

        # 汇总
        all_winners = []
        for pool in pools_data.values():
            all_winners.extend(pool)

        total_spend = sum(w.get("spend", 0) for w in all_winners)
        total_revenue = sum(w.get("all_revenue", 0) for w in all_winners)
        total_installs = sum(w.get("installs", 0) for w in all_winners)

        report = {
            "version": "2.1.8",
            "exported_at": datetime.now().isoformat(),
            "summary": {
                "total_ads_analyzed": self._get_total_ads(),
                "total_image_ads": self._get_image_ads_count(),
                "winners": {
                    "scale": len(pools_data.get("scale", [])),
                    "efficiency": len(pools_data.get("efficiency", [])),
                    "pattern": len(pools_data.get("pattern", [])),
                    "total_unique": len(all_winners),
                },
                "performance": {
                    "total_spend": round(total_spend, 2),
                    "total_revenue": round(total_revenue, 2),
                    "total_installs": total_installs,
                    "overall_roas": round(total_revenue / total_spend, 3) if total_spend > 0 else 0,
                    "avg_cpi": round(total_spend / total_installs, 2) if total_installs > 0 else 0,
                },
                "dna_coverage": {
                    "winners_with_dna": dna_data.get("total", 0),
                    "dna_method": "rule_based",  # 或 "vision_api"
                },
            },
            "top_performers": [
                {
                    "asset_id": w.get("asset_id", ""),
                    "spend": w.get("spend", 0),
                    "all_revenue": w.get("all_revenue", 0),
                    "iap_roas": w.get("iap_roas", 0),
                    "winner_score": w.get("winner_score", 0),
                }
                for w in sorted(all_winners,
                               key=lambda x: x.get("winner_score", 0),
                               reverse=True)[:10]
            ],
        }

        path = OUTPUT_DIR / "performance_report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"[Export] performance_report.json")
        return path

    def _load_pools(self) -> Dict[str, List]:
        """加载三池数据"""
        pools = {}
        pool_file_map = {
            "scale": "scale_winners.json",
            "efficiency": "efficiency_winners.json",
            "pattern": "creative_pattern_winners.json",
        }
        from ..config import WINNERS_DIR as wdir
        for name, filename in pool_file_map.items():
            path = wdir / filename
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                pools[name] = data.get("top_20", [])
            else:
                pools[name] = []
        return pools

    def _load_dna(self) -> Dict:
        """加载 DNA 数据"""
        path = OUTPUT_DIR / "true_winner_dna.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"winners": [], "total": 0}

    def _get_total_ads(self) -> int:
        """获取总广告数"""
        path = OUTPUT_DIR / "creative_performance_raw.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("total", 0)
        return 0

    def _get_image_ads_count(self) -> int:
        """获取图片广告数"""
        path = OUTPUT_DIR / "creative_performance_raw.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("image_ads", 0)
        return 0
