from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class SentimentType(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class ReviewCategory(Enum):
    GAMEPLAY = "gameplay"
    GRAPHICS = "graphics"
    PERFORMANCE = "performance"
    FEATURES = "features"
    MONETIZATION = "monetization"
    UX = "ux"
    BUGS = "bugs"
    GENERAL = "general"


@dataclass
class ReviewData:
    review_id: str
    user_id: str
    rating: int
    text: str
    sentiment: SentimentType = SentimentType.NEUTRAL
    category: ReviewCategory = ReviewCategory.GENERAL
    keywords: List[str] = field(default_factory=list)
    is_featured: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    responded: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "user_id": self.user_id,
            "rating": self.rating,
            "text": self.text,
            "sentiment": self.sentiment.value,
            "category": self.category.value,
            "keywords": self.keywords,
            "is_featured": self.is_featured,
            "created_at": self.created_at.isoformat(),
            "responded": self.responded,
        }


@dataclass
class SentimentAnalysis:
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    neutral_ratio: float = 0.0
    average_rating: float = 0.0
    trending_sentiment: str = "stable"
    key_issues: List[str] = field(default_factory=list)
    key_strengths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "positive_ratio": self.positive_ratio,
            "negative_ratio": self.negative_ratio,
            "neutral_ratio": self.neutral_ratio,
            "average_rating": self.average_rating,
            "trending_sentiment": self.trending_sentiment,
            "key_issues": self.key_issues,
            "key_strengths": self.key_strengths,
        }


@dataclass
class ReviewInsight:
    insight_id: str
    category: ReviewCategory
    insight_type: str
    description: str
    impact_score: float = 0.0
    frequency: int = 0
    actionable: bool = False
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "category": self.category.value,
            "insight_type": self.insight_type,
            "description": self.description,
            "impact_score": self.impact_score,
            "frequency": self.frequency,
            "actionable": self.actionable,
            "recommendation": self.recommendation,
        }


