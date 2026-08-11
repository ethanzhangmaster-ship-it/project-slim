"""E11.5.2 Signal Rules — IAP 产品信号规则。

定义各维度信号的计算规则，将 PerformanceFeedback 指标
转换为 0-1 标准化信号评分。

规则：
  1. 付费信号 (pay_rate)
  2. LTV 信号 (d30_ltv)
  3. 留存信号 (d7_retention)
  4. UA 质量信号 (CPI + Install CVR)
  5. 综合信号
  6. Creative DNA 映射

数据流：
  PerformanceFeedback Metrics → SignalRules → Signal Scores
"""

from __future__ import annotations

from .feedback_schema import (
    UAMetrics,
    EngagementMetrics,
    IAPMetrics,
    PerformanceFeedback,
)


# ═══════════════════════════════════════════════════════════
# 归一化工具函数
# ═══════════════════════════════════════════════════════════

def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """将值限制在 [min_val, max_val] 范围内。"""
    return max(min_val, min(max_val, value))


def _linear_normalize(value: float, ref_low: float, ref_high: float) -> float:
    """线性归一化：value 在 [ref_low, ref_high] 区间映射到 [0, 1]。

    Args:
        value: 原始值
        ref_low: 参考下限（映射到 0）
        ref_high: 参考上限（映射到 1）

    Returns:
        0.0 ~ 1.0 的标准化值
    """
    if ref_high <= ref_low:
        return 0.0
    return _clamp((value - ref_low) / (ref_high - ref_low))


def _inverse_normalize(value: float, ref_low: float, ref_high: float) -> float:
    """逆向归一化：值越低越好（如 CPI）。

    Args:
        value: 原始值
        ref_low: 参考下限（映射到 1）
        ref_high: 参考上限（映射到 0）

    Returns:
        0.0 ~ 1.0 的标准化值
    """
    return 1.0 - _linear_normalize(value, ref_low, ref_high)


# ═══════════════════════════════════════════════════════════
# 规则1 — 付费信号
# ═══════════════════════════════════════════════════════════

def evaluate_monetization_signal(iap: IAPMetrics | None) -> float:
    """评估付费信号。

    基于 pay_rate 计算：
      - 0%    → 0.0
      - 5%    → 0.5
      - 10%+  → 1.0

    Args:
        iap: IAP 指标

    Returns:
        0.0 ~ 1.0 的付费信号评分
    """
    if iap is None:
        return 0.0
    return _linear_normalize(iap.pay_rate, 0.0, 0.10)


def evaluate_arpu_signal(iap: IAPMetrics | None) -> float:
    """评估 ARPU 信号。

    基于 ARPU 计算：
      - $0    → 0.0
      - $2    → 0.5
      - $5+   → 1.0

    Args:
        iap: IAP 指标

    Returns:
        0.0 ~ 1.0 的 ARPU 信号评分
    """
    if iap is None:
        return 0.0
    return _linear_normalize(iap.arpu, 0.0, 5.0)


# ═══════════════════════════════════════════════════════════
# 规则2 — LTV 信号
# ═══════════════════════════════════════════════════════════

def evaluate_ltv_signal(iap: IAPMetrics | None) -> float:
    """评估 LTV 信号。

    基于 D30 LTV 计算：
      - $0    → 0.0
      - $3    → 0.5
      - $10+  → 1.0

    Args:
        iap: IAP 指标

    Returns:
        0.0 ~ 1.0 的 LTV 信号评分
    """
    if iap is None:
        return 0.0
    return _linear_normalize(iap.d30_ltv, 0.0, 10.0)


def evaluate_d7_ltv_signal(iap: IAPMetrics | None) -> float:
    """评估 D7 LTV 信号。

    基于 D7 LTV 计算：
      - $0    → 0.0
      - $1    → 0.5
      - $3+   → 1.0

    Args:
        iap: IAP 指标

    Returns:
        0.0 ~ 1.0 的 D7 LTV 信号评分
    """
    if iap is None:
        return 0.0
    return _linear_normalize(iap.d7_ltv, 0.0, 3.0)


# ═══════════════════════════════════════════════════════════
# 规则3 — 留存信号
# ═══════════════════════════════════════════════════════════

