"""E11.5.1 Market Exceptions — 市场反馈异常定义。

E11.5 Market 模块专用异常层次：
  MarketError          — 基础异常
  MarketAdapterError   — Adapter 适配失败
  InvalidMetricsError  — 数据指标无效
  RepositoryError      — 反馈存储异常
"""

from __future__ import annotations


class MarketError(Exception):
    """Market 模块基础异常。"""
    pass


class MarketAdapterError(MarketError):
    """Adapter 适配失败。

    当外部数据格式不符合预期或缺少必要字段时抛出。
    """
    pass


class InvalidMetricsError(MarketError):
    """数据指标无效。

    当数值超出合理范围或格式不正确时抛出。
    """
    pass


class RepositoryError(MarketError):
    """反馈存储异常。

    当反馈存储操作失败时抛出。
    """
    pass