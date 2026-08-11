"""Playtest simulation module for autonomous product studio."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import random
import uuid


@dataclass
class PlaySession:
    """Represents a simulated play session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_number: int = 0
    duration_minutes: float = 0.0
    levels_completed: int = 0
    deaths: int = 0
    bugs_encountered: int = 0
    fun_rating: float = 0.0
    difficulty_rating: float = 0.0
    dropoff_reason: str = ""


@dataclass
class Feedback:
    """Aggregated player feedback."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    average_fun: float = 0.0
    average_difficulty: float = 0.0
    completion_rate: float = 0.0
    common_praises: List[str] = field(default_factory=list)
    common_complaints: List[str] = field(default_factory=list)
    nps_score: float = 0.0


@dataclass
class Issue:
    """Discovered issue during playtest."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    severity: str = ""  # critical, major, minor, trivial
    category: str = ""  # gameplay, ui, performance, crash, balance
    description: str = ""
    reproduction_rate: float = 0.0


class PlaytestAgent:
    """Simulates playtests and collects feedback."""

    def __init__(self):
        self._sessions: List[PlaySession] = []
        self._feedback: Feedback | None = None
        self._issues: List[Issue] = []

    def simulate_play(self, session_count: int) -> List[PlaySession]:
        """Simulate a number of play sessions."""
        self._sessions = []
        for i in range(session_count):
            duration = round(random.uniform(5, 60), 1)
            levels = random.randint(0, 10)
            deaths = random.randint(0, 20)
            bugs = random.randint(0, 5)
            fun = round(random.uniform(3.0, 10.0), 1)
            difficulty = round(random.uniform(1.0, 10.0), 1)
            dropoff = random.choice(["completed", "frustrated", "bored", "time_limit", "crash"])
            session = PlaySession(
                session_number=i + 1,
                duration_minutes=duration,
                levels_completed=levels,
                deaths=deaths,
                bugs_encountered=bugs,
                fun_rating=fun,
                difficulty_rating=difficulty,
                dropoff_reason=dropoff,
            )
            self._sessions.append(session)
        return self._sessions

    def get_feedback(self) -> Feedback:
        """Aggregate feedback from all simulated sessions."""
        if not self._sessions:
            self.simulate_play(10)
        avg_fun = round(sum(s.fun_rating for s in self._sessions) / len(self._sessions), 2)
        avg_diff = round(sum(s.difficulty_rating for s in self._sessions) / len(self._sessions), 2)
        completed = sum(1 for s in self._sessions if s.dropoff_reason == "completed")
        completion_rate = round(completed / len(self._sessions), 2)
        praises = random.sample(
            ["great visuals", "smooth controls", "engaging loop", "nice music", "rewarding progression"],
            k=random.randint(1, 3),
        )
        complaints = random.sample(
            ["too grindy", "unclear UI", "unfair difficulty", "performance drops", "lack of tutorial"],
            k=random.randint(0, 2),
        )
        nps = round(random.uniform(-50, 80), 2)
        self._feedback = Feedback(
            average_fun=avg_fun,
            average_difficulty=avg_diff,
            completion_rate=completion_rate,
            common_praises=praises,
            common_complaints=complaints,
            nps_score=nps,
        )
        return self._feedback

    def find_issues(self) -> List[Issue]:
        """Find and classify issues from playtest sessions."""
        if not self._sessions:
            self.simulate_play(10)
        issue_pool = [
            ("critical", "crash", "Game crashes after level 5", 0.05),
            ("major", "performance", "Frame drops during combat", 0.25),
            ("major", "gameplay", "Player gets stuck in terrain", 0.15),
            ("minor", "ui", "Text overlap in inventory screen", 0.4),
            ("minor", "balance", "Boss too easy with fire weapon", 0.2),
            ("trivial", "ui", "Icon misaligned by 2 pixels", 0.6),
        ]
        found = random.sample(issue_pool, k=random.randint(1, len(issue_pool)))
        self._issues = [
            Issue(
                severity=sev,
                category=cat,
                description=desc,
                reproduction_rate=rate,
            )
            for sev, cat, desc, rate in found
        ]
        return self._issues
