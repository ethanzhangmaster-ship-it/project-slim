"""Weight Update System - 编译器权重更新

P2-4: 用真实数据更新编译器参数。

更新对象：
1. Visual Budget System - reward/mechanism/identity/ui 预算比例
2. Inference Model - P(understand_mechanism) / P(imagine_reward) / P(identity_projection) 权重
3. Template Selection Policy - merge/evolution/before_after 使用概率

更新逻辑：
if CTR high:
    increase reward_salience weight
    increase center bias

if CTR low:
    increase mechanism visibility weight

if low retention:
    penalize identity projection mismatch
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


DEFAULT_BUDGET_ALLOCATION = {
    "reward": 45,
    "mechanism": 30,
    "identity": 15,
    "ui": 10,
}

DEFAULT_INFERENCE_WEIGHTS = {
    "mechanism_clarity": 0.30,
    "reward_vividness": 0.35,
    "identity_projection": 0.20,
    "low_friction": 0.15,
}

DEFAULT_TEMPLATE_PRIORITIES = {
    "merge_formula": 0.35,
    "evolution_chain": 0.35,
    "before_after": 0.30,
}

THRESHOLDS = {
    "high_ctr": 0.03,
    "low_ctr": 0.01,
    "high_ipm": 5.0,
    "low_ipm": 2.0,
}

LEARNING_RATE = 0.1
MAX_UPDATE_STEP = 0.15


@dataclass
class BudgetAllocation:
    reward: float = 45.0
    mechanism: float = 30.0
    identity: float = 15.0
    ui: float = 10.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "reward": self.reward,
            "mechanism": self.mechanism,
            "identity": self.identity,
            "ui": self.ui,
        }
    
    def total(self) -> float:
        return self.reward + self.mechanism + self.identity + self.ui
    
    def normalize(self):
        total = self.total()
        if total > 0:
            scale = 100.0 / total
            self.reward = round(self.reward * scale, 1)
            self.mechanism = round(self.mechanism * scale, 1)
            self.identity = round(self.identity * scale, 1)
            self.ui = round(self.ui * scale, 1)
    
    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "BudgetAllocation":
        return cls(
            reward=d.get("reward", 45.0),
            mechanism=d.get("mechanism", 30.0),
            identity=d.get("identity", 15.0),
            ui=d.get("ui", 10.0),
        )


@dataclass
class InferenceWeights:
    mechanism_clarity: float = 0.30
    reward_vividness: float = 0.35
    identity_projection: float = 0.20
    low_friction: float = 0.15
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "mechanism_clarity": self.mechanism_clarity,
            "reward_vividness": self.reward_vividness,
            "identity_projection": self.identity_projection,
            "low_friction": self.low_friction,
        }
    
    def total(self) -> float:
        return (self.mechanism_clarity + self.reward_vividness + 
                self.identity_projection + self.low_friction)
    
    def normalize(self):
        total = self.total()
        if total > 0:
            scale = 1.0 / total
            self.mechanism_clarity = round(self.mechanism_clarity * scale, 3)
            self.reward_vividness = round(self.reward_vividness * scale, 3)
            self.identity_projection = round(self.identity_projection * scale, 3)
            self.low_friction = round(self.low_friction * scale, 3)
    
    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "InferenceWeights":
        return cls(
            mechanism_clarity=d.get("mechanism_clarity", 0.30),
            reward_vividness=d.get("reward_vividness", 0.35),
            identity_projection=d.get("identity_projection", 0.20),
            low_friction=d.get("low_friction", 0.15),
        )


@dataclass
class TemplatePriorities:
    merge_formula: float = 0.35
    evolution_chain: float = 0.35
    before_after: float = 0.30
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "merge_formula": self.merge_formula,
            "evolution_chain": self.evolution_chain,
            "before_after": self.before_after,
        }
    
    def normalize(self):
        total = self.total()
        if total > 0:
            scale = 1.0 / total
            self.merge_formula = round(self.merge_formula * scale, 3)
            self.evolution_chain = round(self.evolution_chain * scale, 3)
            self.before_after = round(self.before_after * scale, 3)
    
    def total(self) -> float:
        return self.merge_formula + self.evolution_chain + self.before_after
    
    def sample(self) -> str:
        import random
        r = random.random()
        cumulative = 0.0
        for name, prob in self.to_dict().items():
            cumulative += prob
            if r < cumulative:
                return name
        return "merge_formula"
    
    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "TemplatePriorities":
        return cls(
            merge_formula=d.get("merge_formula", 0.35),
            evolution_chain=d.get("evolution_chain", 0.35),
            before_after=d.get("before_after", 0.30),
        )


@dataclass
class UpdateLog:
    timestamp: int
    update_type: str
    before: Dict[str, Any]
    after: Dict[str, Any]
    ctr_change: float
    reason: str


class CompilerConfig:
    """编译器配置 - 保存所有可学习参数"""
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.output_dir / "compiler_config.json"
        self.log_file = self.output_dir / "update_log.json"
        
        self.budget = BudgetAllocation()
        self.inference_weights = InferenceWeights()
        self.template_priorities = TemplatePriorities()
        
        self.version = 1
        self.updated_at = 0
        
        self.update_logs: List[UpdateLog] = []
        
        self._load()
    
    def _load(self):
        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.budget = BudgetAllocation.from_dict(data.get("budget", {}))
                self.inference_weights = InferenceWeights.from_dict(
                    data.get("inference_weights", {})
                )
                self.template_priorities = TemplatePriorities.from_dict(
                    data.get("template_priorities", {})
                )
                self.version = data.get("version", 1)
                self.updated_at = data.get("updated_at", 0)
                self.update_logs = [
                    UpdateLog(**log) for log in data.get("update_logs", [])
                ]
    
    def _save(self):
        data = {
            "budget": self.budget.to_dict(),
            "inference_weights": self.inference_weights.to_dict(),
            "template_priorities": self.template_priorities.to_dict(),
            "version": self.version,
            "updated_at": self.updated_at,
            "update_logs": [
                {
                    "timestamp": log.timestamp,
                    "update_type": log.update_type,
                    "before": log.before,
                    "after": log.after,
                    "ctr_change": log.ctr_change,
                    "reason": log.reason,
                }
                for log in self.update_logs[-20:]
            ],
        }
        
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def reset(self):
        self.budget = BudgetAllocation()
        self.inference_weights = InferenceWeights()
        self.template_priorities = TemplatePriorities()
        self.version = 1
        self.updated_at = int(time.time())
        self._save()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget": self.budget.to_dict(),
            "inference_weights": self.inference_weights.to_dict(),
            "template_priorities": self.template_priorities.to_dict(),
            "version": self.version,
            "updated_at": self.updated_at,
        }


class WeightUpdateSystem:
    """权重更新系统 - 基于真实CTR反馈更新编译器参数
    
    更新逻辑（启发式）：
    if CTR high:
        increase reward_salience weight
        increase center bias
    if CTR low:
        increase mechanism visibility weight
    """
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.config = CompilerConfig(output_dir)
    
    def compute_updates(self, dataset: Any) -> Dict[str, Any]:
        if not dataset.samples:
            return {"status": "no_data"}
        
        avg_ctr = sum(s.label_ctr for s in dataset.samples) / len(dataset.samples)
        avg_ipm = sum(s.label_ipm for s in dataset.samples) / len(dataset.samples)
        
        high_ctr_samples = [s for s in dataset.samples if s.label_ctr >= THRESHOLDS["high_ctr"]]
        low_ctr_samples = [s for s in dataset.samples if s.label_ctr < THRESHOLDS["low_ctr"]]
        
        updates = {
            "avg_ctr": avg_ctr,
            "avg_ipm": avg_ipm,
            "high_ctr_count": len(high_ctr_samples),
            "low_ctr_count": len(low_ctr_samples),
            "budget_updates": {},
            "inference_updates": {},
            "template_updates": {},
        }
        
        if high_ctr_samples:
            updates["budget_updates"] = self._compute_budget_updates(
                high_ctr_samples, direction="increase_reward"
            )
            updates["inference_updates"] = self._compute_inference_updates(
                high_ctr_samples, direction="increase_reward"
            )
        
        if low_ctr_samples:
            updates["budget_updates"].update(
                self._compute_budget_updates(low_ctr_samples, direction="increase_mechanism")
            )
            updates["inference_updates"].update(
                self._compute_inference_updates(low_ctr_samples, direction="increase_mechanism")
            )
        
        updates["template_updates"] = self._compute_template_updates(dataset)
        
        return updates
    
    def _compute_budget_updates(self, samples: List, direction: str) -> Dict[str, float]:
        if not samples:
            return {}
        
        reward_sizes = [s.features.get("reward_size", 0.4) for s in samples]
        reward_glow = [s.features.get("reward_glow_high", 0.5) for s in samples]
        
        avg_size = sum(reward_sizes) / len(reward_sizes)
        avg_glow = sum(reward_glow) / len(reward_glow)
        
        if direction == "increase_reward":
            if avg_size > 0.4:
                return {"reward": LEARNING_RATE * 2}
            if avg_glow > 0.5:
                return {"reward": LEARNING_RATE}
        
        if direction == "increase_mechanism":
            mech_vis = [s.features.get("mech_visibility_high", 0.5) for s in samples]
            avg_mech = sum(mech_vis) / len(mech_vis)
            if avg_mech < 0.5:
                return {"mechanism": LEARNING_RATE}
        
        return {}
    
    def _compute_inference_updates(self, samples: List, direction: str) -> Dict[str, float]:
        if not samples:
            return {}
        
        if direction == "increase_reward":
            return {
                "reward_vividness": LEARNING_RATE,
                "mechanism_clarity": -LEARNING_RATE * 0.5,
            }
        
        if direction == "increase_mechanism":
            return {
                "mechanism_clarity": LEARNING_RATE,
                "reward_vividness": -LEARNING_RATE * 0.5,
            }
        
        return {}
    
    def _compute_template_updates(self, dataset) -> Dict[str, float]:
        template_ctrs = {}
        
        for s in dataset.samples:
            if s.template_type not in template_ctrs:
                template_ctrs[s.template_type] = []
            template_ctrs[s.template_type].append(s.label_ctr)
        
        avg_ctrs = {
            t: sum(ctrs) / len(ctrs)
            for t, ctrs in template_ctrs.items()
        }
        
        updates = {}
        base_ctr = sum(avg_ctrs.values()) / len(avg_ctrs) if avg_ctrs else 0.02
        
        for template_id, avg_ctr in avg_ctrs.items():
            delta = (avg_ctr - base_ctr) / base_ctr
            updates[template_id] = round(delta * LEARNING_RATE, 3)
        
        return updates
    
    def apply_updates(self, updates: Dict[str, Any]) -> bool:
        if updates.get("status") == "no_data":
            return False
        
        before = self.config.to_dict()
        
        for cat, delta in updates.get("budget_updates", {}).items():
            if cat == "reward":
                self.config.budget.reward += delta * 10
                self.config.budget.mechanism -= delta * 5
            elif cat == "mechanism":
                self.config.budget.mechanism += delta * 10
                self.config.budget.reward -= delta * 5
        
        self.config.budget.normalize()
        
        for weight, delta in updates.get("inference_updates", {}).items():
            if hasattr(self.config.inference_weights, weight):
                current = getattr(self.config.inference_weights, weight)
                new_val = max(0.05, min(0.60, current + delta))
                setattr(self.config.inference_weights, weight, new_val)
        
        self.config.inference_weights.normalize()
        
        for template_id, delta in updates.get("template_updates", {}).items():
            if hasattr(self.config.template_priorities, template_id):
                current = getattr(self.config.template_priorities, template_id)
                new_val = max(0.10, min(0.70, current + delta))
                setattr(self.config.template_priorities, template_id, new_val)
        
        self.config.template_priorities.normalize()
        
        self.config.version += 1
        self.config.updated_at = int(time.time())
        
        after = self.config.to_dict()
        
        log = UpdateLog(
            timestamp=int(time.time()),
            update_type="batch_update",
            before=before,
            after=after,
            ctr_change=updates.get("avg_ctr", 0) - (before.get("avg_ctr", 0) if isinstance(before, dict) else 0),
            reason=f"Updated based on {len(updates.get('budget_updates', {})) + len(updates.get('inference_updates', {}))} changes",
        )
        self.config.update_logs.append(log)
        
        self.config._save()
        
        return True
    
    def get_config(self) -> CompilerConfig:
        return self.config
    
    def sample_template(self) -> str:
        return self.config.template_priorities.sample()
    
    def get_budget_for_template(self, template_id: str) -> BudgetAllocation:
        base = BudgetAllocation(
            reward=self.config.budget.reward,
            mechanism=self.config.budget.mechanism,
            identity=self.config.budget.identity,
            ui=self.config.budget.ui,
        )
        
        if template_id == "merge_formula":
            base.reward += 5
            base.mechanism += 3
            base.normalize()
        elif template_id == "evolution_chain":
            base.mechanism += 5
            base.reward += 2
            base.normalize()
        elif template_id == "before_after":
            base.reward += 5
            base.identity += 2
            base.normalize()
        
        return base
    
    def get_inference_weights(self) -> InferenceWeights:
        return InferenceWeights(
            mechanism_clarity=self.config.inference_weights.mechanism_clarity,
            reward_vividness=self.config.inference_weights.reward_vividness,
            identity_projection=self.config.inference_weights.identity_projection,
            low_friction=self.config.inference_weights.low_friction,
        )
