from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class Sentiment(Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class Review:
    review_id: str
    app_id: str
    user_id: str
    user_name: str
    rating: int = 5
    title: str = ""
    body: str = ""
    sentiment: Sentiment = Sentiment.POSITIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    response: Optional[str] = None
    response_at: Optional[datetime] = None
    version: str = "1.0.0"
    locale: str = "en-US"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "app_id": self.app_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "rating": self.rating,
            "title": self.title,
            "body": self.body,
            "sentiment": self.sentiment.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "response": self.response,
            "response_at": self.response_at.isoformat() if self.response_at else None,
            "version": self.version,
            "locale": self.locale,
        }


@dataclass
class ReviewStats:
    app_id: str
    total_reviews: int = 0
    avg_rating: float = 0.0
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    response_rate: float = 0.0
    reviews_last_24h: int = 0
    reviews_last_7d: int = 0
    trending_up: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "total_reviews": self.total_reviews,
            "avg_rating": self.avg_rating,
            "positive_count": self.positive_count,
            "neutral_count": self.neutral_count,
            "negative_count": self.negative_count,
            "response_rate": self.response_rate,
            "reviews_last_24h": self.reviews_last_24h,
            "reviews_last_7d": self.reviews_last_7d,
            "trending_up": self.trending_up,
        }


@dataclass
class SentimentSummary:
    app_id: str
    overall_sentiment: Sentiment = Sentiment.NEUTRAL
    positive_percentage: float = 0.0
    neutral_percentage: float = 0.0
    negative_percentage: float = 0.0
    top_positive_keywords: List[str] = field(default_factory=list)
    top_negative_keywords: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "overall_sentiment": self.overall_sentiment.value,
            "positive_percentage": self.positive_percentage,
            "neutral_percentage": self.neutral_percentage,
            "negative_percentage": self.negative_percentage,
            "top_positive_keywords": self.top_positive_keywords,
            "top_negative_keywords": self.top_negative_keywords,
            "summary": self.summary,
        }


class ReviewMonitor:
    def __init__(self):
        self._reviews: Dict[str, Review] = {}
        self._app_reviews: Dict[str, List[str]] = {}

    def get_reviews(self, app_id: str) -> List[Review]:
        if app_id not in self._app_reviews:
            return self._generate_mock_reviews(app_id)

        review_ids = self._app_reviews[app_id]
        return sorted(
            [self._reviews[rid] for rid in review_ids],
            key=lambda r: r.created_at,
            reverse=True,
        )

    def _generate_mock_reviews(self, app_id: str) -> List[Review]:
        mock_reviews = [
            {"rating": 5, "title": "Excellent!", "body": "Great game, lots of fun!", "locale": "en-US"},
            {"rating": 4, "title": "Good", "body": "Enjoying the gameplay", "locale": "en-US"},
            {"rating": 3, "title": "Average", "body": "Needs more content", "locale": "en-US"},
            {"rating": 5, "title": "完美!", "body": "非常好玩的游戏", "locale": "zh-CN"},
            {"rating": 2, "title": "Buggy", "body": "Crashes frequently", "locale": "en-US"},
        ]

        reviews = []
        for idx, data in enumerate(mock_reviews):
            review_id = f"{app_id}_review_{idx + 1}"
            sentiment = Sentiment.POSITIVE if data["rating"] >= 4 else Sentiment.NEGATIVE if data["rating"] <= 2 else Sentiment.NEUTRAL
            review = Review(
                review_id=review_id,
                app_id=app_id,
                user_id=f"user_{idx + 1}",
                user_name=f"User{idx + 1}",
                sentiment=sentiment,
                **data,
            )
            reviews.append(review)
            self._reviews[review_id] = review

        if app_id not in self._app_reviews:
            self._app_reviews[app_id] = []
        self._app_reviews[app_id].extend([r.review_id for r in reviews])

        return reviews

    def get_review_stats(self, app_id: str) -> ReviewStats:
        reviews = self.get_reviews(app_id)
        total = len(reviews)

        if total == 0:
            return ReviewStats(app_id=app_id)

        avg_rating = sum(r.rating for r in reviews) / total
        positive_count = sum(1 for r in reviews if r.sentiment == Sentiment.POSITIVE)
        neutral_count = sum(1 for r in reviews if r.sentiment == Sentiment.NEUTRAL)
        negative_count = sum(1 for r in reviews if r.sentiment == Sentiment.NEGATIVE)
        response_rate = sum(1 for r in reviews if r.response) / total

        return ReviewStats(
            app_id=app_id,
            total_reviews=total,
            avg_rating=round(avg_rating, 1),
            positive_count=positive_count,
            neutral_count=neutral_count,
            negative_count=negative_count,
            response_rate=round(response_rate, 2),
            reviews_last_24h=3,
            reviews_last_7d=15,
            trending_up=positive_count > negative_count,
        )

    def respond_to_review(self, review_id: str, response: str) -> bool:
        if review_id not in self._reviews:
            return False

        review = self._reviews[review_id]
        review.response = response
        review.response_at = datetime.now()
        review.updated_at = datetime.now()
        self._reviews[review_id] = review
        return True

    def get_sentiment_summary(self, app_id: str) -> SentimentSummary:
        stats = self.get_review_stats(app_id)

        if stats.total_reviews == 0:
            return SentimentSummary(app_id=app_id)

        positive_pct = (stats.positive_count / stats.total_reviews) * 100
        neutral_pct = (stats.neutral_count / stats.total_reviews) * 100
        negative_pct = (stats.negative_count / stats.total_reviews) * 100

        overall = Sentiment.POSITIVE if positive_pct > 50 else Sentiment.NEGATIVE if negative_pct > 50 else Sentiment.NEUTRAL

        return SentimentSummary(
            app_id=app_id,
            overall_sentiment=overall,
            positive_percentage=round(positive_pct, 1),
            neutral_percentage=round(neutral_pct, 1),
            negative_percentage=round(negative_pct, 1),
            top_positive_keywords=["fun", "great", "excellent", "love"],
            top_negative_keywords=["bug", "crash", "slow", "lag"],
            summary=f"Overall sentiment is {overall.value}. {round(positive_pct)}% positive, {round(neutral_pct)}% neutral, {round(negative_pct)}% negative.",
        )