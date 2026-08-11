"""Predictor Engine - 统一预测入口

支持多种预测器插件：
- RulePredictor: 基于规则的预测（当前默认）
- HistoryPredictor: 基于历史数据的预测
- MLPredictor: 基于机器学习的预测（预留）
- LLMPredictor: 基于大模型的预测（预留）

统一接口：
- predict_ctr(features)
- predict_roas(features)
- predict_cvr(features)
- predict_ipm(features)
- predict_all(features)
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PredictionResult:
    value: float
    confidence: float = 0.0
    breakdown: dict[str, Any] = field(default_factory=dict)
    contributing_features: list[str] = field(default_factory=list)
    predictor_name: str = ""


class BasePredictor(ABC):
    name: str = "base"

    @abstractmethod
    def predict_ctr(self, features: dict[str, Any]) -> PredictionResult:
        ...

    @abstractmethod
    def predict_roas(self, features: dict[str, Any]) -> PredictionResult:
        ...

    @abstractmethod
    def predict_cvr(self, features: dict[str, Any]) -> PredictionResult:
        ...

    @abstractmethod
    def predict_ipm(self, features: dict[str, Any]) -> PredictionResult:
        ...

    def predict_all(self, features: dict[str, Any]) -> dict[str, PredictionResult]:
        return {
            "ctr": self.predict_ctr(features),
            "roas": self.predict_roas(features),
            "cvr": self.predict_cvr(features),
            "ipm": self.predict_ipm(features),
        }

    def _safe_get(self, d: dict, path: list[str], default: Any = None) -> Any:
        current = d
        for key in path:
            if not isinstance(current, dict):
                return default
            current = current.get(key, default)
            if current is None:
                return default
        return current


class RulePredictor(BasePredictor):
    name = "rule"

    HOOK_CTR_WEIGHTS = {
        "collection": 1.25,
        "curiosity": 1.20,
        "crisis": 1.30,
        "reward": 1.15,
        "transformation": 1.28,
        "challenge": 1.22,
        "secret": 1.10,
        "progression": 1.08,
        "achievement": 1.12,
    }

    BRAND_CVR_WEIGHTS = {
        "high": 1.30,
        "medium": 1.10,
        "low": 0.85,
    }

    GAMEPLAY_IPM_WEIGHTS = {
        "merge": 1.20,
        "collection": 1.15,
        "match3": 1.10,
        "puzzle": 1.05,
        "idle": 1.08,
    }

    BASE_CTR = 2.0
    BASE_CVR = 0.15
    BASE_IPM = 8.0
    BASE_ROAS = 0.8

    def predict_ctr(self, features: dict[str, Any]) -> PredictionResult:
        ctr = self.BASE_CTR
        contributing = []
        breakdown = {}

        hook_type = self._safe_get(features, ["hook", "type"], "")
        if hook_type:
            hook_str = str(hook_type).lower()
            weight = 1.0
            for key, w in self.HOOK_CTR_WEIGHTS.items():
                if key in hook_str:
                    weight = max(weight, w)
            if weight != 1.0:
                ctr *= weight
                contributing.append(f"hook:{hook_type}")
                breakdown["hook_factor"] = weight

        colors = self._safe_get(features, ["colors", "mood_palette"], [])
        if colors and isinstance(colors, list):
            vivid_keywords = ["vivid", "bright", "bold", "neon", "鲜艳", "明亮"]
            has_vivid = any(kw in str(c).lower() for c in colors for kw in vivid_keywords)
            if has_vivid:
                ctr *= 1.10
                contributing.append("colors:vivid")
                breakdown["color_factor"] = 1.10

        saturation = self._safe_get(features, ["colors", "saturation"], None)
        if saturation is not None and isinstance(saturation, (int, float)):
            if saturation >= 0.7:
                sat_factor = 1.15
            elif saturation >= 0.5:
                sat_factor = 1.05
            else:
                sat_factor = 0.90
            ctr *= sat_factor
            contributing.append(f"saturation:{saturation}")
            breakdown["saturation_factor"] = sat_factor

        has_cta = self._safe_get(features, ["cta", "has_cta"], False)
        if has_cta:
            ctr *= 1.08
            contributing.append("cta:present")
            breakdown["cta_factor"] = 1.08

        confidence = min(1.0, 0.3 + len(contributing) * 0.1)

        return PredictionResult(
            value=round(ctr, 3),
            confidence=round(confidence, 2),
            breakdown=breakdown,
            contributing_features=contributing,
            predictor_name=self.name,
        )

    def predict_cvr(self, features: dict[str, Any]) -> PredictionResult:
        cvr = self.BASE_CVR
        contributing = []
        breakdown = {}

        brand_consistency = self._safe_get(features, ["brand", "consistency"], "medium")
        brand_str = str(brand_consistency).lower()
        weight = self.BRAND_CVR_WEIGHTS.get(brand_str, 1.0)
        if weight != 1.0:
            cvr *= weight
            contributing.append(f"brand:{brand_consistency}")
            breakdown["brand_factor"] = weight

        character_consistency = self._safe_get(features, ["character", "consistency"], None)
        if character_consistency is not None:
            char_str = str(character_consistency).lower()
            char_weight = self.BRAND_CVR_WEIGHTS.get(char_str, 1.0)
            if char_weight != 1.0:
                cvr *= char_weight
                contributing.append(f"character_consistency:{character_consistency}")
                breakdown["character_factor"] = char_weight

        gameplay_type = self._safe_get(features, ["gameplay", "type"], "")
        if gameplay_type:
            gp_str = str(gameplay_type).lower()
            gp_weight = self.GAMEPLAY_IPM_WEIGHTS.get(gp_str, 1.0)
            if gp_weight != 1.0:
                cvr *= gp_weight * 0.95 + 0.05
                contributing.append(f"gameplay:{gameplay_type}")
                breakdown["gameplay_cvr_factor"] = gp_weight * 0.95 + 0.05

        confidence = min(1.0, 0.25 + len(contributing) * 0.12)

        return PredictionResult(
            value=round(cvr, 4),
            confidence=round(confidence, 2),
            breakdown=breakdown,
            contributing_features=contributing,
            predictor_name=self.name,
        )

    def predict_ipm(self, features: dict[str, Any]) -> PredictionResult:
        ipm = self.BASE_IPM
        contributing = []
        breakdown = {}

        gameplay_type = self._safe_get(features, ["gameplay", "type"], "")
        if gameplay_type:
            gp_str = str(gameplay_type).lower()
            weight = 1.0
            for key, w in self.GAMEPLAY_IPM_WEIGHTS.items():
                if key in gp_str:
                    weight = max(weight, w)
            if weight != 1.0:
                ipm *= weight
                contributing.append(f"gameplay:{gameplay_type}")
                breakdown["gameplay_factor"] = weight

        hook_type = self._safe_get(features, ["hook", "type"], "")
        if hook_type:
            hook_str = str(hook_type).lower()
            if "collection" in hook_str or "reward" in hook_str or "achievement" in hook_str:
                ipm *= 1.12
                contributing.append(f"hook_ipm_boost:{hook_type}")
                breakdown["hook_ipm_factor"] = 1.12

        reward_type = self._safe_get(features, ["reward", "type"], "")
        if reward_type:
            reward_str = str(reward_type).lower()
            if "merge" in reward_str or "upgrade" in reward_str or "unlock" in reward_str:
                ipm *= 1.08
                contributing.append(f"reward:{reward_type}")
                breakdown["reward_factor"] = 1.08

        confidence = min(1.0, 0.3 + len(contributing) * 0.1)

        return PredictionResult(
            value=round(ipm, 2),
            confidence=round(confidence, 2),
            breakdown=breakdown,
            contributing_features=contributing,
            predictor_name=self.name,
        )

    def predict_roas(self, features: dict[str, Any]) -> PredictionResult:
        roas = self.BASE_ROAS
        contributing = []
        breakdown = {}

        ctr_pred = self.predict_ctr(features)
        cvr_pred = self.predict_cvr(features)

        ctr_factor = ctr_pred.value / self.BASE_CTR
        cvr_factor = cvr_pred.value / self.BASE_CVR

        roas *= 0.6 * ctr_factor + 0.4 * cvr_factor
        contributing.extend(ctr_pred.contributing_features)
        contributing.extend(cvr_pred.contributing_features)
        breakdown["ctr_factor"] = ctr_factor
        breakdown["cvr_factor"] = cvr_factor

        similarity = self._safe_get(features, ["similarity", "score"], None)
        if similarity is not None and isinstance(similarity, (int, float)):
            sim_factor = 0.7 + 0.3 * similarity
            roas *= sim_factor
            contributing.append(f"similarity:{similarity}")
            breakdown["similarity_factor"] = sim_factor

        brand_factor = 1.0
        brand_consistency = self._safe_get(features, ["brand", "consistency"], "medium")
        brand_str = str(brand_consistency).lower()
        if brand_str == "high":
            brand_factor = 1.15
        elif brand_str == "low":
            brand_factor = 0.85
        if brand_factor != 1.0:
            roas *= brand_factor
            contributing.append(f"brand_roas:{brand_consistency}")
            breakdown["brand_roas_factor"] = brand_factor

        confidence = min(1.0, 0.25 + len(contributing) * 0.08)

        return PredictionResult(
            value=round(roas, 3),
            confidence=round(confidence, 2),
            breakdown=breakdown,
            contributing_features=list(set(contributing)),
            predictor_name=self.name,
        )


class HistoryPredictor(BasePredictor):
    name = "history"

    def __init__(self, history_data: list[dict[str, Any]] | None = None) -> None:
        self._history: list[dict[str, Any]] = history_data or []

    def set_history_data(self, data: list[dict[str, Any]]) -> None:
        self._history = data

    def add_history_sample(self, sample: dict[str, Any]) -> None:
        self._history.append(sample)

    def _compute_similarity(self, features1: dict[str, Any], features2: dict[str, Any]) -> float:
        score = 0.0
        total = 0.0

        def _compare(v1: Any, v2: Any, weight: float = 1.0) -> tuple[float, float]:
            if v1 is None or v2 is None:
                return 0.0, 0.0
            if isinstance(v1, dict) and isinstance(v2, dict):
                s = 0.0
                t = 0.0
                all_keys = set(v1.keys()) | set(v2.keys())
                for k in all_keys:
                    sub_s, sub_t = _compare(v1.get(k), v2.get(k), weight * 0.5)
                    s += sub_s
                    t += sub_t
                return s, t
            if isinstance(v1, list) and isinstance(v2, list):
                if not v1 and not v2:
                    return weight, weight
                set1 = set(str(x) for x in v1)
                set2 = set(str(x) for x in v2)
                if not set1 or not set2:
                    return 0.0, weight
                overlap = len(set1 & set2)
                union = len(set1 | set2)
                return weight * overlap / union if union > 0 else 0.0, weight
            if str(v1) == str(v2):
                return weight, weight
            return 0.0, weight

        score, total = _compare(features1, features2, 1.0)
        return score / total if total > 0 else 0.0

    def _weighted_predict(
        self,
        features: dict[str, Any],
        metric_key: str,
        min_similarity: float = 0.3,
        top_k: int = 10,
    ) -> PredictionResult:
        scored_samples = []
        for sample in self._history:
            sample_features = sample.get("features", {})
            metric_value = sample.get("metrics", {}).get(metric_key)
            if metric_value is None:
                continue
            sim = self._compute_similarity(features, sample_features)
            if sim >= min_similarity:
                scored_samples.append((sim, metric_value, sample))

        if not scored_samples:
            return PredictionResult(
                value=0.0,
                confidence=0.0,
                breakdown={"reason": "no_matching_history"},
                contributing_features=[],
                predictor_name=self.name,
            )

        scored_samples.sort(key=lambda x: x[0], reverse=True)
        top_samples = scored_samples[:top_k]

        total_weight = sum(sim for sim, _, _ in top_samples)
        if total_weight == 0:
            return PredictionResult(
                value=0.0,
                confidence=0.0,
                breakdown={"reason": "zero_total_weight"},
                contributing_features=[],
                predictor_name=self.name,
            )

        weighted_value = sum(sim * val for sim, val, _ in top_samples) / total_weight
        avg_similarity = total_weight / len(top_samples)
        confidence = min(1.0, avg_similarity * 0.7 + len(top_samples) / top_k * 0.3)

        top_contributors = []
        for sim, val, sample in top_samples[:3]:
            sample_id = sample.get("creative_id", sample.get("id", "unknown"))
            top_contributors.append(f"{sample_id}(sim={sim:.2f})")

        return PredictionResult(
            value=round(weighted_value, 4 if metric_key == "cvr" else 3),
            confidence=round(confidence, 2),
            breakdown={
                "matched_samples": len(top_samples),
                "avg_similarity": round(avg_similarity, 3),
                "top_samples": top_contributors,
            },
            contributing_features=top_contributors,
            predictor_name=self.name,
        )

    def predict_ctr(self, features: dict[str, Any]) -> PredictionResult:
        return self._weighted_predict(features, "ctr")

    def predict_roas(self, features: dict[str, Any]) -> PredictionResult:
        return self._weighted_predict(features, "roas")

    def predict_cvr(self, features: dict[str, Any]) -> PredictionResult:
        return self._weighted_predict(features, "cvr")

    def predict_ipm(self, features: dict[str, Any]) -> PredictionResult:
        return self._weighted_predict(features, "ipm")


class PredictorEngine:
    def __init__(self, default_predictor: str = "rule") -> None:
        self._predictors: dict[str, BasePredictor] = {}
        self._default = default_predictor

        rule_predictor = RulePredictor()
        self._predictors[rule_predictor.name] = rule_predictor

        history_predictor = HistoryPredictor()
        self._predictors[history_predictor.name] = history_predictor

        if default_predictor not in self._predictors:
            self._default = "rule"

    def register_predictor(self, name: str, predictor: BasePredictor) -> None:
        if not isinstance(predictor, BasePredictor):
            raise TypeError("predictor must inherit from BasePredictor")
        self._predictors[name] = predictor

    def set_default(self, name: str) -> None:
        if name not in self._predictors:
            raise ValueError(f"Predictor '{name}' not registered")
        self._default = name

    def _get_predictor(self, name: str | None) -> BasePredictor:
        predictor_name = name or self._default
        if predictor_name not in self._predictors:
            raise ValueError(f"Predictor '{predictor_name}' not registered")
        return self._predictors[predictor_name]

    def predict_ctr(
        self,
        features: dict[str, Any],
        predictor: str | None = None,
    ) -> dict[str, Any]:
        pred = self._get_predictor(predictor)
        result = pred.predict_ctr(features)
        return self._result_to_dict("ctr", result)

    def predict_roas(
        self,
        features: dict[str, Any],
        predictor: str | None = None,
    ) -> dict[str, Any]:
        pred = self._get_predictor(predictor)
        result = pred.predict_roas(features)
        return self._result_to_dict("roas", result)

    def predict_cvr(
        self,
        features: dict[str, Any],
        predictor: str | None = None,
    ) -> dict[str, Any]:
        pred = self._get_predictor(predictor)
        result = pred.predict_cvr(features)
        return self._result_to_dict("cvr", result)

    def predict_ipm(
        self,
        features: dict[str, Any],
        predictor: str | None = None,
    ) -> dict[str, Any]:
        pred = self._get_predictor(predictor)
        result = pred.predict_ipm(features)
        return self._result_to_dict("ipm", result)

    def predict_all(
        self,
        features: dict[str, Any],
        predictor: str | None = None,
    ) -> dict[str, Any]:
        pred = self._get_predictor(predictor)
        results = pred.predict_all(features)
        return {
            metric: self._result_to_dict(metric, result)
            for metric, result in results.items()
        }

    def predict_ensemble(
        self,
        features: dict[str, Any],
        predictor_names: list[str] | None = None,
        weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        if predictor_names is None:
            predictor_names = list(self._predictors.keys())

        all_results: dict[str, list[PredictionResult]] = {}
        for pname in predictor_names:
            if pname not in self._predictors:
                continue
            pred = self._predictors[pname]
            results = pred.predict_all(features)
            for metric, result in results.items():
                all_results.setdefault(metric, []).append(result)

        ensemble = {}
        for metric, results in all_results.items():
            if not results:
                ensemble[metric] = {"value": 0.0, "confidence": 0.0}
                continue

            total_weight = 0.0
            weighted_value = 0.0
            weighted_conf = 0.0
            contributing = []

            for r in results:
                w = 1.0
                if weights and r.predictor_name in weights:
                    w = weights[r.predictor_name]
                w *= r.confidence
                weighted_value += r.value * w
                weighted_conf += r.confidence * w
                total_weight += w
                contributing.extend(r.contributing_features)

            if total_weight > 0:
                final_value = weighted_value / total_weight
                final_conf = weighted_conf / total_weight
            else:
                final_value = sum(r.value for r in results) / len(results)
                final_conf = sum(r.confidence for r in results) / len(results)

            ensemble[metric] = {
                "value": round(final_value, 4 if metric == "cvr" else 3),
                "confidence": round(final_conf, 2),
                "predictor_count": len(results),
                "predictors": [r.predictor_name for r in results],
                "contributing_features": list(set(contributing))[:10],
            }

        return ensemble

    def train(
        self,
        features_list: list[dict[str, Any]],
        labels_list: list[dict[str, float]],
    ) -> dict[str, Any]:
        history_predictor = self._predictors.get("history")
        if history_predictor and isinstance(history_predictor, HistoryPredictor):
            for features, labels in zip(features_list, labels_list):
                history_predictor.add_history_sample({
                    "features": features,
                    "metrics": labels,
                })

        return {
            "trained_predictors": ["history"],
            "samples_added": len(features_list),
        }

    def evaluate(
        self,
        test_features: list[dict[str, Any]],
        test_labels: list[dict[str, float]],
        predictor: str | None = None,
    ) -> dict[str, Any]:
        pred = self._get_predictor(predictor)
        metrics = ["ctr", "roas", "cvr", "ipm"]
        errors: dict[str, list[float]] = {m: [] for m in metrics}

        for features, labels in zip(test_features, test_labels):
            predictions = pred.predict_all(features)
            for metric in metrics:
                actual = labels.get(metric)
                predicted = predictions[metric].value
                if actual is not None and actual > 0:
                    errors[metric].append(abs(predicted - actual) / actual)

        result: dict[str, Any] = {"predictor": pred.name, "sample_count": len(test_features)}
        for metric in metrics:
            err_list = errors[metric]
            if err_list:
                result[f"{metric}_mape"] = round(sum(err_list) / len(err_list), 4)
                result[f"{metric}_samples"] = len(err_list)
            else:
                result[f"{metric}_mape"] = None
                result[f"{metric}_samples"] = 0

        return result

    def _result_to_dict(self, metric: str, result: PredictionResult) -> dict[str, Any]:
        return {
            "metric": metric,
            "value": result.value,
            "confidence": result.confidence,
            "breakdown": result.breakdown,
            "contributing_features": result.contributing_features,
            "predictor": result.predictor_name,
        }

    def get_available_predictors(self) -> list[str]:
        return list(self._predictors.keys())

    def get_default_predictor(self) -> str:
        return self._default
