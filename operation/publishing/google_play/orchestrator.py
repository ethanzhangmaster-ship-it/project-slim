"""Google Play 端到端发布编排器 — Spec google_play_upload_spec.md §6.

7 步发布流程 (对称于 iOS App Store 编排器):
  1. upload_bundle (AAB 上传到 Play Console Edits API)
  2. create_release (在指定 track 创建 release)
  3. submit_review (commit edit → 提交审核)
  4. [外部等待审核通过 — 通常数小时到数天, 非本编排器范围]
  5. check_status (轮询审核状态直到 approved/rejected)
  6. start_rollout (审核通过后启动 staged rollout 到 production)
  7. check_rollout (查询 rollout 进度, 可触发 halt 回滚)

设计原则:
  - 每步独立可重试: 失败后可从失败步重试, 无需从头开始
  - 幂等: 同一 release_id 重复调用返回上次结果
  - 状态持久化: data/google_play_release/{release_id}.json 记录执行进度
  - 错误隔离: 单步失败不阻塞已成功步骤
  - dry_run 支持: SIMULATION 模式走 MockGooglePlayClient

用法:
    orch = GooglePlayReleaseOrchestrator(
        game_id="game_001",
        package_name="com.company.game",
        aab_path="/path/to/app.aab",
        version="1.2.0",
        build_number=42,
        track="internal",
    )
    result = orch.run()  # 执行到 submit_review 即返回 (等待审核)
    # 审核通过后:
    result = orch.run(start_step="start_rollout")
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 发布步骤定义 ──────────────────────────────────────────────

STEPS = [
    "upload_bundle",
    "create_release",
    "submit_review",
    # — 审核等待 (外部, 非编排器范围) —
    "check_status",
    "start_rollout",
    "check_rollout",
]

STEP_DESCRIPTIONS = {
    "upload_bundle": "上传 AAB 到 Play Console Edits API (upload_bundle)",
    "create_release": "在指定 track 创建 release (create_release)",
    "submit_review": "commit edit → 提交审核 (submit_review)",
    "check_status": "轮询审核状态直到 approved/rejected (check_status)",
    "start_rollout": "审核通过后启动 staged rollout 到 production (release_to_production)",
    "check_rollout": "查询 rollout 进度 (get_track_status), 可触发 halt 回滚",
}

# Staged rollout 百分比阶梯 (与 Google Play 默认阶段一致)
ROLLOUT_PHASES = [0.05, 0.10, 0.20, 0.50, 1.00]


@dataclass
class StepResult:
    """单步执行结果."""
    step: str
    success: bool
    started_at: str = ""
    finished_at: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class ReleaseState:
    """发布流程状态 (持久化到 JSON)."""
    release_id: str
    game_id: str
    package_name: str
    version: str
    build_number: int
    aab_path: str
    track: str = "internal"
    rollout_fraction: float = 0.05
    started_at: str = ""
    finished_at: str = ""
    current_step: str = "upload_bundle"
    completed_steps: List[str] = field(default_factory=list)
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    version_code: str = ""        # upload_bundle 成功后填充
    release_id_play: str = ""     # create_release 成功后填充 (Play 内部 release id)
    review_status: str = ""       # check_status 后填充 (approved/rejected)
    rejection: Optional[Dict[str, Any]] = None
    rollout_status: str = ""      # check_rollout 后填充 (completed/inProgress/halted)
    status: str = "pending"       # pending/running/uploading/releasing/submitting/
                                   # submitted/approved/rejected/releasing/released/failed

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["step_results"] = {
            k: asdict(v) if isinstance(v, StepResult) else v
            for k, v in self.step_results.items()
        }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReleaseState":
        sr = d.pop("step_results", {})
        step_results = {
            k: StepResult(**v) if isinstance(v, dict) else v
            for k, v in sr.items()
        }
        return cls(**d, step_results=step_results)


# ── 编排器 ────────────────────────────────────────────────────


class GooglePlayReleaseOrchestrator:
    """Google Play 端到端发布编排器.

    7 步流程: upload_bundle → create_release → submit_review →
              [审核等待] → check_status → start_rollout → check_rollout
    """

    def __init__(
        self,
        game_id: str,
        package_name: str,
        aab_path: str,
        version: str,
        build_number: int,
        release_id: Optional[str] = None,
        track: str = "internal",
        rollout_fraction: float = 0.05,
        poll_timeout: int = 3600,
        poll_interval: int = 60,
        data_dir: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        """初始化编排器.

        Args:
            game_id: 游戏 ID
            package_name: Android package name (e.g. com.company.game)
            aab_path: AAB 文件路径
            version: 版本号 e.g. "1.2.0"
            build_number: version code (整数)
            release_id: 发布 ID (None 则自动生成)
            track: 目标 track (internal/closed/production)
            rollout_fraction: 初始 rollout 百分比 (0.0–1.0)
            poll_timeout: check_status 轮询超时 (秒)
            poll_interval: 轮询间隔 (秒)
            data_dir: 状态持久化目录 (默认 data/google_play_release)
            client: 注入的 GooglePlayClient (None 则按凭证模式创建)
        """
        self.game_id = game_id
        self.package_name = package_name
        self.aab_path = aab_path
        self.version = version
        self.build_number = build_number
        self.release_id = release_id or f"gprel_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.track = track
        self.rollout_fraction = float(rollout_fraction)
        self.poll_timeout = poll_timeout
        self.poll_interval = poll_interval

        project_root = Path(__file__).resolve().parents[3]
        self.data_dir = Path(data_dir) if data_dir else project_root / "data" / "google_play_release"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._client: Optional[Any] = client
        self._state: Optional[ReleaseState] = None

    # ── 状态持久化 ──

    @property
    def state_file(self) -> Path:
        return self.data_dir / f"{self.release_id}.json"

    def _load_state(self) -> ReleaseState:
        if self._state:
            return self._state
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                self._state = ReleaseState.from_dict(json.load(f))
        else:
            self._state = ReleaseState(
                release_id=self.release_id,
                game_id=self.game_id,
                package_name=self.package_name,
                version=self.version,
                build_number=self.build_number,
                aab_path=self.aab_path,
                track=self.track,
                rollout_fraction=self.rollout_fraction,
                started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            self._save_state()
        return self._state

    def _save_state(self) -> None:
        if self._state:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state.to_dict(), f, indent=2, ensure_ascii=False)

    # ── 客户端获取 ──

    def _get_client(self):
        """获取 GooglePlayClient (SIMULATION → Mock, PRODUCTION → Real)."""
        if self._client:
            return self._client

        from operation.providers.live import store_keys
        cred = store_keys.get_googleplay()

        if cred:
            # PRODUCTION 模式 — 有真实凭证
            from operation.publishing.providers.google_play.real_client import GooglePlayRealClient
            cred = dict(cred)  # 浅拷贝避免污染
            cred.setdefault("package_name", self.package_name)
            self._client = GooglePlayRealClient(credential=cred)
            self._client.set_package(self.game_id, self.package_name)
            logger.info("Google Play orchestrator: PRODUCTION mode (real Play Developer API)")
        else:
            # SIMULATION 模式 — 无凭证, 用 mock
            from operation.publishing.google_play.client import MockGooglePlayClient
            self._client = MockGooglePlayClient()
            # mock 需要先 create_app
            self._client.create_app(self.game_id, self.package_name, self.game_id)
            logger.info("Google Play orchestrator: SIMULATION mode (mock client)")

        return self._client

    # ── 步骤执行 ──

    def _execute_step(self, step: str, state: ReleaseState) -> StepResult:
        """执行单个步骤."""
        client = self._get_client()
        started = time.strftime("%Y-%m-%dT%H:%M:%S")
        result = StepResult(step=step, success=False, started_at=started)

        try:
            if step == "upload_bundle":
                r = client.upload_bundle(
                    state.game_id, state.aab_path,
                    state.version, state.build_number)
                if r.get("success"):
                    result.success = True
                    state.version_code = str(r.get("version_code", state.build_number))
                    result.data = {"version_code": state.version_code}
                    state.status = "uploaded"
                else:
                    result.error = r.get("error", "upload failed")

            elif step == "create_release":
                r = client.create_release(state.game_id, track=state.track)
                if r.get("success"):
                    result.success = True
                    state.release_id_play = str(r.get("release_id", ""))
                    result.data = {
                        "release_id_play": state.release_id_play,
                        "track": state.track,
                    }
                    state.status = "release_created"
                else:
                    result.error = r.get("error", "create release failed")

            elif step == "submit_review":
                r = client.submit_review(state.game_id)
                if r.get("success"):
                    result.success = True
                    state.review_status = str(r.get("status", "in_review"))
                    result.data = {"status": state.review_status}
                    state.status = "submitted"
                else:
                    result.error = r.get("error", "submit failed")

            elif step == "check_status":
                # 轮询直到 approved/rejected (或超时)
                deadline = time.time() + self.poll_timeout
                last_status = ""
                while time.time() < deadline:
                    r = client.check_status(state.game_id)
                    if not r.get("success"):
                        # 查询失败不立即失败, 等待下一轮
                        result.error = r.get("error", "check failed")
                        time.sleep(self.poll_interval)
                        continue
                    last_status = str(r.get("status", ""))
                    result.data = {
                        "status": last_status,
                        "rejection": r.get("rejection"),
                    }
                    # approved/rejected 都是终态
                    if last_status in ("approved", "published", "rejected"):
                        break
                    time.sleep(self.poll_interval)

                if last_status in ("approved", "published"):
                    result.success = True
                    state.review_status = "approved"
                    state.status = "approved"
                    result.error = ""
                elif last_status == "rejected":
                    # 审核被拒 — 终态, 不算编排器失败 (是外部决策)
                    result.success = True
                    state.review_status = "rejected"
                    state.rejection = r.get("rejection") if isinstance(r, dict) else None
                    state.status = "rejected"
                    result.data["rejection"] = state.rejection
                    result.error = ""
                else:
                    result.error = f"polling timed out, last_status={last_status}"

            elif step == "start_rollout":
                # 审核必须已通过才能 rollout
                if state.review_status not in ("approved", "published"):
                    result.error = (
                        f"cannot start rollout: review_status={state.review_status} "
                        f"(must be approved/published)"
                    )
                else:
                    # 优先使用 set_rollout (RealClient 支持 staged 百分比)
                    if hasattr(client, "set_rollout"):
                        r = client.set_rollout(
                            state.package_name,
                            track="production",
                            user_fraction=state.rollout_fraction,
                            version_code=state.build_number,
                        )
                    else:
                        # Mock 不支持 set_rollout, 走 release_to_production
                        r = client.release_to_production(state.game_id)
                    if r.get("success"):
                        result.success = True
                        result.data = {
                            "rollout_fraction": state.rollout_fraction,
                            "track": "production",
                        }
                        state.rollout_status = "inProgress"
                        state.status = "releasing"
                    else:
                        result.error = r.get("error", "start rollout failed")

            elif step == "check_rollout":
                # 优先用 get_track_status (RealClient)
                if hasattr(client, "get_track_status"):
                    r = client.get_track_status(state.package_name, track="production")
                else:
                    # Mock 退化为 check_status
                    r = client.check_status(state.game_id)
                if r.get("success"):
                    result.success = True
                    play_status = str(r.get("status", "completed"))
                    user_fraction = float(r.get("user_fraction", state.rollout_fraction))
                    result.data = {
                        "play_status": play_status,
                        "user_fraction": user_fraction,
                        "version_code": r.get("version_code"),
                    }
                    state.rollout_status = play_status
                    if play_status == "completed":
                        state.status = "released"
                    elif play_status == "halted":
                        state.status = "halted"
                    else:
                        state.status = "releasing"
                else:
                    result.error = r.get("error", "check rollout failed")

            else:
                result.error = f"unknown step: {step}"

        except Exception as exc:
            result.error = f"exception: {exc}"
            logger.exception("Google Play orchestrator: step %s failed", step)

        result.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        return result

    # ── 主运行方法 ──

    def run(
        self,
        start_step: Optional[str] = None,
        stop_step: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行发布流程.

        Args:
            start_step: 从指定步骤开始 (None 则从 current_step 继续)
            stop_step: 执行到指定步骤后停止 (None 则执行到 submit_review)

        Returns:
            dict: {success, release_id, status, current_step, completed_steps,
                   failed_step, ...}
        """
        state = self._load_state()

        # 默认 stop_step: submit_review (等待人工审核后再启动 rollout)
        if stop_step is None:
            stop_step = "submit_review"

        # 确定起始步骤
        if start_step:
            if start_step not in STEPS:
                return {"success": False, "error": f"unknown start_step: {start_step}"}
            current = start_step
        else:
            current = state.current_step

        # 执行步骤链
        step_index = STEPS.index(current)
        stop_index = STEPS.index(stop_step)

        state.status = "running"
        self._save_state()

        for i in range(step_index, stop_index + 1):
            step = STEPS[i]
            state.current_step = step
            state.status = f"executing_{step}"
            self._save_state()

            logger.info("Google Play orchestrator [%s]: executing step '%s'",
                        self.release_id, step)

            result = self._execute_step(step, state)
            state.step_results[step] = result
            self._save_state()

            if not result.success:
                state.status = "failed"
                self._save_state()
                logger.error("Google Play orchestrator [%s]: step '%s' failed: %s",
                             self.release_id, step, result.error)
                return {
                    "success": False,
                    "release_id": self.release_id,
                    "status": state.status,
                    "failed_step": step,
                    "error": result.error,
                    "completed_steps": state.completed_steps,
                    "state": state.to_dict(),
                }

            state.completed_steps.append(step)
            state.current_step = STEPS[i + 1] if i + 1 < len(STEPS) else step
            self._save_state()

        # 全部完成
        if stop_step == "check_rollout":
            if state.status != "halted":
                state.status = "released" if state.rollout_status == "completed" else "releasing"
        elif stop_step == "check_status" and state.review_status == "rejected":
            state.status = "rejected"
        else:
            state.status = state.status or "completed"
        state.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_state()

        return {
            "success": True,
            "release_id": self.release_id,
            "status": state.status,
            "current_step": state.current_step,
            "completed_steps": state.completed_steps,
            "version_code": state.version_code,
            "release_id_play": state.release_id_play,
            "review_status": state.review_status,
            "rollout_status": state.rollout_status,
            "state": state.to_dict(),
        }

    def run_full_release(self, start_step: Optional[str] = None) -> Dict[str, Any]:
        """执行完整发布流程 (含 rollout), 到 check_rollout.

        用于审核已通过后的灰度发布阶段.
        """
        return self.run(start_step=start_step, stop_step="check_rollout")

    # ── 状态查询 ──

    def get_status(self) -> Dict[str, Any]:
        """查询当前发布状态."""
        state = self._load_state()
        return {
            "release_id": state.release_id,
            "game_id": state.game_id,
            "package_name": state.package_name,
            "version": state.version,
            "build_number": state.build_number,
            "track": state.track,
            "status": state.status,
            "current_step": state.current_step,
            "completed_steps": state.completed_steps,
            "version_code": state.version_code,
            "release_id_play": state.release_id_play,
            "review_status": state.review_status,
            "rollout_status": state.rollout_status,
            "rollout_fraction": state.rollout_fraction,
            "rejection": state.rejection,
            "step_results": {
                k: asdict(v) if isinstance(v, StepResult) else v
                for k, v in state.step_results.items()
            },
        }

    @classmethod
    def load_release(cls, release_id: str, data_dir: Optional[str] = None) -> "GooglePlayReleaseOrchestrator":
        """从持久化状态加载已存在的发布流程."""
        project_root = Path(__file__).resolve().parents[3]
        ddir = Path(data_dir) if data_dir else project_root / "data" / "google_play_release"
        state_file = ddir / f"{release_id}.json"
        if not state_file.exists():
            raise FileNotFoundError(f"release not found: {release_id}")

        with open(state_file, "r", encoding="utf-8") as f:
            state = ReleaseState.from_dict(json.load(f))

        orch = cls(
            game_id=state.game_id,
            package_name=state.package_name,
            aab_path=state.aab_path,
            version=state.version,
            build_number=state.build_number,
            release_id=state.release_id,
            track=state.track,
            rollout_fraction=state.rollout_fraction,
            data_dir=data_dir,
        )
        orch._state = state
        return orch

    # ── Rollout 控制 (供 API 调用) ──

    def halt_rollout(self) -> Dict[str, Any]:
        """暂停 staged rollout (用户主动暂停/回滚)."""
        state = self._load_state()
        client = self._get_client()
        if hasattr(client, "halt_rollout"):
            r = client.halt_rollout(state.package_name, track="production")
        else:
            r = client.rollback(state.game_id)
        if r.get("success"):
            state.rollout_status = "halted"
            state.status = "halted"
            self._save_state()
            return {"success": True, "status": "halted", "release_id": self.release_id}
        return {
            "success": False,
            "release_id": self.release_id,
            "error": r.get("error", "halt failed"),
        }

    def advance_rollout(self, next_fraction: float) -> Dict[str, Any]:
        """推进 staged rollout 到下一百分比."""
        state = self._load_state()
        client = self._get_client()
        if not hasattr(client, "set_rollout"):
            return {
                "success": False,
                "release_id": self.release_id,
                "error": "client does not support staged rollout (set_rollout missing)",
            }
        r = client.set_rollout(
            state.package_name,
            track="production",
            user_fraction=float(next_fraction),
            version_code=state.build_number,
        )
        if r.get("success"):
            state.rollout_fraction = float(next_fraction)
            state.rollout_status = "inProgress"
            state.status = "releasing"
            self._save_state()
            return {
                "success": True,
                "release_id": self.release_id,
                "rollout_fraction": state.rollout_fraction,
                "status": state.status,
            }
        return {
            "success": False,
            "release_id": self.release_id,
            "error": r.get("error", "advance rollout failed"),
        }


__all__ = [
    "GooglePlayReleaseOrchestrator",
    "ReleaseState",
    "StepResult",
    "STEPS",
    "STEP_DESCRIPTIONS",
    "ROLLOUT_PHASES",
]
