"""Winner Database — 保存真实买量 Winner 数据

输入：Facebook/TikTok/Google Ads 数据
输出：winner_database.json
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class WinnerDatabase:
    """Winner 数据库"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.winners: List[dict] = []
        self._load()

    def _load(self):
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.winners = data.get("winners", [])
            except Exception:
                pass

    def save(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump({
                "winners": self.winners,
                "updated_at": datetime.now().isoformat(),
                "total": len(self.winners),
            }, f, ensure_ascii=False, indent=2)

    def add_winner(self, creative_id: str, video_name: str,
                   ctr: float, cpi: float,
                   d1_roi: Optional[float] = None,
                   d7_roi: Optional[float] = None,
                   d30_roi: Optional[float] = None,
                   spend: float = 0,
                   impressions: int = 0,
                   dna: Optional[dict] = None):
        """添加 Winner"""
        self.winners.append({
            "creative_id": creative_id,
            "video_name": video_name,
            "metrics": {
                "ctr": ctr,
                "cpi": cpi,
                "d1_roi": d1_roi,
                "d7_roi": d7_roi,
                "d30_roi": d30_roi,
                "spend": spend,
                "impressions": impressions,
            },
            "dna": dna or {},
            "timestamp": datetime.now().isoformat(),
        })
        self.save()

    def get_top_winners(self, min_ctr: float = 2.0, top_n: int = 20) -> List[dict]:
        """获取高表现 Winner"""
        filtered = [w for w in self.winners if w["metrics"]["ctr"] >= min_ctr]
        filtered.sort(key=lambda x: x["metrics"]["ctr"], reverse=True)
        return filtered[:top_n]

    def get_winner_dna_patterns(self) -> Dict[str, List[dict]]:
        """获取 Winner DNA 模式"""
        patterns = {}
        for w in self.winners:
            dna = w.get("dna", {})
            for key in ["hook_type", "subject", "action", "emotion"]:
                val = dna.get(key, "")
                if val:
                    if key not in patterns:
                        patterns[key] = []
                    patterns[key].append({
                        "value": val,
                        "ctr": w["metrics"]["ctr"],
                        "video_name": w["video_name"],
                    })
        return patterns

    def seed_from_ranking(self, ranking_db_path: Path, top_n: int = 20):
        """从 Ranking DB 中模拟 Winner（用于无真实数据时启动）"""
        if not ranking_db_path.exists():
            return

        with open(ranking_db_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        shots = data.get("shots", [])
        # 按 ad_value_score 排序
        shots.sort(key=lambda x: x.get("ad_value_score", 0), reverse=True)

        for i, shot in enumerate(shots[:top_n]):
            name = shot.get("video_name", "")
            ad_value = shot.get("ad_value_score", 0)
            # 模拟买量指标
            simulated_ctr = min(5.0, max(1.0, ad_value / 15))
            simulated_cpi = max(0.2, 1.0 - ad_value / 100)
            simulated_d7 = max(0.1, ad_value / 100)

            self.add_winner(
                creative_id=f"simulated_winner_{i+1:03d}",
                video_name=name,
                ctr=round(simulated_ctr, 2),
                cpi=round(simulated_cpi, 2),
                d7_roi=round(simulated_d7, 2),
                dna={
                    "hook_type": self._infer_hook_type(name),
                    "subject": self._infer_subject(name),
                    "action": self._infer_action(name),
                    "emotion": self._infer_emotion(name),
                },
            )
        print(f"[WinnerDB] Seeded {min(top_n, len(shots))} simulated winners from ranking data")

    @staticmethod
    def _infer_hook_type(name: str) -> str:
        s = name.lower()
        if any(k in s for k in ["kaitou", "hook", "start", "trap", "surprise"]):
            return "shock"
        if any(k in s for k in ["level", "vs", "challenge"]):
            return "challenge"
        if any(k in s for k in ["dragon", "egg", "evol"]):
            return "transformation"
        if any(k in s for k in ["witch", "magic", "secret"]):
            return "curiosity"
        return "general"

    @staticmethod
    def _infer_subject(name: str) -> str:
        s = name.lower()
        if "dragon" in s or "龙" in s:
            return "dragon"
        if "witch" in s or "女巫" in s:
            return "witch"
        if "castle" in s or "城堡" in s:
            return "castle"
        if "hero" in s or "warrior" in s:
            return "hero"
        return "character"

    @staticmethod
    def _infer_action(name: str) -> str:
        s = name.lower()
        if any(k in s for k in ["merge", "hecheng", "wanfa"]):
            return "merge"
        if any(k in s for k in ["evol", "upgrade", "level"]):
            return "upgrade"
        if any(k in s for k in ["battle", "fight", "boss"]):
            return "battle"
        if any(k in s for k in ["unlock", "open"]):
            return "unlock"
        return "showcase"

    @staticmethod
    def _infer_emotion(name: str) -> str:
        s = name.lower()
        if any(k in s for k in ["surprise", "shock", "trap", "danger"]):
            return "surprise"
        if any(k in s for k in ["rescue", "save", "help"]):
            return "urgency"
        if any(k in s for k in ["victory", "win", "reward"]):
            return "achievement"
        if any(k in s for k in ["curious", "mystery", "secret"]):
            return "curiosity"
        return "excitement"
