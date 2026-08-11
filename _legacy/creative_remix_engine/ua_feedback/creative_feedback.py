"""Creative Feedback — 真实买量数据反馈系统

支持输入：
- Facebook: CTR, CPI, D1, D7 ROI
- TikTok: CTR, CVR, Spend, CPA
- 反向更新 Creative DNA Weight
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class CreativeFeedback:
    """创意反馈系统"""

    def __init__(self, feedback_path: Path):
        self.feedback_path = feedback_path
        self.feedback_path.parent.mkdir(parents=True, exist_ok=True)
        self.records: List[dict] = []
        self._load()

    def _load(self):
        if self.feedback_path.exists():
            try:
                with open(self.feedback_path, "r", encoding="utf-8") as f:
                    self.records = json.load(f).get("records", [])
            except Exception:
                pass

    def save(self):
        with open(self.feedback_path, "w", encoding="utf-8") as f:
            json.dump({
                "records": self.records,
                "updated_at": datetime.now().isoformat(),
                "total": len(self.records),
            }, f, ensure_ascii=False, indent=2)

    def add_campaign_result(self, video_name: str, platform: str,
                            ctr: float, cvr: float, spend: float,
                            cpi: Optional[float] = None,
                            d1_retention: Optional[float] = None,
                            d7_roi: Optional[float] = None,
                            cpa: Optional[float] = None):
        """添加买量数据"""
        self.records.append({
            "video_name": video_name,
            "platform": platform,
            "metrics": {
                "ctr": ctr,
                "cvr": cvr,
                "spend": spend,
                "cpi": cpi,
                "d1_retention": d1_retention,
                "d7_roi": d7_roi,
                "cpa": cpa,
            },
            "timestamp": datetime.now().isoformat(),
        })
        self.save()

    def get_winner_dna(self, min_ctr: float = 2.0, min_cvr: float = 5.0) -> List[dict]:
        """获取高表现创意的 DNA 特征"""
        winners = []
        for r in self.records:
            m = r["metrics"]
            if m["ctr"] >= min_ctr and m["cvr"] >= min_cvr:
                winners.append(r)
        return winners
