from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import random


class FatigueLevel(Enum):
    HEALTHY = "healthy"
    EARLY_WARNING = "early_warning"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class AlertType(Enum):
    PERFORMANCE_DECLINE = "performance_decline"
    FREQUENCY_CAP = "frequency_cap"
    CTR_DROP = "ctr_drop"
    CVR_DROP = "cvr_drop"
    ROAS_DECLINE = "roas_decline"
    STALENESS = "staleness"


@dataclass
class FatigueMetrics:
    creative_id: str
    fatigue_score: float = 0.0
    fatigue_level: FatigueLevel = FatigueLevel.HEALTHY
    ctr_trend: float = 0.0
    cvr_trend: float = 0.0
    roas_trend: float = 0.0
    frequency: float = 0.0
    days_active: int = 0
    performance_decay: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "fatigue_score": self.fatigue_score,
            "fatigue_level": self.fatigue_level.value,
            "ctr_trend": self.ctr_trend,
            "cvr_trend": self.cvr_trend,
            "roas_trend": self.roas_trend,
            "frequency": self.frequency,
            "days_active": self.days_active,
            "performance_decay": self.performance_decay,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class FatigueAlert:
    alert_id: str
    creative_id: str
    alert_type: AlertType
    severity: FatigueLevel
    message: str
    metric_value: float = 0.0
    threshold: float = 0.0
    recommendation: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "creative_id": self.creative_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "recommendation": self.recommendation,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
        }


