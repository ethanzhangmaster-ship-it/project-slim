"""Creative Director - 创意总监

整个系统的大脑。
负责决定：
- 为什么拍（Objective）
- 怎么拍（Hook / Editing Style）
- 拍给谁（Audience）
- 目标是什么（Target Metric）

输出 Creative Strategy，是所有后续模块的根。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CreativeStrategy:
    """创意策略"""
    variant_id: str
    objective: str            # 提升CTR / 提升CVR / 提升ROAS
    target_metric: str       # ctr / cvr / roas
    hook: str                # reward / collection / merge / transformation / fail / emotion
    hook_priority: str       # 前3秒必须出现奖励
    emotion: str             # 惊喜 / 满足 / 紧迫 / 愉悦
    gameplay: str            # 玩法类型
    reward_style: str        # 奖励风格
    cta_timing: float        # CTA 出现时间（秒）
    cta_message: str         # CTA 文案
    editing_style: str       # 节奏：快/中/慢
    duration: float          # 总时长
    priority: int            # 优先级 1-5
    target_audience: str     # 目标受众
    platform: str            # 平台
    placement: str           # 版位
    country: str             # 国家
    rationale: str           # 创意理由
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "objective": self.objective,
            "target_metric": self.target_metric,
            "hook": self.hook,
            "hook_priority": self.hook_priority,
            "emotion": self.emotion,
            "gameplay": self.gameplay,
            "reward_style": self.reward_style,
            "cta_timing": self.cta_timing,
            "cta_message": self.cta_message,
            "editing_style": self.editing_style,
            "duration": self.duration,
            "priority": self.priority,
            "target_audience": self.target_audience,
            "platform": self.platform,
            "placement": self.placement,
            "country": self.country,
            "rationale": self.rationale,
            "constraints": self.constraints,
            "metadata": self.metadata,
        }


class CreativeDirector:
    """创意总监"""
    
    # 决策分数 → 优先级
    SCORE_TO_PRIORITY: list[tuple[float, int]] = [
        (90.0, 5),  # 极高
        (80.0, 4),  # 高
        (70.0, 3),  # 中
        (60.0, 2),  # 低
        (0.0, 1),   # 最低
    ]

    # 改维 → 创意目标推断
    DIM_TO_OBJECTIVE: dict[str, str] = {
        "lighting": "提升CTR：吸引注意力",
        "creature": "提升CTR：增加新鲜感",
        "character": "提升CVR：建立角色认同",
        "background": "提升CTR：场景差异化",
        "camera": "提升CTR：视觉冲击",
        "hook_type": "提升CTR：钩子优化",
    }

    # 钩子 → 前3秒规则
    HOOK_PRIORITY_RULES: dict[str, str] = {
        "reward": "前3秒必须出现奖励视觉（金币/宝石/宝箱）",
        "collection": "前3秒必须出现惊喜发现表情和发光物品",
        "merge": "前3秒必须出现合成动画开始",
        "transformation": "前3秒必须出现变身/进化对比",
        "fail": "前3秒必须出现失败/错误瞬间",
        "emotion": "前3秒必须出现强烈情感特写",
    }

    # 钩子 → 推荐情感
    HOOK_TO_EMOTION: dict[str, str] = {
        "reward": "满足/惊喜",
        "collection": "好奇/期待",
        "merge": "期待/满意",
        "transformation": "震撼/渴望",
        "fail": "紧张/挑战",
        "emotion": "温暖/共鸣",
    }

    # 决策分数 → 编辑节奏
    SCORE_TO_EDITING: dict[str, str] = {
        "high": "快节奏：0.5-1秒一切换，Hook 强冲击",
        "medium": "中节奏：1-2秒切换，Hook 清晰",
        "low": "慢节奏：2-3秒切换，叙事清晰",
    }

    # 钩子 → CTA 出现时间
    HOOK_TO_CTA_TIMING: dict[str, float] = {
        "reward": 8.0,      # 早 CTA 刺激下载
        "collection": 11.0,  # 中等
        "merge": 12.0,
        "transformation": 13.0,
        "fail": 11.0,
        "emotion": 13.0,
    }

    # 钩子 → CTA 文案
    HOOK_TO_CTA: dict[str, str] = {
        "reward": "Download Now - Claim Your Reward!",
        "collection": "Play Now - Collect All!",
        "merge": "Start Merging - Free!",
        "transformation": "Transform Now - Limited Time!",
        "fail": "Try Again - Can You Do Better?",
        "emotion": "Join the Story - Play Free!",
    }

    def __init__(self):
        self._score_to_priority = list(self.SCORE_TO_PRIORITY)
        self._dim_to_objective = dict(self.DIM_TO_OBJECTIVE)
        self._hook_priority_rules = dict(self.HOOK_PRIORITY_RULES)
        self._hook_to_emotion = dict(self.HOOK_TO_EMOTION)
        self._score_to_editing = dict(self.SCORE_TO_EDITING)
        self._hook_to_cta_timing = dict(self.HOOK_TO_CTA_TIMING)
        self._hook_to_cta = dict(self.HOOK_TO_CTA)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def direct(
        self,
        variant: dict[str, Any],
        duration: float = 15.0,
        platform: str = "facebook",
        placement: str = "feed",
        country: str = "US",
    ) -> CreativeStrategy:
        """制定创意策略

        Args:
            variant: V4.2.2 Decision Variant
            duration: 视频时长
            platform: 平台
            placement: 版位
            country: 国家

        Returns:
            CreativeStrategy
        """
        variant_id = variant.get("variant_id", "unknown")
        decision_score = variant.get("decision_score", 0)
        changed_dim = variant.get("changed_dimension", "")
        new_value = variant.get("new_value", "")
        audience = variant.get("audience", "general")
        dna = variant.get("dna", {})

        # 推断 Hook 类型
        hook_type = self._infer_hook(dna, variant)

        # 目标推断
        objective = self._infer_objective(changed_dim, decision_score, variant)

        # 目标指标
        target_metric = self._infer_target_metric(changed_dim, variant)

        # 情感
        emotion = self._hook_to_emotion.get(hook_type, "好奇/期待")

        # 玩法
        gameplay = self._infer_gameplay(dna)

        # 奖励风格
        reward_style = self._infer_reward_style(hook_type, dna)

        # 编辑节奏
        editing_style = self._infer_editing_style(decision_score)

        # CTA
        cta_timing = self._hook_to_cta_timing.get(hook_type, 12.0)
        if cta_timing >= duration:
            cta_timing = max(5.0, duration - 3.0)
        cta_message = self._hook_to_cta.get(hook_type, "Download Now")

        # 优先级
        priority = self._score_to_priority_func(decision_score)

        # Hook 优先级规则
        hook_priority = self._hook_priority_rules.get(hook_type, "")

        # 创意理由
        rationale = self._build_rationale(
            changed_dim, new_value, hook_type, decision_score, objective
        )

        # 约束
        constraints = self._build_constraints(duration, placement, hook_type)

        return CreativeStrategy(
            variant_id=variant_id,
            objective=objective,
            target_metric=target_metric,
            hook=hook_type,
            hook_priority=hook_priority,
            emotion=emotion,
            gameplay=gameplay,
            reward_style=reward_style,
            cta_timing=cta_timing,
            cta_message=cta_message,
            editing_style=editing_style,
            duration=duration,
            priority=priority,
            target_audience=audience,
            platform=platform,
            placement=placement,
            country=country,
            rationale=rationale,
            constraints=constraints,
            metadata={
                "decision_score": decision_score,
                "changed_dimension": changed_dim,
                "new_value": new_value,
            },
        )

    # ------------------------------------------------------------------
    # 推断方法
    # ------------------------------------------------------------------
    def _infer_hook(self, dna: dict[str, Any], variant: dict[str, Any]) -> str:
        """推断 Hook 类型"""
        hook = dna.get("hook", {})
        hook_type = hook.get("type", "")
        if hook_type:
            return hook_type

        dim = variant.get("changed_dimension", "").lower()
        dim_map = {
            "creature": "collection",
            "character": "emotion",
            "lighting": "collection",
            "background": "collection",
            "hook_type": "reward",
        }
        return dim_map.get(dim, "collection")

    def _infer_objective(
        self,
        changed_dim: str,
        decision_score: float,
        variant: dict[str, Any],
    ) -> str:
        """推断创意目标"""
        # 从改维推断
        if changed_dim and changed_dim in self._dim_to_objective:
            return self._dim_to_objective[changed_dim]

        # 从决策分数推断
        if decision_score >= 80:
            return "提升CTR：高分创意优先投放"
        elif decision_score >= 70:
            return "提升CVR：中等质量规模化"
        else:
            return "提升ROAS：低成本测试"

    def _infer_target_metric(self, changed_dim: str, variant: dict[str, Any]) -> str:
        """推断目标指标"""
        dim_metric_map = {
            "lighting": "ctr",
            "creature": "ctr",
            "character": "cvr",
            "background": "ctr",
            "camera": "ctr",
        }
        return dim_metric_map.get(changed_dim, "ctr")

    def _infer_gameplay(self, dna: dict[str, Any]) -> str:
        """推断玩法"""
        gameplay = dna.get("gameplay", {})
        return gameplay.get("type", "collection")

    def _infer_reward_style(self, hook_type: str, dna: dict[str, Any]) -> str:
        """推断奖励风格"""
        reward_styles = {
            "reward": "金币爆炸 / 宝箱开启 / 升级特效",
            "collection": "稀有物品发光 / 收集完成庆祝",
            "merge": "物品升级 / 进化特效",
            "transformation": "变形 / 进化 / 力量觉醒",
            "fail": "失败提示 / 再来一次",
            "emotion": "温馨结局 / 情感满足",
        }
        return reward_styles.get(hook_type, "奖励视觉")

    def _infer_editing_style(self, decision_score: float) -> str:
        """推断编辑节奏"""
        if decision_score >= 80:
            return self._score_to_editing.get("high", "")
        elif decision_score >= 60:
            return self._score_to_editing.get("medium", "")
        else:
            return self._score_to_editing.get("low", "")

    def _score_to_priority_func(self, score: float) -> int:
        """分数转优先级"""
        for threshold, priority in self._score_to_priority:
            if score >= threshold:
                return priority
        return 1

    def _build_rationale(
        self,
        changed_dim: str,
        new_value: str,
        hook_type: str,
        decision_score: float,
        objective: str,
    ) -> str:
        """构建创意理由"""
        parts = [
            f"决策分数 {decision_score:.1f} → 优先级 P{self._score_to_priority_func(decision_score)}",
            f"改动维度 {changed_dim} → {new_value}",
            f"Hook 类型 {hook_type} → {self._hook_priority_rules.get(hook_type, '')}",
            f"目标: {objective}",
        ]
        return " | ".join(parts)

    def _build_constraints(
        self,
        duration: float,
        placement: str,
        hook_type: str,
    ) -> list[str]:
        """构建约束"""
        constraints = [
            f"总时长 {duration} 秒",
            f"版位 {placement}，需符合 {placement} 安全区域",
        ]

        # 版位特定约束
        placement_constraints = {
            "feed": "中心 80% 安全区，避开顶部 15% 和底部 15%",
            "reels": "9:16 全屏，声音优化，循环友好",
            "stories": "9:16，15秒内，顶部底部安全区",
        }
        if placement in placement_constraints:
            constraints.append(placement_constraints[placement])

        # Hook 特定约束
        if hook_type in self._hook_priority_rules:
            constraints.append(self._hook_priority_rules[hook_type])

        return constraints

    # ------------------------------------------------------------------
    # 导演笔记
    # ------------------------------------------------------------------
    def generate_director_notes(self, strategy: CreativeStrategy) -> str:
        """生成导演笔记（给后续模块看的指导说明）"""
        notes = [
            f"## 创意总监指令 - {strategy.variant_id}",
            f"",
            f"### 目标",
            f"- 核心目标: {strategy.objective}",
            f"- 关注指标: {strategy.target_metric.upper()}",
            f"",
            f"### Hook 策略",
            f"- 类型: {strategy.hook}",
            f"- 规则: {strategy.hook_priority}",
            f"- 情感: {strategy.emotion}",
            f"",
            f"### 玩法与奖励",
            f"- 玩法类型: {strategy.gameplay}",
            f"- 奖励风格: {strategy.reward_style}",
            f"",
            f"### CTA",
            f"- 出现时间: {strategy.cta_timing} 秒",
            f"- 文案: {strategy.cta_message}",
            f"",
            f"### 制作",
            f"- 编辑风格: {strategy.editing_style}",
            f"- 总时长: {strategy.duration} 秒",
            f"- 优先级: P{strategy.priority}",
            f"",
            f"### 创意理由",
            f"{strategy.rationale}",
            f"",
            f"### 约束",
        ]
        for c in strategy.constraints:
            notes.append(f"- {c}")

        return "\n".join(notes)