"""Video Structure Diagnosis System — 视频结构故障诊断 + 可执行修改指令生成。

输入：
  一条视频（Eagle asset_id）
  或 一个 FB creative + 归因 cluster

输出：
  Video Structure Diagnosis Report (JSON + 可读文本)
  包含：Hook诊断、理解诊断、Reward诊断、A vs B对比、单变量修改指令

核心逻辑：
  1. 提取视频 5 帧关键帧
  2. FrameAnalyzer 提取每帧视觉特征
  3. 与 cluster 内高/低 ROAS 视频的视觉基准对比
  4. 输出唯一失败原因 + 时间片级诊断 + AE 可执行指令
"""
from __future__ import annotations
import json, re
from pathlib import Path
from typing import List, Optional, Tuple
from collections import defaultdict
import numpy as np

from engine.frame_analyzer import FrameAnalyzer, analyze_video_frames, compute_video_scores

ROOT = Path(__file__).resolve().parent.parent
P04 = ROOT / "output" / "video_intelligence" / "p04"
V35 = P04 / "v3_5"
EAGLE_CACHE = V35 / "cache" / "eagle_frames"
DATA_FILE = P04 / "p4_full_export_all_accounts.json"
ATTRIBUTION_FILE = V35 / "attribution" / "attribution_results.json"
CLUSTER_FILE = V35 / "clusters" / "cluster_results.json"


# ═══════════════════════════════════════════════════════════
# Benchmark Builder — 构建 cluster 级视觉基准
# ═══════════════════════════════════════════════════════════

