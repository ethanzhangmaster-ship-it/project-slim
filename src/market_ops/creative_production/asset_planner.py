"""Asset Planner - 素材来源规划器（V4.3.1 核心模块）

PRD 强调：整个生产系统最重要模块。
负责决定每个镜头素材从哪里来。

支持的素材来源：
- AI：AI 视频生成（Kling / Runway / Wan / Veo / Lovart / Pika / Luma / Hailuo / ComfyUI）
- EAGLE：Eagle 素材库复用
- UNITY：Unity 录屏
- WINNER：历史 Winner 素材复用
- MANUAL：人工剪辑
- CAPTURE：游戏录屏
- IMAGE_ANIM：图片动效（V4.3 静态图转动态）

输出：
- Production Plan
- 每个 Shot 标注 source / source_path / confidence / fallback
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssetAssignment:
    """单个镜头的素材分配"""
    shot_id: str
    source: str                  # ai / eagle / unity / winner / manual / capture / image_anim
    source_path: str = ""        # 素材路径或模型名
    model: str = ""              # 具体 AI 模型（当 source=ai）
    confidence: float = 0.0      # 匹配置信度 0-1
    fallback: list[str] = field(default_factory=list)  # 备选来源
    reason: str = ""             # 决策理由
    estimated_cost: float = 0.0  # 估算成本（美元）
    estimated_time_sec: float = 0.0  # 估算耗时（秒）
    requires_human_review: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "source": self.source,
            "source_path": self.source_path,
            "model": self.model,
            "confidence": self.confidence,
            "fallback": self.fallback,
            "reason": self.reason,
            "estimated_cost": self.estimated_cost,
            "estimated_time_sec": self.estimated_time_sec,
            "requires_human_review": self.requires_human_review,
            "metadata": self.metadata,
        }


@dataclass
class ProductionPlan:
    """生产计划"""
    plan_id: str
    variant_id: str
    assignments: list[AssetAssignment] = field(default_factory=list)
    source_summary: dict[str, int] = field(default_factory=dict)  # 源 → 镜头数
    total_estimated_cost: float = 0.0
    total_estimated_time_sec: float = 0.0
    requires_human_review_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "variant_id": self.variant_id,
            "assignments": [a.to_dict() for a in self.assignments],
            "source_summary": self.source_summary,
            "total_estimated_cost": self.total_estimated_cost,
            "total_estimated_time_sec": self.total_estimated_time_sec,
            "requires_human_review_count": self.requires_human_review_count,
            "metadata": self.metadata,
        }


class AssetPlanner:
    """素材来源规划器

    决策维度：
    1. 段落类型（Hook/Gameplay/Reward/CTA）
    2. 镜头复杂度（特效强度）
    3. 历史 Winner 库匹配度
    4. Eagle 库匹配度
    5. Unity 录屏可用性
    6. 预算约束
    7. 时间约束
    """

    # 段落类型 → 优先级源（按顺序）
    SEGMENT_SOURCE_PRIORITY: dict[str, list[str]] = {
        "opening":   ["winner", "eagle", "ai", "image_anim"],
        "gameplay":  ["unity", "capture", "winner", "ai"],
        "conflict":  ["ai", "winner", "unity", "manual"],
        "reward":    ["ai", "winner", "image_anim", "eagle"],
        "cta":       ["winner", "image_anim", "eagle", "manual"],
        "ending":    ["winner", "image_anim", "eagle", "manual"],
    }

    # 源 → 默认模型
    SOURCE_DEFAULT_MODEL: dict[str, str] = {
        "ai":         "kling",
        "image_anim": "kling",
        "unity":      "unity_capture",
        "capture":    "obs_capture",
        "winner":     "history_winner",
        "eagle":      "eagle_lib",
        "manual":     "manual_edit",
    }

    # 源 → 成本（美元/秒）
    SOURCE_COST_PER_SEC: dict[str, float] = {
        "ai":         0.20,
        "image_anim": 0.10,
        "unity":      0.02,
        "capture":    0.01,
        "winner":     0.00,
        "eagle":      0.00,
        "manual":     0.50,
    }

    # 源 → 处理时间（秒/镜头，含排队）
    SOURCE_TIME_PER_SHOT: dict[str, float] = {
        "ai":         60.0,
        "image_anim": 30.0,
        "unity":      15.0,
        "capture":    10.0,
        "winner":     5.0,
        "eagle":      3.0,
        "manual":     300.0,
    }

    # AI 模型 → 推荐段落
    MODEL_SEGMENT_AFFINITY: dict[str, list[str]] = {
        "kling":   ["reward", "opening", "conflict"],
        "runway":  ["opening", "reward", "conflict"],
        "veo":     ["gameplay", "opening"],
        "wan":     ["reward", "gameplay"],
        "lovart":  ["reward", "ending", "cta"],
        "pika":    ["opening", "cta"],
        "luma":    ["gameplay", "reward"],
        "hailuo":  ["reward", "opening"],
        "comfyui": ["reward", "conflict", "opening"],
    }

    def __init__(
        self,
        eagle_lib_path: str | None = None,
        winner_history: list[dict[str, Any]] | None = None,
        unity_assets: list[str] | None = None,
    ):
        self.eagle_lib_path = eagle_lib_path
        self.winner_history = winner_history or []
        self.unity_assets = unity_assets or []
        self._seg_priority = {k: list(v) for k, v in self.SEGMENT_SOURCE_PRIORITY.items()}

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def plan(
        self,
        shot_list: Any,         # ShotList
        strategy: Any,          # CreativeStrategy
        variant: dict[str, Any],
        budget_usd: float = 10.0,
    ) -> ProductionPlan:
        """为每个 Shot 分配素材来源

        Args:
            shot_list: 镜头列表
            strategy: 创意策略
            variant: Decision Variant
            budget_usd: 预算上限
        """
        assignments: list[AssetAssignment] = []
        source_counter: dict[str, int] = {}
        total_cost = 0.0
        total_time = 0.0
        review_count = 0

        for shot in shot_list.shots:
            seg_type = self._infer_segment_type(shot)
            priority_list = self._seg_priority.get(seg_type, ["ai", "eagle", "winner"])

            best_assignment: AssetAssignment | None = None
            for source in priority_list:
                # 预算检查
                est_cost = shot.duration * self.SOURCE_COST_PER_SEC.get(source, 0.1)
                if total_cost + est_cost > budget_usd and source not in ("winner", "eagle"):
                    continue  # 跳过超出预算的非免费源
                assignment = self._build_assignment(
                    shot=shot,
                    source=source,
                    seg_type=seg_type,
                    strategy=strategy,
                    variant=variant,
                )
                if assignment is None:
                    continue
                # 选置信度最高的
                if best_assignment is None or assignment.confidence > best_assignment.confidence:
                    best_assignment = assignment

            if best_assignment is None:
                # 兜底：人工
                best_assignment = self._build_assignment(
                    shot=shot,
                    source="manual",
                    seg_type=seg_type,
                    strategy=strategy,
                    variant=variant,
                )

            assignments.append(best_assignment)
            source_counter[best_assignment.source] = source_counter.get(best_assignment.source, 0) + 1
            total_cost += best_assignment.estimated_cost
            total_time += best_assignment.estimated_time_sec
            if best_assignment.requires_human_review:
                review_count += 1

        return ProductionPlan(
            plan_id=f"plan_{shot_list.variant_id}",
            variant_id=shot_list.variant_id,
            assignments=assignments,
            source_summary=source_counter,
            total_estimated_cost=round(total_cost, 2),
            total_estimated_time_sec=round(total_time, 1),
            requires_human_review_count=review_count,
            metadata={
                "shot_list_id": shot_list.shot_list_id,
                "budget_usd": budget_usd,
                "hook": strategy.hook,
                "platform": strategy.platform,
            },
        )

    # ------------------------------------------------------------------
    # 内部：分配决策
    # ------------------------------------------------------------------
    def _build_assignment(
        self,
        shot: Any,
        source: str,
        seg_type: str,
        strategy: Any,
        variant: dict[str, Any],
    ) -> AssetAssignment | None:
        """构造一次素材分配"""
        confidence, source_path, reason = self._evaluate_source(
            source, shot, seg_type, strategy, variant
        )

        if confidence <= 0.0 and source != "ai":
            return None

        # AI：选具体模型
        model = ""
        if source == "ai" or source == "image_anim":
            model = self._select_ai_model(seg_type, shot)

        # 置信度 < 0.6 → 标记人工审核
        requires_review = confidence < 0.6

        # 兜底链
        fallback = self._build_fallback(seg_type, source)

        cost = round(shot.duration * self.SOURCE_COST_PER_SEC.get(source, 0.1), 3)
        time_sec = self.SOURCE_TIME_PER_SHOT.get(source, 30.0)

        return AssetAssignment(
            shot_id=shot.shot_id,
            source=source,
            source_path=source_path,
            model=model,
            confidence=round(confidence, 3),
            fallback=fallback,
            reason=reason,
            estimated_cost=cost,
            estimated_time_sec=time_sec,
            requires_human_review=requires_review,
            metadata={
                "segment_type": seg_type,
                "duration": shot.duration,
                "shot_name": shot.name,
            },
        )

    def _evaluate_source(
        self,
        source: str,
        shot: Any,
        seg_type: str,
        strategy: Any,
        variant: dict[str, Any],
    ) -> tuple[float, str, str]:
        """评估某源对该镜头的匹配度

        Returns:
            (confidence, source_path, reason)
        """
        if source == "ai":
            return (
                0.85,
                f"ai://{self._select_ai_model(seg_type, shot)}",
                f"AI 生成 - 段落 {seg_type} 推荐使用 AI 模型生成",
            )

        if source == "image_anim":
            return (
                0.70,
                "v4.3://image_anim",
                "图片动效 - 基于 V4.3 静态图转动态",
            )

        if source == "unity":
            if self.unity_assets:
                # 简单匹配
                path = self.unity_assets[0]
                return (0.75, path, f"Unity 录屏素材: {path}")
            return (0.40, "unity://pending", "Unity 录屏 - 需确认资产可用")

        if source == "capture":
            return (0.65, "obs://capture", "录屏 - 通用游戏画面")

        if source == "winner":
            if self.winner_history:
                # 选第一个匹配段落的
                for w in self.winner_history:
                    if w.get("hook") == strategy.hook or w.get("segment") == seg_type:
                        return (
                            0.90,
                            w.get("path", f"history://{w.get('id', 'unknown')}"),
                            f"历史 Winner 复用 - 决策分数 {w.get('decision_score', 'N/A')}",
                        )
                # 无精确匹配，置信度降低
                return (
                    0.55,
                    f"history://{self.winner_history[0].get('id', 'unknown')}",
                    "历史 Winner 复用 - 段落不精确匹配，需人工确认",
                )
            return (0.0, "", "无历史 Winner 库")

        if source == "eagle":
            if self.eagle_lib_path and os.path.exists(self.eagle_lib_path):
                return (0.70, self.eagle_lib_path, f"Eagle 素材库: {self.eagle_lib_path}")
            return (0.0, "", "Eagle 库不可用")

        if source == "manual":
            return (0.95, "manual://editor", "人工剪辑 - 完全可控")

        return (0.0, "", f"未知来源 {source}")

    def _select_ai_model(self, seg_type: str, shot: Any) -> str:
        """根据段落类型和镜头特性选择 AI 模型"""
        # 优先使用 MODEL_SEGMENT_AFFINITY
        for model, segs in self.MODEL_SEGMENT_AFFINITY.items():
            if seg_type in segs:
                return model
        return "kling"

    def _build_fallback(self, seg_type: str, primary: str) -> list[str]:
        """构造兜底链"""
        chain = {
            "ai":         ["image_anim", "winner", "eagle", "manual"],
            "image_anim": ["ai", "winner", "eagle", "manual"],
            "unity":      ["capture", "ai", "manual"],
            "capture":    ["unity", "ai", "manual"],
            "winner":     ["eagle", "ai", "manual"],
            "eagle":      ["winner", "ai", "image_anim", "manual"],
            "manual":     ["ai", "winner"],
        }
        fallbacks = chain.get(primary, ["ai", "manual"])
        # 移除主源本身
        return [f for f in fallbacks if f != primary]

    def _infer_segment_type(self, shot: Any) -> str:
        """从 shot 推断段类型"""
        # shot.metadata 里可能保留 scene 信息
        meta = shot.metadata or {}
        if "segment_type" in meta:
            return meta["segment_type"]
        # 从 shot name 推断
        name = (shot.name or "").lower()
        for seg in self._seg_priority.keys():
            if seg in name:
                return seg
        return "gameplay"

    # ------------------------------------------------------------------
    # 批量
    # ------------------------------------------------------------------
    def plan_batch(
        self,
        shot_lists: list[Any],
        strategies: list[Any],
        variants: list[dict[str, Any]],
        budget_usd: float = 10.0,
    ) -> list[ProductionPlan]:
        """批量规划"""
        out = []
        for sl, st, v in zip(shot_lists, strategies, variants):
            try:
                out.append(self.plan(sl, st, v, budget_usd))
            except Exception:
                continue
        return out

    # ------------------------------------------------------------------
    # 格式化
    # ------------------------------------------------------------------
    def format_as_text(self, plan: ProductionPlan) -> str:
        """生产计划可读输出"""
        lines = [
            f"# {plan.plan_id}",
            f"总镜头: {len(plan.assignments)}",
            f"估算成本: ${plan.total_estimated_cost:.2f}",
            f"估算耗时: {plan.total_estimated_time_sec/60:.1f} 分钟",
            f"需人工审核: {plan.requires_human_review_count} 镜头",
            "",
            "## 素材来源分布",
        ]
        for src, n in plan.source_summary.items():
            lines.append(f"- {src}: {n} 镜头")
        lines.append("")
        lines.append("## 镜头分配详情")
        for a in plan.assignments:
            lines.append(
                f"- {a.shot_id} | {a.source} | {a.model or '-'} "
                f"| conf={a.confidence:.2f} | ${a.estimated_cost:.2f} "
                f"| review={a.requires_human_review}"
            )
        return "\n".join(lines)
