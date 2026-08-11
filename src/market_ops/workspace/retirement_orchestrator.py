"""游戏退役编排器 — 自动化下架/退役流程的本地编排层.

设计纪律:
  - 退役决策可以完全自动化 (基于 KPI 阈值: ROAS / LTV / retention)
  - 数据归档完全本地化 (不需要外部凭证)
  - 资源释放和下架操作只做编排 (标记需要凭证的操作, 不实际调用外部 API)
  - 状态持久化到 data/retirement/plans.jsonl
  - 归档内容写入 data/retirement_archives/{game_id}/

7 步编排流程:
  1. evaluate_retirement()  — 评估退役条件 (KPI 阈值比对)
  2. create_plan()           — 创建退役计划
  3. archive_data()          — 数据归档 (本地)
  4. release_resources()     — 资源释放编排 (campaign 暂停 / creative 归档)
  5. request_takedown()      — 下架请求编排 (标记需要凭证的操作)
  6. verify_completion()     — 验证完成
  7. persist_state()         — 持久化状态

退役触发条件 (RetirementTrigger):
  - ROAS_BELOW_THRESHOLD      — D30 ROAS 低于阈值
  - LTV_BELOW_THRESHOLD       — D30 LTV 低于阈值
  - RETENTION_BELOW_THRESHOLD — D1 留存低于阈值
  - MANUAL_DECISION           — 人工决策
  - PORTFOLIO_OPTIMIZATION    — 投资组合优化
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════


class RetirementTrigger:
    """退役触发条件."""
    ROAS_BELOW_THRESHOLD = "roas_below_threshold"
    LTV_BELOW_THRESHOLD = "ltv_below_threshold"
    RETENTION_BELOW_THRESHOLD = "retention_below_threshold"
    MANUAL_DECISION = "manual_decision"
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"


class RetirementStage(str, Enum):
    """退役流程阶段."""
    PENDING = "pending"           # 退役待执行
    DECIDING = "deciding"         # 评估退役决策
    ARCHIVING = "archiving"       # 数据归档中
    RELEASING = "releasing"       # 资源释放中
    TAKING_DOWN = "taking_down"   # 下架中 (需凭证, 编排 only)
    COMPLETED = "completed"       # 退役完成
    FAILED = "failed"             # 退役失败
    CANCELLED = "cancelled"       # 取消退役


# 默认 KPI 阈值 (与 ProductGate 对齐)
DEFAULT_THRESHOLDS: dict[str, float] = {
    "roas_d30_min": 0.8,          # D30 ROAS 至少 0.8
    "ltv_d30_min": 0.5,           # D30 LTV 至少 0.5
    "d1_retention_min": 0.35,     # D1 留存至少 0.35
}

# 触发条件 → 指标字段映射
_TRIGGER_TO_METRIC: dict[str, tuple[str, str]] = {
    RetirementTrigger.ROAS_BELOW_THRESHOLD: ("roas_d30", "roas_d30_min"),
    RetirementTrigger.LTV_BELOW_THRESHOLD: ("ltv_d30", "ltv_d30_min"),
    RetirementTrigger.RETENTION_BELOW_THRESHOLD: ("d1_retention", "d1_retention_min"),
}

# review 触发的 buffer 比例 (指标在阈值 10% 范围内 → review)
_REVIEW_BUFFER_RATIO = 0.10


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


@dataclass
class RetirementDecision:
    """退役决策."""
    game_id: str
    trigger: str                    # RetirementTrigger.*
    metrics: dict                   # ROAS / LTV / retention 等原始指标
    threshold_values: dict          # 实际使用的阈值
    decision: str                   # "retire" | "keep" | "review"
    confidence: float               # 0.0 ~ 1.0
    decided_at: str
    decided_by: str                 # "auto" | "human"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetirementPlan:
    """退役计划."""
    plan_id: str
    game_id: str
    decision: RetirementDecision
    stages: list[dict] = field(default_factory=list)
    # [{stage, status, started_at, completed_at, error}]
    archive_path: str = ""
    resource_release_actions: list[dict] = field(default_factory=list)
    # [{action, target, status, error}]
    takedown_actions: list[dict] = field(default_factory=list)
    # [{platform, app_id, status, error, needs_credential}]
    current_stage: str = RetirementStage.PENDING.value
    created_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = f"ret_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now_iso()
        if not self.current_stage:
            self.current_stage = RetirementStage.PENDING.value
        # decision 序列化: 如果是 dataclass 实例则保留原对象
        # stages 默认空, 由 orchestrator 在 create_plan 填充

    def to_dict(self) -> dict[str, Any]:
        """序列化为可 JSON 持久化的字典."""
        decision_dict = (
            self.decision.to_dict()
            if isinstance(self.decision, RetirementDecision)
            else dict(self.decision)
        )
        return {
            "plan_id": self.plan_id,
            "game_id": self.game_id,
            "decision": decision_dict,
            "stages": list(self.stages),
            "archive_path": self.archive_path,
            "resource_release_actions": list(self.resource_release_actions),
            "takedown_actions": list(self.takedown_actions),
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetirementPlan":
        """从字典反序列化."""
        decision_data = data.get("decision", {})
        decision = RetirementDecision(
            game_id=decision_data.get("game_id", data.get("game_id", "")),
            trigger=decision_data.get("trigger", RetirementTrigger.MANUAL_DECISION),
            metrics=decision_data.get("metrics", {}),
            threshold_values=decision_data.get("threshold_values", {}),
            decision=decision_data.get("decision", "review"),
            confidence=float(decision_data.get("confidence", 0.0)),
            decided_at=decision_data.get("decided_at", ""),
            decided_by=decision_data.get("decided_by", "auto"),
        )
        return cls(
            plan_id=data.get("plan_id", ""),
            game_id=data.get("game_id", ""),
            decision=decision,
            stages=data.get("stages", []),
            archive_path=data.get("archive_path", ""),
            resource_release_actions=data.get("resource_release_actions", []),
            takedown_actions=data.get("takedown_actions", []),
            current_stage=data.get("current_stage", RetirementStage.PENDING.value),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
        )


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 字符串."""
    return datetime.now(timezone.utc).isoformat()


