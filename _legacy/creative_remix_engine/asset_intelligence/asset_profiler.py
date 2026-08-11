"""Asset Profiler — 生成 Creative Library 全景报告"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter

from .asset_dna_extractor import AssetDNAExtractor
from .asset_cluster import AssetCluster
from .hook_miner import HookMiner
from .gameplay_miner import GameplayMiner
from .asset_quality_gate import AssetQualityGate


class AssetProfiler:
    """资产画像器 — 一键生成全部报告"""

    def __init__(self, video_dir: Path, output_dir: Path,
                 ranking_db_path: Optional[Path] = None):
        self.video_dir = video_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.dna_extractor = AssetDNAExtractor(ranking_db_path)
        self.cluster = AssetCluster(ranking_db_path)
        self.hook_miner = HookMiner(ranking_db_path)
        self.gameplay_miner = GameplayMiner(ranking_db_path)
        self.quality_gate = AssetQualityGate(ranking_db_path)

    def run(self) -> Dict:
        """运行全部分析流程"""
        print("=" * 70)
        print("V3.7 Creative Asset Intelligence Expansion")
        print("=" * 70)

        # 1. DNA Extraction
        print("\n[Step 1] Extracting Creative DNA for all assets...")
        all_videos = sorted([p.stem for p in self.video_dir.glob("*.mp4")])
        dna_results = {}
        for i, name in enumerate(all_videos):
            if i % 100 == 0:
                print(f"  [{i}/{len(all_videos)}] {name[:40]}...")
            dna_results[name] = self.dna_extractor.extract(name)
        print(f"  DNA extracted: {len(dna_results)}")

        # 2. Quality Gate
        print("\n[Step 2] Running Quality Gate...")
        quality_report = self.quality_gate.evaluate_all()
        self.quality_gate.export(quality_report, self.output_dir / "quality_report.json")
        print(f"  S={quality_report.s_grade} | A={quality_report.a_grade} | B={quality_report.b_grade} | C={quality_report.c_grade}")

        # 3. Hook Mining
        print("\n[Step 3] Mining Hook Candidates...")
        hook_candidates = self.hook_miner.mine(target_count=100)
        hook_lib = self.hook_miner.export_library(
            hook_candidates, self.output_dir / "hook_library.json"
        )
        print(f"  Hook candidates: {len(hook_candidates)}")

        # 4. Gameplay Mining
        print("\n[Step 4] Mining Gameplay Candidates...")
        gp_candidates = self.gameplay_miner.mine(target_count=100)
        gp_lib = self.gameplay_miner.export_library(
            gp_candidates, self.output_dir / "gameplay_library.json"
        )
        print(f"  Gameplay candidates: {len(gp_candidates)}")

        # 5. Clustering
        print("\n[Step 5] Clustering assets...")
        frame_dir = Path("D:/project_slim/output/P04_remix_videos/v35_cache/frames")
        archetypes = self.cluster.cluster(all_videos, frame_dir=frame_dir, n_clusters=8)
        print(f"  Archetypes discovered: {len(archetypes)}")
        for i, arch in enumerate(archetypes[:5]):
            dna = arch["dominant_dna"]
            print(f"    #{i+1}: {arch['performance_tier']} | size={arch['size']} | "
                  f"subjects={dna['dominant_subjects']} | actions={dna['dominant_actions']} | "
                  f"ad_value={arch['avg_scores']['ad_value']}")

        # 6. Creative Library
        print("\n[Step 6] Building Creative Library...")
        library = self._build_library(dna_results, quality_report, hook_candidates, gp_candidates, archetypes)
        with open(self.output_dir / "creative_library.json", "w", encoding="utf-8") as f:
            json.dump(library, f, ensure_ascii=False, indent=2, default=str)
        print(f"  Creative Library: {library['total_assets']} assets")

        # 7. Cluster Report HTML
        print("\n[Step 7] Generating Cluster Report HTML...")
        self._generate_cluster_html(archetypes, hook_candidates[:20], gp_candidates[:20], quality_report)

        return {
            "dna_count": len(dna_results),
            "hook_count": len(hook_candidates),
            "gameplay_count": len(gp_candidates),
            "archetypes": len(archetypes),
            "quality": {
                "S": quality_report.s_grade,
                "A": quality_report.a_grade,
                "B": quality_report.b_grade,
                "C": quality_report.c_grade,
            },
        }

    def _build_library(self, dna_results, quality, hooks, gameplays, archetypes) -> dict:
        return {
            "version": "V3.7",
            "total_assets": len(dna_results),
            "quality_distribution": {
                "S": quality.s_grade,
                "A": quality.a_grade,
                "B": quality.b_grade,
                "C": quality.c_grade,
            },
            "hook_library": {"total": len(hooks), "top_10": [h.video_name for h in hooks[:10]]},
            "gameplay_library": {"total": len(gameplays), "top_10": [g.video_name for g in gameplays[:10]]},
            "creative_archetypes": archetypes,
            "dna_schema": {
                "role": ["hook", "gameplay", "reward", "problem", "cta"],
                "subject": ["dragon", "witch", "castle", "hero", "npc", "creature"],
                "action": ["merge", "upgrade", "drag", "unlock", "battle", "collect"],
                "emotion": ["surprise", "curiosity", "excitement", "achievement", "urgency", "satisfaction"],
                "scene": ["battle", "magic", "treasure", "forest", "dungeon", "sky"],
            },
        }

    def _generate_cluster_html(self, archetypes, top_hooks, top_gps, quality):
        """生成 HTML 聚类报告"""
        css = """
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }
            h1 { color: #1a1a2e; }
            .summary { background: white; padding: 24px; border-radius: 8px; margin: 20px 0; }
            .cluster { background: white; padding: 20px; border-radius: 8px; margin: 16px 0; }
            .HIGH { border-left: 4px solid #16c79a; }
            .MEDIUM { border-left: 4px solid #f4a261; }
            .LOW { border-left: 4px solid #e94560; }
            .tag { display: inline-block; background: #16213e; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; margin: 2px; }
            .score { font-weight: bold; color: #e94560; }
            table { width: 100%; border-collapse: collapse; background: white; margin: 16px 0; }
            th { background: #16213e; color: white; padding: 10px; }
            td { padding: 8px 10px; border-bottom: 1px solid #eee; }
        </style>
        """

        # Archetypes section
        arch_html = ""
        for i, arch in enumerate(archetypes[:8]):
            dna = arch["dominant_dna"]
            tags = ""
            for s in dna.get("dominant_subjects", []):
                tags += f'<span class="tag">{s}</span>'
            for a in dna.get("dominant_actions", []):
                tags += f'<span class="tag">{a}</span>'
            for e in dna.get("dominant_emotions", []):
                tags += f'<span class="tag">{e}</span>'

            arch_html += f"""
            <div class="cluster {arch['performance_tier']}">
                <h3>#{i+1} Archetype — {arch['performance_tier']} (size: {arch['size']})</h3>
                <p>Avg Ad Value: <span class="score">{arch['avg_scores']['ad_value']}</span> |
                   Hook: {arch['avg_scores']['hook']} |
                   Gameplay: {arch['avg_scores']['gameplay']} |
                   Reward: {arch['avg_scores']['reward']}</p>
                <p>{tags}</p>
                <p><small>Top videos: {', '.join(arch['top_videos'][:3])}</small></p>
            </div>
            """

        # Top Hooks
        hook_rows = ""
        for h in top_hooks:
            hook_rows += f"<tr><td>#{h.rank}</td><td>{h.video_name[:50]}</td><td>{h.hook_score}</td><td>{h.reason}</td></tr>"

        # Top Gameplay
        gp_rows = ""
        for g in top_gps:
            gp_rows += f"<tr><td>#{g.rank}</td><td>{g.video_name[:50]}</td><td>{g.gameplay_score}</td><td>{g.reason}</td></tr>"

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>V3.7 Creative Asset Cluster Report</title>{css}</head><body>
<h1>V3.7 Creative Asset Intelligence — Cluster Report</h1>
<p>Generated: 2026-07-13</p>

<div class="summary">
    <h2>Summary</h2>
    <p>Total Assets: {quality.total} | Approved: {quality.approved} | Rejected: {quality.rejected}</p>
    <p>Quality: S={quality.s_grade} | A={quality.a_grade} | B={quality.b_grade} | C={quality.c_grade}</p>
</div>

<div class="summary">
    <h2>Creative Archetypes</h2>
    {arch_html}
</div>

<div class="summary">
    <h2>Top 20 Hook Candidates</h2>
    <table><thead><tr><th>Rank</th><th>Video</th><th>Hook Score</th><th>Reason</th></tr></thead><tbody>{hook_rows}</tbody></table>
</div>

<div class="summary">
    <h2>Top 20 Gameplay Candidates</h2>
    <table><thead><tr><th>Rank</th><th>Video</th><th>Clarity</th><th>Reason</th></tr></thead><tbody>{gp_rows}</tbody></table>
</div>

</body></html>"""

        path = self.output_dir / "creative_cluster_report.html"
        path.write_text(html, encoding="utf-8")
        print(f"  HTML: {path}")
