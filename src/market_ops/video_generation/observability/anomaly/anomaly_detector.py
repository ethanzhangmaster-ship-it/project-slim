"""Anomaly Detector - 异常检测器"""
from typing import Dict, List, Any, Optional
from datetime import datetime

from .threshold_policy import ThresholdManager, ThresholdPolicy
from .alert_manager import AlertManager, AlertType, AlertSeverity


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(
        self,
        threshold_manager: ThresholdManager = None,
        alert_manager: AlertManager = None,
    ):
        self.threshold = threshold_manager or ThresholdManager()
        self.alerts = alert_manager or AlertManager()
        self._history: Dict[str, List[float]] = {}
    
    def record_metric(self, metric_name: str, value: float):
        """记录指标值"""
        if metric_name not in self._history:
            self._history[metric_name] = []
        self._history[metric_name].append(value)
        
        # 保持最近 30 条记录
        self._history[metric_name] = self._history[metric_name][-30:]
    
    def detect_cost_spike(self, current_cost: float) -> bool:
        """检测成本异常"""
        if self.threshold.check_cost_spike(current_cost):
            baseline = self.threshold.get_baseline("avg_cost")
            self.alerts.create_alert(
                alert_type=AlertType.COST_SPIKE,
                severity=AlertSeverity.HIGH,
                message=f"Cost spike detected: ${current_cost:.3f} (baseline ${baseline:.3f})",
                metric="avg_cost",
                current_value=current_cost,
                threshold_value=baseline * self.threshold.policy.cost_multiplier,
                action="Review platform allocation and generation parameters",
            )
            return True
        return False
    
    def detect_quality_drop(self, current_qa: float) -> bool:
        """检测 QA 质量下降"""
        if self.threshold.check_qa_drop(current_qa):
            baseline = self.threshold.get_baseline("qa_score")
            self.alerts.create_alert(
                alert_type=AlertType.QUALITY_DROP,
                severity=AlertSeverity.HIGH,
                message=f"QA quality drop: {current_qa:.1f} (baseline {baseline:.1f})",
                metric="qa_score",
                current_value=current_qa,
                threshold_value=baseline * (1 - self.threshold.policy.qa_drop_percent),
                action="Pause generation and review prompt quality",
            )
            return True
        return False
    
    def detect_creative_fatigue(self, current_ctr: float) -> bool:
        """检测创意疲劳"""
        if self.threshold.check_ctr_drop(current_ctr):
            baseline = self.threshold.get_baseline("ctr")
            self.alerts.create_alert(
                alert_type=AlertType.CREATIVE_FATIGUE,
                severity=AlertSeverity.MEDIUM,
                message=f"Creative fatigue detected: CTR {current_ctr:.2f}% (baseline {baseline:.2f}%)",
                metric="ctr",
                current_value=current_ctr,
                threshold_value=baseline * (1 - self.threshold.policy.ctr_drop_percent),
                action="Refresh creative DNA and generate new variants",
            )
            return True
        return False
    
    def detect_success_rate_drop(self, success_rate: float) -> bool:
        """检测成功率下降"""
        if self.threshold.check_success_rate(success_rate):
            self.alerts.create_alert(
                alert_type=AlertType.SUCCESS_RATE_DROP,
                severity=AlertSeverity.CRITICAL,
                message=f"Success rate dropped to {success_rate * 100:.1f}%",
                metric="success_rate",
                current_value=success_rate,
                threshold_value=self.threshold.policy.success_rate_min,
                action="Check platform health and worker status",
            )
            return True
        return False
    
    def detect_queue_backlog(self, queue_size: int, processing: int) -> bool:
        """检测队列积压"""
        latency = queue_size / max(processing, 1) * 60  # 估算延迟（秒）
        if self.threshold.check_queue_latency(latency):
            self.alerts.create_alert(
                alert_type=AlertType.QUEUE_BACKLOG,
                severity=AlertSeverity.MEDIUM,
                message=f"Queue backlog: {queue_size} pending, estimated latency {latency:.0f}s",
                metric="queue_latency",
                current_value=latency,
                threshold_value=self.threshold.policy.queue_latency_max,
                action="Scale workers or reduce generation rate",
            )
            return True
        return False
    
    def scan_all(self, metrics: Dict[str, float]) -> List[Any]:
        """扫描所有指标"""
        detected = []
        
        if "avg_cost" in metrics:
            if self.detect_cost_spike(metrics["avg_cost"]):
                detected.append("cost_spike")
        
        if "qa_score" in metrics:
            if self.detect_quality_drop(metrics["qa_score"]):
                detected.append("quality_drop")
        
        if "ctr" in metrics:
            if self.detect_creative_fatigue(metrics["ctr"]):
                detected.append("creative_fatigue")
        
        if "success_rate" in metrics:
            if self.detect_success_rate_drop(metrics["success_rate"]):
                detected.append("success_rate_drop")
        
        return detected
    
    def get_active_alerts(self) -> List[Any]:
        """获取活跃告警"""
        return self.alerts.get_active_alerts()
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """获取告警摘要"""
        return self.alerts.get_summary()