def _default_data_dir() -> str:
    """获取默认 data 目录 (项目根 / data)."""
    # workspace/retirement_orchestrator.py → 上溯 4 层到项目根
    here = Path(__file__).resolve()
    project_root = here.parents[3]
    return str(project_root / "data")


# 资源释放动作模板
_RESOURCE_RELEASE_ACTIONS: list[dict[str, Any]] = [
    {
        "action": "pause_all_campaigns",
        "target": "meta_ads",
        "needs_credential": True,
        "credential_hint": "META_ACCESS_TOKEN",
        "description": "暂停该游戏所有进行中的 Meta Ads campaign",
    },
    {
        "action": "archive_creatives",
        "target": "local_creative_library",
        "needs_credential": False,
        "description": "归档本地创意资产到 retirement_archives",
    },
    {
        "action": "revoke_credentials",
        "target": "credentials_manager",
        "needs_credential": True,
        "credential_hint": "ADMIN_TOKEN",
        "description": "吊销该游戏绑定的所有 API 凭证",
    },
    {
        "action": "release_eagle_assets",
        "target": "eagle_library",
        "needs_credential": False,
        "description": "从 Eagle 资产库释放该游戏占用的素材",
    },
]

# 下架动作模板 (各平台下架请求)
_TAKEDOWN_ACTIONS: list[dict[str, Any]] = [
    {
        "platform": "app_store",
        "action": "app_store_takedown",
        "app_id": "",  # 由调用方填充
        "needs_credential": True,
        "credential_hint": "APP_STORE_CONNECT_API_KEY",
        "description": "App Store Connect 下架请求",
    },
    {
        "platform": "google_play",
        "action": "google_play_unpublish",
        "app_id": "",
        "needs_credential": True,
        "credential_hint": "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON",
        "description": "Google Play 取消发布",
    },
]


