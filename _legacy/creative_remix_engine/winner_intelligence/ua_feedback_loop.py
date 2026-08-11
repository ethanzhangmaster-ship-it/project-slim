"""UA Feedback Loop — 买量数据反馈闭环

接收 Facebook/TikTok/Google Ads 数据，自动更新 Winner Database，
优化 Buying Score 模型和 Archetype 发现。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .winner_database import WinnerDatabase
from .creative_value_predictor import CreativeValuePredictor
from .winner_dna_extractor import WinnerDNAExtractor


@dataclass
class FeedbackResult:
    """反馈结果"""
    new_winners_added: int
    winners_updated: int
    model_calibrated: bool
    new_archetypes: int
    top_performer: str
    avg_ctr_change: float


class UAFeedbackLoop:
    """UA 反馈闭环引擎"""

    # 判定 Winner 的阈值
    WINNER_THRESHOLDS = {
        "min_ctr": 2.0,
        "max_cpi": 0.8,
        "min_d7_roi": 0.15,
        "min_spend": 50.0,
        "min_impressions": 1000,
    }

    def __init__(self, winner_db_path: Path, ranking_db_path: Optional[Path] = None):
        self.winner_db = WinnerDatabase(winner_db_path)
        self.dna_extractor = WinnerDNAExtractor(ranking_db_path)
        self.value_predictor = CreativeValuePredictor(ranking_db_path, winner_db_path)

        self.feedback_history: List[dict] = []

    def ingest_platform_data(self, platform: str, data: List[dict]) -> FeedbackResult:
        """摄入平台广告数据"""
        new_winners = 0
        updated = 0

        for item in data:
            creative_id = item.get("creative_id", item.get("ad_id", ""))
            video_name = item.get("video_name", item.get("ad_name", ""))
            ctr = item.get("ctr", 0)
            cpi = item.get("cpi", item.get("cpa", 1.0))
            spend = item.get("spend", 0)
            impressions = item.get("impressions", 0)
            d1_roi = item.get("d1_roi")
            d7_roi = item.get("d7_roi")
            d30_roi = item.get("d30_roi")

            # 判断是否为 Winner
            is_winner = self._is_winner(ctr, cpi, d7_roi, spend, impressions)

            if is_winner:
                # 提取 DNA
                dna = self._extract_dna_for_feedback(video_name, item)

                # 检查是否已存在
                existing = self._find_existing_winner(creative_id)
                if existing:
                    # 更新
                    self._update_winner(existing, item)
                    updated += 1
                else:
                    # 新增
                    self.winner_db.add_winner(
                        creative_id=creative_id,
                        video_name=video_name,
                        ctr=ctr,
                        cpi=cpi,
                        d1_roi=d1_roi,
                        d7_roi=d7_roi,
                        d30_roi=d30_roi,
                        spend=spend,
                        impressions=impressions,
                        dna=dna,
                    )
                    new_winners += 1

        # 重新校准预测模型
        calibrated = False
        if new_winners > 0 or updated > 0:
            calibrated = self._calibrate_predictor()

        # 记录反馈历史
        self.feedback_history.append({
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "new_winners": new_winners,
            "updated": updated,
            "calibrated": calibrated,
        })

        # 获取 Top Performer
        top_winners = self.winner_db.get_top_winners(min_ctr=0, top_n=1)
        top_performer = top_winners[0]["video_name"] if top_winners else ""

        return FeedbackResult(
            new_winners_added=new_winners,
            winners_updated=updated,
            model_calibrated=calibrated,
            new_archetypes=0,
            top_performer=top_performer,
            avg_ctr_change=0.0,
        )

    def _is_winner(self, ctr: float, cpi: float, roi: Optional[float],
                   spend: float, impressions: int) -> bool:
        """判断是否为 Winner"""
        thresholds = self.WINNER_THRESHOLDS

        # 数据量门槛
        if spend < thresholds["min_spend"]:
            return False
        if impressions < thresholds["min_impressions"]:
            return False

        # CTR 门槛
        if ctr < thresholds["min_ctr"]:
            return False

        # CPI 门槛
        if cpi > thresholds["max_cpi"]:
            return False

        # ROI 门槛（如有）
        if roi is not None and roi < thresholds["min_d7_roi"]:
            return False

        return True

    def _find_existing_winner(self, creative_id: str) -> Optional[dict]:
        """查找已存在的 Winner"""
        for w in self.winner_db.winners:
            if w["creative_id"] == creative_id:
                return w
        return None

    def _update_winner(self, existing: dict, new_data: dict):
        """更新已有 Winner 数据"""
        metrics = existing["metrics"]
        new_metrics = new_data

        # 简单加权更新（按 spend 加权）
        old_spend = metrics.get("spend", 0)
        new_spend = new_metrics.get("spend", 0)
        total_spend = old_spend + new_spend

        if total_spend > 0:
            # CTR 加权平均
            old_ctr = metrics.get("ctr", 0)
            new_ctr = new_metrics.get("ctr", 0)
            metrics["ctr"] = round(
                (old_ctr * old_spend + new_ctr * new_spend) / total_spend, 2
            )

            # CPI 加权平均
            old_cpi = metrics.get("cpi", 0)
            new_cpi = new_metrics.get("cpi", 0)
            metrics["cpi"] = round(
                (old_cpi * old_spend + new_cpi * new_spend) / total_spend, 2
            )

            metrics["spend"] = round(total_spend, 2)
            metrics["impressions"] = metrics.get("impressions", 0) + new_metrics.get("impressions", 0)

        # ROI 更新（取最新）
        for roi_key in ["d1_roi", "d7_roi", "d30_roi"]:
            if new_metrics.get(roi_key) is not None:
                metrics[roi_key] = new_metrics[roi_key]

        existing["last_updated"] = datetime.now().isoformat()
        self.winner_db.save()

    def _extract_dna_for_feedback(self, video_name: str, ad_data: dict) -> dict:
        """为反馈数据提取 DNA"""
        try:
            dna = self.dna_extractor.extract(video_name)
            # 扁平化部分字段便于 Winner DB 使用
            return {
                "hook_type": dna.get("hook_dna", {}).get("hook_type", "general"),
                "subject": dna.get("subject_dna", {}).get("primary_subject", "character"),
                "action": dna.get("gameplay_dna", {}).get("action", "showcase"),
                "emotion": dna.get("hook_dna", {}).get("emotion", 50),
                "full_dna": dna,
            }
        except Exception:
            # Fallback: 从广告数据推断
            return {
                "hook_type": self._infer_from_name(video_name, "hook"),
                "subject": self._infer_from_name(video_name, "subject"),
                "action": self._infer_from_name(video_name, "action"),
                "emotion": 50,
            }

    @staticmethod
    def _infer_from_name(name: str, attr: str) -> str:
        """从名称推断属性"""
        s = name.lower()
        if attr == "hook":
            if any(k in s for k in ["trap", "shock", "surprise", "danger"]):
                return "shock"
            if any(k in s for k in ["challenge", "vs", "level"]):
                return "challenge"
            if any(k in s for k in ["evol", "transform", "upgrade"]):
                return "transformation"
            return "general"
        elif attr == "subject":
            if "dragon" in s or "龙" in s:
                return "dragon"
            if "witch" in s:
                return "witch"
            return "character"
        elif attr == "action":
            if "merge" in s:
                return "merge"
            if "evol" in s or "upgrade" in s:
                return "upgrade"
            return "showcase"
        return "general"

    def _calibrate_predictor(self) -> bool:
        """校准预测模型"""
        try:
            # 基于新 Winner 数据重新计算 Winner 模式权重
            winners = self.winner_db.winners
            if len(winners) < 3:
                return False

            # 计算各模式的平均 CTR
            pattern_stats = {}
            for w in winners:
                dna = w.get("dna", {})
                ctr = w["metrics"].get("ctr", 0)
                for key in ["hook_type", "subject", "action"]:
                    val = dna.get(key, "")
                    if val:
                        if key not in pattern_stats:
                            pattern_stats[key] = {}
                        if val not in pattern_stats[key]:
                            pattern_stats[key][val] = []
                        pattern_stats[key][val].append(ctr)

            # 更新预测器的 Winner 模式
            for key, patterns in pattern_stats.items():
                for val, ctrs in patterns.items():
                    avg_ctr = sum(ctrs) / len(ctrs)
                    if key not in self.value_predictor.winner_patterns:
                        self.value_predictor.winner_patterns[key] = {}
                    self.value_predictor.winner_patterns[key][val] = ctrs

            return True
        except Exception:
            return False

    def generate_feedback_report(self) -> dict:
        """生成反馈报告"""
        total_winners = len(self.winner_db.winners)
        avg_ctr = 0.0
        avg_cpi = 0.0

        if total_winners > 0:
            avg_ctr = sum(w["metrics"].get("ctr", 0) for w in self.winner_db.winners) / total_winners
            avg_cpi = sum(w["metrics"].get("cpi", 0) for w in self.winner_db.winners) / total_winners

        top_winners = self.winner_db.get_top_winners(min_ctr=0, top_n=5)
        winner_patterns = self.winner_db.get_winner_dna_patterns()

        return {
            "report_time": datetime.now().isoformat(),
            "total_winners": total_winners,
            "avg_ctr": round(avg_ctr, 2),
            "avg_cpi": round(avg_cpi, 2),
            "feedback_cycles": len(self.feedback_history),
            "top_5_winners": [
                {
                    "video_name": w["video_name"],
                    "ctr": w["metrics"]["ctr"],
                    "cpi": w["metrics"]["cpi"],
                }
                for w in top_winners
            ],
            "winner_patterns": {
                key: [
                    {"value": p["value"], "avg_ctr": p["ctr"]}
                    for p in patterns[:5]
                ]
                for key, patterns in winner_patterns.items()
            },
            "recent_feedback": self.feedback_history[-5:],
        }

    def simulate_feedback_from_ranking(self, ranking_db_path: Path,
                                        top_n: int = 20) -> FeedbackResult:
        """从 Ranking DB 模拟反馈（用于冷启动）"""
        # 先 Seed Winner DB
        self.winner_db.seed_from_ranking(ranking_db_path, top_n)

        # 模拟一次反馈
        result = FeedbackResult(
            new_winners_added=top_n,
            winners_updated=0,
            model_calibrated=True,
            new_archetypes=0,
            top_performer="",
            avg_ctr_change=0.0,
        )

        if self.winner_db.winners:
            result.top_performer = self.winner_db.winners[0]["video_name"]

        return result
