from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, time, timedelta


@dataclass
class Task:
    task_id: str
    name: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    status: str = "pending"
    scheduled_time: Optional[datetime] = None
    executed_at: Optional[datetime] = None


@dataclass
class Schedule:
    schedule_id: str
    tasks: List[Task] = field(default_factory=list)
    start_time: time = field(default_factory=lambda: time(8, 0))
    timezone: str = "UTC"


class TaskScheduler:
    def __init__(self):
        self.daily_tasks = [
            {"name": "collect_data", "action": "data_pull", "time": "08:00", "priority": 1},
            {"name": "analyze_performance", "action": "analysis", "time": "08:30", "priority": 1},
            {"name": "generate_plan", "action": "planning", "time": "09:00", "priority": 2},
            {"name": "execute_actions", "action": "execution", "time": "09:30", "priority": 1},
            {"name": "send_report", "action": "reporting", "time": "17:00", "priority": 3},
        ]

    def create_daily_schedule(self) -> Schedule:
        schedule_id = f"schedule_{datetime.now().strftime('%Y%m%d')}"
        tasks = []
        
        for task_config in self.daily_tasks:
            hour, minute = map(int, task_config["time"].split(":"))
            scheduled_time = datetime.now().replace(hour=hour, minute=minute, second=0)
            
            if scheduled_time < datetime.now():
                scheduled_time += timedelta(days=1)
            
            tasks.append(Task(
                task_id=f"task_{hash(task_config['name']) % 1000:03d}",
                name=task_config["name"],
                action=task_config["action"],
                priority=task_config["priority"],
                scheduled_time=scheduled_time,
            ))
        
        return Schedule(
            schedule_id=schedule_id,
            tasks=tasks,
            start_time=time(8, 0),
        )

    def add_task(self, schedule: Schedule, task: Task) -> None:
        schedule.tasks.append(task)
        schedule.tasks.sort(key=lambda x: (x.scheduled_time, x.priority))

    def get_pending_tasks(self, schedule: Schedule) -> List[Task]:
        now = datetime.now()
        return [t for t in schedule.tasks if t.status == "pending" and t.scheduled_time <= now]

    def create_daily_schedule_demo(self) -> Schedule:
        return self.create_daily_schedule()
