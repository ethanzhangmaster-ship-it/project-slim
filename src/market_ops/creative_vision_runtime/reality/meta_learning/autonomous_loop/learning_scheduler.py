"""E12.5.5 — Learning Scheduler。

决定何时触发 Meta Learning Cycle。

触发条件:
  1. 实验数 >= min_experiments
  2. 总花费 >= min_spend
  3. 距上次学习 >= learning_interval_days
  4. 新增实验 >= min_new_experiments
  5. 性能下降 >= performance_drop

避免噪声数据触发学习。
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import LearningSchedule, LearningTrigger, TriggerReason


class LearningScheduler:
    """学习调度器 —— 决定何时启动学习。

    Usage:
        >>> scheduler = LearningScheduler()
        >>> trigger = scheduler.check(
        ...     experiment_count=132,
        ...     total_spend=38000,
        ...     days_since_last=7,
        ... )
        >>> if trigger.should_trigger:
        ...     # start meta learning cycle
    """

    def __init__(self, schedule: LearningSchedule | None = None) -> None:
        self.schedule = schedule or LearningSchedule()

    # ── Check ──────────────────────────────────────────────

    def check(
        self,
        experiment_count: int = 0,
        total_spend: float = 0.0,
        new_experiments: int = 0,
        days_since_last: float = 0.0,
        performance_drop: float = 0.0,
        last_cycle_time: datetime | None = None,
    ) -> LearningTrigger:
        """检查是否应该触发学习。

        Args:
            experiment_count: 当前实验数
            total_spend:      总花费
            new_experiments:  新增实验数
            days_since_last:  距上次学习天数
            performance_drop: 性能下降幅度
            last_cycle_time:  上次周期时间

        Returns:
            LearningTrigger
        """
        if not self.schedule.auto_trigger:
            return LearningTrigger(
                reason=TriggerReason.MANUAL,
                experiment_count=experiment_count,
                total_spend=total_spend,
                new_experiments=new_experiments,
                days_since_last=days_since_last,
                performance_drop=performance_drop,
                should_trigger=False,
                message="Auto-trigger is disabled",
            )

        # 检查性能下降（最高优先级）
        if performance_drop >= self.schedule.performance_drop:
            return LearningTrigger(
                reason=TriggerReason.PERFORMANCE_DROP,
                experiment_count=experiment_count,
                total_spend=total_spend,
                new_experiments=new_experiments,
                days_since_last=days_since_last,
                performance_drop=performance_drop,
                should_trigger=True,
                message=f"Performance drop {performance_drop:.1%} >= threshold {self.schedule.performance_drop:.1%}",
            )

        # 检查时间间隔
        if days_since_last >= self.schedule.learning_interval_days:
            if experiment_count >= self.schedule.min_experiments:
                return LearningTrigger(
                    reason=TriggerReason.TIME_INTERVAL,
                    experiment_count=experiment_count,
                    total_spend=total_spend,
                    new_experiments=new_experiments,
                    days_since_last=days_since_last,
                    performance_drop=performance_drop,
                    should_trigger=True,
                    message=f"Interval {days_since_last:.0f}d >= {self.schedule.learning_interval_days}d "
                    f"with {experiment_count} experiments",
                )

        # 检查实验数
        if experiment_count >= self.schedule.min_experiments:
            return LearningTrigger(
                reason=TriggerReason.EXPERIMENT_COUNT,
                experiment_count=experiment_count,
                total_spend=total_spend,
                new_experiments=new_experiments,
                days_since_last=days_since_last,
                performance_drop=performance_drop,
                should_trigger=True,
                message=f"Experiment count {experiment_count} >= {self.schedule.min_experiments}",
            )

        # 检查花费
        if total_spend >= self.schedule.min_spend:
            return LearningTrigger(
                reason=TriggerReason.SPEND_THRESHOLD,
                experiment_count=experiment_count,
                total_spend=total_spend,
                new_experiments=new_experiments,
                days_since_last=days_since_last,
                performance_drop=performance_drop,
                should_trigger=True,
                message=f"Spend ${total_spend:,.0f} >= ${self.schedule.min_spend:,.0f}",
            )

        # 检查新增实验
        if new_experiments >= self.schedule.min_new_experiments:
            return LearningTrigger(
                reason=TriggerReason.EXPERIMENT_COUNT,
                experiment_count=experiment_count,
                total_spend=total_spend,
                new_experiments=new_experiments,
                days_since_last=days_since_last,
                performance_drop=performance_drop,
                should_trigger=True,
                message=f"New experiments {new_experiments} >= {self.schedule.min_new_experiments}",
            )

        # 不触发
        return LearningTrigger(
            reason=TriggerReason.SCHEDULED,
            experiment_count=experiment_count,
            total_spend=total_spend,
            new_experiments=new_experiments,
            days_since_last=days_since_last,
            performance_drop=performance_drop,
            should_trigger=False,
            message="No trigger conditions met",
        )

    def check_from_state(
        self,
        experiment_count: int,
        total_spend: float,
        last_cycle: datetime | None = None,
        current_performance: float = 0.0,
        previous_performance: float = 0.0,
    ) -> LearningTrigger:
        """从系统状态检查触发。

        Args:
            experiment_count:     当前实验数
            total_spend:          总花费
            last_cycle:           上次周期时间
            current_performance:  当前性能指标
            previous_performance: 之前性能指标

        Returns:
            LearningTrigger
        """
        # 计算距上次学习天数
        days_since_last = 0.0
        if last_cycle is not None:
            delta = datetime.now(timezone.utc) - last_cycle
            days_since_last = delta.total_seconds() / 86400.0

        # 计算性能下降
        performance_drop = 0.0
        if previous_performance > 0:
            drop = (previous_performance - current_performance) / previous_performance
            performance_drop = max(0.0, drop)

        return self.check(
            experiment_count=experiment_count,
            total_spend=total_spend,
            new_experiments=0,
            days_since_last=days_since_last,
            performance_drop=performance_drop,
            last_cycle_time=last_cycle,
        )

    def should_trigger(self, trigger: LearningTrigger) -> bool:
        """判断是否应该触发。

        Args:
            trigger: 触发信息

        Returns:
            True if should trigger
        """
        return trigger.should_trigger

    def to_dict(self) -> dict:
        return {
            "schedule": self.schedule.to_dict(),
        }

    def __repr__(self) -> str:
        return f"LearningScheduler({self.schedule})"