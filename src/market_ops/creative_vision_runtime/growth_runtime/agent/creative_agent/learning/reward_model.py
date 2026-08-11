"""E14.4.4.1 Reward Model — 创意奖励量化模型.

Reward Model 是 Learning Loop 的核心评分引擎，负责量化「什么 DNA 有价值」:

核心公式:
  CreativeReward = ROAS × 0.5 + LTV × 0.3 - spend_risk × 0.2

设计原则:
  - 确定性、可解释 — 所有评分基于明确的公式
  - 从 resolved 决策记录中提取奖励
  - 支持 DNA 级别和 Mutation 级别的奖励分解
  - 奖励值归一化到 [-1.0, 1.0] 区间
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..memory import CreativeDecisionRecord, CreativeDecisionOutcome, CreativeMemory
from ..experiment import VariantMetrics


# ═══════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class RewardConfig:
    """奖励计算配置.

    Attributes:
        roas_weight: ROAS 权重 (默认 0.5)
        ltv_weight: LTV 权重 (默认 0.3)
        spend_risk_weight: 花费风险权重 (默认 0.2)
        roas_baseline: ROAS 基准线 (低于此值奖励为负)
        min_samples_for_reward: 最小样本数
        reward_clip: 奖励裁剪区间
    """
    roas_weight: float = 0.5
    ltv_weight: float = 0.3
    spend_risk_weight: float = 0.2
    roas_baseline: float = 1.0
    min_samples_for_reward: int = 500
    reward_clip: tuple[float, float] = (-1.0, 1.0)


# ═══════════════════════════════════════════════════════════════
# Reward Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeReward:
    """创意奖励 — 单个创意/实验的综合奖励.

    Attributes:
        reward_id: 奖励 ID
        creative_id: 创意 ID
        total_reward: 总奖励值 [-1.0, 1.0]
        roas_component: ROAS 贡献
        ltv_component: LTV 贡献
        risk_component: 风险扣分
        confidence: 置信度
        sample_size: 样本量
        roas: ROAS 值
        ltv: LTV 值
        fatigue: 疲劳度
        created_at: 创建时间
    """
    reward_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    creative_id: str = ""
    total_reward: float = 0.0
    roas_component: float = 0.0
    ltv_component: float = 0.0
    risk_component: float = 0.0
    confidence: float = 0.0
    sample_size: int = 0
    roas: float = 0.0
    ltv: float = 0.0
    fatigue: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_positive(self) -> bool:
        return self.total_reward > 0

    @property
    def is_strong_positive(self) -> bool:
        return self.total_reward >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "reward_id": self.reward_id,
            "creative_id": self.creative_id,
            "total_reward": round(self.total_reward, 4),
            "roas_component": round(self.roas_component, 4),
            "ltv_component": round(self.ltv_component, 4),
            "risk_component": round(self.risk_component, 4),
            "confidence": round(self.confidence, 4),
            "sample_size": self.sample_size,
            "roas": round(self.roas, 4),
            "ltv": round(self.ltv, 4),
            "fatigue": round(self.fatigue, 4),
            "is_positive": self.is_positive,
            "is_strong_positive": self.is_strong_positive,
            "created_at": self.created_at,
        }


@dataclass
class DNAReward:
    """DNA 奖励 — 某个 DNA 基因模式的综合奖励.

    Attributes:
        dna_reward_id: DNA 奖励 ID
        gene_category: 基因类别 (hook/visual/emotion/...)
        gene_value: 基因值
        total_reward: 综合奖励
        occurrence_count: 出现次数
        win_count: 赢家次数
        win_rate: 胜率
        avg_roas: 平均 ROAS
        avg_ltv: 平均 LTV
        confidence: 置信度
    """
    dna_reward_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    gene_category: str = ""
    gene_value: str = ""
    total_reward: float = 0.0
    occurrence_count: int = 0
    win_count: int = 0
    win_rate: float = 0.0
    avg_roas: float = 0.0
    avg_ltv: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna_reward_id": self.dna_reward_id,
            "gene_category": self.gene_category,
            "gene_value": self.gene_value,
            "total_reward": round(self.total_reward, 4),
            "occurrence_count": self.occurrence_count,
            "win_count": self.win_count,
            "win_rate": round(self.win_rate, 4),
            "avg_roas": round(self.avg_roas, 4),
            "avg_ltv": round(self.avg_ltv, 4),
            "confidence": round(self.confidence, 4),
        }


@dataclass
class MutationReward:
    """Mutation 奖励 — 某个变异操作的奖励.

    Attributes:
        mutation_reward_id: Mutation 奖励 ID
        gene_category: 基因类别
        mutation_action: 变异动作 (CHANGE/KEEP/EXPLORE)
        total_reward: 综合奖励
        attempt_count: 尝试次数
        success_count: 成功次数
        success_rate: 成功率
        avg_impact: 平均影响
        confidence: 置信度
    """
    mutation_reward_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    gene_category: str = ""
    mutation_action: str = ""
    total_reward: float = 0.0
    attempt_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    avg_impact: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_reward_id": self.mutation_reward_id,
            "gene_category": self.gene_category,
            "mutation_action": self.mutation_action,
            "total_reward": round(self.total_reward, 4),
            "attempt_count": self.attempt_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_rate, 4),
            "avg_impact": round(self.avg_impact, 4),
            "confidence": round(self.confidence, 4),
        }


# ═══════════════════════════════════════════════════════════════
# Reward Model
# ═══════════════════════════════════════════════════════════════


class RewardModel:
    """创意奖励模型 — 量化「什么有价值」.

    职责:
      1. 从实验/变体指标计算综合奖励
      2. 从历史决策记录中分解 DNA 级别奖励
      3. 从变异记录中分解 Mutation 级别奖励
      4. 归一化奖励值到 [-1.0, 1.0]

    用法:
        model = RewardModel()
        reward = model.calculate(metrics)  # 从 VariantMetrics 计算
        dna_rewards = model.calculate_dna_rewards(memory)  # 从记忆计算
    """

    def __init__(self, config: RewardConfig | None = None, memory: CreativeMemory | None = None):
        self._config = config or RewardConfig()
        self._memory = memory or CreativeMemory()
        self._reward_history: list[CreativeReward] = []

    # ── 核心计算 ──────────────────────────────────────────────

    def calculate(
        self,
        metrics: VariantMetrics,
        baseline_roas: float | None = None,
    ) -> CreativeReward:
        """从 VariantMetrics 计算综合奖励.

        公式: ROAS × 0.5 + LTV × 0.3 - spend_risk × 0.2

        Args:
            metrics: 变体指标
            baseline_roas: 基准 ROAS (默认使用 config 中的值)

        Returns:
            CreativeReward: 综合奖励
        """
        c = self._config
        baseline = baseline_roas if baseline_roas is not None else c.roas_baseline

        # ROAS 组件: 相对于基准线的表现
        if metrics.roas > 0:
            roas_ratio = (metrics.roas - baseline) / max(baseline, 0.1)
            roas_component = c.roas_weight * min(max(roas_ratio, -1.0), 1.0)
        else:
            roas_component = -c.roas_weight

        # LTV 组件: 归一化到 [-1, 1]
        if metrics.ltv > 0:
            ltv_normalized = min((metrics.ltv - 3.0) / 10.0, 1.0)  # 假设 3.0 为基准
            ltv_component = c.ltv_weight * ltv_normalized
        else:
            ltv_component = 0.0

        # 风险组件: 疲劳度 + 花费风险
        fatigue_risk = min(metrics.fatigue, 0.5) / 0.5  # 归一化到 [0, 1]
        spend_risk = min(metrics.spend / 5000.0, 1.0) if metrics.spend > 0 else 0.0
        risk = (fatigue_risk + spend_risk) / 2.0
        risk_component = -c.spend_risk_weight * risk

        total = roas_component + ltv_component + risk_component
        total = max(c.reward_clip[0], min(c.reward_clip[1], total))

        # 置信度: 基于样本量
        confidence = min(metrics.installs / max(c.min_samples_for_reward, 1), 1.0)

        reward = CreativeReward(
            creative_id=metrics.creative_id,
            total_reward=total,
            roas_component=roas_component,
            ltv_component=ltv_component,
            risk_component=risk_component,
            confidence=confidence,
            sample_size=metrics.installs,
            roas=metrics.roas,
            ltv=metrics.ltv,
            fatigue=metrics.fatigue,
        )
        self._reward_history.append(reward)
        return reward

    def calculate_batch(
        self,
        metrics_list: list[VariantMetrics],
        baseline_roas: float | None = None,
    ) -> list[CreativeReward]:
        """批量计算奖励."""
        return [self.calculate(m, baseline_roas) for m in metrics_list]

    # ── DNA 级别奖励 ──────────────────────────────────────────

    def calculate_dna_rewards(
        self,
        dna_entries: list[dict[str, Any]] | None = None,
    ) -> list[DNAReward]:
        """从创意记忆中的 DNA 记录计算 DNA 级别奖励.

        从存储的 winner DNA 和决策记录中提取:
        - 哪些基因值 (e.g. transformation hook) 经常出现在赢家中
        - 哪些基因组合带来高 ROAS

        Args:
            dna_entries: DNA 条目列表 (基因值 → 表现)

        Returns:
            list[DNAReward]: DNA 级别奖励列表
        """
        if dna_entries is None:
            # 从 memory 中提取
            winner_dnas = self._memory.get_winner_dnas()
            dna_entries = [
                {"genes": e.dna.genes if e.dna else {}, "performance": e.performance}
                for e in winner_dnas
            ]

        # 按基因类别聚合
        gene_stats: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in dna_entries:
            genes = entry.get("genes", {})
            perf = entry.get("performance", {})
            for category, gene_data in genes.items():
                if isinstance(gene_data, dict):
                    gene_value = gene_data.get("value", str(gene_data))
                else:
                    gene_value = str(gene_data)
                gene_stats[category].append({
                    "value": gene_value,
                    "roas": perf.get("roas", 0),
                    "ltv": perf.get("ltv", 0),
                })

        rewards = []
        for category, entries in gene_stats.items():
            for gene_value in set(e["value"] for e in entries):
                matched = [e for e in entries if e["value"] == gene_value]
                count = len(matched)
                avg_roas = sum(e["roas"] for e in matched) / max(count, 1)
                avg_ltv = sum(e["ltv"] for e in matched) / max(count, 1)

                # 计算奖励: ROAS 偏离基准 + LTV 偏离基准
                roas_reward = (avg_roas - self._config.roas_baseline) / max(self._config.roas_baseline, 0.1)
                ltv_reward = (avg_ltv - 3.0) / 10.0
                total = self._config.roas_weight * roas_reward + self._config.ltv_weight * ltv_reward
                total = max(self._config.reward_clip[0], min(self._config.reward_clip[1], total))

                # 置信度: 基于出现次数
                win_count = sum(1 for e in matched if e.get("roas", 0) >= 1.5)
                confidence = min(count / 10.0, 1.0) * 0.5 + min(win_count / max(count, 1), 1.0) * 0.5

                rewards.append(DNAReward(
                    gene_category=category,
                    gene_value=gene_value,
                    total_reward=total,
                    occurrence_count=count,
                    win_count=win_count,
                    win_rate=win_count / max(count, 1),
                    avg_roas=avg_roas,
                    avg_ltv=avg_ltv,
                    confidence=confidence,
                ))

        # 按 total_reward 降序排列
        rewards.sort(key=lambda r: r.total_reward, reverse=True)
        return rewards

    def get_top_dna_genes(
        self,
        min_confidence: float = 0.3,
        top_n: int = 10,
    ) -> list[DNAReward]:
        """获取最有价值的 DNA 基因."""
        rewards = self.calculate_dna_rewards()
        return [
            r for r in rewards
            if r.confidence >= min_confidence
        ][:top_n]

    # ── Mutation 级别奖励 ─────────────────────────────────────

    def calculate_mutation_rewards(
        self,
        resolved_records: list[CreativeDecisionRecord] | None = None,
    ) -> list[MutationReward]:
        """从已解析的决策记录中计算 Mutation 级别奖励.

        从 GENERATE_VARIANTS / MUTATE_DNA 类型的决策中提取:
        - 哪些 mutation 操作带来了正向结果
        - 哪些基因类别的变异最有效

        Args:
            resolved_records: 已解析的决策记录

        Returns:
            list[MutationReward]: Mutation 级别奖励
        """
        if resolved_records is None:
            resolved_records = self._memory.get_resolved()

        # 按 gene_category × mutation_action 聚合
        mutation_stats: dict[str, list[float]] = defaultdict(list)
        for record in resolved_records:
            if record.action_type.value not in ("generate_variants", "mutate_dna"):
                continue
            params = record.action_params
            gene_category = params.get("gene_category", "")
            mutation_action = params.get("mutation_action", "")
            if not gene_category:
                continue

            key = f"{gene_category}:{mutation_action}"
            mutation_stats[key].append(record.reward)

        rewards = []
        for key, values in mutation_stats.items():
            gene_category, mutation_action = key.split(":", 1)
            count = len(values)
            avg_reward = sum(values) / max(count, 1)
            success_count = sum(1 for v in values if v > 0)
            success_rate = success_count / max(count, 1)

            # 置信度: 基于尝试次数
            confidence = min(count / 5.0, 1.0) * 0.7 + success_rate * 0.3

            rewards.append(MutationReward(
                gene_category=gene_category,
                mutation_action=mutation_action,
                total_reward=avg_reward,
                attempt_count=count,
                success_count=success_count,
                success_rate=success_rate,
                avg_impact=avg_reward,
                confidence=confidence,
            ))

        rewards.sort(key=lambda r: r.total_reward, reverse=True)
        return rewards

    def get_mutation_priorities(
        self,
        min_confidence: float = 0.2,
    ) -> list[MutationReward]:
        """获取变异优先级排序."""
        rewards = self.calculate_mutation_rewards()
        return [
            r for r in rewards
            if r.confidence >= min_confidence
        ]

    # ── 综合评估 ──────────────────────────────────────────────

    def evaluate_creative(
        self,
        metrics: VariantMetrics,
        dna_genes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """综合评估一个创意素材.

        返回:
          - 综合奖励
          - DNA 基因贡献
          - 改进建议
        """
        reward = self.calculate(metrics)

        result: dict[str, Any] = {
            "reward": reward.to_dict(),
            "verdict": "strong_winner" if reward.is_strong_positive
            else "winner" if reward.is_positive
            else "underperformer",
        }

        if dna_genes:
            all_dna = self.calculate_dna_rewards()
            gene_contributions = {}
            for category, value in dna_genes.items():
                for dr in all_dna:
                    if dr.gene_category == category and dr.gene_value == value:
                        gene_contributions[category] = {
                            "value": value,
                            "reward": dr.total_reward,
                            "confidence": dr.confidence,
                        }
                        break
            result["gene_contributions"] = gene_contributions

        return result

    def stats(self) -> dict[str, Any]:
        return {
            "total_rewards": len(self._reward_history),
            "avg_reward": round(
                sum(r.total_reward for r in self._reward_history) / max(len(self._reward_history), 1), 4,
            ),
            "config": {
                "roas_weight": self._config.roas_weight,
                "ltv_weight": self._config.ltv_weight,
                "spend_risk_weight": self._config.spend_risk_weight,
            },
        }

    def reset(self) -> None:
        self._reward_history.clear()


def create_reward_model(
    roas_weight: float = 0.5,
    ltv_weight: float = 0.3,
    spend_risk_weight: float = 0.2,
    roas_baseline: float = 1.0,
    memory: CreativeMemory | None = None,
) -> RewardModel:
    """创建默认 RewardModel."""
    config = RewardConfig(
        roas_weight=roas_weight,
        ltv_weight=ltv_weight,
        spend_risk_weight=spend_risk_weight,
        roas_baseline=roas_baseline,
    )
    return RewardModel(config=config, memory=memory)