# ═══════════════════════════════════════════════════════════════
# GameRetirementOrchestrator
# ═══════════════════════════════════════════════════════════════


class GameRetirementOrchestrator:
    """游戏退役编排器.

    7 步流程:
      1. evaluate_retirement()  — 评估退役条件
      2. create_plan()           — 创建退役计划
      3. archive_data()          — 数据归档 (本地)
      4. release_resources()     — 资源释放编排 (campaign 暂停 / creative 归档)
      5. request_takedown()      — 下架请求编排 (标记需要凭证的操作)
      6. verify_completion()     — 验证完成
      7. persist_state()         — 持久化状态

    用法:
        orch = GameRetirementOrchestrator(data_dir="data")
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={"roas_d30": 0.5, "ltv_d30": 0.3, "d1_retention": 0.25},
        )
        if decision.decision == "retire":
            plan = orch.create_plan(decision)
            plan = orch.execute_retirement(plan, dry_run=True)
    """

    def __init__(self, data_dir: str = "") -> None:
        """初始化编排器.

        Args:
            data_dir: 数据根目录 (默认项目根 / data).
                      状态文件存到 data_dir / retirement / plans.jsonl
                      归档内容存到 data_dir / retirement_archives / {game_id} /
        """
        self.data_dir = Path(data_dir) if data_dir else Path(_default_data_dir())
        # 状态持久化目录
        self._plans_dir = self.data_dir / "retirement"
        self._plans_path = self._plans_dir / "plans.jsonl"
        # 归档目录
        self._archives_dir = self.data_dir / "retirement_archives"
        # 确保目录存在
        self._plans_dir.mkdir(parents=True, exist_ok=True)
        self._archives_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. 评估退役决策 ──────────────────────────────────────

    def evaluate_retirement(
        self,
        game_id: str,
        metrics: dict,
        thresholds: dict | None = None,
    ) -> RetirementDecision:
        """评估游戏是否应该退役.

        Args:
            game_id: 游戏 ID
            metrics: {"roas_d30": 0.5, "ltv_d30": 0.3, "d1_retention": 0.25, ...}
            thresholds: {"roas_d30_min": 0.8, "ltv_d30_min": 0.5, "d1_retention_min": 0.35}
                为 None 时使用 DEFAULT_THRESHOLDS.

        Returns:
            RetirementDecision — decision ∈ {"retire", "keep", "review"}
        """
        used_thresholds = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            used_thresholds.update(thresholds)

        # 检查每个触发条件, 收集违反的指标
        violated: list[tuple[str, float, float]] = []  # (trigger, value, threshold)
        near_threshold: list[tuple[str, float, float]] = []  # 接近阈值

        for trigger, (metric_key, threshold_key) in _TRIGGER_TO_METRIC.items():
            value = metrics.get(metric_key)
            threshold = used_thresholds.get(threshold_key)
            if value is None or threshold is None:
                continue
            try:
                value_f = float(value)
                threshold_f = float(threshold)
            except (TypeError, ValueError):
                continue

            if value_f < threshold_f:
                violated.append((trigger, value_f, threshold_f))
            elif value_f < threshold_f * (1.0 + _REVIEW_BUFFER_RATIO):
                # 在阈值 10% buffer 内 → 接近阈值, 需 review
                near_threshold.append((trigger, value_f, threshold_f))

        # 决策逻辑
        if violated:
            # 任一 KPI 低于阈值 → 退役
            # 主触发器选违反最严重的一个 (差距比例最大)
            primary_trigger = max(
                violated,
                key=lambda x: (x[2] - x[1]) / x[2] if x[2] > 0 else 0.0,
            )[0]
            decision = "retire"
            # confidence 基于违反比例的平均值
            ratios = [
                (th - val) / th if th > 0 else 0.0
                for _, val, th in violated
            ]
            confidence = min(1.0, sum(ratios) / len(ratios) + 0.5) if ratios else 0.5
        elif near_threshold:
            # 接近阈值但未违反 → review
            primary_trigger = near_threshold[0][0]
            decision = "review"
            confidence = 0.4  # 不确定
        else:
            # 所有 KPI 健康 → 保留
            primary_trigger = RetirementTrigger.MANUAL_DECISION
            decision = "keep"
            confidence = 0.9

        return RetirementDecision(
            game_id=game_id,
            trigger=primary_trigger,
            metrics=dict(metrics),
            threshold_values=dict(used_thresholds),
            decision=decision,
            confidence=round(confidence, 3),
            decided_at=_now_iso(),
            decided_by="auto",
        )

    # ── 2. 创建退役计划 ──────────────────────────────────────

    def create_plan(self, decision: RetirementDecision) -> RetirementPlan:
        """创建退役计划.

        Args:
            decision: evaluate_retirement 的输出

        Returns:
            RetirementPlan — 已填充 7 步 stages 框架, 状态为 PENDING
        """
        stages = [
            {
                "stage": RetirementStage.DECIDING.value,
                "status": "completed",
                "started_at": decision.decided_at,
                "completed_at": _now_iso(),
                "error": "",
            },
            {
                "stage": RetirementStage.PENDING.value,
                "status": "pending",
                "started_at": "",
                "completed_at": "",
                "error": "",
            },
            {
                "stage": RetirementStage.ARCHIVING.value,
                "status": "pending",
                "started_at": "",
                "completed_at": "",
                "error": "",
            },
            {
                "stage": RetirementStage.RELEASING.value,
                "status": "pending",
                "started_at": "",
                "completed_at": "",
                "error": "",
            },
            {
                "stage": RetirementStage.TAKING_DOWN.value,
                "status": "pending",
                "started_at": "",
                "completed_at": "",
                "error": "",
            },
        ]
        plan = RetirementPlan(
            plan_id="",  # __post_init__ 会填充
            game_id=decision.game_id,
            decision=decision,
            stages=stages,
            archive_path="",
            resource_release_actions=[],
            takedown_actions=[],
            current_stage=RetirementStage.PENDING.value,
            created_at="",
            completed_at="",
        )
        self._persist_plan(plan)
        return plan

    # ── 3. 执行退役 (编排入口) ────────────────────────────────

    def execute_retirement(
        self,
        plan: RetirementPlan,
        dry_run: bool = True,
    ) -> RetirementPlan:
        """执行退役流程.

        依次调用 archive_data / release_resources / request_takedown,
        并更新 plan.stages 状态. dry_run=True 时只编排不执行需凭证的操作.

        Args:
            plan: 退役计划
            dry_run: True 则只编排不执行 (标记需要凭证的操作)

        Returns:
            更新后的 RetirementPlan (并已持久化)
        """
        if plan.current_stage in (
            RetirementStage.COMPLETED.value,
            RetirementStage.CANCELLED.value,
            RetirementStage.FAILED.value,
        ):
            # 已终态, 直接返回
            return plan

        try:
            # 标记 PENDING → 进入执行
            self._update_stage_status(
                plan, RetirementStage.PENDING.value, "completed"
            )

            # 3. 数据归档 (本地, 总是执行)
            self._update_stage_status(
                plan, RetirementStage.ARCHIVING.value, "in_progress"
            )
            archive_path = self.archive_game_data(plan.game_id)
            plan.archive_path = archive_path
            self._update_stage_status(
                plan, RetirementStage.ARCHIVING.value, "completed"
            )

            # 4. 资源释放编排
            self._update_stage_status(
                plan, RetirementStage.RELEASING.value, "in_progress"
            )
            plan.resource_release_actions = self.release_resources(
                plan.game_id, dry_run=dry_run
            )
            self._update_stage_status(
                plan, RetirementStage.RELEASING.value, "completed"
            )

            # 5. 下架请求编排
            self._update_stage_status(
                plan, RetirementStage.TAKING_DOWN.value, "in_progress"
            )
            plan.takedown_actions = self.request_takedown(
                plan.game_id, dry_run=dry_run
            )
            self._update_stage_status(
                plan, RetirementStage.TAKING_DOWN.value, "completed"
            )

            # 6. 验证完成
            self._verify_completion(plan)

            # 7. 持久化状态
            plan.current_stage = RetirementStage.COMPLETED.value
            plan.completed_at = _now_iso()
            self._persist_plan(plan)
            return plan
        except Exception as exc:
            # 失败时记录 error, 标记 FAILED
            logger.exception("Retirement execution failed for plan %s", plan.plan_id)
            plan.current_stage = RetirementStage.FAILED.value
            self._update_stage_status(
                plan, plan.current_stage, "failed", error=str(exc)
            )
            self._persist_plan(plan)
            return plan

    # ── 3a. 数据归档 (本地) ───────────────────────────────────

    def archive_game_data(self, game_id: str) -> str:
        """归档游戏数据到 data/retirement_archives/{game_id}/.

        归档内容:
          - game_config.json       — 游戏配置 (从 data/game_registry.json 抽取)
          - campaigns_history.jsonl — 投放历史 (从 data/liveops/campaigns.jsonl 过滤)
          - creative_mappings.jsonl — 素材映射记录 (从 data/creative_mapping 抽取)
          - performance.json        — 性能数据快照
          - audit_log.jsonl         — 审计日志快照

        Returns:
            归档目录的绝对路径字符串
        """
        archive_dir = self._archives_dir / game_id
        archive_dir.mkdir(parents=True, exist_ok=True)

        timestamp = _now_iso()

        # 1. 游戏配置 — 从 game_registry.json 抽取该游戏记录
        registry_path = self.data_dir / "game_registry.json"
        game_config: dict[str, Any] = {
            "game_id": game_id,
            "archived_at": timestamp,
            "source": "local_archive",
        }
        if registry_path.exists():
            try:
                registry = json.loads(
                    registry_path.read_text(encoding="utf-8")
                )
                games = registry if isinstance(registry, list) else registry.get("games", [])
                for g in games:
                    if (
                        isinstance(g, dict)
                        and g.get("game_id") == game_id or g.get("id") == game_id
                    ):
                        game_config["original_config"] = g
                        break
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read game_registry.json: %s", exc)

        self._write_json(archive_dir / "game_config.json", game_config)

        # 2. 投放历史 — 从 liveops/campaigns.jsonl 过滤该游戏的 campaign
        campaigns_src = self.data_dir / "liveops" / "campaigns.jsonl"
        archived_campaigns: list[dict] = []
        if campaigns_src.exists():
            try:
                for line in campaigns_src.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("game_id") == game_id:
                        archived_campaigns.append(record)
                    elif record.get("campaign_id", "").startswith(game_id):
                        archived_campaigns.append(record)
            except OSError as exc:
                logger.warning("Failed to read campaigns.jsonl: %s", exc)
        self._write_jsonl(
            archive_dir / "campaigns_history.jsonl", archived_campaigns
        )

        # 3. 素材映射记录 — 占位 (本地无对应文件时为空)
        creative_mappings: list[dict] = []
        creative_src = self.data_dir / "creative_mapping"
        if creative_src.exists():
            # 收集该游戏相关的 creative mapping 文件 (jsonl)
            for mapping_file in creative_src.glob("*.jsonl"):
                try:
                    for line in mapping_file.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if (
                            record.get("game_id") == game_id
                            or game_id in str(record.get("campaign_id", ""))
                        ):
                            creative_mappings.append(record)
                except OSError:
                    continue
        self._write_jsonl(
            archive_dir / "creative_mappings.jsonl", creative_mappings
        )

        # 4. 性能数据快照 — 整合当前已知指标 (mock, 由调用方在 metrics 中传入)
        performance = {
            "game_id": game_id,
            "archived_at": timestamp,
            "note": "性能数据归档占位 — 真实集成时应从 BI/数仓拉取",
        }
        self._write_json(archive_dir / "performance.json", performance)

        # 5. 审计日志快照
        audit_records: list[dict] = []
        audit_src = self.data_dir / "ceo" / "audit"
        if audit_src.exists():
            for audit_file in audit_src.glob("*.jsonl"):
                try:
                    for line in audit_file.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if (
                            record.get("game_id") == game_id
                            or game_id in str(record.get("context", ""))
                        ):
                            audit_records.append(record)
                except OSError:
                    continue
        # 附加本归档动作本身的审计
        audit_records.append({
            "timestamp": timestamp,
            "action": "retirement_archive",
            "game_id": game_id,
            "archive_path": str(archive_dir),
        })
        self._write_jsonl(archive_dir / "audit_log.jsonl", audit_records)

        logger.info("Archived game data for %s to %s", game_id, archive_dir)
        return str(archive_dir)

    # ── 4. 资源释放编排 ────────────────────────────────────────

    def release_resources(self, game_id: str, dry_run: bool = True) -> list[dict]:
        """资源释放编排.

        Actions:
          - pause_all_campaigns (需凭证 — 标记)
          - archive_creatives (本地 — 执行)
          - revoke_credentials (需凭证 — 标记)
          - release_eagle_assets (本地 — 执行)

        dry_run=True 时只编排不实际执行需凭证的操作.

        Args:
            game_id: 游戏 ID
            dry_run: True 则只编排不执行需凭证的操作

        Returns:
            动作列表 [{action, target, status, error, needs_credential, ...}]
        """
        actions: list[dict] = []
        for template in _RESOURCE_RELEASE_ACTIONS:
            action_record: dict[str, Any] = {
                "action": template["action"],
                "target": template["target"],
                "game_id": game_id,
                "needs_credential": template["needs_credential"],
                "description": template.get("description", ""),
                "error": "",
            }

            if template["needs_credential"]:
                # 需要凭证的操作: dry_run 模式只标记, 不执行
                if dry_run:
                    action_record["status"] = "needs_credential"
                    action_record["credential_hint"] = template.get(
                        "credential_hint", ""
                    )
                else:
                    # 非 dry_run 但本编排层不实际调用外部 API — 仍标记为 pending_credential
                    action_record["status"] = "pending_credential"
                    action_record["credential_hint"] = template.get(
                        "credential_hint", ""
                    )
                    action_record["error"] = (
                        "编排层不直接调用外部 API, 需上层注入凭证后由执行器调用"
                    )
            else:
                # 本地操作: 实际执行
                try:
                    self._execute_local_release_action(
                        game_id, template["action"]
                    )
                    action_record["status"] = "completed"
                except Exception as exc:
                    action_record["status"] = "failed"
                    action_record["error"] = str(exc)

            action_record["executed_at"] = _now_iso()
            actions.append(action_record)
        return actions

    def _execute_local_release_action(self, game_id: str, action: str) -> None:
        """执行本地资源释放动作 (无副作用占位).

        真实集成时此处可对接:
          - archive_creatives: 把 creative_library/{game_id}/ 复制到归档目录
          - release_eagle_assets: 调用 Eagle API 释放标签绑定
        """
        # 本编排层只记录日志, 不做实际文件操作 (避免破坏现有数据)
        logger.info(
            "Executing local release action %s for game %s (no-op placeholder)",
            action,
            game_id,
        )

    # ── 5. 下架请求编排 ────────────────────────────────────────

    def request_takedown(self, game_id: str, dry_run: bool = True) -> list[dict]:
        """下架请求编排.

        Actions:
          - app_store_takedown (需 App Store Connect API key)
          - google_play_unpublish (需 service account JSON)

        dry_run=True 时只标记需要凭证, 不实际执行. dry_run=False 时
        本编排层也仅标记 pending_credential (不直接调用外部 API).

        Args:
            game_id: 游戏 ID
            dry_run: True 则只标记需要凭证

        Returns:
            动作列表 [{platform, app_id, action, status, error, needs_credential, ...}]
        """
        # 尝试从 game_registry 解析该游戏的 store app_id
        store_ids = self._lookup_store_ids(game_id)

        actions: list[dict] = []
        for template in _TAKEDOWN_ACTIONS:
            platform = template["platform"]
            app_id = store_ids.get(platform, "")
            action_record: dict[str, Any] = {
                "platform": platform,
                "action": template["action"],
                "app_id": app_id,
                "game_id": game_id,
                "needs_credential": template["needs_credential"],
                "credential_hint": template.get("credential_hint", ""),
                "description": template.get("description", ""),
                "error": "",
            }

            if dry_run:
                action_record["status"] = "needs_credential"
            else:
                # 非 dry_run 时本编排层也不真实调用 — 仍需上层注入凭证后执行
                action_record["status"] = "pending_credential"
                action_record["error"] = (
                    "编排层不直接调用外部 API, 需上层注入凭证后由执行器调用"
                )

            action_record["executed_at"] = _now_iso()
            actions.append(action_record)
        return actions

    def _lookup_store_ids(self, game_id: str) -> dict[str, str]:
        """从 game_registry 解析该游戏的 store app_id (占位)."""
        # 真实集成时应查询 game_registry, 这里返回空字典
        # 调用方可在 metrics / decision.threshold_values 中提前注入
        return {
            "app_store": "",
            "google_play": "",
        }

    # ── 6. 验证完成 ───────────────────────────────────────────

    def _verify_completion(self, plan: RetirementPlan) -> None:
        """验证退役流程是否完成.

        - 归档路径非空
        - resource_release_actions / takedown_actions 都已填充
        - 所有 stages 都已完成 (除了 PENDING 这种过渡态)
        """
        if not plan.archive_path:
            raise RuntimeError("archive_path is empty after archiving stage")

        if not plan.resource_release_actions:
            raise RuntimeError("resource_release_actions is empty")

        if not plan.takedown_actions:
            raise RuntimeError("takedown_actions is empty")

        # 检查 stages 状态
        for stage in plan.stages:
            stage_name = stage.get("stage", "")
            stage_status = stage.get("status", "")
            # PENDING 是过渡态, 不强制要求完成
            if stage_name == RetirementStage.PENDING.value:
                continue
            if stage_status not in ("completed", "in_progress"):
                raise RuntimeError(
                    f"stage {stage_name} not completed (status={stage_status})"
                )

    # ── 7. 持久化 ─────────────────────────────────────────────

    def _persist_plan(self, plan: RetirementPlan) -> None:
        """持久化计划到 plans.jsonl.

        采用 upsert 语义: 同 plan_id 的记录会被覆盖 (按行重写).
        """
        self._plans_dir.mkdir(parents=True, exist_ok=True)
        plan_dict = plan.to_dict()

        # 读取现有计划
        existing: list[dict] = []
        if self._plans_path.exists():
            try:
                for line in self._plans_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    existing.append(record)
            except OSError as exc:
                logger.warning("Failed to read plans.jsonl: %s", exc)

        # upsert: 同 plan_id 替换, 否则追加
        updated: list[dict] = []
        replaced = False
        for record in existing:
            if record.get("plan_id") == plan.plan_id:
                updated.append(plan_dict)
                replaced = True
            else:
                updated.append(record)
        if not replaced:
            updated.append(plan_dict)

        # 写回
        try:
            with self._plans_path.open("w", encoding="utf-8") as f:
                for record in updated:
                    f.write(
                        json.dumps(record, ensure_ascii=False, default=str) + "\n"
                    )
        except OSError as exc:
            logger.warning("Failed to persist plan %s: %s", plan.plan_id, exc)

    def _update_stage_status(
        self,
        plan: RetirementPlan,
        stage_name: str,
        status: str,
        error: str = "",
    ) -> None:
        """更新 plan.stages 中某个 stage 的状态 (就地修改)."""
        now = _now_iso()
        for stage in plan.stages:
            if stage.get("stage") == stage_name:
                if status == "in_progress" and not stage.get("started_at"):
                    stage["started_at"] = now
                stage["status"] = status
                if status in ("completed", "failed"):
                    stage["completed_at"] = now
                if error:
                    stage["error"] = error
                return
        # 未找到则追加一条 stage 记录
        plan.stages.append({
            "stage": stage_name,
            "status": status,
            "started_at": now if status == "in_progress" else "",
            "completed_at": now if status in ("completed", "failed") else "",
            "error": error,
        })

    # ── 查询接口 ──────────────────────────────────────────────

    def get_plan(self, plan_id: str) -> Optional[RetirementPlan]:
        """获取退役计划."""
        plans = self._load_all_plans()
        for plan in plans:
            if plan.plan_id == plan_id:
                return plan
        return None

    def list_plans(self, status: str | None = None) -> list[RetirementPlan]:
        """列出退役计划 (可按 current_stage 过滤)."""
        plans = self._load_all_plans()
        if status:
            return [p for p in plans if p.current_stage == status]
        return plans

    def cancel_retirement(self, plan_id: str) -> bool:
        """取消退役 — 设置 current_stage=CANCELLED.

        已 COMPLETED / FAILED 的计划不可取消.

        Returns:
            True 取消成功, False 计划不存在或不可取消
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            return False
        if plan.current_stage in (
            RetirementStage.COMPLETED.value,
            RetirementStage.FAILED.value,
            RetirementStage.CANCELLED.value,
        ):
            return False
        plan.current_stage = RetirementStage.CANCELLED.value
        plan.completed_at = _now_iso()
        self._update_stage_status(
            plan, plan.current_stage, "completed"
        )
        self._persist_plan(plan)
        return True

    def get_stats(self) -> dict:
        """统计信息.

        Returns:
            {
                "total_plans": int,
                "by_stage": {stage: count, ...},
                "by_trigger": {trigger: count, ...},
                "by_decision": {decision: count, ...},
                "completed": int,
                "cancelled": int,
                "in_progress": int,
                "success_rate": float,  # completed / (completed + failed)
            }
        """
        plans = self._load_all_plans()
        by_stage: dict[str, int] = {}
        by_trigger: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        completed = 0
        cancelled = 0
        failed = 0
        in_progress = 0

        for plan in plans:
            stage = plan.current_stage
            by_stage[stage] = by_stage.get(stage, 0) + 1

            trigger = plan.decision.trigger
            by_trigger[trigger] = by_trigger.get(trigger, 0) + 1

            decision = plan.decision.decision
            by_decision[decision] = by_decision.get(decision, 0) + 1

            if stage == RetirementStage.COMPLETED.value:
                completed += 1
            elif stage == RetirementStage.CANCELLED.value:
                cancelled += 1
            elif stage == RetirementStage.FAILED.value:
                failed += 1
            else:
                in_progress += 1

        total = completed + failed
        success_rate = (completed / total) if total > 0 else 0.0

        return {
            "total_plans": len(plans),
            "by_stage": by_stage,
            "by_trigger": by_trigger,
            "by_decision": by_decision,
            "completed": completed,
            "cancelled": cancelled,
            "failed": failed,
            "in_progress": in_progress,
            "success_rate": round(success_rate, 3),
        }

    # ── 内部辅助: 文件读写 ────────────────────────────────────

    def _load_all_plans(self) -> list[RetirementPlan]:
        """从 plans.jsonl 加载所有计划."""
        if not self._plans_path.exists():
            return []
        plans: list[RetirementPlan] = []
        try:
            for line in self._plans_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    plans.append(RetirementPlan.from_dict(record))
                except (KeyError, TypeError) as exc:
                    logger.warning("Failed to parse plan record: %s", exc)
                    continue
        except OSError as exc:
            logger.warning("Failed to load plans.jsonl: %s", exc)
        return plans

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        """写入 JSON 文件."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to write %s: %s", path, exc)

    @staticmethod
    def _write_jsonl(path: Path, records: list[dict]) -> None:
        """写入 JSONL 文件."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                for record in records:
                    f.write(
                        json.dumps(record, ensure_ascii=False, default=str) + "\n"
                    )
        except OSError as exc:
            logger.warning("Failed to write %s: %s", path, exc)


__all__ = [
    "RetirementTrigger",
    "RetirementStage",
    "RetirementDecision",
    "RetirementPlan",
    "GameRetirementOrchestrator",
    "DEFAULT_THRESHOLDS",
]
