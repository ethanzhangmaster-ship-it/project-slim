"""Test Scheduler - 测试调度器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class TestSchedule:
    """测试调度"""
    test_id: str = ""
    name: str = ""
    variants: List[str] = None
    start_time: str = ""
    end_time: str = ""
    status: str = "pending"
    budget: float = 0.0
    
    def __post_init__(self):
        if self.variants is None:
            self.variants = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "variants": self.variants,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "budget": round(self.budget, 2),
        }


class TestScheduler:
    """测试调度器"""
    
    def __init__(self):
        self._schedules: Dict[str, TestSchedule] = {}
        self._counter = 0
    
    def schedule_test(
        self,
        name: str,
        variants: List[str],
        budget: float = 1000.0,
        start_time: str = "",
        end_time: str = "",
    ) -> TestSchedule:
        """调度测试"""
        self._counter += 1
        test_id = f"test_{self._counter:04d}"
        
        schedule = TestSchedule(
            test_id=test_id,
            name=name,
            variants=variants,
            start_time=start_time or "2024-01-15T08:00:00",
            end_time=end_time or "2024-01-18T08:00:00",
            status="scheduled",
            budget=budget,
        )
        
        self._schedules[test_id] = schedule
        return schedule
    
    def get_schedule(self, test_id: str) -> TestSchedule:
        """获取调度"""
        return self._schedules.get(test_id, TestSchedule(test_id=test_id))
    
    def get_active_tests(self) -> List[TestSchedule]:
        """获取活跃测试"""
        return [s for s in self._schedules.values() if s.status == "running"]
    
    def start_test(self, test_id: str) -> bool:
        """开始测试"""
        if test_id not in self._schedules:
            return False
        
        self._schedules[test_id].status = "running"
        return True
    
    def end_test(self, test_id: str) -> bool:
        """结束测试"""
        if test_id not in self._schedules:
            return False
        
        self._schedules[test_id].status = "completed"
        return True
    
    def schedule_demo(self) -> TestSchedule:
        """演示调度"""
        return self.schedule_test(
            name="Hook Comparison Test",
            variants=["creative_A", "creative_B", "creative_C"],
            budget=1500.0,
        )
