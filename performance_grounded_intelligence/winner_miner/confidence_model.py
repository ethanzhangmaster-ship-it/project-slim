"""Confidence Model — 数据置信度评分

解决小样本虚高问题: 花费少/安装少/数据天数短的素材不应获得高排名。

Confidence = 0.4 * SpendConf + 0.3 * InstallConf + 0.3 * DataDaysConf
"""
from typing import Dict

from ..config import CONFIDENCE_WEIGHTS, CONFIDENCE_CAPS


def calculate_confidence(spend: float, installs: int, data_days: int) -> float:
    """计算单条素材的数据置信度

    Args:
        spend: 花费 (USD)
        installs: 安装数
        data_days: 有数据的天数

    Returns:
        0.0 ~ 1.0 置信度
    """
    spend_conf = min(1.0, spend / CONFIDENCE_CAPS["spend"])
    install_conf = min(1.0, installs / CONFIDENCE_CAPS["installs"])
    days_conf = min(1.0, data_days / CONFIDENCE_CAPS["data_days"])

    confidence = (
        CONFIDENCE_WEIGHTS["spend"] * spend_conf +
        CONFIDENCE_WEIGHTS["installs"] * install_conf +
        CONFIDENCE_WEIGHTS["data_days"] * days_conf
    )

    return round(confidence, 4)


def calculate_confidence_from_record(record: dict) -> float:
    """从 performance record 计算置信度"""
    return calculate_confidence(
        spend=record.get("spend", 0),
        installs=record.get("installs", 0),
        data_days=record.get("data_days", 0),
    )


def get_confidence_breakdown(record: dict) -> Dict[str, float]:
    """获取置信度各维度明细"""
    spend = record.get("spend", 0)
    installs = record.get("installs", 0)
    data_days = record.get("data_days", 0)

    return {
        "spend_conf": round(min(1.0, spend / CONFIDENCE_CAPS["spend"]), 3),
        "install_conf": round(min(1.0, installs / CONFIDENCE_CAPS["installs"]), 3),
        "days_conf": round(min(1.0, data_days / CONFIDENCE_CAPS["data_days"]), 3),
        "total": calculate_confidence(spend, installs, data_days),
    }