def evaluate_retention_signal(eng: EngagementMetrics | None) -> float:
    """评估留存信号。

    基于 D7 retention 计算：
      - 0%    → 0.0
      - 30%   → 0.5
      - 60%+  → 1.0

    Args:
        eng: 用户行为指标

    Returns:
        0.0 ~ 1.0 的留存信号评分
    """
    if eng is None:
        return 0.0
    return _linear_normalize(eng.d7_retention, 0.0, 0.60)


def evaluate_d1_retention_signal(eng: EngagementMetrics | None) -> float:
    """评估 D1 留存信号。

    基于 D1 retention 计算：
      - 0%    → 0.0
      - 40%   → 0.5
      - 80%+  → 1.0

    Args:
        eng: 用户行为指标

    Returns:
        0.0 ~ 1.0 的 D1 留存信号评分
    """
    if eng is None:
        return 0.0
    return _linear_normalize(eng.d1_retention, 0.0, 0.80)


def evaluate_engagement_signal(eng: EngagementMetrics | None) -> float:
    """评估综合参与度信号。

    基于 playtime 计算：
      - 0分钟   → 0.0
      - 30分钟  → 0.5
      - 60分钟+ → 1.0

    Args:
        eng: 用户行为指标

    Returns:
        0.0 ~ 1.0 的参与度信号评分
    """
    if eng is None:
        return 0.0
    return _linear_normalize(eng.playtime, 0.0, 60.0)


# ═══════════════════════════════════════════════════════════
# 规则4 — UA 质量信号
# ═══════════════════════════════════════════════════════════

def evaluate_cpi_signal(ua: UAMetrics | None) -> float:
    """评估 CPI 信号（越低越好）。

    基于 CPI 计算：
      - $0    → 1.0
      - $2    → 0.5
      - $5+   → 0.0

    Args:
        ua: UA 指标

    Returns:
        0.0 ~ 1.0 的 CPI 信号评分
    """
    if ua is None:
        return 0.0
    return _inverse_normalize(ua.cpi, 0.0, 5.0)


def evaluate_install_cvr_signal(ua: UAMetrics | None) -> float:
    """评估 Install CVR 信号。

    基于 Install CVR 计算：
      - 0%    → 0.0
      - 30%   → 0.5
      - 60%+  → 1.0

    Args:
        ua: UA 指标

    Returns:
        0.0 ~ 1.0 的 Install CVR 信号评分
    """
    if ua is None:
        return 0.0
    return _linear_normalize(ua.install_cvr, 0.0, 0.60)


def evaluate_acquisition_signal(ua: UAMetrics | None) -> float:
    """评估综合获客质量信号。

    综合 CPI (40%) + Install CVR (60%)。

    Args:
        ua: UA 指标

    Returns:
        0.0 ~ 1.0 的获客信号评分
    """
    if ua is None:
        return 0.0
    cpi_score = evaluate_cpi_signal(ua)
    cvr_score = evaluate_install_cvr_signal(ua)
    return round(cpi_score * 0.4 + cvr_score * 0.6, 4)


# ═══════════════════════════════════════════════════════════
# 规则5 — 综合信号
# ═══════════════════════════════════════════════════════════

def evaluate_overall_quality(
    feedback: PerformanceFeedback,
) -> float:
    """评估综合质量评分。

    权重分配（IAP 产品导向）：
      - Monetization (pay_rate + ARPU): 40%
      - LTV (d30_ltv): 25%
      - Engagement (d7_retention): 20%
      - Acquisition (CPI + CVR): 15%

    Args:
        feedback: PerformanceFeedback 实例

    Returns:
        0.0 ~ 1.0 的综合质量评分
    """
    monetization = 0.0
    ltv = 0.0
    engagement = 0.0
    acquisition = 0.0

    if feedback.monetization_metrics:
        iap = feedback.monetization_metrics
        monetization = (
            evaluate_monetization_signal(iap) * 0.6
            + evaluate_arpu_signal(iap) * 0.4
        )
        ltv = evaluate_ltv_signal(iap)

    if feedback.engagement_metrics:
        engagement = evaluate_retention_signal(feedback.engagement_metrics)

    if feedback.ua_metrics:
        acquisition = evaluate_acquisition_signal(feedback.ua_metrics)

    return round(
        monetization * 0.40
        + ltv * 0.25
        + engagement * 0.20
        + acquisition * 0.15,
        4,
    )


