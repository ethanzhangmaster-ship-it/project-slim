"""Video Feature Store - 统一视频特征定义和标准化

所有 Agent 统一使用这里的特征定义。
特征标准化：数值型归一化，类别型编码。
"""
from __future__ import annotations

from typing import Any


FEATURE_SCHEMA = {
    "character_type": {"type": "categorical", "values": ["witch", "wizard", "girl", "boy", "fairy_queen", "sorceress"]},
    "character_clothes": {"type": "string"},
    "character_pose": {"type": "categorical", "values": ["standing", "sitting", "floating", "walking", "kneeling"]},
    "character_gesture": {"type": "categorical", "values": ["hands_clasped", "pointing", "waving", "casting", "holding_creature", "arms_open"]},
    "character_emotion": {"type": "categorical", "values": ["happy", "gentle", "surprised", "curious", "mysterious"]},

    "creature_0_type": {"type": "categorical", "values": ["dragon", "cat", "fox", "owl", "unicorn", "fairy", "magic_egg", "squirrel", "phoenix", "rabbit"]},
    "creature_0_color": {"type": "categorical", "values": ["blue", "cyan", "pink", "purple", "green", "gold", "orange", "white", "rainbow", "silver"]},
    "creature_0_glow": {"type": "categorical", "values": ["cyan", "pink", "gold", "white", "purple", "green", "rainbow", "soft_blue"]},
    "creature_0_action": {"type": "categorical", "values": ["perched", "flying", "sleeping", "playing", "curious", "eating", "hiding", "running", "glowing"]},
    "creature_count": {"type": "numeric", "min": 0, "max": 10},

    "environment_type": {"type": "categorical", "values": ["magic_forest", "crystal_cave", "moon_lake", "magic_garden", "star_tower", "sky_island", "vineyard", "mushroom_village"]},
    "environment_time": {"type": "categorical", "values": ["night", "sunset", "dawn", "dusk", "midnight", "twilight"]},

    "lighting_temperature": {"type": "categorical", "values": ["warm", "cool", "neutral", "golden", "moonlit", "sunset", "dawn", "mysterious"]},
    "lighting_effects_0": {"type": "categorical", "values": ["particles", "bloom", "sparkles", "glow", "rays", "fireflies", "snow", "bubbles", "stars"]},

    "colors_mood": {"type": "categorical", "values": ["balanced", "warm", "cool", "vibrant", "dark", "pastel", "enchanted", "mysterious", "epic"]},
    "saturation_level": {"type": "numeric", "min": 0, "max": 1},
    "brightness_level": {"type": "numeric", "min": 0, "max": 1},

    "camera_shot": {"type": "categorical", "values": ["medium", "close_up", "wide", "full_body", "extreme_close"]},
    "camera_movement": {"type": "categorical", "values": ["static", "push_in", "orbit", "tilt_up", "pull_back", "slow_zoom"]},

    "composition_layout": {"type": "categorical", "values": ["centered", "layered", "rule_of_thirds", "split", "diagonal"]},

    "hook_type": {"type": "categorical", "values": ["collection", "curiosity", "crisis", "reward", "comparison", "transformation", "challenge"]},

    "gameplay_type": {"type": "categorical", "values": ["merge", "collection", "match3", "story", "simulation"]},

    "country": {"type": "categorical"},
    "age_range": {"type": "categorical", "values": ["18-24", "25-34", "35-44", "45+"]},
    "gender": {"type": "categorical", "values": ["M", "F", "ALL"]},
    "placement": {"type": "categorical", "values": ["FB_Feed", "IG_Feed", "IG_Reels", "FB_Reels", "Audience_Network", "Stories"]},
    "os": {"type": "categorical", "values": ["iOS", "Android", "ALL"]},

    "ctr": {"type": "target", "min": 0, "max": 1},
    "cvr": {"type": "target", "min": 0, "max": 1},
    "ipm": {"type": "target", "min": 0, "max": 100},
    "roas_d7": {"type": "target", "min": 0, "max": 10},
}


