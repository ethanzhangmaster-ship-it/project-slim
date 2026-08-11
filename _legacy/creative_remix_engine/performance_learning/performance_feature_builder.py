"""Performance Feature Builder — 把 Video DNA 转换为机器学习 Feature

输入：Video DNA
输出：Feature Vector

用于模型训练和预测。
"""
from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np


class PerformanceFeatureBuilder:
    """表现特征构建器"""

    # 编码映射
    HOOK_TYPES = ["transformation", "challenge", "curiosity", "urgency", "shock", "general"]
    SUBJECT_TYPES = ["dragon", "witch", "castle", "hero", "monster", "treasure", "character"]
    GAMEPLAY_TYPES = ["merge", "upgrade", "battle", "unlock", "showcase", "drag"]
    REWARD_TYPES = ["evolution", "treasure", "magic", "new_character", "general"]

    def __init__(self):
        self.hook_encoder = {t: i for i, t in enumerate(self.HOOK_TYPES)}
        self.subject_encoder = {t: i for i, t in enumerate(self.SUBJECT_TYPES)}
        self.gameplay_encoder = {t: i for i, t in enumerate(self.GAMEPLAY_TYPES)}
        self.reward_encoder = {t: i for i, t in enumerate(self.REWARD_TYPES)}

    def encode_dna(self, dna: Dict) -> np.ndarray:
        """把 DNA 编码为特征向量"""
        features = []

        # Hook Type (One-Hot)
        hook_onehot = self._one_hot_encode(dna.get("hook", ""), self.hook_encoder, len(self.HOOK_TYPES))
        features.extend(hook_onehot)

        # Subject Type (One-Hot)
        subject_onehot = self._one_hot_encode(dna.get("subject", ""), self.subject_encoder, len(self.SUBJECT_TYPES))
        features.extend(subject_onehot)

        # Gameplay Type (One-Hot)
        gameplay_onehot = self._one_hot_encode(dna.get("gameplay", ""), self.gameplay_encoder, len(self.GAMEPLAY_TYPES))
        features.extend(gameplay_onehot)

        # Reward Type (One-Hot)
        reward_onehot = self._one_hot_encode(dna.get("reward", ""), self.reward_encoder, len(self.REWARD_TYPES))
        features.extend(reward_onehot)

        # Numeric Features
        features.append(dna.get("motion_score", 50) / 100)
        features.append(dna.get("subject_size", 30) / 100)
        features.append(dna.get("gameplay_clarity", 50) / 100)
        features.append(dna.get("reward_strength", 50) / 100)
        features.append(dna.get("emotion", 50) / 100)
        features.append(dna.get("duration", 15) / 30)
        features.append(dna.get("structure_score", 50) / 100)

        return np.array(features, dtype=np.float32)

    def _one_hot_encode(self, value: str, encoder: Dict[str, int], size: int) -> List[float]:
        """One-Hot 编码"""
        encoded = [0.0] * size
        if value in encoder:
            encoded[encoder[value]] = 1.0
        return encoded

    def build_feature_matrix(self, dna_list: List[Dict]) -> np.ndarray:
        """构建特征矩阵"""
        features = []
        for dna in dna_list:
            features.append(self.encode_dna(dna))
        return np.array(features)

    def build_training_data(self, data: List[Dict], target_key: str = "ctr") -> tuple:
        """构建训练数据 (X, y)"""
        X = []
        y = []

        for item in data:
            dna = item.get("dna", {})
            perf = item.get("performance", {})

            if target_key in perf:
                X.append(self.encode_dna(dna))
                y.append(perf[target_key])

        return np.array(X), np.array(y)

    def get_feature_names(self) -> List[str]:
        """获取特征名称"""
        names = []

        for t in self.HOOK_TYPES:
            names.append(f"hook_{t}")
        for t in self.SUBJECT_TYPES:
            names.append(f"subject_{t}")
        for t in self.GAMEPLAY_TYPES:
            names.append(f"gameplay_{t}")
        for t in self.REWARD_TYPES:
            names.append(f"reward_{t}")

        names.extend([
            "motion_score",
            "subject_size",
            "gameplay_clarity",
            "reward_strength",
            "emotion",
            "duration",
            "structure_score",
        ])

        return names

    def analyze_feature_importance(self, importances: np.ndarray) -> List[Dict]:
        """分析特征重要性"""
        names = self.get_feature_names()
        result = []

        for name, importance in zip(names, importances):
            result.append({
                "feature": name,
                "importance": round(float(importance), 4),
            })

        result.sort(key=lambda x: -x["importance"])
        return result

    def normalize_features(self, X: np.ndarray) -> np.ndarray:
        """归一化特征"""
        X_norm = X.copy()
        for i in range(X.shape[1]):
            col = X[:, i]
            min_val = np.min(col)
            max_val = np.max(col)
            if max_val > min_val:
                X_norm[:, i] = (col - min_val) / (max_val - min_val)
        return X_norm
