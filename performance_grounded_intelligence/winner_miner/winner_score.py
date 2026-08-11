"""Winner Score — 综合评分模型

WinnerScore = 0.4 * ROAS_norm + 0.3 * Scale_norm + 0.2 * Confidence + 0.1 * RevPI_norm

同时考虑:
- ROAS (赚钱效率)
- Revenue Scale (总收入规模)
- Confidence (数据可靠性)
- Revenue Per Install (用户质量)
"""
from typing import Dict

from ..config import WINNER_SCORE_WEIGHTS, WINNER_SCORE_CAPS
from .confidence_model import calculate_confidence


def calculate_winner_score(spend: float, iap_roas: float, all_revenue: float,
                           installs: int, data_days: int) -> float:
    """计算 Winner Score

    Args:
        spend: 花费
        iap_roas: IAP ROAS
        all_revenue: 总收入
        installs: 安装数
        data_days: 数据天数

    Returns:
        0.0 ~ 1.0 综合评分
    """
    # ROAS 归一化
    roas_norm = min(1.0, iap_roas / WINNER_SCORE_CAPS["roas"])

    # 规模归一化
    scale_norm = min(1.0, all_revenue / WINNER_SCORE_CAPS["scale"])

    # 置信度
    confidence = calculate_confidence(spend, installs, data_days)

    # RevPI (Revenue Per Install)
    revpi = all_revenue / max(installs, 1)
    revpi_norm = min(1.0, revpi / WINNER_SCORE_CAPS["revpi"])

    # 综合评分
    score = (
        WINNER_SCORE_WEIGHTS["roas"] * roas_norm +
        WINNER_SCORE_WEIGHTS["scale"] * scale_norm +
        WINNER_SCORE_WEIGHTS["confidence"] * confidence +
        WINNER_SCORE_WEIGHTS["revpi"] * revpi_norm
    )

    return round(score, 4)


def calculate_winner_score_from_record(record: dict) -> float:
    """从 asset/performance record 计算 Winner Score"""
    return calculate_winner_score(
        spend=record.get("spend", 0),
        iap_roas=record.get("iap_roas", 0),
        all_revenue=record.get("all_revenue", 0),
        installs=record.get("installs", 0),
        data_days=record.get("data_days", 0),
    )


def get_score_breakdown(record: dict) -> Dict[str, float]:
    """获取评分各维度明细"""
    spend = record.get("spend", 0)
    iap_roas = record.get("iap_roas", 0)
    all_revenue = record.get("all_revenue", 0)
    installs = record.get("installs", 0)
    data_days = record.get("data_days", 0)

    revpi = all_revenue / max(installs, 1)
    confidence = calculate_confidence(spend, installs, data_days)

    return {
        "roas_norm": round(min(1.0, iap_roas / WINNER_SCORE_CAPS["roas"]), 3),
        "scale_norm": round(min(1.0, all_revenue / WINNER_SCORE_CAPS["scale"]), 3),
        "confidence": round(confidence, 3),
        "revpi": round(revpi, 2),
        "revpi_norm": round(min(1.0, revpi / WINNER_SCORE_CAPS["revpi"]), 3),
        "winner_score": calculate_winner_score(spend, iap_roas, all_revenue, installs, data_days),
    }
