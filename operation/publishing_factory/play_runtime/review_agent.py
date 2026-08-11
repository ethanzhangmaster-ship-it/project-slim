"""E13.5 — Review Agent (comment -> intelligence -> auto-reply).

The voice of the Play Runtime toward players. It reads an app's user reviews
through the ``PlayConnector`` (inheriting the three-tier gate — READ never
writes, PRODUCTION real READ), classifies each review with **deterministic
keyword rules** (no LLM, Lean), recommends (and optionally posts) a developer
reply through the lowest-blast-radius write (``reviews.reply``).

Idempotency: ``run_daily`` skips reviews already seen in the audit log and
never double-replies a review (the connector also refuses non-owned packages
so no cross-account writes happen).

Recommendations / categories:
  crash      — app closes / freeze / black screen -> apologize + ask device
  bug        — broken feature / lag / won't load -> log + promise fix
  complaint  — ads / paywall / balance / UX gripe -> acknowledge + tuning
  question   — how-to / where-is -> point to in-game help
  praise     — love / fun / thanks -> thank + tease upcoming content
  ignore     — neutral, nothing actionable -> no reply

Lean rule: pure Python, deterministic, JSONL audit, no LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.models import (
    BlastRadius, GateStage, PlayResult,
)
from operation.publishing_factory.play_runtime.review_audit import (
    append as review_append,
)
from operation.publishing_factory.play_runtime.review_audit import (
    replied_ids, seen_ids,
)


# Keywords that bucket a review into a response category. Order matters:
# crash is checked before bug (a crash is a special, higher-priority bug).
_CRASH_KW = ["crash", "crashes", "freeze", "frozen", "force close",
             "force stop", "black screen", "won't open",
             "wont open", "force quit", "keeps closing", "closes itself"]
_BUG_KW = ["bug", "glitch", "error", "broken", "doesn't work",
           "does not work", "not working", "won't load", "wont load",
           "lag", "laggy", "slow", "freezes", "won't start", "wont start",
           "can't play", "cant play", "unplayable"]
_COMPLAINT_KW = ["too many ads", "too much ads", "ads", "paywall",
                 "expensive", "scam", "fake", "boring", "too hard",
                 "confusing", "unfair", "worst", "waste", "annoying",
                 "greedy", "money grab", "rip off", "ripoff"]
_QUESTION_KW = ["how", "where", "?", "can't find", "cant find",
                "how do i", "how to", "what is", "what's", "help me",
                "how can i", "tips", "guide"]
_PRAISE_KW = ["love", "great", "awesome", "best", "amazing", "fun",
              "addictive", "thanks", "thank you", "excellent", "perfect",
              "enjoy", "favorite", "fantastic", "wonderful", "good game",
              "happy"]


@dataclass
class ReviewPolicy:
    """Tunable classification + reply rules (deterministic, no LLM)."""
    # Star thresholds for "should we reply at all".
    reply_below_star: int = 3          # <= this star -> always reply
    thank_at_star: int = 4             # >= this star + praise -> thank
    # When a review is neither crash/bug/complaint/question/praise and lands
    # in the neutral bucket, do not reply.
    max_reply_chars: int = 350         # hard Play console cap (defensive)


@dataclass
class ReviewReport:
    """One review's classification + recommended reply (no write yet)."""
    package_name: str
    review_id: str
    author_name: str = ""
    star_rating: Optional[int] = None
    category: str = "ignore"          # crash/bug/complaint/question/praise/ignore
    sentiment: str = "neutral"        # positive/negative/neutral
    needs_reply: bool = False
    recommended_reply: str = ""
    replied: bool = False
    reply_text: str = ""
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "review_id": self.review_id,
            "author_name": self.author_name,
            "star_rating": self.star_rating,
            "category": self.category,
            "sentiment": self.sentiment,
            "needs_reply": self.needs_reply,
            "recommended_reply": self.recommended_reply,
            "replied": self.replied,
            "reply_text": self.reply_text,
            "evaluated_at": self.evaluated_at,
        }