class FatigueDetector:
    def __init__(self, warning_threshold: float = 40.0, critical_threshold: float = 70.0):
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._fatigue_metrics: Dict[str, FatigueMetrics] = {}
        self._alerts: List[FatigueAlert] = []
        self._performance_history: Dict[str, List[Dict[str, Any]]] = {}
        self._thresholds = {
            "ctr_drop": -0.2,
            "cvr_drop": -0.15,
            "roas_drop": -0.25,
            "frequency_cap": 3.0,
            "staleness_days": 14,
            "performance_decay": 0.3,
        }

    def detect_fatigue(self, creative_id: str, performance_data: Dict[str, Any] = None) -> FatigueMetrics:
        if creative_id not in self._fatigue_metrics:
            self._fatigue_metrics[creative_id] = FatigueMetrics(creative_id=creative_id)

        metrics = self._fatigue_metrics[creative_id]
        data = performance_data or self._generate_sample_performance(creative_id)

        self._update_performance_history(creative_id, data)

        metrics.ctr_trend = self._calculate_trend(creative_id, "ctr")
        metrics.cvr_trend = self._calculate_trend(creative_id, "cvr")
        metrics.roas_trend = self._calculate_trend(creative_id, "roas")
        metrics.frequency = data.get("frequency", random.uniform(1.0, 5.0))
        metrics.days_active = data.get("days_active", random.randint(1, 30))
        metrics.performance_decay = self._calculate_performance_decay(creative_id)

        metrics.fatigue_score = self._calculate_fatigue_score(metrics)
        metrics.fatigue_level = self._determine_fatigue_level(metrics.fatigue_score)
        metrics.last_updated = datetime.now()

        self._check_and_create_alerts(metrics, data)

        return metrics

    def _generate_sample_performance(self, creative_id: str) -> Dict[str, Any]:
        return {
            "ctr": random.uniform(0.01, 0.08),
            "cvr": random.uniform(0.02, 0.15),
            "roas": random.uniform(0.5, 3.0),
            "frequency": random.uniform(1.0, 5.0),
            "days_active": random.randint(1, 30),
        }

    def _update_performance_history(self, creative_id: str, data: Dict[str, Any]):
        if creative_id not in self._performance_history:
            self._performance_history[creative_id] = []

        self._performance_history[creative_id].append({
            "timestamp": datetime.now().isoformat(),
            "data": data,
        })

        if len(self._performance_history[creative_id]) > 30:
            self._performance_history[creative_id] = self._performance_history[creative_id][-30:]

    def _calculate_trend(self, creative_id: str, metric: str) -> float:
        history = self._performance_history.get(creative_id, [])
        if len(history) < 2:
            return 0.0

        recent = [h["data"].get(metric, 0) for h in history[-7:]]
        if len(recent) < 2:
            return 0.0

        older = [h["data"].get(metric, 0) for h in history[-14:-7]] if len(history) >= 14 else recent
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older) if older else recent_avg

        if older_avg == 0:
            return 0.0

        return (recent_avg - older_avg) / older_avg

    def _calculate_performance_decay(self, creative_id: str) -> float:
        history = self._performance_history.get(creative_id, [])
        if len(history) < 7:
            return 0.0

        recent_roas = [h["data"].get("roas", 0) for h in history[-7:]]
        initial_roas = [h["data"].get("roas", 0) for h in history[:7]]

        recent_avg = sum(recent_roas) / len(recent_roas)
        initial_avg = sum(initial_roas) / len(initial_roas)

        if initial_avg == 0:
            return 0.0

        return max(0, (initial_avg - recent_avg) / initial_avg)

    def _calculate_fatigue_score(self, metrics: FatigueMetrics) -> float:
        score = 0.0

        if metrics.ctr_trend < self._thresholds["ctr_drop"]:
            score += abs(metrics.ctr_trend) * 100

        if metrics.cvr_trend < self._thresholds["cvr_drop"]:
            score += abs(metrics.cvr_trend) * 80

        if metrics.roas_trend < self._thresholds["roas_drop"]:
            score += abs(metrics.roas_trend) * 120

        if metrics.frequency > self._thresholds["frequency_cap"]:
            score += (metrics.frequency - self._thresholds["frequency_cap"]) * 10

        if metrics.days_active > self._thresholds["staleness_days"]:
            score += (metrics.days_active - self._thresholds["staleness_days"]) * 2

        score += metrics.performance_decay * 50

        return min(100, max(0, score))

    def _determine_fatigue_level(self, fatigue_score: float) -> FatigueLevel:
        if fatigue_score >= 80:
            return FatigueLevel.CRITICAL
        elif fatigue_score >= 60:
            return FatigueLevel.SEVERE
        elif fatigue_score >= 40:
            return FatigueLevel.MODERATE
        elif fatigue_score >= 20:
            return FatigueLevel.EARLY_WARNING
        return FatigueLevel.HEALTHY

    def _check_and_create_alerts(self, metrics: FatigueMetrics, data: Dict[str, Any]):
        if metrics.ctr_trend < self._thresholds["ctr_drop"]:
            self._create_alert(
                metrics.creative_id,
                AlertType.CTR_DROP,
                metrics.fatigue_level,
                f"CTR declined by {abs(metrics.ctr_trend)*100:.1f}%",
                metrics.ctr_trend,
                self._thresholds["ctr_drop"],
                "Consider refreshing creative or testing new variations",
            )

        if metrics.cvr_trend < self._thresholds["cvr_drop"]:
            self._create_alert(
                metrics.creative_id,
                AlertType.CVR_DROP,
                metrics.fatigue_level,
                f"CVR declined by {abs(metrics.cvr_trend)*100:.1f}%",
                metrics.cvr_trend,
                self._thresholds["cvr_drop"],
                "Review landing page or targeting alignment",
            )

        if metrics.frequency > self._thresholds["frequency_cap"]:
            self._create_alert(
                metrics.creative_id,
                AlertType.FREQUENCY_CAP,
                metrics.fatigue_level,
                f"Frequency at {metrics.frequency:.1f} exceeds threshold",
                metrics.frequency,
                self._thresholds["frequency_cap"],
                "Expand audience or rotate creative",
            )

        if metrics.days_active > self._thresholds["staleness_days"]:
            self._create_alert(
                metrics.creative_id,
                AlertType.STALENESS,
                FatigueLevel.EARLY_WARNING,
                f"Creative active for {metrics.days_active} days",
                metrics.days_active,
                self._thresholds["staleness_days"],
                "Consider creative refresh or rotation",
            )

    def _create_alert(
        self,
        creative_id: str,
        alert_type: AlertType,
        severity: FatigueLevel,
        message: str,
        metric_value: float,
        threshold: float,
        recommendation: str
    ):
        alert_id = f"alert_{creative_id}_{alert_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        existing = [a for a in self._alerts if a.creative_id == creative_id and a.alert_type == alert_type and not a.acknowledged]
        if existing:
            return

        alert = FatigueAlert(
            alert_id=alert_id,
            creative_id=creative_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric_value=metric_value,
            threshold=threshold,
            recommendation=recommendation,
        )
        self._alerts.append(alert)

    def get_fatigue_score(self, creative_id: str) -> float:
        metrics = self._fatigue_metrics.get(creative_id)
        return metrics.fatigue_score if metrics else 0.0

    def get_fatigue_alerts(self, creative_id: str = None, severity: FatigueLevel = None) -> List[FatigueAlert]:
        alerts = self._alerts
        if creative_id:
            alerts = [a for a in alerts if a.creative_id == creative_id]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return sorted(alerts, key=lambda a: (a.severity.value, a.created_at), reverse=True)

    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_all_fatigue_metrics(self) -> List[FatigueMetrics]:
        return list(self._fatigue_metrics.values())

    def get_fatigued_creatives(self, min_score: float = 40.0) -> List[str]:
        return [cid for cid, m in self._fatigue_metrics.items() if m.fatigue_score >= min_score]

    def get_stats(self) -> Dict[str, Any]:
        metrics = list(self._fatigue_metrics.values())
        return {
            "total_creatives_monitored": len(metrics),
            "fatigue_distribution": {
                level.value: sum(1 for m in metrics if m.fatigue_level == level)
                for level in FatigueLevel
            },
            "total_alerts": len(self._alerts),
            "unacknowledged_alerts": sum(1 for a in self._alerts if not a.acknowledged),
            "average_fatigue_score": sum(m.fatigue_score for m in metrics) / len(metrics) if metrics else 0,
            "high_fatigue_creatives": len(self.get_fatigued_creatives()),
        }