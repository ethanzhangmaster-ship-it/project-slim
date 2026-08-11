"""Performance Archetype Discovery — 高绩效创意原型发现

从 Winner 数据库中聚类发现高绩效创意模式，形成 Performance Archetype。
例如：Dragon Evolution、Rescue Story、Merge Challenge 等。
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter, defaultdict
from dataclasses import dataclass

from .dna_similarity import DNASimilarityEngine


@dataclass
class PerformanceArchetype:
    """Performance Archetype"""
    name: str
    description: str
    avg_ctr: float
    avg_cpi: float
    avg_d7_roi: float
    winner_count: int
    representative_dna: dict
    key_features: List[str]
    confidence: float


class ArchetypeDiscoveryEngine:
    """Archetype 发现引擎"""

    def __init__(self, winner_db_path: Optional[Path] = None):
        self.winners: List[dict] = []
        self.archetypes: Dict[str, PerformanceArchetype] = {}
        self.similarity_engine = DNASimilarityEngine()

        if winner_db_path and winner_db_path.exists():
            self._load_winners(winner_db_path)

    def _load_winners(self, path: Path):
        """加载 Winner 数据"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.winners = data.get("winners", [])
        except Exception:
            pass

    def discover_archetypes(self, min_winners: int = 3) -> Dict[str, PerformanceArchetype]:
        """从 Winner 中发现 Archetype"""
        if len(self.winners) < min_winners:
            return self._build_default_archetypes()

        # 基于 DNA 特征聚类
        clusters = self._cluster_by_dna_patterns()

        # 为每个 Cluster 生成 Archetype
        for cluster_name, cluster_winners in clusters.items():
            if len(cluster_winners) < min_winners:
                continue

            archetype = self._build_archetype_from_cluster(
                cluster_name, cluster_winners
            )
            self.archetypes[cluster_name] = archetype

            # 注册到相似度引擎
            self.similarity_engine.add_archetype(
                cluster_name,
                archetype.representative_dna,
                {
                    "avg_ctr": archetype.avg_ctr,
                    "avg_cpi": archetype.avg_cpi,
                    "avg_d7_roi": archetype.avg_d7_roi,
                }
            )

        if not self.archetypes:
            return self._build_default_archetypes()

        return self.archetypes

    def _cluster_by_dna_patterns(self) -> Dict[str, List[dict]]:
        """基于 DNA 模式聚类"""
        clusters = defaultdict(list)

        for winner in self.winners:
            dna = winner.get("dna", {})
            metrics = winner.get("metrics", {})

            # 高 CTR 阈值
            is_high_ctr = metrics.get("ctr", 0) >= 2.5

            # 基于 Hook + Action 组合聚类
            hook_type = dna.get("hook_type", "general")
            subject = dna.get("subject", "character")
            action = dna.get("action", "showcase")

            # 命名 Archetype
            archetype_name = self._name_archetype(hook_type, subject, action, is_high_ctr)
            clusters[archetype_name].append(winner)

        return dict(clusters)

    @staticmethod
    def _name_archetype(hook_type: str, subject: str, action: str, is_high_ctr: bool) -> str:
        """命名 Archetype"""
        prefix = "Premium" if is_high_ctr else "Classic"

        subject_map = {
            "dragon": "Dragon",
            "witch": "Witch",
            "castle": "Castle",
            "hero": "Hero",
            "character": "Character",
        }
        subj_name = subject_map.get(subject, subject.title())

        hook_action_map = {
            "transformation": "Evolution",
            "upgrade": "Upgrade",
            "merge": "Merge",
            "shock": "Shock",
            "challenge": "Challenge",
            "curiosity": "Mystery",
            "urgency": "Rescue",
            "battle": "Battle",
            "unlock": "Unlock",
            "showcase": "Showcase",
        }
        action_name = hook_action_map.get(action, hook_action_map.get(hook_type, "General"))

        return f"{prefix}_{subj_name}_{action_name}"

    def _build_archetype_from_cluster(self, name: str, winners: List[dict]) -> PerformanceArchetype:
        """从聚类构建 Archetype"""
        ctrs = [w["metrics"].get("ctr", 0) for w in winners]
        cpis = [w["metrics"].get("cpi", 1.0) for w in winners]
        rois = [w["metrics"].get("d7_roi", 0) for w in winners if w["metrics"].get("d7_roi")]

        avg_ctr = float(np.mean(ctrs)) if ctrs else 0
        avg_cpi = float(np.mean(cpis)) if cpis else 1.0
        avg_roi = float(np.mean(rois)) if rois else 0

        # 提取关键特征
        all_dna = [w.get("dna", {}) for w in winners]
        key_features = self._extract_key_features(all_dna)

        # 构建代表性 DNA（取均值）
        rep_dna = self._compute_representative_dna(all_dna)

        # 置信度 = Winner 数量 * 平均 CTR 归一化
        confidence = min(100, len(winners) * 10 + avg_ctr * 5)

        description = f"{name} archetype with {len(winners)} winners, " \
                     f"avg CTR {avg_ctr:.2f}%, avg CPI ${avg_cpi:.2f}"

        return PerformanceArchetype(
            name=name,
            description=description,
            avg_ctr=round(avg_ctr, 2),
            avg_cpi=round(avg_cpi, 2),
            avg_d7_roi=round(avg_roi, 3),
            winner_count=len(winners),
            representative_dna=rep_dna,
            key_features=key_features,
            confidence=round(confidence, 1),
        )

    @staticmethod
    def _extract_key_features(dna_list: List[dict]) -> List[str]:
        """提取关键特征"""
        features = Counter()

        for dna in dna_list:
            if dna.get("hook_type"):
                features[f"hook:{dna['hook_type']}"] += 1
            if dna.get("subject"):
                features[f"subject:{dna['subject']}"] += 1
            if dna.get("action"):
                features[f"action:{dna['action']}"] += 1
            if dna.get("emotion"):
                features[f"emotion:{dna['emotion']}"] += 1

        return [f for f, _ in features.most_common(5)]

    @staticmethod
    def _compute_representative_dna(dna_list: List[dict]) -> dict:
        """计算代表性 DNA（均值）"""
        n = len(dna_list) or 1

        def avg_key(key, default=0):
            vals = [d.get(key, default) for d in dna_list if isinstance(d.get(key), (int, float))]
            return float(np.mean(vals)) if vals else default

        def most_common(key):
            vals = [d.get(key, "") for d in dna_list if d.get(key)]
            if not vals:
                return ""
            return Counter(vals).most_common(1)[0][0]

        return {
            "hook_dna": {
                "hook_type": most_common("hook_type"),
                "first_frame_strength": round(avg_key("first_frame_strength"), 1),
                "motion_speed": round(avg_key("motion_speed"), 1),
                "novelty": round(avg_key("novelty"), 1),
                "emotion": round(avg_key("emotion"), 1),
                "overall_hook": round(avg_key("overall_hook"), 1),
            },
            "subject_dna": {
                "primary_subject": most_common("subject"),
                "subjects": [most_common("subject")],
                "size_ratio": round(avg_key("size_ratio", 0.3), 3),
            },
            "gameplay_dna": {
                "action": most_common("action"),
                "clarity": round(avg_key("clarity"), 1),
                "merge_score": round(avg_key("merge_score"), 1),
                "upgrade_score": round(avg_key("upgrade_score"), 1),
            },
            "reward_dna": {
                "reward_type": most_common("reward_type"),
                "reward_score": round(avg_key("reward_score"), 1),
                "flash_strength": round(avg_key("flash_strength"), 1),
            },
            "structure_dna": {
                "pacing": most_common("pacing") or "medium",
                "hook_duration": round(avg_key("hook_duration", 2), 1),
                "gameplay_duration": round(avg_key("gameplay_duration", 6), 1),
                "reward_duration": round(avg_key("reward_duration", 4), 1),
            },
        }

    def _build_default_archetypes(self) -> Dict[str, PerformanceArchetype]:
        """构建默认 Archetype（无数据时）"""
        defaults = [
            {
                "name": "Dragon_Evolution",
                "description": "龙进化类创意 - 从蛋到巨龙的成长展示",
                "avg_ctr": 3.5,
                "avg_cpi": 0.45,
                "avg_d7_roi": 0.35,
                "winner_count": 0,
                "key_features": ["hook:transformation", "subject:dragon", "action:upgrade", "emotion:achievement"],
                "dna": {
                    "hook_dna": {"hook_type": "transformation", "first_frame_strength": 75, "motion_speed": 60, "novelty": 70, "emotion": 65, "overall_hook": 72},
                    "subject_dna": {"primary_subject": "dragon", "subjects": ["dragon"], "size_ratio": 0.45},
                    "gameplay_dna": {"action": "upgrade", "clarity": 70, "merge_score": 40, "upgrade_score": 80},
                    "reward_dna": {"reward_type": "dragon_evolution", "reward_score": 80, "flash_strength": 70},
                    "structure_dna": {"pacing": "medium", "hook_duration": 2.0, "gameplay_duration": 7.0, "reward_duration": 4.0},
                },
            },
            {
                "name": "Witch_Magic",
                "description": "女巫魔法类创意 - 魔法效果与神秘氛围",
                "avg_ctr": 3.2,
                "avg_cpi": 0.50,
                "avg_d7_roi": 0.30,
                "winner_count": 0,
                "key_features": ["hook:curiosity", "subject:witch", "action:showcase", "emotion:curiosity"],
                "dna": {
                    "hook_dna": {"hook_type": "curiosity", "first_frame_strength": 70, "motion_speed": 55, "novelty": 75, "emotion": 60, "overall_hook": 68},
                    "subject_dna": {"primary_subject": "witch", "subjects": ["witch", "magic"], "size_ratio": 0.40},
                    "gameplay_dna": {"action": "showcase", "clarity": 65, "merge_score": 30, "upgrade_score": 50},
                    "reward_dna": {"reward_type": "magic_effect", "reward_score": 75, "flash_strength": 80},
                    "structure_dna": {"pacing": "medium", "hook_duration": 2.5, "gameplay_duration": 6.5, "reward_duration": 4.0},
                },
            },
            {
                "name": "Merge_Challenge",
                "description": "合并挑战类创意 - 合并玩法与进度展示",
                "avg_ctr": 2.8,
                "avg_cpi": 0.55,
                "avg_d7_roi": 0.28,
                "winner_count": 0,
                "key_features": ["hook:challenge", "subject:character", "action:merge", "emotion:excitement"],
                "dna": {
                    "hook_dna": {"hook_type": "challenge", "first_frame_strength": 65, "motion_speed": 70, "novelty": 60, "emotion": 55, "overall_hook": 63},
                    "subject_dna": {"primary_subject": "character", "subjects": ["character"], "size_ratio": 0.35},
                    "gameplay_dna": {"action": "merge", "clarity": 80, "merge_score": 85, "upgrade_score": 60},
                    "reward_dna": {"reward_type": "general", "reward_score": 65, "flash_strength": 55},
                    "structure_dna": {"pacing": "fast", "hook_duration": 1.5, "gameplay_duration": 8.0, "reward_duration": 3.5},
                },
            },
            {
                "name": "Rescue_Story",
                "description": "救援故事类创意 - 紧急救援与情感共鸣",
                "avg_ctr": 3.8,
                "avg_cpi": 0.40,
                "avg_d7_roi": 0.38,
                "winner_count": 0,
                "key_features": ["hook:urgency", "subject:character", "action:unlock", "emotion:urgency"],
                "dna": {
                    "hook_dna": {"hook_type": "urgency", "first_frame_strength": 80, "motion_speed": 65, "novelty": 65, "emotion": 80, "overall_hook": 78},
                    "subject_dna": {"primary_subject": "character", "subjects": ["character", "treasure"], "size_ratio": 0.40},
                    "gameplay_dna": {"action": "unlock", "clarity": 70, "merge_score": 30, "upgrade_score": 65},
                    "reward_dna": {"reward_type": "treasure", "reward_score": 85, "flash_strength": 75},
                    "structure_dna": {"pacing": "fast", "hook_duration": 1.8, "gameplay_duration": 6.0, "reward_duration": 5.0},
                },
            },
        ]

        for item in defaults:
            archetype = PerformanceArchetype(
                name=item["name"],
                description=item["description"],
                avg_ctr=item["avg_ctr"],
                avg_cpi=item["avg_cpi"],
                avg_d7_roi=item["avg_d7_roi"],
                winner_count=item["winner_count"],
                representative_dna=item["dna"],
                key_features=item["key_features"],
                confidence=70.0,
            )
            self.archetypes[item["name"]] = archetype
            self.similarity_engine.add_archetype(
                item["name"], item["dna"],
                {"avg_ctr": item["avg_ctr"], "avg_cpi": item["avg_cpi"], "avg_d7_roi": item["avg_d7_roi"]}
            )

        return self.archetypes

    def classify_creative(self, dna: dict) -> dict:
        """分类创意到最接近的 Archetype"""
        if not self.archetypes:
            self.discover_archetypes()

        archetype_name, similarity = self.similarity_engine.find_closest_archetype(dna)
        archetype = self.archetypes.get(archetype_name)

        return {
            "archetype": archetype_name,
            "similarity": similarity.overall,
            "confidence": similarity.confidence,
            "archetype_info": {
                "avg_ctr": archetype.avg_ctr if archetype else 0,
                "avg_cpi": archetype.avg_cpi if archetype else 1.0,
                "avg_d7_roi": archetype.avg_d7_roi if archetype else 0,
                "key_features": archetype.key_features if archetype else [],
            },
            "dimension_similarity": {
                "hook": similarity.hook_similarity,
                "subject": similarity.subject_similarity,
                "gameplay": similarity.gameplay_similarity,
                "reward": similarity.reward_similarity,
                "structure": similarity.structure_similarity,
            },
        }

    def get_archetype_ranking(self) -> List[dict]:
        """按绩效排序 Archetype"""
        ranked = []
        for name, arch in self.archetypes.items():
            score = arch.avg_ctr * 0.4 + (1.0 / max(arch.avg_cpi, 0.01)) * 0.3 + arch.avg_d7_roi * 100 * 0.3
            ranked.append({
                "name": name,
                "avg_ctr": arch.avg_ctr,
                "avg_cpi": arch.avg_cpi,
                "avg_d7_roi": arch.avg_d7_roi,
                "winner_count": arch.winner_count,
                "performance_score": round(score, 2),
                "key_features": arch.key_features,
            })
        ranked.sort(key=lambda x: x["performance_score"], reverse=True)
        return ranked

    def save_archetypes(self, output_path: Path):
        """保存 Archetype 到文件"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "archetypes": {
                name: {
                    "name": arch.name,
                    "description": arch.description,
                    "avg_ctr": arch.avg_ctr,
                    "avg_cpi": arch.avg_cpi,
                    "avg_d7_roi": arch.avg_d7_roi,
                    "winner_count": arch.winner_count,
                    "representative_dna": arch.representative_dna,
                    "key_features": arch.key_features,
                    "confidence": arch.confidence,
                }
                for name, arch in self.archetypes.items()
            },
            "ranking": self.get_archetype_ranking(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
