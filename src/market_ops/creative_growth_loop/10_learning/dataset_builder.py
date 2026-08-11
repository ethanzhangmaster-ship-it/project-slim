"""Dataset Builder - 构建训练数据集

P2-3: 从 Creative ↔ Performance 映射构建 offline RL / contextual bandit 数据集。

输出格式：
{
  "layout_ast": "...",
  "render_constraints": "...",
  "template_type": "merge/evolution/before_after",
  "features": {
    "mechanism_visibility": 0-1,
    "reward_salience": 0-1,
    "identity_projection": 0-1
  },
  "label": {
    "ctr": 0.0,
    "ipm": 0.0,
    "roas": 0.0
  }
}
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .creative_performance_mapper import CreativePerformanceMapper, CreativeRecord
from .event_tracker import EventTracker, PerformanceMetrics


@dataclass
class TrainingSample:
    """训练样本 - 单条训练数据"""
    creative_id: str
    layout_ast_id: str
    template_type: str
    
    features: Dict[str, float]
    
    label_ctr: float
    label_ipm: float
    label_roas: float
    
    impressions: int
    clicks: int
    installs: int
    
    sample_weight: float = 1.0
    
    created_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "layout_ast_id": self.layout_ast_id,
            "template_type": self.template_type,
            "features": self.features,
            "label": {
                "ctr": round(self.label_ctr, 4),
                "ipm": round(self.label_ipm, 3),
                "roas": round(self.label_roas, 2),
            },
            "metrics": {
                "impressions": self.impressions,
                "clicks": self.clicks,
                "installs": self.installs,
            },
            "sample_weight": round(self.sample_weight, 2),
            "created_at": self.created_at,
        }


@dataclass
class TrainingDataset:
    """训练数据集"""
    samples: List[TrainingSample] = field(default_factory=list)
    
    template_counts: Dict[str, int] = field(default_factory=dict)
    avg_ctr: float = 0.0
    avg_ipm: float = 0.0
    avg_roas: float = 0.0
    
    total_impressions: int = 0
    total_clicks: int = 0
    total_installs: int = 0
    
    built_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "samples": [s.to_dict() for s in self.samples],
            "metadata": {
                "template_counts": self.template_counts,
                "avg_ctr": round(self.avg_ctr, 4),
                "avg_ipm": round(self.avg_ipm, 3),
                "avg_roas": round(self.avg_roas, 2),
                "total_impressions": self.total_impressions,
                "total_clicks": self.total_clicks,
                "total_installs": self.total_installs,
                "sample_count": len(self.samples),
                "built_at": self.built_at,
            },
        }
    
    def save(self, filepath: Path):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: Path) -> "TrainingDataset":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        samples = [TrainingSample(**{k: v for k, v in s.items()}) for s in data["samples"]]
        
        dataset = cls(
            samples=samples,
            template_counts=data["metadata"]["template_counts"],
            avg_ctr=data["metadata"]["avg_ctr"],
            avg_ipm=data["metadata"]["avg_ipm"],
            avg_roas=data["metadata"]["avg_roas"],
            total_impressions=data["metadata"]["total_impressions"],
            total_clicks=data["metadata"]["total_clicks"],
            total_installs=data["metadata"]["total_installs"],
            built_at=data["metadata"]["built_at"],
        )
        
        return dataset


class DatasetBuilder:
    """训练数据集构建器
    
    从 creative-performances 映射构建 offline RL / contextual bandit 数据集。
    """
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.mapper = CreativePerformanceMapper(output_dir=str(self.output_dir))
        self.tracker = EventTracker(output_dir=str(self.output_dir))
    
    def build_dataset(self, min_impressions: int = 50,
                      min_sample_weight: float = 1.0) -> TrainingDataset:
        records = self.mapper.get_all_records()
        
        samples = []
        template_counts = {}
        total_impressions = 0
        total_clicks = 0
        total_installs = 0
        ctr_sum = 0.0
        ipm_sum = 0.0
        roas_sum = 0.0
        ctr_count = 0
        
        for record in records:
            if not record.metrics or record.metrics.impressions < min_impressions:
                continue
            
            features = self._extract_features(record)
            
            sample = TrainingSample(
                creative_id=record.creative_id,
                layout_ast_id=record.layout_ast_id,
                template_type=record.template_id,
                features=features,
                label_ctr=record.metrics.ctr,
                label_ipm=record.metrics.ipm,
                label_roas=record.metrics.roas,
                impressions=record.metrics.impressions,
                clicks=record.metrics.clicks,
                installs=record.metrics.installs,
                sample_weight=self._compute_sample_weight(record.metrics),
                created_at=int(time.time()),
            )
            
            samples.append(sample)
            
            template_counts[record.template_id] = template_counts.get(record.template_id, 0) + 1
            total_impressions += record.metrics.impressions
            total_clicks += record.metrics.clicks
            total_installs += record.metrics.installs
            
            if record.metrics.ctr > 0:
                ctr_sum += record.metrics.ctr
                ipm_sum += record.metrics.ipm
                if record.metrics.roas > 0:
                    roas_sum += record.metrics.roas
                ctr_count += 1
        
        avg_ctr = ctr_sum / ctr_count if ctr_count > 0 else 0.0
        avg_ipm = ipm_sum / ctr_count if ctr_count > 0 else 0.0
        avg_roas = roas_sum / ctr_count if ctr_count > 0 else 0.0
        
        dataset = TrainingDataset(
            samples=samples,
            template_counts=template_counts,
            avg_ctr=avg_ctr,
            avg_ipm=avg_ipm,
            avg_roas=avg_roas,
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_installs=total_installs,
            built_at=int(time.time()),
        )
        
        return dataset
    
    def _extract_features(self, record: CreativeRecord) -> Dict[str, float]:
        if record.features:
            return record.features
        
        features = {}
        
        constraints = record.render_constraints
        
        if "reward" in constraints:
            reward = constraints["reward"]
            features["reward_position_center"] = 1.0 if reward.get("position") == "center" else 0.0
            features["reward_size"] = reward.get("size", 0.4)
            features["reward_glow_high"] = 1.0 if reward.get("glow") == "high" else 0.0
        
        if "mechanism" in constraints:
            mech = constraints["mechanism"]
            features["mech_visibility_high"] = 1.0 if mech.get("visibility") == "high" else 0.0
            features["mech_structure_ui"] = 1.0 if mech.get("structure") == "ui-based" else 0.0
        
        if "identity" in constraints:
            ident = constraints["identity"]
            features["identity_opacity_low"] = 1.0 if ident.get("opacity", 1.0) < 0.5 else 0.0
            features["identity_peripheral"] = 1.0 if ident.get("position") == "peripheral" else 0.0
        
        features.setdefault("reward_position_center", 0.5)
        features.setdefault("reward_size", 0.4)
        features.setdefault("reward_glow_high", 0.5)
        features.setdefault("mech_visibility_high", 0.5)
        features.setdefault("identity_opacity_low", 0.5)
        
        return features
    
    def _compute_sample_weight(self, metrics: PerformanceMetrics) -> float:
        if metrics.impressions < 100:
            return 0.5
        elif metrics.impressions < 500:
            return 1.0
        elif metrics.impressions < 2000:
            return 2.0
        else:
            return 3.0
    
    def build_dataset_by_template(self, template_id: str,
                                 min_impressions: int = 50) -> TrainingDataset:
        records = self.mapper.get_records_by_template(template_id)
        
        samples = []
        total_impressions = 0
        total_clicks = 0
        total_installs = 0
        ctr_sum = 0.0
        ipm_sum = 0.0
        ctr_count = 0
        
        for record in records:
            if not record.metrics or record.metrics.impressions < min_impressions:
                continue
            
            features = self._extract_features(record)
            
            sample = TrainingSample(
                creative_id=record.creative_id,
                layout_ast_id=record.layout_ast_id,
                template_type=record.template_id,
                features=features,
                label_ctr=record.metrics.ctr,
                label_ipm=record.metrics.ipm,
                label_roas=record.metrics.roas,
                impressions=record.metrics.impressions,
                clicks=record.metrics.clicks,
                installs=record.metrics.installs,
                sample_weight=self._compute_sample_weight(record.metrics),
                created_at=int(time.time()),
            )
            
            samples.append(sample)
            
            total_impressions += record.metrics.impressions
            total_clicks += record.metrics.clicks
            total_installs += record.metrics.installs
            
            if record.metrics.ctr > 0:
                ctr_sum += record.metrics.ctr
                ipm_sum += record.metrics.ipm
                ctr_count += 1
        
        avg_ctr = ctr_sum / ctr_count if ctr_count > 0 else 0.0
        avg_ipm = ipm_sum / ctr_count if ctr_count > 0 else 0.0
        
        dataset = TrainingDataset(
            samples=samples,
            template_counts={template_id: len(samples)},
            avg_ctr=avg_ctr,
            avg_ipm=avg_ipm,
            avg_roas=0.0,
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_installs=total_installs,
            built_at=int(time.time()),
        )
        
        return dataset
    
    def get_feature_ctr_correlation(self, dataset: TrainingDataset) -> Dict[str, float]:
        if not dataset.samples:
            return {}
        
        correlations = {}
        
        feature_names = set()
        for s in dataset.samples:
            feature_names.update(s.features.keys())
        
        for feature in feature_names:
            feature_values = []
            ctr_values = []
            
            for s in dataset.samples:
                if feature in s.features:
                    feature_values.append(s.features[feature])
                    ctr_values.append(s.label_ctr)
            
            if len(feature_values) > 5:
                corr = self._pearson_correlation(feature_values, ctr_values)
                correlations[feature] = round(corr, 3)
        
        return correlations
    
    def _pearson_correlation(self, x: List[float], y: List[float]) -> float:
        n = len(x)
        if n < 2:
            return 0.0
        
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        
        sum_sq_x = sum((v - mean_x) ** 2 for v in x)
        sum_sq_y = sum((v - mean_y) ** 2 for v in y)
        
        denominator = (sum_sq_x * sum_sq_y) ** 0.5
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def save_dataset(self, dataset: TrainingDataset,
                    filename: str = "training_dataset.json") -> Path:
        filepath = self.output_dir / filename
        dataset.save(filepath)
        return filepath
    
    def build_and_save(self, min_impressions: int = 50) -> Tuple[TrainingDataset, Path]:
        dataset = self.build_dataset(min_impressions=min_impressions)
        filepath = self.save_dataset(dataset)
        return dataset, filepath