class ReviewAnalyzer:
    def __init__(self):
        self._reviews: Dict[str, ReviewData] = {}
        self._sentiment_cache: Optional[SentimentAnalysis] = None
        self._insights: Dict[str, ReviewInsight] = {}
        self._keyword_frequency: Dict[str, int] = {}
        self._category_stats: Dict[ReviewCategory, Dict[str, Any]] = {}

    def add_review(self, rating: int, text: str, user_id: str = None) -> ReviewData:
        review_id = f"review_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        sentiment = self._classify_sentiment(rating, text)
        category = self._classify_category(text)
        keywords = self._extract_keywords(text)

        review = ReviewData(
            review_id=review_id,
            user_id=user_id or f"user_{random.randint(1000, 9999)}",
            rating=rating,
            text=text,
            sentiment=sentiment,
            category=category,
            keywords=keywords,
        )
        self._reviews[review_id] = review
        self._update_keyword_frequency(keywords)
        self._sentiment_cache = None
        return review

    def _classify_sentiment(self, rating: int, text: str) -> SentimentType:
        if rating >= 4:
            return SentimentType.POSITIVE
        elif rating <= 2:
            return SentimentType.NEGATIVE
        elif rating == 3:
            positive_words = ["good", "great", "love", "amazing", "excellent"]
            negative_words = ["bad", "hate", "terrible", "worst", "poor", "bug", "crash"]
            has_positive = any(w in text.lower() for w in positive_words)
            has_negative = any(w in text.lower() for w in negative_words)
            if has_positive and has_negative:
                return SentimentType.MIXED
            elif has_positive:
                return SentimentType.POSITIVE
            elif has_negative:
                return SentimentType.NEGATIVE
        return SentimentType.NEUTRAL

    def _classify_category(self, text: str) -> ReviewCategory:
        category_keywords = {
            ReviewCategory.GAMEPLAY: ["gameplay", "play", "controls", "difficulty", "level", "mode"],
            ReviewCategory.GRAPHICS: ["graphics", "visual", "animation", "art", "design", "look"],
            ReviewCategory.PERFORMANCE: ["performance", "lag", "slow", "fast", "loading", "speed"],
            ReviewCategory.FEATURES: ["feature", "missing", "new", "update", "content", "add"],
            ReviewCategory.MONETIZATION: ["price", "cost", "pay", "purchase", "money", "ads", "premium"],
            ReviewCategory.UX: ["interface", "ui", "menu", "navigation", "easy", "hard"],
            ReviewCategory.BUGS: ["bug", "crash", "error", "fix", "broken", "glitch"],
        }

        text_lower = text.lower()
        for category, keywords in category_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return category
        return ReviewCategory.GENERAL

    def _extract_keywords(self, text: str) -> List[str]:
        common_keywords = ["game", "fun", "play", "good", "bad", "love", "bug", "crash", "update", "feature", "ads", "graphics"]
        text_lower = text.lower()
        return [kw for kw in common_keywords if kw in text_lower]

    def _update_keyword_frequency(self, keywords: List[str]):
        for kw in keywords:
            self._keyword_frequency[kw] = self._keyword_frequency.get(kw, 0) + 1

    def analyze_sentiment(self) -> SentimentAnalysis:
        if self._sentiment_cache:
            return self._sentiment_cache

        reviews = list(self._reviews.values())
        if not reviews:
            return SentimentAnalysis()

        total = len(reviews)
        positive = sum(1 for r in reviews if r.sentiment == SentimentType.POSITIVE)
        negative = sum(1 for r in reviews if r.sentiment == SentimentType.NEGATIVE)
        neutral = sum(1 for r in reviews if r.sentiment in [SentimentType.NEUTRAL, SentimentType.MIXED])

        avg_rating = sum(r.rating for r in reviews) / total

        top_keywords = sorted(self._keyword_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
        issues = [kw for kw, freq in top_keywords if kw in ["bug", "crash", "ads", "lag", "slow"]]
        strengths = [kw for kw, freq in top_keywords if kw in ["fun", "love", "good", "great", "amazing"]]

        analysis = SentimentAnalysis(
            positive_ratio=positive / total,
            negative_ratio=negative / total,
            neutral_ratio=neutral / total,
            average_rating=avg_rating,
            trending_sentiment=self._determine_trend(),
            key_issues=issues,
            key_strengths=strengths,
        )
        self._sentiment_cache = analysis
        return analysis

    def _determine_trend(self) -> str:
        reviews = list(self._reviews.values())
        if len(reviews) < 10:
            return "insufficient_data"

        recent = reviews[-20:]
        older = reviews[:-20] if len(reviews) > 20 else reviews

        recent_avg = sum(r.rating for r in recent) / len(recent)
        older_avg = sum(r.rating for r in older) / len(older)

        if recent_avg > older_avg + 0.5:
            return "improving"
        elif recent_avg < older_avg - 0.5:
            return "declining"
        return "stable"

    def generate_insights(self) -> List[ReviewInsight]:
        insights = []
        category_data = self._analyze_categories()

        for category, data in category_data.items():
            if data["negative_count"] > 3:
                insight = ReviewInsight(
                    insight_id=f"insight_{category.value}_{datetime.now().strftime('%Y%m%d')}",
                    category=category,
                    insight_type="issue",
                    description=f"{data['negative_count']} negative reviews about {category.value}",
                    impact_score=data["negative_ratio"] * 10,
                    frequency=data["negative_count"],
                    actionable=True,
                    recommendation=f"Address {category.value} issues mentioned in reviews",
                )
                insights.append(insight)
                self._insights[insight.insight_id] = insight

            if data["positive_count"] > 5:
                insight = ReviewInsight(
                    insight_id=f"insight_{category.value}_strength_{datetime.now().strftime('%Y%m%d')}",
                    category=category,
                    insight_type="strength",
                    description=f"{data['positive_count']} positive reviews about {category.value}",
                    impact_score=data["positive_ratio"] * 5,
                    frequency=data["positive_count"],
                    actionable=False,
                    recommendation=f"Continue enhancing {category.value}",
                )
                insights.append(insight)
                self._insights[insight.insight_id] = insight

        return insights

    def _analyze_categories(self) -> Dict[ReviewCategory, Dict[str, Any]]:
        reviews = list(self._reviews.values())
        category_data = {}

        for category in ReviewCategory:
            cat_reviews = [r for r in reviews if r.category == category]
            if cat_reviews:
                positive = sum(1 for r in cat_reviews if r.sentiment == SentimentType.POSITIVE)
                negative = sum(1 for r in cat_reviews if r.sentiment == SentimentType.NEGATIVE)
                category_data[category] = {
                    "total": len(cat_reviews),
                    "positive_count": positive,
                    "negative_count": negative,
                    "positive_ratio": positive / len(cat_reviews),
                    "negative_ratio": negative / len(cat_reviews),
                    "avg_rating": sum(r.rating for r in cat_reviews) / len(cat_reviews),
                }
            else:
                category_data[category] = {
                    "total": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "positive_ratio": 0,
                    "negative_ratio": 0,
                    "avg_rating": 0,
                }

        self._category_stats = category_data
        return category_data

    def get_reviews(self, rating: int = None, sentiment: SentimentType = None, category: ReviewCategory = None) -> List[ReviewData]:
        reviews = list(self._reviews.values())
        if rating:
            reviews = [r for r in reviews if r.rating == rating]
        if sentiment:
            reviews = [r for r in reviews if r.sentiment == sentiment]
        if category:
            reviews = [r for r in reviews if r.category == category]
        return reviews

    def get_review(self, review_id: str) -> Optional[ReviewData]:
        return self._reviews.get(review_id)

    def get_insights(self) -> List[ReviewInsight]:
        return list(self._insights.values())

    def get_keyword_frequency(self) -> Dict[str, int]:
        return dict(self._keyword_frequency)

    def get_category_stats(self) -> Dict[str, Any]:
        return {k.value: v for k, v in self._category_stats.items()}

    def get_stats(self) -> Dict[str, Any]:
        reviews = list(self._reviews.values())
        return {
            "total_reviews": len(reviews),
            "reviews_by_rating": {
                str(i): sum(1 for r in reviews if r.rating == i)
                for i in range(1, 6)
            },
            "reviews_by_sentiment": {
                s.value: sum(1 for r in reviews if r.sentiment == s)
                for s in SentimentType
            },
            "reviews_by_category": {
                c.value: sum(1 for r in reviews if r.category == c)
                for c in ReviewCategory
            },
            "total_insights": len(self._insights),
            "unique_keywords": len(self._keyword_frequency),
        }