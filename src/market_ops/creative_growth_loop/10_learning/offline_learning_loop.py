"""Offline Learning Loop - 离线学习循环

P2-5: 实现最小训练循环。

流程：
1. collect data (7 days) → build dataset
2. compute gradients (or heuristic update)
3. update compiler config
4. redeploy

验收标准：
A. 数据闭环成立: creative → ad → CTR → dataset → update
B. 至少 1 个指标能自优化: CTR 或 IPM
C. 至少 1 个结构能变化: template weight 或 budget allocation
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .event_tracker import EventTracker
from .creative_performance_mapper import CreativePerformanceMapper
from .dataset_builder import DatasetBuilder, TrainingDataset
from .weight_update_system import WeightUpdateSystem, CompilerConfig


@dataclass
class LearningCycleResult:
    cycle_id: str
    started_at: int
    completed_at: int
    duration_seconds: float
    
    samples_collected: int
    min_impressions_threshold: int
    
    dataset_path: str
    config_version_before: int
    config_version_after: int
    
    avg_ctr_before: float
    avg_ctr_after: float
    ctr_change: float
    
    updates_applied: Dict[str, Any]
    
    status: str
    error_message: str = ""


@dataclass
class LearningLoopConfig:
    data_collect_days: int = 7
    min_impressions: int = 50
    auto_deploy: bool = False
    learning_rate: float = 0.1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_collect_days": self.data_collect_days,
            "min_impressions": self.min_impressions,
            "auto_deploy": self.auto_deploy,
            "learning_rate": self.learning_rate,
        }


class OfflineLearningLoop:
    """离线学习循环 - 实现最小化自优化训练
    
    最小训练循环：
    collect data (7 days) → build dataset → compute updates → update config → redeploy
    """
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.tracker = EventTracker(output_dir=str(self.output_dir))
        self.mapper = CreativePerformanceMapper(output_dir=str(self.output_dir))
        self.dataset_builder = DatasetBuilder(output_dir=str(self.output_dir))
        self.weight_updater = WeightUpdateSystem(output_dir=str(self.output_dir))
        
        self.learning_config = LearningLoopConfig()
        
        self.loop_state_file = self.output_dir / "loop_state.json"
        self.cycle_history_file = self.output_dir / "cycle_history.json"
        
        self._load_state()
    
    def _load_state(self):
        if self.loop_state_file.exists():
            with open(self.loop_state_file, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        else:
            self.state = {
                "last_cycle_at": 0,
                "total_cycles": 0,
                "last_ctr": 0.0,
            }
        
        if self.cycle_history_file.exists():
            with open(self.cycle_history_file, "r", encoding="utf-8") as f:
                self.cycle_history = json.load(f)
        else:
            self.cycle_history = []
    
    def _save_state(self):
        with open(self.loop_state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
        
        with open(self.cycle_history_file, "w", encoding="utf-8") as f:
            json.dump(self.cycle_history[-20:], f, indent=2)
    
    def run_cycle(self, min_impressions: int = None) -> LearningCycleResult:
        start_time = time.time()
        cycle_id = f"cycle_{int(start_time)}"
        
        if min_impressions is None:
            min_impressions = self.learning_config.min_impressions
        
        config_before = self.weight_updater.get_config()
        ctr_before = config_before.inference_weights.reward_vividness
        
        try:
            samples = self.tracker.get_recent_events(self.learning_config.data_collect_days)
            
            self.mapper.sync_with_tracker(self.tracker)
            
            dataset = self.dataset_builder.build_dataset(min_impressions=min_impressions)
            
            dataset_path = self.dataset_builder.save_dataset(
                dataset,
                f"dataset_{cycle_id}.json"
            )
            
            updates = self.weight_updater.compute_updates(dataset)
            
            updates_applied = {
                "budget_updates": updates.get("budget_updates", {}),
                "inference_updates": updates.get("inference_updates", {}),
                "template_updates": updates.get("template_updates", {}),
            }
            
            applied = self.weight_updater.apply_updates(updates)
            
            config_after = self.weight_updater.get_config()
            ctr_after = config_after.inference_weights.reward_vividness
            
            completed_at = int(time.time())
            duration = completed_at - start_time
            
            result = LearningCycleResult(
                cycle_id=cycle_id,
                started_at=int(start_time),
                completed_at=completed_at,
                duration_seconds=duration,
                samples_collected=len(samples),
                min_impressions_threshold=min_impressions,
                dataset_path=str(dataset_path),
                config_version_before=config_before.version,
                config_version_after=config_after.version,
                avg_ctr_before=ctr_before,
                avg_ctr_after=ctr_after,
                ctr_change=ctr_after - ctr_before,
                updates_applied=updates_applied,
                status="success" if applied else "no_updates",
            )
            
            self.state["last_cycle_at"] = completed_at
            self.state["total_cycles"] += 1
            self.state["last_ctr"] = updates.get("avg_ctr", 0)
            
            self.cycle_history.append({
                "cycle_id": cycle_id,
                "completed_at": completed_at,
                "samples_collected": len(samples),
                "avg_ctr": updates.get("avg_ctr", 0),
                "config_version": config_after.version,
                "updates_applied": applied,
            })
            
            self._save_state()
            
            return result
            
        except Exception as e:
            completed_at = int(time.time())
            return LearningCycleResult(
                cycle_id=cycle_id,
                started_at=int(start_time),
                completed_at=completed_at,
                duration_seconds=completed_at - start_time,
                samples_collected=0,
                min_impressions_threshold=min_impressions,
                dataset_path="",
                config_version_before=config_before.version,
                config_version_after=config_before.version,
                avg_ctr_before=ctr_before,
                avg_ctr_after=ctr_before,
                ctr_change=0,
                updates_applied={},
                status="error",
                error_message=str(e),
            )
    
    def should_run_cycle(self) -> bool:
        if self.state["last_cycle_at"] == 0:
            return True
        
        days_since_last = (int(time.time()) - self.state["last_cycle_at"]) / 86400
        
        return days_since_last >= self.learning_config.data_collect_days
    
    def get_loop_status(self) -> Dict[str, Any]:
        config = self.weight_updater.get_config()
        
        days_since_last = 0
        if self.state["last_cycle_at"] > 0:
            days_since_last = (int(time.time()) - self.state["last_cycle_at"]) / 86400
        
        return {
            "total_cycles": self.state["total_cycles"],
            "last_cycle_at": self.state["last_cycle_at"],
            "days_since_last_cycle": round(days_since_last, 1),
            "should_run": self.should_run_cycle(),
            "config_version": config.version,
            "budget": config.budget.to_dict(),
            "inference_weights": config.inference_weights.to_dict(),
            "template_priorities": config.template_priorities.to_dict(),
        }
    
    def get_cycle_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.cycle_history[-limit:]
    
    def reset_loop(self):
        self.state = {
            "last_cycle_at": 0,
            "total_cycles": 0,
            "last_ctr": 0.0,
        }
        self.cycle_history = []
        self._save_state()
        
        self.weight_updater.config.reset()
    
    def preview_updates(self, min_impressions: int = None) -> Dict[str, Any]:
        if min_impressions is None:
            min_impressions = self.learning_config.min_impressions
        
        self.mapper.sync_with_tracker(self.tracker)
        dataset = self.dataset_builder.build_dataset(min_impressions=min_impressions)
        
        updates = self.weight_updater.compute_updates(dataset)
        
        current_config = self.weight_updater.get_config()
        
        return {
            "dataset_info": {
                "sample_count": len(dataset.samples),
                "total_impressions": dataset.total_impressions,
                "avg_ctr": round(dataset.avg_ctr, 4),
                "avg_ipm": round(dataset.avg_ipm, 3),
            },
            "current_config": current_config.to_dict(),
            "suggested_updates": updates,
        }


class SelfOptimizingCompiler:
    """自优化编译器 - 整合所有模块的端到端编译器"""
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        
        self.tracker = EventTracker(output_dir=str(self.output_dir))
        self.mapper = CreativePerformanceMapper(output_dir=str(self.output_dir))
        self.weight_updater = WeightUpdateSystem(output_dir=str(self.output_dir))
        self.loop = OfflineLearningLoop(output_dir=str(self.output_dir))
    
    def generate_with_tracking(self, template_id: str,
                               layout_ast_id: str,
                               render_constraints: Dict[str, Any],
                               features: Dict[str, float] = None) -> str:
        creative_id = self.mapper.register_creative(
            layout_ast_id=layout_ast_id,
            template_id=template_id,
            render_constraints=render_constraints,
            features=features,
        )
        
        return creative_id
    
    def link_ad(self, creative_id: str, ad_id: str, campaign_id: str = "") -> bool:
        return self.mapper.link_ad(creative_id, ad_id, campaign_id)
    
    def sync_performance(self) -> int:
        return self.mapper.sync_with_tracker(self.tracker)
    
    def run_learning_cycle(self) -> LearningCycleResult:
        return self.loop.run_cycle()
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "loop_status": self.loop.get_loop_status(),
            "performance_summary": self.tracker.get_performance_summary(),
            "mapping_summary": self.mapper.get_mapping_summary(),
        }
