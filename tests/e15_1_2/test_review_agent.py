"""E13.5 — Review Agent tests (real client + connector gate + agent logic).

Covers:
  * real_client.get_reviews / reply_to_review (with _api_override seam)
  * connector.read_reviews / reply_review three-tier gating + ownership
  * ReviewAgent classify / build_reply / run_daily idempotency + dedup
  * review_audit persistence + summary_by_package
  * daily_briefing._run_review section rendering

Lean: all tests are offline (fake client / override seam), no network.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from monetization.providers.models import SandboxMode

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.models import GateStage
from operation.publishing_factory.play_runtime.review_agent import (
    ReviewAgent, ReviewPolicy, ReviewReport,
)
from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient,
)


# --------------------------------------------------------------------- #
# fake transport for the connector / agent
class FakeReviewClient:
    def __init__(self, owned: bool = True, reviews=None, reply_fail=False):
        self.owned = owned
        self.reviews = reviews or []
        self.reply_fail = reply_fail
        self.calls: list = []

    def check_status(self, package_name):
        self.calls.append(("check_status", package_name))
        if self.owned:
            return {"success": True, "status": "published",
                    "play_status": "completed"}
        return {"success": False, "status_code": 404,
                "error": "package not found in account"}

    def get_reviews(self, package_name, max_results=100):
        self.calls.append(("get_reviews", package_name, max_results))
        return {"success": True, "package_name": package_name,
                "reviews": self.reviews, "count": len(self.reviews),
                "token": None, "fetched_at": "...",
                "source": "androidpublisher.reviews.list"}

    def reply_to_review(self, package_name, review_id, reply_text):
        self.calls.append(("reply", package_name, review_id, reply_text))
        if self.reply_fail:
            return {"success": False, "status_code": 500, "error": "boom"}
        return {"success": True, "package_name": package_name,
                "review_id": review_id, "reply_text": reply_text,
                "result": "replied", "detail": "reply posted"}


PKG = "com.ofwsalary.ofwcalculator"


def _connector(sandbox, auto_pilot=False, client=None, audit_file=None,
               review_file=None):
    if audit_file is not None:
        os.environ["LAUNCHFORGE_PLAY_AUDIT"] = str(audit_file)
    if review_file is not None:
        os.environ["LAUNCHFORGE_PLAY_REVIEWS"] = str(review_file)
    return PlayConnector(client=client or FakeReviewClient(),
                         sandbox=sandbox, auto_pilot=auto_pilot)


def _agent(client, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
           audit_file=None, review_file=None):
    conn = _connector(sandbox, auto_pilot=auto_pilot, client=client,
                      audit_file=audit_file, review_file=review_file)
    return ReviewAgent(conn, policy=ReviewPolicy()), conn


# ===================================================================== #
# 1) real_client.get_reviews
def test_real_client_get_reviews_parse():
    c = GooglePlayRealClient(credential={"package_name": PKG})
    cap = {}

    def ov(method, path, body):
        cap["method"] = method
        cap["path"] = path
        return {"success": True, "status_code": 200, "data": {
            "reviews": [{
                "reviewId": "r1",
                "author": {"name": "Alice"},
                "comments": [{
                    "userComment": {"text": "keeps crashing on launch",
                                    "starRating": 1,
                                    "lastModified": {"seconds": "100"}},
                }],
            }]}}
    c.arm_real_client(ov)
    res = c.get_reviews(PKG, max_results=50)
    assert cap["method"] == "GET"
    assert "reviews" in cap["path"] and "maxResults=50" in cap["path"]
    assert res["success"] is True
    assert res["count"] == 1
    r0 = res["reviews"][0]
    assert r0["review_id"] == "r1"
    assert r0["author_name"] == "Alice"
    assert r0["star_rating"] == 1
    assert "crashing" in r0["text"]


# ===================================================================== #
# 2) real_client.reply_to_review
def test_real_client_reply_too_long():
    c = GooglePlayRealClient(credential={"package_name": PKG})
    r = c.reply_to_review(PKG, "r1", "x" * 351)
    assert r["success"] is False
    assert "too long" in r["error"]


def test_real_client_reply_success():
    c = GooglePlayRealClient(credential={"package_name": PKG})
    cap = {}

    def ov(method, path, body):
        cap.update(method=method, path=path, body=body)
        return {"success": True, "status_code": 200,
                "data": {"result": "replied"}}
    c.arm_real_client(ov)
    r = c.reply_to_review(PKG, "r1", "Hi Alice, sorry for the crash!")
    assert r["success"] is True
    assert cap["method"] == "POST"
    assert cap["path"].endswith("/reviews/r1:reply")
    assert cap["body"] == {"replyText": "Hi Alice, sorry for the crash!"}


def test_real_client_reply_rejects_empty():
    c = GooglePlayRealClient(credential={"package_name": PKG})
    r = c.reply_to_review(PKG, "r1", "   ")
    assert r["success"] is False


# ===================================================================== #
# 3) connector.read_reviews (READ radius)
def test_connector_read_reviews_simulation(tmp_path):
    c = _connector(SandboxMode.SIMULATION, client=FakeReviewClient(),
                   audit_file=tmp_path / "a.jsonl")
    r = c.read_reviews(PKG)
    assert r.stage == GateStage.RECOMMEND
    assert r.real_api_called is False


def test_connector_read_reviews_production_reads(tmp_path):
    fc = FakeReviewClient(reviews=[{"review_id": "r1", "text": "hi",
                                    "star_rating": 5}])
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.read_reviews(PKG)
    assert r.stage == GateStage.EXECUTE
    assert r.real_api_called is True
    assert r.data["count"] == 1


# ===================================================================== #
# 4) connector.reply_review (METADATA radius, gated write)
def test_connector_reply_blocked_without_autopilot(tmp_path):
    fc = FakeReviewClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=False, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.reply_review(PKG, "r1", "hi", apply=True)
    assert r.stage == GateStage.BLOCKED
    assert r.real_api_called is False
    assert fc.calls == []


def test_connector_reply_dry_preview(tmp_path):
    fc = FakeReviewClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.reply_review(PKG, "r1", "hi there", apply=False)
    assert r.stage == GateStage.SIMULATE
    assert r.real_api_called is True   # ownership verify read
    assert ("check_status", PKG) in fc.calls
    assert all(call[0] != "reply" for call in fc.calls)


def test_connector_reply_execute(tmp_path):
    fc = FakeReviewClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.reply_review(PKG, "r1", "hi there", apply=True)
    assert r.stage == GateStage.EXECUTE
    assert r.ok is True
    assert ("reply", PKG, "r1", "hi there") in fc.calls


def test_connector_reply_non_owned_refused(tmp_path):
    fc = FakeReviewClient(owned=False)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.reply_review(PKG, "r1", "hi", apply=True)
    assert r.stage == GateStage.EXECUTE
    assert r.ok is False
    assert all(call[0] != "reply" for call in fc.calls)


# ===================================================================== #
# 5) ReviewAgent classification
def test_classify_crash():
    a, _ = _agent(FakeReviewClient())
    rep = a.classify({"package_name": PKG, "review_id": "r1",
                      "text": "keeps crashing on launch", "star_rating": 1})
    assert rep.category == "crash"
    assert rep.needs_reply is True
    assert rep.recommended_reply.startswith("Hi")


def test_classify_bug():
    a, _ = _agent(FakeReviewClient())
    rep = a.classify({"package_name": PKG, "review_id": "r1",
                      "text": "level won't load, stuck", "star_rating": 2})
    assert rep.category == "bug"
    assert rep.needs_reply is True


def test_classify_complaint():
    a, _ = _agent(FakeReviewClient())
    rep = a.classify({"package_name": PKG, "review_id": "r1",
                      "text": "too many ads, greedy", "star_rating": 2})
    assert rep.category == "complaint"
    assert rep.needs_reply is True


def test_classify_question():
    a, _ = _agent(FakeReviewClient())
    rep = a.classify({"package_name": PKG, "review_id": "r1",
                      "text": "how do I unlock level 5?", "star_rating": 4})
    assert rep.category == "question"
    assert rep.needs_reply is True


def test_classify_praise_replied_when_high_star():
    a, _ = _agent(FakeReviewClient())
    rep = a.classify({"package_name": PKG, "review_id": "r1",
                      "text": "i love this game so fun", "star_rating": 5})
    assert rep.category == "praise"
    assert rep.needs_reply is True
    assert rep.sentiment == "positive"


def test_classify_praise_low_star_no_reply():
    a, _ = _agent(FakeReviewClient())
    rep = a.classify({"package_name": PKG, "review_id": "r1",
                      "text": "i love this game", "star_rating": 2})
    assert rep.category == "praise"
    assert rep.needs_reply is False   # 2-star, below thank threshold


def test_classify_ignore_neutral():
    a, _ = _agent(FakeReviewClient())
    rep = a.classify({"package_name": PKG, "review_id": "r1",
                      "text": "ok game", "star_rating": 3})
    assert rep.category == "ignore"
    assert rep.needs_reply is False


def test_classify_low_star_generic_promoted_to_complaint():
    a, _ = _agent(FakeReviewClient())
    rep = a.classify({"package_name": PKG, "review_id": "r1",
                      "text": "game sucks", "star_rating": 1})
    assert rep.category == "complaint"   # promoted, still gets a reply
    assert rep.needs_reply is True


def test_build_reply_under_cap_and_greeting():
    a, _ = _agent(FakeReviewClient())
    for cat in ("crash", "bug", "complaint", "question", "praise"):
        t = a.build_reply(cat, "Bob", 3)
        assert len(t) <= 350
        assert t.startswith("Hi Bob,")


# ===================================================================== #
# 6) ReviewAgent.run_daily idempotency + dedup
def test_run_daily_replies_new_then_skips(tmp_path):
    reviews = [
        {"package_name": PKG, "review_id": "r1",
         "text": "crashes", "star_rating": 1},
        {"package_name": PKG, "review_id": "r2",
         "text": "i love it", "star_rating": 5},
    ]
    fc = FakeReviewClient(owned=True, reviews=reviews)
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl",
                  review_file=tmp_path / "reviews.jsonl")
    out = a.run_daily([PKG], apply=True)
    agg = out["per_package"][PKG]
    assert agg["new"] == 2
    assert agg["posted"] == 2
    assert sum(1 for c in fc.calls if c[0] == "reply") == 2

    # second run: everything already seen -> no new replies
    out2 = a.run_daily([PKG], apply=True)
    assert out2["skipped_seen"] >= 2
    assert out2["per_package"][PKG]["posted"] == 0
    assert sum(1 for c in fc.calls if c[0] == "reply") == 2   # unchanged


def test_run_daily_reply_failure_recorded(tmp_path):
    reviews = [{"package_name": PKG, "review_id": "r1",
                "text": "crashes", "star_rating": 1}]
    fc = FakeReviewClient(owned=True, reviews=reviews, reply_fail=True)
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl",
                  review_file=tmp_path / "reviews.jsonl")
    out = a.run_daily([PKG], apply=True)
    assert out["per_package"][PKG]["posted"] == 0
    assert out["per_package"][PKG]["failed"] == 1
    assert out["failed"] == 1


def test_run_daily_preview_no_reply(tmp_path):
    reviews = [{"package_name": PKG, "review_id": "r1",
                "text": "crashes", "star_rating": 1}]
    fc = FakeReviewClient(owned=True, reviews=reviews)
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl",
                  review_file=tmp_path / "reviews.jsonl")
    out = a.run_daily([PKG], apply=False)
    assert out["applied"] is False
    assert out["per_package"][PKG]["posted"] == 0
    assert all(call[0] != "reply" for call in fc.calls)


# ===================================================================== #
# 7) agent.reply gating preview
def test_agent_reply_preview_without_apply(tmp_path):
    fc = FakeReviewClient(owned=True)
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl")
    res = a.reply(PKG, "r1", "hi there", apply=False)
    assert res.stage == GateStage.SIMULATE
    assert all(call[0] != "reply" for call in fc.calls)


# ===================================================================== #
# 8) review_audit persistence + summary
def test_review_audit_summary_and_dedup(tmp_path):
    os.environ["LAUNCHFORGE_PLAY_REVIEWS"] = str(tmp_path / "reviews.jsonl")
    from operation.publishing_factory.play_runtime.review_audit import (
        append, seen_ids, replied_ids, summary_by_package)
    append(ReviewReport(PKG, "r1", category="crash", needs_reply=True,
                        replied=True, reply_text="hi"))
    append(ReviewReport(PKG, "r2", category="praise", needs_reply=True,
                        replied=False))
    assert "r1" in replied_ids()
    assert "r2" not in replied_ids()
    assert seen_ids() == {"r1", "r2"}
    board = summary_by_package()
    assert board[PKG]["crash"] == 1
    assert board[PKG]["praise"] == 1
    assert board[PKG]["replied"] == 1
    assert board[PKG]["needs_reply"] == 2


# ===================================================================== #
# 9) daily_briefing._run_review section
def test_run_review_section_renders(tmp_path):
    os.environ["LAUNCHFORGE_PLAY_REVIEWS"] = str(tmp_path / "reviews.jsonl")
    from operation.publishing_factory.play_runtime.review_audit import append
    append(ReviewReport(PKG, "r1", category="crash", needs_reply=True,
                        replied=True, reply_text="hi"))
    append(ReviewReport(PKG, "r2", category="complaint", needs_reply=True,
                        replied=False))
    from operation.optimizer.daily_briefing import _run_review
    out = _run_review(notify=False)
    assert out["status"] == "OK"
    assert PKG in out["markdown"]
    assert "崩溃" in out["markdown"]
    assert "吐槽" in out["markdown"]


def test_run_review_section_empty(tmp_path):
    os.environ["LAUNCHFORGE_PLAY_REVIEWS"] = str(tmp_path / "empty.jsonl")
    from operation.optimizer.daily_briefing import _run_review
    out = _run_review(notify=False)
    assert out["status"] == "EMPTY"
