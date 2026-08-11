"""E11 Phase 2.5 — Test Lifecycle 状态机。

管理一次测试的完整生命周期：
  CREATED → RUNNING → JUDGING → PASSED / FAILED / BORDERLINE
  BORDERLINE → EXTENDED (回到 RUNNING) 或 FAILED_BORDERLINE
  PASSED → SCALING → ACTIVE
  FAILED → KILLED

状态转换规则：
  - CREATED → RUNNING: 测试开始
  - RUNNING → JUDGING: 达到测试周期 或 数据充足时手动触发
  - JUDGING → PASSED: ROAS 达标 且 CPI 不超标
  - JUDGING → FAILED: ROAS 低于 borderline
  - JUDGING → BORDERLINE: ROAS 在 borderline 和 pass 之间
  - BORDERLINE → EXTENDED: 延长测试（回到 RUNNING）
  - BORDERLINE → FAILED_BORDERLINE: 延长次数用尽
  - PASSED → SCALING: 开始放量
  - SCALING → ACTIVE: 放量稳定运行
  - FAILED/FAILED_BORDERLINE → KILLED: 关闭广告

终态：ACTIVE, KILLED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TestStatus(str, Enum):
    """测试生命周期状态。"""
    CREATED = "CREATED"               # 已创建，等待开始
    RUNNING = "RUNNING"               # 测试中
    JUDGING = "JUDGING"               # 正在判定
    PASSED = "PASSED"                 # 通过
    FAILED = "FAILED"                 # 失败
    BORDERLINE = "BORDERLINE"         # 边缘
    EXTENDED = "EXTENDED"             # 已延长（回到 RUNNING 逻辑）
    FAILED_BORDERLINE = "FAILED_BORDERLINE"  # 边缘多次后失败
    SCALING = "SCALING"               # 放量中
    ACTIVE = "ACTIVE"                 # 放量稳定运行（终态）
    KILLED = "KILLED"                 # 已关闭（终态）


# 有效状态转换
VALID_TRANSITIONS: dict[TestStatus, set[TestStatus]] = {
    TestStatus.CREATED:           {TestStatus.RUNNING},
    TestStatus.RUNNING:           {TestStatus.JUDGING, TestStatus.KILLED},
    TestStatus.JUDGING:           {TestStatus.PASSED, TestStatus.FAILED, TestStatus.BORDERLINE},
    TestStatus.PASSED:            {TestStatus.SCALING},
    TestStatus.FAILED:            {TestStatus.KILLED},
    TestStatus.BORDERLINE:        {TestStatus.EXTENDED, TestStatus.FAILED_BORDERLINE},
    TestStatus.EXTENDED:          {TestStatus.RUNNING, TestStatus.JUDGING},
    TestStatus.FAILED_BORDERLINE: {TestStatus.KILLED},
    TestStatus.SCALING:           {TestStatus.ACTIVE, TestStatus.KILLED},
    TestStatus.ACTIVE:            {TestStatus.KILLED},  # 终态
    TestStatus.KILLED:            set(),                 # 终态
}

# 终态集合
TERMINAL_STATES: set[TestStatus] = {TestStatus.ACTIVE, TestStatus.KILLED}


@dataclass
class TestLifecycle:
    """测试生命周期。

    追踪一次测试从创建到终态的完整状态变化。

    Usage:
        lifecycle = TestLifecycle.create("test_001", "MW_IMG_260721_000123")
        lifecycle.start()                     # → RUNNING
        lifecycle.judge()                     # → JUDGING
        lifecycle.mark_passed()               # → PASSED
        lifecycle.start_scaling()             # → SCALING
        lifecycle.mark_active()               # → ACTIVE (终态)
    """

    test_id: str = ""
    creative_asset_id: str = ""
    status: TestStatus = TestStatus.CREATED
    status_history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    # ── 工厂方法 ────────────────────────────────────────

    @classmethod
    def create(cls, test_id: str, creative_asset_id: str) -> TestLifecycle:
        """创建新的测试生命周期。"""
        now = datetime.now().isoformat()
        lifecycle = cls(
            test_id=test_id,
            creative_asset_id=creative_asset_id,
            status=TestStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        lifecycle._record_transition(None, TestStatus.CREATED)
        return lifecycle

    # ── 状态转换 ────────────────────────────────────────

    def start(self) -> TestLifecycle:
        """开始测试 → RUNNING。"""
        return self._transition(TestStatus.RUNNING)

    def judge(self) -> TestLifecycle:
        """开始判定 → JUDGING。"""
        return self._transition(TestStatus.JUDGING)

    def mark_passed(self) -> TestLifecycle:
        """标记通过 → PASSED。"""
        return self._transition(TestStatus.PASSED)

    def mark_failed(self) -> TestLifecycle:
        """标记失败 → FAILED。"""
        return self._transition(TestStatus.FAILED)

    def mark_borderline(self) -> TestLifecycle:
        """标记边缘 → BORDERLINE。"""
        return self._transition(TestStatus.BORDERLINE)

    def extend(self) -> TestLifecycle:
        """延长测试 → EXTENDED。"""
        return self._transition(TestStatus.EXTENDED)

    def mark_failed_borderline(self) -> TestLifecycle:
        """边缘失败 → FAILED_BORDERLINE。"""
        return self._transition(TestStatus.FAILED_BORDERLINE)

    def start_scaling(self) -> TestLifecycle:
        """开始放量 → SCALING。"""
        return self._transition(TestStatus.SCALING)

    def mark_active(self) -> TestLifecycle:
        """标记活跃 → ACTIVE。"""
        return self._transition(TestStatus.ACTIVE)

    def kill(self) -> TestLifecycle:
        """关闭测试 → KILLED。"""
        return self._transition(TestStatus.KILLED)

    # ── 内部方法 ────────────────────────────────────────

    def _transition(self, new_status: TestStatus) -> TestLifecycle:
        """执行状态转换（带验证）。"""
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} → {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now().isoformat()
        self._record_transition(old_status, new_status)
        return self

    def _record_transition(
        self,
        old_status: TestStatus | None,
        new_status: TestStatus,
    ) -> None:
        self.status_history.append({
            "from": old_status.value if old_status else None,
            "to": new_status.value,
            "at": self.updated_at or datetime.now().isoformat(),
            "test_id": self.test_id,
        })

    # ── 属性 ────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    @property
    def is_active(self) -> bool:
        return self.status in {TestStatus.RUNNING, TestStatus.EXTENDED, TestStatus.SCALING}

    @property
    def is_done(self) -> bool:
        return self.status in {TestStatus.PASSED, TestStatus.FAILED, TestStatus.FAILED_BORDERLINE, TestStatus.ACTIVE, TestStatus.KILLED}

    @property
    def transition_count(self) -> int:
        return len(self.status_history)

    # ── 序列化 ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "creative_asset_id": self.creative_asset_id,
            "status": self.status.value,
            "status_history": self.status_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestLifecycle:
        return cls(
            test_id=data.get("test_id", ""),
            creative_asset_id=data.get("creative_asset_id", ""),
            status=TestStatus(data.get("status", "CREATED")),
            status_history=data.get("status_history", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def __repr__(self) -> str:
        return f"TestLifecycle(id={self.test_id!r}, status={self.status.value})"


class TestLifecycleManager:
    """测试生命周期管理器。

    管理多个 TestLifecycle，提供批量操作和查询。

    Usage:
        manager = TestLifecycleManager()
        lifecycle = manager.create_test("test_001", "MW_IMG_001")
        lifecycle.start()
        manager.get_active_tests()  # → [lifecycle]
    """

    def __init__(self) -> None:
        self._tests: dict[str, TestLifecycle] = {}

    def create_test(
        self,
        test_id: str,
        creative_asset_id: str,
    ) -> TestLifecycle:
        """创建新测试。"""
        lifecycle = TestLifecycle.create(test_id, creative_asset_id)
        self._tests[test_id] = lifecycle
        return lifecycle

    def get(self, test_id: str) -> TestLifecycle | None:
        return self._tests.get(test_id)

    def get_by_creative(self, creative_asset_id: str) -> list[TestLifecycle]:
        """按素材 ID 查找所有测试。"""
        return [
            t for t in self._tests.values()
            if t.creative_asset_id == creative_asset_id
        ]

    def get_active_tests(self) -> list[TestLifecycle]:
        """获取所有活跃测试。"""
        return [t for t in self._tests.values() if t.is_active]

    def get_terminal_tests(self) -> list[TestLifecycle]:
        """获取所有终态测试。"""
        return [t for t in self._tests.values() if t.is_terminal]

    def get_by_status(self, status: TestStatus) -> list[TestLifecycle]:
        """按状态筛选。"""
        return [t for t in self._tests.values() if t.status == status]

    def count_by_status(self) -> dict[str, int]:
        """按状态统计。"""
        counts: dict[str, int] = {}
        for t in self._tests.values():
            key = t.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    @property
    def total_tests(self) -> int:
        return len(self._tests)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tests": {
                tid: t.to_dict() for tid, t in self._tests.items()
            },
            "total": self.total_tests,
        }

    def __repr__(self) -> str:
        return f"TestLifecycleManager(tests={self.total_tests})"