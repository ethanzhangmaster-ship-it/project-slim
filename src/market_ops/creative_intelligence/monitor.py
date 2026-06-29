"""FinalBandit Monitor (Spec §14 — Runtime Monitoring)

只读监控层。不修改任何算法、不修改 theta/sigma/trials 更新公式。
仅通过包装 FinalBandit 的 update()/sample() 来记录事件。

事件类型:
- update: 每次 update() 前后状态快照
- sample: 每次 sample() 的候选 arm 和概率
- system: 定时系统状态快照
- health: 运行时健康事件 (去重/异常/缺失归因)

数据存储: 环形 buffer (内存) + JSON log (文件, 可追加)
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.creative_intelligence.final_bandit import FinalBandit


# ============================================================================
# Monitor — 只读包装, 不修改 FinalBandit
# ============================================================================

class FinalBanditMonitor:
    """FinalBandit 运行时监控器

    包装 FinalBandit, 拦截 update()/sample(), 记录事件。
    所有事件写入环形 buffer (内存) + 追加到 JSON log 文件。
    """

    # 环形 buffer 容量
    MAX_UPDATE_EVENTS = 1000
    MAX_SAMPLE_EVENTS = 500
    MAX_HEALTH_EVENTS = 200

    def __init__(
        self,
        bandit: FinalBandit,
        log_dir: str | Path = "output/monitor",
    ) -> None:
        self._bandit = bandit
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # 环形 buffer
        self._update_events: deque[dict] = deque(maxlen=self.MAX_UPDATE_EVENTS)
        self._sample_events: deque[dict] = deque(maxlen=self.MAX_SAMPLE_EVENTS)
        self._health_events: deque[dict] = deque(maxlen=self.MAX_HEALTH_EVENTS)

        # 计数器
        self._update_count = 0
        self._sample_count = 0
        self._duplicate_reject_count = 0
        self._failed_update_count = 0
        self._invalid_observation_count = 0
        self._missing_attribution_count = 0

        # 系统快照历史
        self._system_snapshots: deque[dict] = deque(maxlen=168)  # 7天 × 24小时

        # 初始化 log 文件
        self._update_log_path = self._log_dir / "update_events.jsonl"
        self._sample_log_path = self._log_dir / "sample_events.jsonl"
        self._health_log_path = self._log_dir / "health_events.jsonl"
        self._snapshot_path = self._log_dir / "current_state.json"

    # ========================================================================
    # 包装方法 (拦截 + 记录, 然后委托给 FinalBandit)
    # ========================================================================

    def update(self, gene_type: str, gene_value: str, reward: float) -> None:
        """包装 FinalBandit.update(), 记录前后状态"""
        ts = datetime.now(timezone.utc).isoformat()
        key = f"{gene_type}_{gene_value}"

        # 记录 before 状态
        before = self._snap_arm(key)
        if before is None:
            # 新 arm, 默认值
            before = {"theta": 0.0, "sigma": 0.5, "trials": 0}

        # 验证 reward
        if not (-1.0 <= reward <= 1.0):
            self._invalid_observation_count += 1
            self._log_health("invalid_observation",
                f"reward={reward} out of range [-1,1] for {key}")

        # 委托给 FinalBandit
        try:
            self._bandit.update(gene_type, gene_value, reward)
            self._update_count += 1
        except Exception as e:
            self._failed_update_count += 1
            self._log_health("failed_update",
                f"update({gene_type}, {gene_value}, {reward}) failed: {e}")
            return

        # 记录 after 状态
        after = self._snap_arm(key)
        if after is None:
            after = {"theta": 0.0, "sigma": 0.5, "trials": 0}

        event = {
            "ts": ts,
            "type": "update",
            "gene_type": gene_type,
            "gene_value": gene_value,
            "reward": round(reward, 6),
            "delta": round(reward - before["theta"], 6),
            "theta_before": round(before["theta"], 6),
            "theta_after": round(after["theta"], 6),
            "sigma_before": round(before["sigma"], 6),
            "sigma_after": round(after["sigma"], 6),
            "trials_before": before["trials"],
            "trials_after": after["trials"],
        }
        self._update_events.append(event)
        self._append_jsonl(self._update_log_path, event)

    def sample(self, gene_type: str) -> str:
        """包装 FinalBandit.sample(), 记录候选和概率"""
        ts = datetime.now(timezone.utc).isoformat()
        type_arms = [a for a in self._bandit.arms.values() if a.gene_type == gene_type]

        # 收集候选 arm 状态 (采样前)
        candidates = []
        if type_arms:
            tau = self._bandit._auto_tau(gene_type)
            for a in type_arms:
                score = a.theta / max(tau, 1e-6) + self._bandit.gamma * a.sigma
                candidates.append({
                    "gene_value": a.gene_value,
                    "theta": round(a.theta, 6),
                    "sigma": round(a.sigma, 6),
                    "trials": a.trials,
                    "score": round(score, 6),
                })

            # 计算 softmax 概率
            if candidates:
                max_score = max(c["score"] for c in candidates)
                exp_scores = [
                    math.exp((c["score"] - max_score) / max(tau, 1e-6))
                    for c in candidates
                ]
                total = sum(exp_scores)
                for c, e in zip(candidates, exp_scores):
                    c["probability"] = round(e / total, 6)

        # 委托给 FinalBandit
        try:
            selected = self._bandit.sample(gene_type)
            self._sample_count += 1
        except Exception as e:
            selected = "unknown"
            self._failed_update_count += 1
            self._log_health("failed_sample",
                f"sample({gene_type}) failed: {e}")

        event = {
            "ts": ts,
            "type": "sample",
            "gene_type": gene_type,
            "selected": selected,
            "greedy": self._bandit.best(gene_type),
            "tau": round(self._bandit._auto_tau(gene_type), 6),
            "entropy": round(self._bandit.entropy(gene_type), 6),
            "candidates": candidates,
        }
        self._sample_events.append(event)
        self._append_jsonl(self._sample_log_path, event)

        return selected

    # ========================================================================
    # 健康事件记录
    # ========================================================================

    def log_duplicate_reject(self, gene_type: str, gene_value: str, date_str: str) -> None:
        """记录去重拒绝"""
        self._duplicate_reject_count += 1
        self._log_health("duplicate_reject",
            f"{gene_type}/{gene_value} already learned on {date_str}")

    def log_missing_attribution(self, creative_id: str, variant_ids: list[str]) -> None:
        """记录缺失归因"""
        self._missing_attribution_count += 1
        self._log_health("missing_attribution",
            f"creative={creative_id} → variants={variant_ids}")

    def log_failed_update(self, msg: str) -> None:
        """记录失败更新"""
        self._failed_update_count += 1
        self._log_health("failed_update", msg)

    def log_invalid_observation(self, msg: str) -> None:
        """记录无效 observation"""
        self._invalid_observation_count += 1
        self._log_health("invalid_observation", msg)

    def _log_health(self, subtype: str, message: str) -> None:
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "health",
            "subtype": subtype,
            "message": message,
        }
        self._health_events.append(event)
        self._append_jsonl(self._health_log_path, event)

    # ========================================================================
    # 系统快照
    # ========================================================================

    def take_snapshot(self) -> dict[str, Any]:
        """拍系统快照 (可定时调用)"""
        ts = datetime.now(timezone.utc).isoformat()
        snapshot = self.get_current_state()
        snapshot["ts"] = ts
        self._system_snapshots.append(snapshot)

        # 写入 current_state.json 供 Dashboard 读取
        with open(self._snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

        return snapshot

    # ========================================================================
    # 只读查询 (供 Dashboard)
    # ========================================================================

    def get_current_state(self) -> dict[str, Any]:
        """返回当前完整系统状态 (只读)"""
        # 聚合所有 gene_type
        all_arms: list[dict] = []
        gene_types: set[str] = {a.gene_type for a in self._bandit.arms.values()}
        system_states: dict[str, dict] = {}

        for gt in gene_types:
            state = self._bandit.get_state(gt)
            system_states[gt] = {
                "n_arms": state["n_arms"],
                "entropy": state["entropy"],
                "tau": state["tau"],
                "ranking": state["ranking"],
            }
            for gv, arm_data in state["arms"].items():
                all_arms.append({
                    "gene_type": gt,
                    "gene_value": gv,
                    "theta": arm_data["theta"],
                    "sigma": arm_data["sigma"],
                    "trials": arm_data["trials"],
                })

        # 按 theta DESC 排序
        all_arms.sort(key=lambda a: a["theta"], reverse=True)

        # 计算总体 entropy
        total_entropy = 0.0
        if gene_types:
            total_entropy = sum(s["entropy"] for s in system_states.values()) / len(gene_types)

        return {
            "total_step": self._bandit._step,
            "total_arms": len(self._bandit.arms),
            "active_gene_types": sorted(gene_types),
            "overall_entropy": round(total_entropy, 6),
            "system_states": system_states,
            "arms": all_arms,
            "health": self.get_health(),
        }

    def get_health(self) -> dict[str, Any]:
        """返回运行时健康指标"""
        return {
            "update_count": self._update_count,
            "sample_count": self._sample_count,
            "duplicate_reject_count": self._duplicate_reject_count,
            "failed_update_count": self._failed_update_count,
            "invalid_observation_count": self._invalid_observation_count,
            "missing_attribution_count": self._missing_attribution_count,
            "warnings": self._get_warnings(),
        }

    def _get_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self._duplicate_reject_count > 100:
            warnings.append(f"duplicate_reject > 100 ({self._duplicate_reject_count})")
        if self._failed_update_count > 0:
            warnings.append(f"failed_update_count = {self._failed_update_count}")
        if self._invalid_observation_count > 0:
            warnings.append(f"invalid_observation_count = {self._invalid_observation_count}")
        if self._missing_attribution_count > 0:
            warnings.append(f"missing_attribution_count = {self._missing_attribution_count}")
        return warnings

    def get_recent_updates(self, limit: int = 50) -> list[dict]:
        """返回最近 N 条 update 事件"""
        items = list(self._update_events)
        return items[-limit:]

    def get_recent_samples(self, limit: int = 50) -> list[dict]:
        """返回最近 N 条 sample 事件"""
        items = list(self._sample_events)
        return items[-limit:]

    def get_recent_health(self, limit: int = 50) -> list[dict]:
        """返回最近 N 条健康事件"""
        items = list(self._health_events)
        return items[-limit:]

    def get_system_snapshots(self) -> list[dict]:
        """返回系统快照历史"""
        return list(self._system_snapshots)

    def export_dashboard_data(self) -> dict[str, Any]:
        """导出完整 Dashboard 数据 (一次性返回所有)"""
        return {
            "current": self.get_current_state(),
            "recent_updates": self.get_recent_updates(100),
            "recent_samples": self.get_recent_samples(50),
            "recent_health": self.get_recent_health(50),
            "snapshots": self.get_system_snapshots(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ========================================================================
    # 内部工具
    # ========================================================================

    def _snap_arm(self, key: str) -> dict | None:
        arm = self._bandit.arms.get(key)
        if arm is None:
            return None
        return {"theta": arm.theta, "sigma": arm.sigma, "trials": arm.trials}

    @staticmethod
    def _append_jsonl(path: Path, event: dict) -> None:
        """追加一行 JSON 到文件"""
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 静默失败, 不影响 runtime

    # ========================================================================
    # 委托 — 其他 FinalBandit 方法直接透传
    # ========================================================================

    def __getattr__(self, name: str):
        """将未拦截的方法/属性直接委托给 FinalBandit"""
        return getattr(self._bandit, name)
