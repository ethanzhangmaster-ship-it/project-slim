"""P2.2 Play Provider — 发布执行器（Google Play）。

第一阶段仅支持：CREATE_RELEASE（生成发布/版本任务）。

关键纪律：Play Provider **永不直接调用 Google Play 发布接口**。
原因：商店审核风险高，且沙箱无服务账号凭据。它只把意图转成一份
可人工复核的 ReleaseTask（本地工单），交由人工在后台落子。

因此无论 DRY_RUN 还是 PRODUCTION，real_api_called 永远为 False
——这正是「大脑提案，人落子」在发布域的体现（与 E17 全局 SIM 纪律一致）。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ...models import ExecutionAction, ExecutionIntent, ExecutionRequest
from ..base import BaseExecutionProvider
from ..result import STATUS_SUCCESS, ExecutionResult


@dataclass
class ReleaseTask:
    """一份发布工单（本地可复核，不直接发布到商店）。"""

    task_id: str
    game_id: str
    release_type: str
    reason: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)
    requires_human_publish: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "game_id": self.game_id,
            "release_type": self.release_type,
            "reason": self.reason,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "requires_human_publish": self.requires_human_publish,
        }


class PlayExecutionProvider(BaseExecutionProvider):
    provider_id = "play"
    supported_actions = (ExecutionAction.CREATE_RELEASE,)

    def __init__(self, *, task_sink: Optional[Any] = None) -> None:
        # task_sink 可注入（如 JsonlReleaseStore）；缺省仅内存构造不落盘
        self.task_sink = task_sink

    # ------------------------------------------------------------------
    def can_execute(self, intent: ExecutionIntent) -> bool:
        return intent.action in self.supported_actions

    # ------------------------------------------------------------------
    # Play 永远只生成工单，不真实发布
    # ------------------------------------------------------------------
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        intent = request.intent
        if not self.can_execute(intent):
            return self._blocked(
                request, f"{self.provider_id} 不支持动作 {intent.action.value}"
            )

        impact = intent.expected_impact or {}
        release_type = impact.get("release_type") or "store_listing_update"
        task = ReleaseTask(
            task_id=f"rel_{uuid.uuid4().hex[:12]}",
            game_id=intent.target_id,
            release_type=release_type,
            reason=intent.reason,
            metadata={
                "decision_id": intent.decision_id,
                "confidence": intent.confidence,
                "mode": request.mode.value,
            },
        )
        if self.task_sink is not None:
            try:
                self.task_sink.put(task)
            except Exception:
                # 落盘失败不影响工单生成本身（本地内存态仍成立）
                pass

        # 关键：real_api_called 恒 False（未触碰 Google Play）
        return ExecutionResult(
            request_id=request.request_id,
            provider=self.provider_id,
            status=STATUS_SUCCESS,
            real_api_called=False,
            before_state={"published": False},
            after_state={
                "task": task.to_dict(),
                "note": "已生成发布工单，需人工在 Google Play 后台发布",
            },
        )


class JsonlReleaseStore:
    """发布工单落盘（append-only JSONL），供人工后台复核与发布。"""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def put(self, task: ReleaseTask) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> list:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out


__all__ = ["ReleaseTask", "PlayExecutionProvider", "JsonlReleaseStore"]