class VideoFeatureStore:
    """视频特征存储 - 统一特征定义和标准化"""

    def __init__(self, schema: dict[str, dict[str, Any]] | None = None) -> None:
        self._schema = schema or FEATURE_SCHEMA

    def get_feature_type(self, name: str) -> str:
        """获取特征类型

        Args:
            name: 特征名

        Returns:
            特征类型: categorical, numeric, string, target
        """
        if name not in self._schema:
            return "unknown"
        return self._schema[name]["type"]

    def get_feature_names(self) -> list[str]:
        """获取所有特征名

        Returns:
            所有特征名列表
        """
        return list(self._schema.keys())

    def get_target_names(self) -> list[str]:
        """获取所有预测目标名

        Returns:
            预测目标名列表
        """
        return [name for name, spec in self._schema.items() if spec["type"] == "target"]

    def get_categorical_names(self) -> list[str]:
        """获取所有类别特征名

        Returns:
            类别特征名列表
        """
        return [name for name, spec in self._schema.items() if spec["type"] == "categorical"]

    def get_numeric_names(self) -> list[str]:
        """获取所有数值特征名

        Returns:
            数值特征名列表
        """
        return [name for name, spec in self._schema.items() if spec["type"] == "numeric"]

    def get_categorical_values(self, name: str) -> list[str]:
        """获取类别特征的所有可能值

        Args:
            name: 特征名

        Returns:
            可能值列表，如果没有预定义则返回空列表
        """
        if name not in self._schema:
            return []
        spec = self._schema[name]
        if spec["type"] != "categorical":
            return []
        return spec.get("values", [])

    def normalize_feature(self, name: str, value: Any) -> float | str:
        """单个特征标准化

        Args:
            name: 特征名
            value: 原始值

        Returns:
            标准化后的值
            - numeric: 归一化到 [0, 1]
            - categorical: 返回原值 (用于后续编码)
            - string: 返回原值
            - target: 归一化到 [0, 1]
        """
        if name not in self._schema:
            return value

        spec = self._schema[name]
        ftype = spec["type"]

        if ftype == "numeric" or ftype == "target":
            return self._normalize_numeric(value, spec.get("min", 0), spec.get("max", 1))

        if ftype == "categorical":
            return self._normalize_categorical(value, spec.get("values", []))

        if ftype == "string":
            return str(value) if value is not None else ""

        return value

    def _normalize_numeric(self, value: Any, min_val: float, max_val: float) -> float:
        """数值归一化

        Args:
            value: 原始值
            min_val: 最小值
            max_val: 最大值

        Returns:
            归一化后的值 [0, 1]
        """
        try:
            v = float(value)
        except (ValueError, TypeError):
            return 0.0

        if max_val == min_val:
            return 0.0

        normalized = (v - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    def _normalize_categorical(self, value: Any, valid_values: list[str]) -> str:
        """类别特征标准化

        Args:
            value: 原始值
            valid_values: 有效值列表 (空列表表示不限制)

        Returns:
            标准化后的类别值
        """
        s = str(value).strip().lower() if value is not None else ""

        if not valid_values:
            return s

        lower_valid = [v.lower() for v in valid_values]
        if s in lower_valid:
            idx = lower_valid.index(s)
            return valid_values[idx]

        return s

    def normalize_batch(self, features_dict: dict[str, Any]) -> dict[str, Any]:
        """批量标准化

        Args:
            features_dict: 原始特征字典

        Returns:
            标准化后的特征字典
        """
        result: dict[str, Any] = {}
        for name, value in features_dict.items():
            result[name] = self.normalize_feature(name, value)
        return result

    def encode_categorical(self, name: str, value: str) -> dict[str, int]:
        """类别特征 one-hot 编码

        Args:
            name: 特征名
            value: 特征值

        Returns:
            one-hot 编码字典 {feature_value: 0/1}
        """
        values = self.get_categorical_values(name)
        if not values:
            return {f"{name}_{value}": 1} if value else {}

        result: dict[str, int] = {}
        lower_val = value.lower() if value else ""

        for v in values:
            key = f"{name}_{v}"
            result[key] = 1 if v.lower() == lower_val else 0

        return result

    def encode_batch_categorical(self, features_dict: dict[str, Any],
                                 only_categorical: bool = True) -> dict[str, Any]:
        """批量 one-hot 编码类别特征

        Args:
            features_dict: 特征字典
            only_categorical: 是否只包含类别特征的编码结果

        Returns:
            编码后的特征字典
        """
        result: dict[str, Any] = {}

        if not only_categorical:
            for name, value in features_dict.items():
                ftype = self.get_feature_type(name)
                if ftype in ("numeric", "target"):
                    result[name] = self.normalize_feature(name, value)

        for name, value in features_dict.items():
            if self.get_feature_type(name) == "categorical":
                encoded = self.encode_categorical(name, str(value))
                result.update(encoded)

        return result

    def extract_features_from_dna(self, dna_dict: dict[str, Any]) -> dict[str, Any]:
        """从 DNA dict 提取扁平特征

        支持嵌套字典，递归展平为扁平键。

        Args:
            dna_dict: DNA 字典 (可嵌套)

        Returns:
            扁平特征字典
        """
        result: dict[str, Any] = {}
        self._flatten_dict(dna_dict, "", result)
        return result

    def _flatten_dict(self, d: dict[str, Any], prefix: str, result: dict[str, Any]) -> None:
        """递归展平字典

        Args:
            d: 当前字典
            prefix: 键前缀
            result: 结果字典
        """
        for key, value in d.items():
            new_key = f"{prefix}_{key}" if prefix else key
            if isinstance(value, dict):
                self._flatten_dict(value, new_key, result)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._flatten_dict(item, f"{new_key}_{i}", result)
                    else:
                        result[f"{new_key}_{i}"] = item
            else:
                result[new_key] = value

    def validate_features(self, features_dict: dict[str, Any]) -> tuple[bool, list[str]]:
        """验证特征合法性

        Args:
            features_dict: 待验证的特征字典

        Returns:
            (是否合法, 错误信息列表)
        """
        errors: list[str] = []

        for name, value in features_dict.items():
            if name not in self._schema:
                continue

            spec = self._schema[name]
            ftype = spec["type"]

            if ftype == "categorical":
                valid_values = spec.get("values", [])
                if valid_values and value is not None:
                    lower_val = str(value).lower()
                    lower_valid = [v.lower() for v in valid_values]
                    if lower_val not in lower_valid and lower_val != "":
                        errors.append(
                            f"特征 '{name}' 的值 '{value}' 不在有效值列表中: {valid_values}"
                        )

            elif ftype in ("numeric", "target"):
                if value is not None:
                    try:
                        v = float(value)
                        min_val = spec.get("min")
                        max_val = spec.get("max")
                        if min_val is not None and v < min_val:
                            errors.append(
                                f"特征 '{name}' 的值 {v} 小于最小值 {min_val}"
                            )
                        if max_val is not None and v > max_val:
                            errors.append(
                                f"特征 '{name}' 的值 {v} 大于最大值 {max_val}"
                            )
                    except (ValueError, TypeError):
                        errors.append(f"特征 '{name}' 的值 '{value}' 不是有效数值")

        return len(errors) == 0, errors

    def get_feature_spec(self, name: str) -> dict[str, Any] | None:
        """获取特征规格

        Args:
            name: 特征名

        Returns:
            特征规格字典
        """
        return self._schema.get(name)

    def add_feature(self, name: str, spec: dict[str, Any]) -> None:
        """添加自定义特征

        Args:
            name: 特征名
            spec: 特征规格字典
        """
        self._schema[name] = spec

    def remove_feature(self, name: str) -> None:
        """移除特征

        Args:
            name: 特征名
        """
        if name in self._schema:
            del self._schema[name]

    def filter_features(self, features_dict: dict[str, Any],
                        include_types: list[str] | None = None,
                        exclude_types: list[str] | None = None,
                        include_names: list[str] | None = None,
                        exclude_names: list[str] | None = None) -> dict[str, Any]:
        """过滤特征

        Args:
            features_dict: 原始特征字典
            include_types: 只包含这些类型的特征
            exclude_types: 排除这些类型的特征
            include_names: 只包含这些名称的特征
            exclude_names: 排除这些名称的特征

        Returns:
            过滤后的特征字典
        """
        result: dict[str, Any] = {}

        for name, value in features_dict.items():
            if include_names and name not in include_names:
                continue
            if exclude_names and name in exclude_names:
                continue

            ftype = self.get_feature_type(name)
            if include_types and ftype not in include_types:
                continue
            if exclude_types and ftype in exclude_types:
                continue

            result[name] = value

        return result

    def get_encoded_dimension(self, feature_names: list[str] | None = None) -> int:
        """获取编码后的总维度

        Args:
            feature_names: 特征名列表，None 表示所有特征

        Returns:
            总维度数
        """
        if feature_names is None:
            feature_names = self.get_feature_names()

        total = 0
        for name in feature_names:
            spec = self._schema.get(name)
            if not spec:
                continue
            ftype = spec["type"]
            if ftype == "categorical":
                values = spec.get("values", [])
                total += len(values) if values else 1
            elif ftype in ("numeric", "target"):
                total += 1
            else:
                total += 1

        return total