# ═══════════════════════════════════════════════════════════
# 规则6 — Creative DNA 映射
# ═══════════════════════════════════════════════════════════

def map_to_creative_genes(
    feedback: PerformanceFeedback,
) -> dict[str, float]:
    """将市场信号映射到 Creative DNA 基因槽位。

    映射关系：
      - hook:      CPI + Install CVR + D1 retention（获客 + 首日留存）
      - visual:    CTR + Install CVR（视觉吸引力）
      - reward:    pay_rate + ARPU + LTV（付费转化）
      - emotion:   D7 retention + playtime（情感共鸣）
      - gameplay:  D30 retention + level_progress（长期留存）

    Args:
        feedback: PerformanceFeedback 实例

    Returns:
        {gene_name: score} 字典
    """
    ua = feedback.ua_metrics
    eng = feedback.engagement_metrics
    iap = feedback.monetization_metrics

    signals: dict[str, float] = {}

    # hook: 获客能力 + 首日留存 → 能否吸引用户
    hook_score = 0.0
    hook_count = 0
    if ua is not None:
        hook_score += evaluate_cpi_signal(ua)
        hook_score += evaluate_install_cvr_signal(ua)
        hook_count += 2
    if eng is not None:
        hook_score += evaluate_d1_retention_signal(eng)
        hook_count += 1
    signals["hook"] = round(hook_score / hook_count, 4) if hook_count > 0 else 0.0

    # visual: 视觉吸引力 → CTR + CVR
    visual_score = 0.0
    visual_count = 0
    if ua is not None:
        visual_score += _linear_normalize(ua.ctr, 0.0, 0.10)
        visual_score += evaluate_install_cvr_signal(ua)
        visual_count += 2
    signals["visual"] = round(visual_score / visual_count, 4) if visual_count > 0 else 0.0

    # reward: 付费转化 → 最能体现商业价值
    reward_score = 0.0
    reward_count = 0
    if iap is not None:
        reward_score += evaluate_monetization_signal(iap)
        reward_score += evaluate_arpu_signal(iap)
        reward_score += evaluate_ltv_signal(iap)
        reward_count += 3
    signals["reward"] = round(reward_score / reward_count, 4) if reward_count > 0 else 0.0

    # emotion: 情感共鸣 → 留存 + 游戏时长
    emotion_score = 0.0
    emotion_count = 0
    if eng is not None:
        emotion_score += evaluate_retention_signal(eng)
        emotion_score += evaluate_engagement_signal(eng)
        emotion_count += 2
    signals["emotion"] = round(emotion_score / emotion_count, 4) if emotion_count > 0 else 0.0

    # gameplay: 长期留存 → D30 + 进度
    gameplay_score = 0.0
    gameplay_count = 0
    if eng is not None:
        gameplay_score += _linear_normalize(eng.d30_retention, 0.0, 0.30)
        gameplay_score += _linear_normalize(eng.level_progress, 0.0, 10.0)
        gameplay_count += 2
    signals["gameplay"] = round(gameplay_score / gameplay_count, 4) if gameplay_count > 0 else 0.0

    return signals


# ═══════════════════════════════════════════════════════════
# 规则7 — 置信度计算
# ═══════════════════════════════════════════════════════════

def compute_confidence(
    feedback: PerformanceFeedback,
) -> tuple[float, int]:
    """计算信号置信度。

    基于样本量和数据完整性：
      - sample_size = UA installs
      - sample_weight = min(sample_size / 10000, 1.0)
      - data_quality = 完整数据源比例
      - confidence = sample_weight * 0.7 + data_quality * 0.3

    Args:
        feedback: PerformanceFeedback 实例

    Returns:
        (confidence, sample_size)
    """
    # 样本量
    sample_size = 0
    if feedback.ua_metrics:
        sample_size = feedback.ua_metrics.installs

    # 样本量权重
    sample_weight = min(sample_size / 10000.0, 1.0)

    # 数据质量
    quality = 0.0
    if feedback.has_ua_data:
        quality += 0.33
    if feedback.has_engagement_data:
        quality += 0.33
    if feedback.has_monetization_data:
        quality += 0.34

    confidence = round(sample_weight * 0.7 + quality * 0.3, 4)
    return confidence, sample_size