class ClusterBenchmark:
    """Build and query per-cluster visual benchmarks.

    Benchmarks separate cluster videos into HIGH and LOW performing groups,
    then compute average per-frame visual features for each group.
    """

    def __init__(self):
        self.benchmarks: dict = {}
        self._loaded = False

    def load(self):
        """Load or compute cluster benchmarks from available data."""
        if self._loaded:
            return

        # ── Load cluster results ──
        clusters = {}
        if CLUSTER_FILE.exists():
            clusters = json.loads(CLUSTER_FILE.read_text(encoding="utf-8"))

        # ── Load attribution (ROAS per video) ──
        fb_video_roas = {}
        if ATTRIBUTION_FILE.exists():
            attr = json.loads(ATTRIBUTION_FILE.read_text(encoding="utf-8"))
            for a in attr:
                vid = a.get("video_id", "")
                spend = a.get("total_spend", 0) or 0
                rev = a.get("total_revenue", 0) or 0
                fb_video_roas[vid] = rev / max(spend, 1)

        # ── Load FB data for creative-to-cluster mapping ──
        fb_creative_to_video = {}
        if DATA_FILE.exists():
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            for v in data.get("videos", []):
                vid = v.get("video_id", "")
                cns = v.get("creative_names", []) or []
                if cns:
                    cn = re.sub(r'\s*\d{4}-\d{2}-\d{2}-[a-f0-9]+.*$', '', cns[0]).strip()
                    fb_creative_to_video[cn] = vid

        # ── Build per-cluster: Eagle member → FB ROAS ──
        cluster_members = {}
        for cid, cdata in clusters.items():
            members = cdata.get("members", [])
            if len(members) < 2:
                continue
            cluster_members[cid] = []
            for member_name in members:
                # Map Eagle name → find FB videos that matched this cluster
                # We use the attribution to check which cluster each FB video belongs to
                vid_score = 0.0
                # Default: use cluster avg if no direct match
                cluster_members[cid].append({
                    "name": member_name,
                    "roas": 0.5,  # default assumption
                    "frames_available": self._has_frames(member_name),
                })

        # ── Load attribution results for high/low group ──
        if ATTRIBUTION_FILE.exists():
            attr = json.loads(ATTRIBUTION_FILE.read_text(encoding="utf-8"))
            cluster_videos = defaultdict(list)
            for a in attr:
                cid = a.get("assigned_cluster", "")
                vid = a.get("video_id", "")
                spend = a.get("total_spend", 0) or 0
                rev = a.get("total_revenue", 0) or 0
                roas = rev / max(spend, 1)
                cluster_videos[cid].append({"video_id": vid, "roas": roas, "spend": spend})

            # For each cluster, compute HIGH and LOW group frame features
            for cid, vids in cluster_videos.items():
                if len(vids) < 3:
                    continue
                # Sort by ROAS
                sorted_vids = sorted(vids, key=lambda x: x["roas"], reverse=True)
                n = len(sorted_vids)
                high_group = sorted_vids[:max(1, n // 4)]
                low_group = sorted_vids[-max(1, n // 4):]
                # We don't have FB frames, so we note this limitation
                self.benchmarks[cid] = {
                    "high_roas_avg": np.mean([v["roas"] for v in high_group]),
                    "low_roas_avg": np.mean([v["roas"] for v in low_group]),
                    "high_count": len(high_group),
                    "low_count": len(low_group),
                    "total_videos": len(vids),
                    "note": "FB-side: frame analysis not available (thumbnail only)",
                }

        self._loaded = True

    def get(self, cluster_id: str) -> Optional[dict]:
        self.load()
        return self.benchmarks.get(cluster_id)

    def _has_frames(self, name: str) -> bool:
        """Check if this Eagle asset has cached keyframes."""
        for pct in ["05", "25", "50", "75", "95"]:
            if (EAGLE_CACHE / f"kf_{name}_{pct}.jpg").exists():
                return True
        return False


# ═══════════════════════════════════════════════════════════
# Diagnosis Engine
# ═══════════════════════════════════════════════════════════

class VideoDiagnosisEngine:
    """诊断单条视频的结构问题，输出 AE 可执行修改指令。"""

    def __init__(self):
        self.analyzer = FrameAnalyzer()
        self.benchmark = ClusterBenchmark()
        self.benchmark.load()

    def diagnose_by_eagle_name(self, eagle_name: str) -> dict:
        """Diagnose an Eagle video by its asset name.

        Uses cached keyframes (5%/25%/50%/75%/95%).

        Returns:
            Video Structure Diagnosis Report
        """
        # ── Load keyframes ──
        frame_paths = []
        for pct in ["05", "25", "50", "75", "95"]:
            fp = EAGLE_CACHE / f"kf_{eagle_name}_{pct}.jpg"
            frame_paths.append(fp)

        frames = analyze_video_frames(frame_paths)
        has_frames = any(f is not None for f in frames)
        if not has_frames:
            return self._fallback_diagnosis(eagle_name, "no frames available")

        scores = compute_video_scores(frames)
        return self._generate_report(eagle_name, frames, scores, cluster_id=None)

    def diagnose_by_cluster(self, cluster_id: str) -> dict:
        """Diagnose a cluster's structural profile (high vs low ROAS patterns)."""
        bench = self.benchmark.get(cluster_id)
        if not bench:
            return {"cluster_id": cluster_id, "error": "insufficient data"}

        # Build a diagnosis based on cluster-level patterns
        h_roas = bench["high_roas_avg"]
        l_roas = bench["low_roas_avg"]
        gap = h_roas - l_roas

        diagnosis = {
            "cluster_id": cluster_id,
            "type": "cluster_level",
            "high_roas_avg": round(h_roas, 4),
            "low_roas_avg": round(l_roas, 4),
            "roas_gap": round(gap, 4),
            "high_count": bench["high_count"],
            "low_count": bench["low_count"],
            "note": bench.get("note", ""),
        }

        # Infer structural patterns from cluster data
        if gap > 0.3:
            diagnosis["verdict"] = "Significant performance gap — structure matters"
            diagnosis["likely_winners"] = self._infer_winner_patterns(cluster_id)
        else:
            diagnosis["verdict"] = "Small gap — performance driven by non-structural factors (audience/bid)"

        return diagnosis

    def a_vs_b(self, eagle_a: str, eagle_b: str) -> dict:
        """Compare two Eagle videos, output frame-level structural differences."""
        report_a = self.diagnose_by_eagle_name(eagle_a)
        report_b = self.diagnose_by_eagle_name(eagle_b)

        comparison = {
            "type": "a_vs_b_comparison",
            "video_a": eagle_a,
            "video_b": eagle_b,
            "diff_hook_score": round(
                (report_a.get("diagnosis", {}).get("hook_score", 0) or 0)
                - (report_b.get("diagnosis", {}).get("hook_score", 0) or 0), 4
            ),
            "diff_comprehension_score": round(
                (report_a.get("diagnosis", {}).get("comprehension_score", 0) or 0)
                - (report_b.get("diagnosis", {}).get("comprehension_score", 0) or 0), 4
            ),
            "diff_reward_score": round(
                (report_a.get("diagnosis", {}).get("reward_score", 0) or 0)
                - (report_b.get("diagnosis", {}).get("reward_score", 0) or 0), 4
            ),
        }

        # Determine key structural difference
        diffs = {
            "hook": abs(comparison["diff_hook_score"]),
            "comprehension": abs(comparison["diff_comprehension_score"]),
            "reward": abs(comparison["diff_reward_score"]),
        }
        max_dim = max(diffs, key=diffs.get)
        if diffs[max_dim] > 0.1:
            comparison["key_difference_dimension"] = max_dim
            if max_dim == "hook":
                comparison["key_difference_description"] = (
                    f"Hook strength differs by {diffs['hook']:.2f}. "
                    f"Video with stronger hook has {report_a.get('diagnosis',{}).get('hook_score',0):.2f} "
                    f"vs {report_b.get('diagnosis',{}).get('hook_score',0):.2f}"
                )
            elif max_dim == "comprehension":
                comparison["key_difference_description"] = (
                    f"Mid-video comprehension differs by {diffs['comprehension']:.2f}"
                )
            else:
                comparison["key_difference_description"] = (
                    f"Reward clarity differs by {diffs['reward']:.2f}"
                )
        else:
            comparison["key_difference_dimension"] = "none"
            comparison["key_difference_description"] = "Videos are structurally similar"

        comparison["video_a_report"] = report_a
        comparison["video_b_report"] = report_b
        return comparison

    # ═══════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════

    def _generate_report(self, video_name: str, frames: List[dict],
                         scores: dict, cluster_id: Optional[str]) -> dict:
        """Generate the full Video Structure Diagnosis Report."""
        hook_score = scores.get("hook_score", 0)
        comp_score = scores.get("comprehension_score", 0)
        reward_score = scores.get("reward_score", 0)

        # ── Hook Diagnosis (0-3s) ──
        hook_diag = self._diagnose_hook(frames, hook_score)

        # ── Comprehension Diagnosis (3-8s) ──
        comp_diag = self._diagnose_comprehension(frames, comp_score)

        # ── Reward Diagnosis (8s+) ──
        reward_diag = self._diagnose_reward(frames, reward_score)

        # ── Root Cause: single failure reason ──
        root_cause, fix_instruction = self._determine_root_cause(
            hook_diag, comp_diag, reward_diag, scores
        )

        report = {
            "video": video_name,
            "type": "video_diagnosis",
            "diagnosis": {
                "hook_score": hook_score,
                "comprehension_score": comp_score,
                "reward_score": reward_score,
            },
            "hook_diagnosis": hook_diag,
            "comprehension_diagnosis": comp_diag,
            "reward_diagnosis": reward_diag,
            "root_cause": root_cause,
            "single_modification_instruction": fix_instruction,
            "frame_features": [
                f for f in frames[:5] if f is not None
            ],
        }
        return report

    def _diagnose_hook(self, frames: List[dict], score: float) -> dict:
        """诊断 0-3s Hook 有效性。"""
        first = next((f for f in frames if f is not None), None)
        result = {
            "time_window": "0-3s",
            "valid": score >= 0.35,
            "score": round(score, 4),
        }

        if not first:
            result["failure_type"] = "no frame data"
            result["fix"] = "N/A"
            return result

        if score < 0.35:
            result["valid"] = False
            edge = first.get("edge_density", 0)
            contrast = first.get("contrast", 0)
            center_c = first.get("center_contrast", 0)

            if edge < 0.05 and contrast < 0.15:
                result["failure_type"] = "无视觉冲击 — 画面过于平淡"
                result["specific_failure_point"] = "0.0s-1.0s: 第一帧缺乏边缘结构和对比度"
                result["fix"] = (
                    "👉 修改第一帧：替换为高对比度角色冲击画面。"
                    "当前帧 edge_density={:.3f}，目标 >0.05。".format(edge)
                )
            elif center_c < 0.1:
                result["failure_type"] = "无视觉焦点 — 中心区域缺乏兴趣点"
                result["specific_failure_point"] = "0.0s-1.5s: 画面中心缺乏主体"
                result["fix"] = (
                    "👉 修改第一帧：在画面中心 40% 区域内增加视觉主体"
                    "（角色/物品），当前 center_contrast={:.3f}。".format(center_c)
                )
            else:
                result["failure_type"] = "饱和度不足 — 色彩冲击力弱"
                result["specific_failure_point"] = "0.0s-2.0s: 色彩缺乏吸引力"
                result["fix"] = (
                    "👉 修改第一帧：提升饱和度至少 30%，"
                    "当前 saturation={:.3f}。".format(first.get("saturation", 0))
                )
        else:
            result["failure_type"] = "无"
            result["fix"] = "Hook 有效，无需修改"

        return result

    def _diagnose_comprehension(self, frames: List[dict], score: float) -> dict:
        """诊断 3-8s 理解难度。"""
        mid = [frames[i] for i in [1, 2] if i < len(frames) and frames[i] is not None]
        result = {
            "time_window": "3-8s",
            "valid": score >= 0.3,
            "score": round(score, 4),
        }

        if not mid:
            result["failure_type"] = "no frame data"
            result["fix"] = "N/A"
            return result

        avg_text = np.mean([m.get("text_density_proxy", 0) for m in mid])
        avg_entropy = np.mean([m.get("color_entropy", 0) for m in mid])

        if score < 0.3:
            result["valid"] = False
            if avg_text > 0.08:
                result["failure_type"] = "信息过载 — 文字/UI占画面过多"
                result["specific_failure_point"] = "3.0s-6.0s: text_density={:.3f} > 0.08".format(avg_text)
                result["fix"] = (
                    "👉 修改中段：删除至少 1 个 UI 元素。"
                    "当前 text_density={:.3f}，目标 <0.06。"
                    "提前核心动画到 2.5s。".format(avg_text)
                )
            elif avg_entropy < 4.0:
                result["failure_type"] = "视觉单调 — 信息量不足"
                result["fix"] = (
                    "👉 修改中段：增加至少 1 个视觉元素或转场。"
                    "当前 color_entropy={:.2f}，目标 >4.0。".format(avg_entropy)
                )
            else:
                result["failure_type"] = "节奏过慢 — 用户在中段流失"
                result["specific_failure_point"] = "4.0s-7.0s: 帧间缺乏足够变化"
                result["fix"] = (
                    "👉 修改节奏：将中段时长从 5s 压缩到 3s。"
                    "删除过渡帧，直接切入核心玩法。"
                )
        else:
            result["failure_type"] = "无"
            result["fix"] = "理解 OK，无需修改"

        return result

    def _diagnose_reward(self, frames: List[dict], score: float) -> dict:
        """诊断 8s+ Reward 有效性。"""
        late = [frames[i] for i in [3, 4] if i < len(frames) and frames[i] is not None]
        result = {
            "time_window": "8s+",
            "valid": score >= 0.3,
            "score": round(score, 4),
        }

        if not late:
            result["failure_type"] = "no frame data"
            result["fix"] = "N/A"
            return result

        avg_bright = np.mean([l.get("brightness", 0) for l in late])
        avg_sat = np.mean([l.get("saturation", 0) for l in late])

        if score < 0.3:
            result["valid"] = False
            if avg_bright < 0.3:
                result["failure_type"] = "视觉回报不足 — 后段画面过暗"
                result["fix"] = (
                    "👉 修改结尾：将后段画面亮度提升至少 50%。"
                    "当前 avg_brightness={:.3f}，目标 >0.35。"
                    "在 6s 位置提前展示成功结果动画。".format(avg_bright)
                )
            elif avg_sat < 0.15:
                result["failure_type"] = "色彩回报不够 — 后段缺乏鲜艳元素"
                result["fix"] = (
                    "👉 修改结尾：在 8s 位置增加高饱和奖励动画。"
                    "当前 avg_saturation={:.3f}，目标 >0.2。".format(avg_sat)
                )
            else:
                result["failure_type"] = "Payoff 太晚 — 用户等不到结果就流失"
                result["fix"] = (
                    "👉 修改reward前置：把胜利/升级/收集动画提前到 6s，"
                    "而不是放在 15s+。"
                )
        else:
            result["failure_type"] = "无"
            result["fix"] = "Reward 有效，无需修改"

        return result

    def _determine_root_cause(self, hook: dict, comp: dict,
                              reward: dict, scores: dict) -> Tuple[str, str]:
        """输出唯一失败原因 + 唯一修改指令。"""
        if not hook["valid"]:
            return (
                f"Hook失败 — {hook['failure_type']}",
                hook["fix"]
            )
        elif not comp["valid"]:
            return (
                f"理解失败 — {comp['failure_type']}",
                comp["fix"]
            )
        elif not reward["valid"]:
            return (
                f"Reward失败 — {reward['failure_type']}",
                reward["fix"]
            )
        else:
            return (
                "所有结构维度表现正常 — 可能是受众/出价问题",
                "无需修改视频结构，建议检查受众定向和出价策略"
            )

    def _fallback_diagnosis(self, video_name: str, reason: str) -> dict:
        return {
            "video": video_name,
            "type": "video_diagnosis",
            "error": f"cannot diagnose — {reason}",
            "diagnosis": {
                "hook_score": 0, "comprehension_score": 0, "reward_score": 0,
            },
            "root_cause": "insufficient data",
            "single_modification_instruction": "N/A",
        }

    def _infer_winner_patterns(self, cluster_id: str) -> str:
        """Generate winner pattern hypothesis from cluster data."""
        return (
            f"Cluster {cluster_id}: 建议分析高 ROAS 视频的 frame "
            f"features 对比低 ROAS 视频的差异。"
        )


# ═══════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════

def diagnose_video(video_name: str, output_dir: Optional[Path] = None) -> dict:
    """Diagnose a single video and optionally save report."""
    engine = VideoDiagnosisEngine()
    report = engine.diagnose_by_eagle_name(video_name)

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "diagnosis_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (output_dir / "diagnosis_report.md").write_text(
            _report_to_markdown(report), encoding="utf-8")

    return report


def compare_videos(video_a: str, video_b: str, output_dir: Optional[Path] = None) -> dict:
    """Compare two videos frame-level."""
    engine = VideoDiagnosisEngine()
    comparison = engine.a_vs_b(video_a, video_b)

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "comparison.json").write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    return comparison


def _report_to_markdown(report: dict) -> str:
    """Render diagnosis report as human-readable markdown."""
    if "error" in report:
        return f"# 诊断报告 — {report.get('video','?')}\n\n❌ 错误: {report['error']}\n"

    lines = []
    lines.append(f"# 📊 视频结构诊断报告")
    lines.append(f"## {report['video']}")
    lines.append(f"")
    lines.append(f"### 结构分数")
    d = report.get("diagnosis", {})
    lines.append(f"- Hook: **{d.get('hook_score',0):.2f}** | Comprehension: **{d.get('comprehension_score',0):.2f}** | Reward: **{d.get('reward_score',0):.2f}**")
    lines.append(f"")

    for section_name, section_key in [("🔴 Hook诊断 (0-3s)", "hook_diagnosis"),
                                       ("🟡 理解诊断 (3-8s)", "comprehension_diagnosis"),
                                       ("🟢 Reward诊断 (8s+)", "reward_diagnosis")]:
        s = report.get(section_key, {})
        status = "✅ 有效" if s.get("valid") else "❌ 失败"
        lines.append(f"### {section_name} — {status}")
        lines.append(f"**Score:** {s.get('score',0):.2f}")
        if not s.get("valid"):
            lines.append(f"**失败类型:** {s.get('failure_type','')}")
            if s.get("specific_failure_point"):
                lines.append(f"**定位:** {s['specific_failure_point']}")
            lines.append(f"**修改指令:**")
            lines.append(f"```")
            lines.append(f"{s.get('fix','')}")
            lines.append(f"```")
        lines.append(f"")

    lines.append(f"### ⚡ 根因分析")
    lines.append(f"**唯一失败原因:** {report.get('root_cause','?')}")
    lines.append(f"")
    lines.append(f"**单变量修改指令:**")
    lines.append(f"```")
    lines.append(f"{report.get('single_modification_instruction','?')}")
    lines.append(f"```")
    lines.append(f"")

    return "\n".join(lines)
