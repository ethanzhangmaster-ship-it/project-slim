from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class GrowthCycleStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GrowthCycle:
    cycle_id: str
    date: str
    status: GrowthCycleStatus = GrowthCycleStatus.PENDING
    issues: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "date": self.date,
            "status": self.status.value,
            "issues": self.issues,
            "actions": self.actions,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class GrowthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class GrowthOrchestrator:
    def __init__(self):
        self._cycles: List[GrowthCycle] = []
        self._current_cycle: Optional[GrowthCycle] = None
        self._data_collectors: Dict[str, callable] = {}
        self._analyzers: Dict[str, callable] = {}
        self._action_generators: Dict[str, callable] = {}

    def register_data_collector(self, name: str, collector: callable):
        self._data_collectors[name] = collector

    def register_analyzer(self, name: str, analyzer: callable):
        self._analyzers[name] = analyzer

    def register_action_generator(self, name: str, generator: callable):
        self._action_generators[name] = generator

    def collect_data(self) -> Dict[str, Any]:
        data = {}
        for name, collector in self._data_collectors.items():
            try:
                data[name] = collector()
            except Exception as e:
                data[name] = {"error": str(e)}
        return data

    def analyze_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        analysis = {}
        for name, analyzer in self._analyzers.items():
            try:
                analysis[name] = analyzer(data)
            except Exception as e:
                analysis[name] = {"error": str(e)}
        return analysis

    def generate_actions(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions = []
        for name, generator in self._action_generators.items():
            try:
                generated = generator(analysis)
                if generated:
                    actions.extend(generated if isinstance(generated, list) else [generated])
            except Exception:
                pass
        return actions

    def execute_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for action in actions:
            try:
                result = {"action": action, "status": "executed", "timestamp": datetime.now().isoformat()}
            except Exception as e:
                result = {"action": action, "status": "failed", "error": str(e)}
            results.append(result)
        return results

    def evaluate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        success_count = sum(1 for r in results if r.get("status") == "executed")
        return {
            "total_actions": len(results),
            "successful": success_count,
            "failed": len(results) - success_count,
            "success_rate": success_count / len(results) if results else 0,
        }

    def run_daily_cycle(self, date: str = None) -> GrowthCycle:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        cycle_id = f"cycle_{date}"
        cycle = GrowthCycle(cycle_id=cycle_id, date=date, status=GrowthCycleStatus.RUNNING, start_time=datetime.now())
        self._current_cycle = cycle

        try:
            data = self.collect_data()
            analysis = self.analyze_data(data)
            actions = self.generate_actions(analysis)
            cycle.actions = actions

            issues = self._detect_issues(analysis)
            cycle.issues = issues

            results = self.execute_actions(actions)
            evaluation = self.evaluate_results(results)

            cycle.status = GrowthCycleStatus.COMPLETED
        except Exception as e:
            cycle.status = GrowthCycleStatus.FAILED
            cycle.issues.append({"type": "error", "message": str(e)})

        cycle.end_time = datetime.now()
        self._cycles.append(cycle)
        self._current_cycle = None
        return cycle

    def _detect_issues(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues = []
        for name, result in analysis.items():
            if isinstance(result, dict) and result.get("issues"):
                issues.extend(result["issues"])
        return issues

    def get_growth_status(self) -> GrowthStatus:
        if not self._cycles:
            return GrowthStatus.UNKNOWN

        last_cycle = self._cycles[-1]
        if last_cycle.status == GrowthCycleStatus.COMPLETED:
            if len(last_cycle.issues) > 5:
                return GrowthStatus.CRITICAL
            elif len(last_cycle.issues) > 0:
                return GrowthStatus.WARNING
            return GrowthStatus.HEALTHY
        return GrowthStatus.WARNING

    def get_cycles(self, limit: int = 30) -> List[GrowthCycle]:
        return self._cycles[-limit:]

    def get_current_cycle(self) -> Optional[GrowthCycle]:
        return self._current_cycle

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._cycles)
        completed = sum(1 for c in self._cycles if c.status == GrowthCycleStatus.COMPLETED)
        failed = sum(1 for c in self._cycles if c.status == GrowthCycleStatus.FAILED)
        return {
            "total_cycles": total,
            "completed_cycles": completed,
            "failed_cycles": failed,
            "current_status": self.get_growth_status().value,
        }