def _hit(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)


def _greet(author: str) -> str:
    return f"Hi {author}," if author and author.strip() else "Hi there,"


class ReviewAgent:
    """Review intelligence + lowest-blast-radius auto-reply over a
    PlayConnector.

    ``reviews_provider`` lets callers inject the raw read (offline cache or
    test double). If omitted, the agent reads through the connector
    (``read_reviews`` -> ``GooglePlayRealClient.get_reviews``).
    """

    def __init__(self,
                 connector: PlayConnector,
                 policy: Optional[ReviewPolicy] = None,
                 reviews_provider: Optional[Callable[[str, int], Optional[Dict]]] = None):
        self.connector = connector
        self.policy = policy or ReviewPolicy()
        self.reviews_provider = reviews_provider  # (pkg, max) -> dict | None

    # ------------------------------------------------------------------ #
    # review acquisition
    def read_reviews(self, package_name: str,
                     max_results: int = 100) -> Optional[Dict]:
        if self.reviews_provider is not None:
            return self.reviews_provider(package_name, max_results)
        res = self.connector.read_reviews(package_name,
                                          max_results=max_results)
        if not res.ok:
            return None
        return res.data or None

    # ------------------------------------------------------------------ #
    # classification (pure, deterministic)
    def classify(self, review: Dict[str, Any]) -> ReviewReport:
        """Turn one normalized review dict into a classification + reply.

        ``review`` is the shape produced by
        ``GooglePlayRealClient.get_reviews`` (review_id / author_name /
        star_rating / text / ...).
        """
        pkg = review.get("package_name", "")
        rid = review.get("review_id") or ""
        text = review.get("text", "") or ""
        author = review.get("author_name", "") or ""
        star = review.get("star_rating")
        try:
            star = int(star) if star is not None else None
        except (TypeError, ValueError):
            star = None

        # 1) bucket by keyword precedence
        if _hit(text, _CRASH_KW):
            category = "crash"
        elif _hit(text, _BUG_KW):
            category = "bug"
        elif _hit(text, _COMPLAINT_KW):
            category = "complaint"
        elif _hit(text, _QUESTION_KW):
            category = "question"
        elif _hit(text, _PRAISE_KW):
            category = "praise"
        else:
            category = "ignore"

        # A low-star review with no specific keyword is still a complaint
        # worth a reply (generic apology), so promote it.
        if category == "ignore" and star is not None and star <= 2:
            category = "complaint"

        # 2) sentiment from star + category
        if star is not None and star <= 2:
            sentiment = "negative"
        elif star is not None and star >= 4:
            sentiment = "positive" if category in ("praise", "ignore") else "mixed"
        elif category in ("crash", "bug", "complaint"):
            sentiment = "negative"
        elif category == "praise":
            sentiment = "positive"
        else:
            sentiment = "neutral"

        # 3) decide whether a reply is warranted
        if category == "ignore":
            needs_reply = False
        elif category == "praise":
            needs_reply = star is None or star >= self.policy.thank_at_star
        else:
            # crash/bug/complaint/question: always reply when star low or
            # when there is a clear actionable signal.
            needs_reply = (star is None or star <= self.policy.reply_below_star
                           or category in ("crash", "bug", "complaint",
                                           "question"))

        reply = self.build_reply(category, author, star) if needs_reply else ""

        return ReviewReport(
            package_name=pkg, review_id=rid, author_name=author,
            star_rating=star, category=category, sentiment=sentiment,
            needs_reply=needs_reply, recommended_reply=reply)

    def build_reply(self, category: str, author: str,
                    star: Optional[int]) -> str:
        """Deterministic templated reply (always < 350 chars)."""
        greet = _greet(author)
        templates = {
            "crash": (f"{greet} sorry for the crash! We're investigating and "
                      f"a fix is coming in the next update. If you can share "
                      f"your device model we'll reproduce it faster. Thanks "
                      f"for your patience."),
            "bug": (f"{greet} thanks for the report! We've logged the issue "
                    f"and a fix is on the way. Please update to the latest "
                    f"version once it's available."),
            "complaint": (f"{greet} thanks for the honest feedback! We're "
                          f"tuning balance and ads to keep the game fair and "
                          f"fun. More free content is on the way."),
            "question": (f"{greet} happy to help! Tap the in-game help (?) "
                         f"button for tips, or tell us which level you're "
                         f"stuck on and we'll guide you."),
            "praise": (f"{greet} thank you so much for the kind words! We're "
                       f"glad you're enjoying the game and have new levels "
                       f"and events coming soon."),
        }
        text = templates.get(category, f"{greet} thanks for playing!")
        if len(text) > self.policy.max_reply_chars:
            text = text[:self.policy.max_reply_chars]
        return text

    # ------------------------------------------------------------------ #
    # evaluate (classification only, no write)
    def evaluate_review(self, review: Dict[str, Any]) -> ReviewReport:
        return self.classify(review)

    def read_and_classify(self, package_name: str, *,
                          max_results: int = 100) -> List[ReviewReport]:
        """Read via the connector and classify every returned review.

        This does NOT persist to the audit log and does NOT skip already-seen
        reviews — it is the inspection path used by the CLI.
        """
        data = self.read_reviews(package_name, max_results=max_results)
        if not data:
            return []
        out: List[ReviewReport] = []
        for r in data.get("reviews", []):
            r.setdefault("package_name", package_name)
            out.append(self.classify(r))
        return out

    # ------------------------------------------------------------------ #
    # single reply (gated write through the connector)
    def reply(self, package_name: str, review_id: str, reply_text: str, *,
              apply: bool = False) -> PlayResult:
        """Post a reply to one review. Routes through the connector's
        three-tier gate; PRODUCTION writes only with auto-pilot + apply."""
        return self.connector.reply_review(
            package_name, review_id, reply_text, apply=apply)

    # ------------------------------------------------------------------ #
    # daily sweep (idempotent)
    def run_daily(self, packages: List[str], *, apply: bool = False,
                  max_results: int = 100) -> Dict[str, Any]:
        """Read + classify every package; persist to the review audit; post
        replies (when ``apply``) only for *new* reviews that need one and
        that have not been replied to before.

        Idempotency: already-seen review_ids are skipped; the connector also
        refuses non-owned packages so no cross-account writes occur.
        """
        seen = seen_ids()
        already_replied = replied_ids()
        per_pkg: Dict[str, Dict[str, int]] = {}
        posted: List[Dict[str, Any]] = []
        skipped_seen = 0
        failed = 0

        for pkg in packages:
            reports = self.read_and_classify(pkg, max_results=max_results)
            agg = per_pkg.setdefault(pkg, {
                "evaluated": 0, "needs_reply": 0,
                "posted": 0, "failed": 0, "new": 0})
            for rep in reports:
                if rep.review_id in seen:
                    skipped_seen += 1
                    continue
                agg["new"] += 1
                agg["evaluated"] += 1
                if rep.needs_reply:
                    agg["needs_reply"] += 1
                # persist classification regardless of whether we reply
                review_append(rep)
                if rep.needs_reply and rep.review_id not in already_replied:
                    if apply:
                        res = self.reply(pkg, rep.review_id,
                                         rep.recommended_reply, apply=True)
                        if res.ok:
                            rep.replied = True
                            rep.reply_text = rep.recommended_reply
                            # re-append the now-replied record so the audit
                            # reflects the posted state (idempotency source).
                            review_append(rep)
                            agg["posted"] += 1
                            posted.append(rep.to_dict())
                        else:
                            failed += 1
                            agg["failed"] += 1

        return {
            "per_package": per_pkg,
            "skipped_seen": skipped_seen,
            "replied_total": len(already_replied) + len(posted),
            "posted_this_run": posted,
            "failed": failed,
            "applied": apply,
        }


__all__ = ["ReviewAgent", "ReviewPolicy", "ReviewReport"]
