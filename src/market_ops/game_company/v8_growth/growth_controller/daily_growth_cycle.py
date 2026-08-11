from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import time


class CycleStatus(Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class CyclePhase:
    phase_id: str
    name: str
    order: int
    status: CycleStatus = CycleStatus.RUNNING
    progress: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "name": self.name,
            "order": self.order,
            "status": self.status.value,
            "progress": self.progress,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


@dataclass
class CycleProgress:
    current_phase: str
    total_phases: int
    completed_phases: int
    progress_percent: float
    elapsed_time_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_phase": self.current_phase,
            "total_phases": self.total_phases,
            "completed_phases": self.completed_phases,
            "progress_percent": self.progress_percent,
            "elapsed_time_seconds": self.elapsed_time_seconds,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
        }


@dataclass
class CycleHistory:
    cycle_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: CycleStatus = CycleStatus.RUNNING
    phases: List[CyclePhase] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "phases": [p.to_dict() for p in self.phases],
            "results": self.results,
        }


class DailyGrowthCycle:
    def __init__(self):
        self._phases: List[CyclePhase] = [
            CyclePhase(phase_id="collect", name="Data Collection", order=1),
            CyclePhase(phase_id="analyze", name="Analysis", order=2),
            CyclePhase(phase_id="detect", name="Opportunity Detection", order=3),
            CyclePhase(phase_id="plan", name="Action Planning", order=4),
            CyclePhase(phase_id="execute", name="Execution", order=5),
            CyclePhase(phase_id="evaluate", name="Evaluation", order=6),
            CyclePhase(phase_id="learn", name="Learning", order=7),
        ]
        self._current_phase_index: int = 0
        self._status: CycleStatus = CycleStatus.PAUSED
        self._history: List[CycleHistory] = []
        self._current_cycle: Optional[CycleHistory] = None
        self._start_time: Optional[float] = None

    def start(self) -> CycleHistory:
        self._status = CycleStatus.RUNNING
        self._current_phase_index = 0
        self._start_time = time.time()

        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._current_cycle = CycleHistory(
            cycle_id=cycle_id,
            start_time=datetime.now(),
            status=CycleStatus.RUNNING,
            phases=[],
        )

        for phase in self._phases:
            phase.status = CycleStatus.RUNNING if phase.order == 1 else CycleStatus.PAUSED
            phase.start_time = datetime.now() if phase.order == 1 else None
            phase.progress = 0.0

        return self._current_cycle

    def pause(self) -> bool:
        if self._status == CycleStatus.RUNNING:
            self._status = CycleStatus.PAUSED
            return True
        return False

    def resume(self) -> bool:
        if self._status == CycleStatus.PAUSED:
            self._status = CycleStatus.RUNNING
            return True
        return False

    def complete_phase(self, phase_id: str) -> bool:
        for i, phase in enumerate(self._phases):
            if phase.phase_id == phase_id:
                phase.status = CycleStatus.COMPLETED
                phase.progress = 100.0
                phase.end_time = datetime.now()

                if self._current_cycle:
                    self._current_cycle.phases.append(phase)

                if i + 1 < len(self._phases):
                    self._phases[i + 1].status = CycleStatus.RUNNING
                    self._phases[i + 1].start_time = datetime.now()
                    self._current_phase_index = i + 1
                else:
                    self._status = CycleStatus.COMPLETED
                    if self._current_cycle:
                        self._current_cycle.end_time = datetime.now()
                        self._current_cycle.status = CycleStatus.COMPLETED
                        self._history.append(self._current_cycle)

                return True
        return False

    def get_current_phase(self) -> Optional[CyclePhase]:
        if 0 <= self._current_phase_index < len(self._phases):
            return self._phases[self._current_phase_index]
        return None

    def get_progress(self) -> CycleProgress:
        completed = sum(1 for p in self._phases if p.status == CycleStatus.COMPLETED)
        elapsed = time.time() - self._start_time if self._start_time else 0
        avg_phase_time = elapsed / max(1, completed) if completed > 0 else 0
        remaining = avg_phase_time * (len(self._phases) - completed)

        return CycleProgress(
            current_phase=self._phases[self._current_phase_index].name if self._current_phase_index < len(self._phases) else "completed",
            total_phases=len(self._phases),
            completed_phases=completed,
            progress_percent=(completed / len(self._phases)) * 100,
            elapsed_time_seconds=elapsed,
            estimated_remaining_seconds=remaining,
        )

    def get_history(self, limit: int = 30) -> List[CycleHistory]:
        return self._history[-limit:]

    def get_status(self) -> CycleStatus:
        return self._status

    def is_running(self) -> bool:
        return self._status == CycleStatus.RUNNING

    def get_phases(self) -> List[CyclePhase]:
        return list(self._phases)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_cycles": len(self._history),
            "current_status": self._status.value,
            "current_phase": self.get_current_phase().name if self.get_current_phase() else None,
            "progress": self.get_progress().to_dict(),
        }