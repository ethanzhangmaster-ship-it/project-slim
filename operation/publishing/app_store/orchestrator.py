"""iOS App Store 端到端发布编排器 — Spec ios_upload_spec.md §6.

7 步发布流程:
  1. upload_build (altool 上传 IPA)
  2. poll_build_status (等待 Apple processing 完成)
  3. select_build (关联 build 到 appStoreVersion)
  4. submit_review (提交审核)
  5. [外部等待审核通过 — 通常 24-48h, 非本编排器范围]
  6. start_phased_release (审核通过后启动 7 天灰度)
  7. check_phased_release (查询灰度进度)

设计原则:
  - 每步独立可重试: 失败后可从失败步重试, 无需从头开始
  - 幂等: 同一 release_id 重复调用返回上次结果
  - 状态持久化: data/ios_release/{release_id}.json 记录执行进度
  - 错误隔离: 单步失败不阻塞已成功步骤
  - dry_run 支持: SIMULATION 模式走 MockAppStoreClient

用法:
    orch = IOSReleaseOrchestrator(
        game_id="game_001",
        bundle_id="com.company.game",
        ipa_path="/path/to/app.ipa",
        version="1.2.0",
        build_number=42,
    )
    result = orch.run()  # 执行到 submit_review 即返回 (等待审核)
    # 审核通过后:
    result = orch.run(start_step="start_phased_release")
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
    "upload_build",
    "poll_build_status",
    "select_build",
    "submit_review",
    # — 审核等待 (外部, 非编排器范围) —
    "start_phased_release",
    "check_phased_release",
]

STEP_DESCRIPTIONS = {
    "upload_build": "altool CLI 上传 IPA 到 App Store Connect",
    "poll_build_status": "轮询 build processing 状态直到 VALID/FAILED",
    "select_build": "关联 build 到 appStoreVersion",
    "submit_review": "提交审核 (POST /appStoreVersionSubmissions)",
    "start_phased_release": "审核通过后启动 7 天灰度发布",
    "check_phased_release": "查询灰度发布进度 (1%→2%→5%→10%→20%→50%→100%)",
}


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
    bundle_id: str
    version: str
    build_number: int
    ipa_path: str
    started_at: str = ""
    finished_at: str = ""
    current_step: str = "upload_build"
    completed_steps: List[str] = field(default_factory=list)
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    build_id: str = ""           # upload_build 成功后填充
    version_id: str = ""         # create_version/select_build 用
    phased_release_id: str = ""  # start_phased_release 成功后填充
    status: str = "pending"      # pending/running/uploading/processing/submitting/submitted/releasing/released/failed

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


class IOSReleaseOrchestrator:
    """iOS App Store 端到端发布编排器.

    7 步流程: upload_build → poll → select → submit_review →
              [审核等待] → start_phased → check_phased
    """

    def __init__(
        self,
        game_id: str,
        bundle_id: str,
        ipa_path: str,
        version: str,
        build_number: int,
        release_id: Optional[str] = None,
        version_id: Optional[str] = None,
        poll_timeout: int = 1800,
        poll_interval: int = 30,
        data_dir: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        """初始化编排器.

        Args:
            game_id: 游戏 ID
            bundle_id: App bundle identifier
            ipa_path: IPA 文件路径
            version: 版本号 e.g. "1.2.0"
            build_number: build 号 e.g. 42
            release_id: 发布 ID (None 则自动生成)
            version_id: 已存在的 appStoreVersion ID (None 则需先创建)
            poll_timeout: build processing 轮询超时 (秒)
            poll_interval: 轮询间隔 (秒)
            data_dir: 状态持久化目录 (默认 data/ios_release)
            client: 注入的 AppStoreClient (None 则按 sandbox 模式创建)
        """
        self.game_id = game_id
        self.bundle_id = bundle_id
        self.ipa_path = ipa_path
        self.version = version
        self.build_number = build_number
        self.release_id = release_id or f"rel_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.version_id = version_id or ""
        self.poll_timeout = poll_timeout
        self.poll_interval = poll_interval

        project_root = Path(__file__).resolve().parents[3]
        self.data_dir = Path(data_dir) if data_dir else project_root / "data" / "ios_release"
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
                bundle_id=self.bundle_id,
                version=self.version,
                build_number=self.build_number,
                ipa_path=self.ipa_path,
                version_id=self.version_id,
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
        """获取 AppStoreClient (SIMULATION → Mock, PRODUCTION → Real)."""
        if self._client:
            return self._client

        from operation.providers.live import store_keys
        cred = store_keys.get_appstore()

        if cred:
            # PRODUCTION 模式 — 有真实凭证
            from operation.publishing.providers.app_store.real_client import AppStoreRealClient
            # 补充 bundle_id
            cred["bundle_id"] = self.bundle_id
            self._client = AppStoreRealClient(credential=cred)
            logger.info("iOS orchestrator: PRODUCTION mode (real App Store Connect API)")
        else:
            # SIMULATION 模式 — 无凭证, 用 mock
            from operation.publishing.app_store.client import MockAppStoreClient
            self._client = MockAppStoreClient()
            # mock 需要先 create_app
            self._client.create_app(self.game_id, self.bundle_id, self.game_id)
            logger.info("iOS orchestrator: SIMULATION mode (mock client)")

        return self._client

    # ── 步骤执行 ──

    def _execute_step(self, step: str, state: ReleaseState) -> StepResult:
        """执行单个步骤."""
        client = self._get_client()
        started = time.strftime("%Y-%m-%dT%H:%M:%S")
        result = StepResult(step=step, success=False, started_at=started)

        try:
            if step == "upload_build":
                r = client.upload_build(
                    state.game_id, state.ipa_path,
                    state.version, state.build_number)
                if r.get("success"):
                    result.success = True
                    state.build_id = r.get("build_id", "")
                    result.data = {"build_id": state.build_id}
                    state.status = "uploaded"
                else:
                    result.error = r.get("error", "upload failed")

            elif step == "poll_build_status":
                r = client.poll_build_status(
                    state.game_id, state.version, state.build_number,
                    timeout_seconds=self.poll_timeout,
                    poll_interval_seconds=self.poll_interval)
                if r.get("success"):
                    result.success = True
                    bs = r.get("build_status", {})
                    result.data = bs
                    state.status = "processing_valid"
                else:
                    result.error = r.get("error", "polling failed")
                    state.status = "processing_failed"

            elif step == "select_build":
                r = client.select_build(state.version_id, state.build_id)
                if r.get("success"):
                    result.success = True
                    state.status = "build_selected"
                else:
                    result.error = r.get("error", "select failed")

            elif step == "submit_review":
                r = client.submit_review(state.game_id, state.version_id or None)
                if r.get("success"):
                    result.success = True
                    result.data = {"status": r.get("status", "waiting_for_review")}
                    state.status = "submitted"
                else:
                    result.error = r.get("error", "submit failed")

            elif step == "start_phased_release":
                r = client.start_phased_release(state.version_id)
                if r.get("success"):
                    result.success = True
                    # 尝试提取 phased_release_id
                    data = r.get("data") or {}
                    if isinstance(data, dict):
                        inner = data.get("data", {})
                        state.phased_release_id = inner.get("id", "")
                    result.data = {"phased_release_id": state.phased_release_id}
                    state.status = "releasing"
                else:
                    result.error = r.get("error", "start phased release failed")

            elif step == "check_phased_release":
                r = client.check_phased_release(state.version_id)
                if r.get("success"):
                    result.success = True
                    data = r.get("data") or {}
                    result.data = data
                    # 判断是否完成
                    inner = data.get("data", {}) if isinstance(data, dict) else {}
                    attrs = inner.get("attributes", {}) if isinstance(inner, dict) else {}
                    phase_state = attrs.get("state", "")
                    if phase_state == "COMPLETE":
                        state.status = "released"
                    else:
                        state.status = "releasing"
                else:
                    result.error = r.get("error", "check failed")

            else:
                result.error = f"unknown step: {step}"

        except Exception as exc:
            result.error = f"exception: {exc}"
            logger.exception("iOS orchestrator: step %s failed", step)

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
            dict: {release_id, status, current_step, completed_steps, failed_step, ...}
        """
        state = self._load_state()

        # 默认 stop_step: submit_review (等待人工审核后再启动灰度)
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

            logger.info("iOS orchestrator [%s]: executing step '%s'",
                        self.release_id, step)

            result = self._execute_step(step, state)
            state.step_results[step] = result
            self._save_state()

            if not result.success:
                state.status = "failed"
                self._save_state()
                logger.error("iOS orchestrator [%s]: step '%s' failed: %s",
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
        if stop_step == "check_phased_release":
            state.status = "released" if state.status != "releasing" else "releasing"
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
            "build_id": state.build_id,
            "version_id": state.version_id,
            "state": state.to_dict(),
        }

    def run_full_release(self, start_step: Optional[str] = None) -> Dict[str, Any]:
        """执行完整发布流程 (含灰度), 到 check_phased_release.

        用于审核已通过后的灰度发布阶段.
        """
        return self.run(start_step=start_step, stop_step="check_phased_release")

    # ── 状态查询 ──

    def get_status(self) -> Dict[str, Any]:
        """查询当前发布状态."""
        state = self._load_state()
        return {
            "release_id": state.release_id,
            "game_id": state.game_id,
            "version": state.version,
            "build_number": state.build_number,
            "status": state.status,
            "current_step": state.current_step,
            "completed_steps": state.completed_steps,
            "build_id": state.build_id,
            "version_id": state.version_id,
            "phased_release_id": state.phased_release_id,
            "step_results": {
                k: asdict(v) if isinstance(v, StepResult) else v
                for k, v in state.step_results.items()
            },
        }

    @classmethod
    def load_release(cls, release_id: str, data_dir: Optional[str] = None) -> "IOSReleaseOrchestrator":
        """从持久化状态加载已存在的发布流程."""
        project_root = Path(__file__).resolve().parents[3]
        ddir = Path(data_dir) if data_dir else project_root / "data" / "ios_release"
        state_file = ddir / f"{release_id}.json"
        if not state_file.exists():
            raise FileNotFoundError(f"release not found: {release_id}")

        with open(state_file, "r", encoding="utf-8") as f:
            state = ReleaseState.from_dict(json.load(f))

        orch = cls(
            game_id=state.game_id,
            bundle_id=state.bundle_id,
            ipa_path=state.ipa_path,
            version=state.version,
            build_number=state.build_number,
            release_id=state.release_id,
            version_id=state.version_id,
            data_dir=data_dir,
        )
        orch._state = state
        return orch


__all__ = [
    "IOSReleaseOrchestrator",
    "ReleaseState",
    "StepResult",
    "STEPS",
    "STEP_DESCRIPTIONS",
]
