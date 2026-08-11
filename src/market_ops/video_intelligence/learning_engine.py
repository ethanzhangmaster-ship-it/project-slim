"""Learning Engine - 增量学习引擎

输入：Facebook 投放结果（CTR/CVR/IPM/ROAS/Spend）
输出：
- Feature Importance 变化
- Variable Weight 更新
- Predictor Update

支持 incremental_train()，不要全量训练。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import math


@dataclass(slots=True)
class LearningStats:
    total_samples: int = 0
    last_update: str = ""
    feature_count: int = 0
    drift_detected: bool = False


@dataclass(slots=True)
class FeatureImportance:
    feature_name: str
    importance: float = 0.0
    delta: float = 0.0
    trend: str = "stable"


class VideoLearningEngine:
    """增量学习引擎 - 基于投放结果持续优化"""

    def __init__(
        self,
        memory_engine: Any = None,
        predictor_engine: Any = None,
    ):
        self.memory_engine = memory_engine
        self.predictor_engine = predictor_engine

        self._feature_weights: dict[str, float] = {}
        self._feature_importance_history: list[dict[str, float]] = []
        self._training_data: list[dict] = []
        self._baseline_stats: dict[str, float] = {}
        self._stats = LearningStats()
        self._learning_rate = 0.1
        self._initialized = False

    def incremental_train(self, new_results: list[dict]) -> dict[str, Any]:
        """增量训练

        - 更新 Memory Engine
        - 更新 Knowledge Graph
        - 更新 Predictor 权重
        - 返回学习报告
        """
        if not new_results:
            return {
                "status": "skipped",
                "reason": "no_new_data",
                "samples_processed": 0,
            }

        valid_results = self._validate_results(new_results)
        if not valid_results:
            return {
                "status": "skipped",
                "reason": "no_valid_data",
                "samples_processed": 0,
            }

        self._training_data.extend(valid_results)
        self._stats.total_samples += len(valid_results)
        self._stats.last_update = datetime.now().isoformat()

        prev_importance = self._get_current_importance()
        self._update_feature_weights(valid_results)
        new_importance = self._get_current_importance()

        if self.memory_engine is not None and hasattr(self.memory_engine, "update"):
            try:
                self.memory_engine.update(valid_results)
            except Exception:
                pass

        if self.predictor_engine is not None and hasattr(self.predictor_engine, "update_weights"):
            try:
                self.predictor_engine.update_weights(self._feature_weights)
            except Exception:
                pass

        importance_changes = self._compute_importance_changes(prev_importance, new_importance)

        drift_result = {}
        if self._baseline_stats:
            current_stats = self._compute_batch_stats(valid_results)
            drift_result = self.detect_drift(current_stats, self._baseline_stats)
            self._stats.drift_detected = drift_result.get("drift_detected", False)
        else:
            self._baseline_stats = self._compute_batch_stats(valid_results)

        self._feature_importance_history.append(dict(new_importance))
        if len(self._feature_importance_history) > 100:
            self._feature_importance_history = self._feature_importance_history[-100:]

        self._initialized = True

        report = {
            "status": "success",
            "samples_processed": len(valid_results),
            "total_samples": self._stats.total_samples,
            "feature_count": len(self._feature_weights),
            "importance_changes": importance_changes,
            "drift": drift_result,
            "top_winning_patterns": self.get_top_winning_patterns(limit=5),
            "top_losing_patterns": self.get_top_losing_patterns(limit=5),
            "timestamp": datetime.now().isoformat(),
        }

        return report

    def _validate_results(self, results: list[dict]) -> list[dict]:
        """验证输入数据"""
        valid = []
        required_metrics = {"spend", "ctr", "cvr", "roas"}

        for r in results:
            if not isinstance(r, dict):
                continue

            has_any_metric = any(k in r for k in required_metrics)
            if not has_any_metric:
                continue

            spend = r.get("spend", 0)
            if spend is None or spend <= 0:
                continue

            valid.append(r)

        return valid

    def _update_feature_weights(self, results: list[dict]) -> None:
        """更新特征权重（增量方式）"""
        feature_performance: dict[str, list[float]] = {}

        for result in results:
            roas = result.get("roas", 0)
            ctr = result.get("ctr", 0)
            cvr = result.get("cvr", 0)
            spend = result.get("spend", 1)

            performance_score = self._compute_performance_score(roas, ctr, cvr, spend)

            features = self._extract_features(result)

            for feat_name, feat_value in features.items():
                if feat_name not in feature_performance:
                    feature_performance[feat_name] = []
                feature_performance[feat_name].append(performance_score)

        for feat_name, scores in feature_performance.items():
            if not scores:
                continue

            avg_score = sum(scores) / len(scores)
            normalized_score = max(-1.0, min(1.0, (avg_score - 50) / 50))

            if feat_name in self._feature_weights:
                old_weight = self._feature_weights[feat_name]
                new_weight = old_weight + self._learning_rate * (normalized_score - old_weight)
                self._feature_weights[feat_name] = max(-1.0, min(1.0, new_weight))
            else:
                self._feature_weights[feat_name] = normalized_score

        self._stats.feature_count = len(self._feature_weights)

    def _compute_performance_score(
        self,
        roas: float,
        ctr: float,
        cvr: float,
        spend: float,
    ) -> float:
        """计算综合性能分数 0-100"""
        roas_score = min(100, roas * 25) if roas > 0 else 0
        ctr_score = min(100, ctr * 200) if ctr > 0 else 0
        cvr_score = min(100, cvr * 500) if cvr > 0 else 0
        spend_factor = min(1.0, math.log(spend + 1) / math.log(1000))

        score = (
            roas_score * 0.4
            + ctr_score * 0.25
            + cvr_score * 0.25
            + spend_factor * 10
        )

        return max(0, min(100, score))

    def _extract_features(self, result: dict) -> dict[str, Any]:
        """从结果中提取特征"""
        features: dict[str, Any] = {}

        feature_prefixes = [
            "hook_", "story_", "reward_", "character_",
            "environment_", "camera_", "motion_", "emotion_",
            "cta_", "style_", "color_", "audio_",
        ]

        for key, value in result.items():
            if any(key.startswith(p) for p in feature_prefixes):
                if isinstance(value, (str, int, float, bool)):
                    features[key] = value
                elif isinstance(value, list):
                    for item in value:
                        features[f"{key}_{item}"] = True

        if "creative_type" in result:
            features["creative_type"] = result["creative_type"]

        if "video_duration" in result:
            duration = result["video_duration"]
            if duration < 15:
                features["duration_short"] = True
            elif duration < 30:
                features["duration_medium"] = True
            else:
                features["duration_long"] = True

        return features

    def _get_current_importance(self) -> dict[str, float]:
        """获取当前特征重要性"""
        return {k: abs(v) for k, v in self._feature_weights.items()}

    def _compute_importance_changes(
        self,
        prev: dict[str, float],
        current: dict[str, float],
    ) -> list[dict]:
        """计算特征重要性变化"""
        changes = []

        all_features = set(prev.keys()) | set(current.keys())

        for feat in all_features:
            old_val = prev.get(feat, 0)
            new_val = current.get(feat, 0)
            delta = new_val - old_val

            if abs(delta) > 0.01 or old_val > 0 or new_val > 0:
                if delta > 0.05:
                    trend = "rising"
                elif delta < -0.05:
                    trend = "falling"
                else:
                    trend = "stable"

                changes.append({
                    "feature": feat,
                    "old_importance": round(old_val, 4),
                    "new_importance": round(new_val, 4),
                    "delta": round(delta, 4),
                    "trend": trend,
                })

        changes.sort(key=lambda x: abs(x["delta"]), reverse=True)
        return changes[:20]

    def compute_feature_importance(self, metric: str = "roas") -> list[dict]:
        """计算特征重要性"""
        if not self._training_data:
            return []

        feature_correlations: dict[str, list[tuple[float, float]]] = {}

        for result in self._training_data:
            metric_value = result.get(metric, 0)
            if metric_value is None:
                continue

            features = self._extract_features(result)

            for feat_name, feat_value in features.items():
                if feat_name not in feature_correlations:
                    feature_correlations[feat_name] = []
                if isinstance(feat_value, bool):
                    feature_correlations[feat_name].append((1.0 if feat_value else 0.0, metric_value))
                elif isinstance(feat_value, (int, float)):
                    feature_correlations[feat_name].append((float(feat_value), metric_value))

        importance_list = []
        for feat_name, pairs in feature_correlations.items():
            if len(pairs) < 5:
                continue

            x_vals = [p[0] for p in pairs]
            y_vals = [p[1] for p in pairs]

            correlation = self._pearson_correlation(x_vals, y_vals)
            importance = abs(correlation)

            importance_list.append({
                "feature_name": feat_name,
                "importance": round(importance, 4),
                "correlation": round(correlation, 4),
                "sample_count": len(pairs),
            })

        importance_list.sort(key=lambda x: x["importance"], reverse=True)
        return importance_list

    def _pearson_correlation(self, x: list[float], y: list[float]) -> float:
        """计算皮尔逊相关系数"""
        n = len(x)
        if n < 2:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denom_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
        denom_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))

        if denom_x == 0 or denom_y == 0:
            return 0.0

        return numerator / (denom_x * denom_y)

    def detect_drift(
        self,
        current_results: dict[str, float] | list[dict],
        baseline_results: dict[str, float] | list[dict] | None = None,
    ) -> dict[str, Any]:
        """检测数据漂移"""
        if isinstance(current_results, list):
            current_stats = self._compute_batch_stats(current_results)
        else:
            current_stats = current_results

        if baseline_results is None:
            baseline_stats = self._baseline_stats
        elif isinstance(baseline_results, list):
            baseline_stats = self._compute_batch_stats(baseline_results)
        else:
            baseline_stats = baseline_results

        if not baseline_stats:
            return {
                "drift_detected": False,
                "message": "no_baseline",
                "metrics": {},
            }

        drift_metrics = {}
        total_drift = 0.0
        drifted_metrics = []

        for metric, current_val in current_stats.items():
            baseline_val = baseline_stats.get(metric)
            if baseline_val is None or baseline_val == 0:
                continue

            relative_change = abs(current_val - baseline_val) / abs(baseline_val)
            drift_score = min(1.0, relative_change)

            is_drifted = relative_change > 0.3
            if is_drifted:
                drifted_metrics.append(metric)

            drift_metrics[metric] = {
                "current": current_val,
                "baseline": baseline_val,
                "relative_change": round(relative_change, 4),
                "drift_score": round(drift_score, 4),
                "is_drifted": is_drifted,
            }

            total_drift += drift_score

        avg_drift = total_drift / len(drift_metrics) if drift_metrics else 0
        drift_detected = len(drifted_metrics) > 0 and avg_drift > 0.2

        return {
            "drift_detected": drift_detected,
            "drift_score": round(avg_drift, 4),
            "drifted_metrics": drifted_metrics,
            "metrics": drift_metrics,
            "severity": "high" if avg_drift > 0.5 else "medium" if avg_drift > 0.2 else "low",
        }

    def _compute_batch_stats(self, results: list[dict]) -> dict[str, float]:
        """计算批量统计数据"""
        if not results:
            return {}

        metrics = ["ctr", "cvr", "roas", "ipm", "spend", "cpc", "cpm", "cpa"]
        stats: dict[str, float] = {}

        for metric in metrics:
            values = [r.get(metric, 0) for r in results if r.get(metric) is not None]
            if values:
                stats[f"avg_{metric}"] = sum(values) / len(values)

        return stats

    def get_learning_progress(self) -> dict[str, Any]:
        """获取学习进度"""
        convergence_score = 0.0
        if len(self._feature_importance_history) >= 10:
            recent = self._feature_importance_history[-5:]
            older = self._feature_importance_history[-10:-5]

            if recent and older:
                recent_avg = self._avg_importance_magnitude(recent[-1])
                older_avg = self._avg_importance_magnitude(older[-1])
                if older_avg > 0:
                    change_rate = abs(recent_avg - older_avg) / older_avg
                    convergence_score = max(0, 1 - change_rate)

        learning_phase = "initial"
        if self._stats.total_samples > 100:
            learning_phase = "learning"
        if self._stats.total_samples > 500 and convergence_score > 0.7:
            learning_phase = "stable"
        if self._stats.drift_detected:
            learning_phase = "adapting"

        return {
            "total_samples": self._stats.total_samples,
            "feature_count": self._stats.feature_count,
            "last_update": self._stats.last_update,
            "learning_phase": learning_phase,
            "convergence_score": round(convergence_score, 4),
            "drift_detected": self._stats.drift_detected,
            "initialized": self._initialized,
        }

    def _avg_importance_magnitude(self, importance_dict: dict[str, float]) -> float:
        """计算平均重要性量级"""
        if not importance_dict:
            return 0.0
        return sum(abs(v) for v in importance_dict.values()) / len(importance_dict)

    def export_training_data(self, output_path: str) -> None:
        """导出训练数据(parquet格式)"""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for parquet export")

        if not self._training_data:
            raise ValueError("No training data to export")

        flat_data = []
        for record in self._training_data:
            flat_record = {}
            for key, value in record.items():
                if isinstance(value, (str, int, float, bool)):
                    flat_record[key] = value
                elif isinstance(value, list):
                    flat_record[key] = ",".join(str(v) for v in value)
                else:
                    flat_record[key] = str(value)
            flat_data.append(flat_record)

        df = pd.DataFrame(flat_data)
        df.to_parquet(output_path, index=False)

    def get_top_winning_patterns(
        self,
        metric: str = "roas",
        limit: int = 10,
    ) -> list[dict]:
        """Top赢家模式"""
        if not self._training_data:
            return []

        pattern_scores: dict[str, list[float]] = {}

        for result in self._training_data:
            metric_value = result.get(metric, 0)
            if metric_value is None or metric_value <= 0:
                continue

            features = self._extract_features(result)

            for feat_name, feat_value in features.items():
                if isinstance(feat_value, bool) and feat_value:
                    if feat_name not in pattern_scores:
                        pattern_scores[feat_name] = []
                    pattern_scores[feat_name].append(metric_value)

        patterns = []
        for pattern, scores in pattern_scores.items():
            if len(scores) < 3:
                continue

            avg_score = sum(scores) / len(scores)
            patterns.append({
                "pattern": pattern,
                f"avg_{metric}": round(avg_score, 4),
                "sample_count": len(scores),
                "type": "winner",
            })

        patterns.sort(key=lambda x: x[f"avg_{metric}"], reverse=True)
        return patterns[:limit]

    def get_top_losing_patterns(
        self,
        metric: str = "roas",
        limit: int = 10,
    ) -> list[dict]:
        """Top输家模式"""
        if not self._training_data:
            return []

        pattern_scores: dict[str, list[float]] = {}

        for result in self._training_data:
            metric_value = result.get(metric, 0)
            if metric_value is None:
                continue

            features = self._extract_features(result)

            for feat_name, feat_value in features.items():
                if isinstance(feat_value, bool) and feat_value:
                    if feat_name not in pattern_scores:
                        pattern_scores[feat_name] = []
                    pattern_scores[feat_name].append(metric_value)

        patterns = []
        for pattern, scores in pattern_scores.items():
            if len(scores) < 3:
                continue

            avg_score = sum(scores) / len(scores)
            patterns.append({
                "pattern": pattern,
                f"avg_{metric}": round(avg_score, 4),
                "sample_count": len(scores),
                "type": "loser",
            })

        patterns.sort(key=lambda x: x[f"avg_{metric}"])
        return patterns[:limit]
