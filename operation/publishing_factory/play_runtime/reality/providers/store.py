"""StoreProvider — 商店表现采集 (rating / review / installs).

包裹 GooglePlayRealClient.get_reviews 并本地聚合:
- rating_average: 评论星级均值 (Play Console Reviews API 只回 recent reviews,
  作为近似信号使用, 精确 lifetime rating 需要另一 API)
- negative_review_ratio: <=2 星占比
API 失败返回 fallback 空壳，package 级隔离。
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import StoreMetrics


class StoreProvider:
    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client

    def get_store_metrics(
        self, package_name: str, max_reviews: int = 50
    ) -> StoreMetrics:
        if self._client is None:
            return StoreMetrics(package_name=package_name, source="fallback")
        try:
            raw = self._client.get_reviews(package_name, max_results=max_reviews) or {}
        except Exception:
            return StoreMetrics(package_name=package_name, source="fallback")

        reviews = raw.get("reviews") or []
        ratings = []
        negative = 0
        for review in reviews:
            star = review.get("star_rating")
            try:
                star = float(star)
            except (TypeError, ValueError):
                continue
            ratings.append(star)
            if star <= 2:
                negative += 1

        rating_average: Optional[float] = None
        negative_ratio: Optional[float] = None
        if ratings:
            rating_average = round(sum(ratings) / len(ratings), 2)
            negative_ratio = round(negative / len(ratings), 4)

        count = raw.get("count")
        try:
            count = int(count) if count is not None else len(reviews)
        except (TypeError, ValueError):
            count = len(reviews)

        return StoreMetrics(
            package_name=package_name,
            rating_average=rating_average,
            review_count=count,
            installs=None,  # Publishing API 不含安装量; 留 seam 给未来数据源
            negative_review_ratio=negative_ratio,
            source="live",
        )
